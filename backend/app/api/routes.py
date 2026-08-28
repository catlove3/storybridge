from __future__ import annotations

import logging
from typing import Literal
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field, model_validator

from app.api.contracts import (
    BibleResponse,
    DataExportResponse,
    DeleteProjectResponse,
    JobKind,
    JobResponse,
    JobSubmitted,
    ProjectCreated,
    ProjectDetail,
    ProjectSummary,
    RuntimePolicyResponse,
    SceneDiffResponse,
    StateSummaryResponse,
    StoryGraphResponse,
)
from app.api.security import require_owner, usage_guard
from app.config import api_key_owners, get_config
from app.graph import StoryGraph
from app.llm.router import LLMBudgetExceeded
from app.schemas import (
    AdaptationPlan,
    DataPolicy,
    PropagationResult,
    Revision,
    StoryState,
    TargetScript,
    VerifyReport,
)
from app.storage import MarketProfile
from app.workflow.engine import (
    ApplyResult,
    DuplicateOperation,
    StateVersionConflict,
    StoryBridgeWorkflow,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", dependencies=[Depends(require_owner)])


def _workflow(request: Request) -> StoryBridgeWorkflow:
    return request.app.state.workflow


def _owner(request: Request) -> str:
    return request.state.owner_id


def _project_or_404(workflow: StoryBridgeWorkflow, project_id: str, request: Request):
    meta = workflow.store.load_meta(project_id)
    if meta is None or meta.owner_id != _owner(request):
        raise HTTPException(
            status_code=404,
            detail={"code": "project_not_found", "message": "Project not found"},
        )
    return meta


def _upstream_failure(operation: str, project_id: str, exc: Exception) -> HTTPException:
    if isinstance(exc, LLMBudgetExceeded):
        return HTTPException(
            status_code=429,
            detail={"code": "llm_budget_exhausted", "message": str(exc)},
        )
    logger.error(
        "%s failed for project %s exception_type=%s",
        operation,
        project_id,
        type(exc).__name__,
    )
    return HTTPException(
        status_code=502,
        detail={
            "code": "upstream_generation_failed",
            "message": f"{operation} could not be completed",
        },
    )


def _submit(jobs, *args, **kwargs):
    try:
        return jobs.submit(*args, **kwargs)
    except ValueError as exc:
        raise HTTPException(
            status_code=409,
            detail={"code": "idempotency_conflict", "message": str(exc)},
        ) from exc


def _run_logger(workflow: StoryBridgeWorkflow):
    return getattr(workflow.rewriter.client, "run_logger", None)


def _enforce_llm_budget(workflow: StoryBridgeWorkflow, project_id: str) -> None:
    run_logger = _run_logger(workflow)
    if run_logger is None:
        return
    try:
        run_logger.ensure_budget(project_id)
    except LLMBudgetExceeded as exc:
        raise HTTPException(
            status_code=429,
            detail={"code": "llm_budget_exhausted", "message": str(exc)},
        ) from exc


class CreateProjectBody(BaseModel):
    name: str = Field(default="", max_length=200)
    script: str = Field(min_length=1, max_length=500_000)
    market: MarketProfile = Field(default_factory=MarketProfile)
    data_policy: DataPolicy = Field(default_factory=DataPolicy)


class PlanBody(BaseModel):
    culture_mechanism_id: str = Field(pattern=r"^CM\d+$")


class ApplyBody(BaseModel):
    culture_mechanism_id: str = Field(pattern=r"^CM\d+$")
    option_label: Literal["A", "B", "C"]
    auto_verify_and_repair: bool = True
    based_on_version: int | None = Field(default=None, ge=1)
    operation_id: str | None = Field(default=None, min_length=1, max_length=200)


@router.get("/runtime-policy", response_model=RuntimePolicyResponse)
async def runtime_policy():
    config = get_config()
    profile = config.llm.profiles[config.llm.default_profile]
    endpoint = urlsplit(profile.base_url)
    return {
        "authentication_required": bool(api_key_owners(config)),
        "provider_endpoint": f"{endpoint.scheme}://{endpoint.netloc}",
        "model": profile.model,
        "sft_collection_enabled": config.logging.sft_log_enabled,
        "sft_redaction_enabled": config.logging.sft_redact_pii,
        "sft_retention_days": config.logging.sft_retention_days,
        "max_script_chars": config.security.max_script_chars,
        "max_project_llm_tokens": config.security.max_project_llm_tokens,
    }


@router.post("/projects", response_model=ProjectCreated)
async def create_project(body: CreateProjectBody, request: Request):
    workflow = _workflow(request)
    max_chars = get_config().security.max_script_chars
    if len(body.script) > max_chars:
        raise HTTPException(
            status_code=413,
            detail={
                "code": "script_too_large",
                "message": f"Script exceeds the configured {max_chars} character limit",
            },
        )
    meta = await workflow.create_project(
        body.name,
        body.script,
        body.market,
        owner_id=_owner(request),
        data_policy=body.data_policy,
    )
    return {"id": meta.id, "name": meta.name}


@router.get("/projects", response_model=list[ProjectSummary])
async def list_projects(request: Request):
    return [
        {"id": m.id, "name": m.name, "created_at": m.created_at}
        for m in _workflow(request).store.list_projects()
        if m.owner_id == _owner(request)
    ]


@router.get("/projects/{project_id}", response_model=ProjectDetail)
async def get_project(project_id: str, request: Request):
    workflow = _workflow(request)
    meta = _project_or_404(workflow, project_id, request)
    state = workflow.store.load_state(project_id)
    return {
        "id": meta.id,
        "name": meta.name,
        "market": meta.market,
        "analyzed": state is not None,
        "data_policy": meta.data_policy,
    }


@router.post("/projects/{project_id}/analyze", response_model=StateSummaryResponse)
async def analyze(project_id: str, request: Request):
    workflow = _workflow(request)
    _project_or_404(workflow, project_id, request)
    _enforce_llm_budget(workflow, project_id)
    try:
        state = await workflow.analyze(project_id)
    except Exception as exc:
        raise _upstream_failure("analyze", project_id, exc) from exc
    return _state_summary(state)


@router.get("/projects/{project_id}/state", response_model=StoryState)
async def get_state(project_id: str, request: Request):
    workflow = _workflow(request)
    _project_or_404(workflow, project_id, request)
    try:
        state = workflow.require_state(project_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return state.model_dump()


@router.get("/projects/{project_id}/graph", response_model=StoryGraphResponse)
async def get_graph(
    project_id: str,
    request: Request,
    focus: str | None = None,
    depth: int = Query(default=2, ge=0, le=6),
):
    workflow = _workflow(request)
    _project_or_404(workflow, project_id, request)
    try:
        state = workflow.require_state(project_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    graph = StoryGraph(state)
    if focus and not graph.has_node(focus):
        raise HTTPException(status_code=404, detail=f"unknown node: {focus}")
    sub = graph.display_subgraph([focus] if focus else None, depth=depth)

    def label_for(node_id: str) -> str:
        node = state.node(node_id)
        for attr in ("name", "title"):
            value = getattr(node, attr, None)
            if isinstance(value, str) and value:
                return value
        description = getattr(node, "description", None)
        if isinstance(description, str) and description:
            return description[:24]
        return node_id

    nodes = [{"id": n, "kind": sub.nodes[n].get("kind", ""), "label": label_for(n)} for n in sub.nodes]
    edges = [
        {
            "id": edge_key,
            "source": u,
            "target": v,
            "relation": d.get("relation", ""),
            "evidence": d.get("evidence", ""),
            "confidence": d.get("confidence", 1.0),
        }
        for u, v, edge_key, d in sub.edges(keys=True, data=True)
    ]
    return {"nodes": nodes, "edges": edges}


@router.get("/projects/{project_id}/propagate", response_model=PropagationResult)
async def propagate(project_id: str, request: Request, mechanism: str):
    workflow = _workflow(request)
    _project_or_404(workflow, project_id, request)
    try:
        result = workflow.propagate(project_id, mechanism)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return result.model_dump()


@router.post("/projects/{project_id}/adaptations/plan", response_model=AdaptationPlan)
async def create_plan(project_id: str, body: PlanBody, request: Request):
    workflow = _workflow(request)
    _project_or_404(workflow, project_id, request)
    _enforce_llm_budget(workflow, project_id)
    try:
        plan = await workflow.plan(project_id, body.culture_mechanism_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise _upstream_failure("planning", project_id, exc) from exc
    return plan.model_dump()


@router.post("/projects/{project_id}/adaptations/apply", response_model=ApplyResult)
async def apply_adaptation(project_id: str, body: ApplyBody, request: Request):
    workflow = _workflow(request)
    _project_or_404(workflow, project_id, request)
    _enforce_llm_budget(workflow, project_id)
    try:
        result: ApplyResult = await workflow.apply_adaptation(
            project_id,
            body.culture_mechanism_id,
            body.option_label,
            auto_verify_and_repair=body.auto_verify_and_repair,
            based_on_version=body.based_on_version,
            operation_id=body.operation_id,
        )
    except (StateVersionConflict, DuplicateOperation) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise _upstream_failure("apply", project_id, exc) from exc
    return result.model_dump()


@router.post("/projects/{project_id}/verify", response_model=VerifyReport)
async def verify(project_id: str, request: Request):
    workflow = _workflow(request)
    _project_or_404(workflow, project_id, request)
    _enforce_llm_budget(workflow, project_id)
    try:
        report: VerifyReport = await workflow.verify(project_id)
    except Exception as exc:
        raise _upstream_failure("verification", project_id, exc) from exc
    return report.model_dump()


@router.post("/projects/{project_id}/target-script", response_model=TargetScript)
async def render_target_script(project_id: str, request: Request):
    workflow = _workflow(request)
    _project_or_404(workflow, project_id, request)
    _enforce_llm_budget(workflow, project_id)
    try:
        target_script = await workflow.render_target_script(project_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise _upstream_failure("target rendering", project_id, exc) from exc
    return target_script.model_dump()


@router.get("/projects/{project_id}/target-script", response_model=TargetScript)
async def get_target_script(project_id: str, request: Request):
    workflow = _workflow(request)
    _project_or_404(workflow, project_id, request)
    target_script = workflow.store.load_target_script(project_id)
    if target_script is None:
        raise HTTPException(404, "target script is missing or stale; render it first")
    return target_script.model_dump()


@router.get("/projects/{project_id}/revisions", response_model=list[Revision])
async def revisions(project_id: str, request: Request):
    workflow = _workflow(request)
    _project_or_404(workflow, project_id, request)
    return [r.model_dump() for r in workflow.store.list_revisions(project_id)]


@router.get("/projects/{project_id}/diff", response_model=list[SceneDiffResponse])
async def diff(project_id: str, request: Request):
    from app.export import changed_scenes_diff

    workflow = _workflow(request)
    _project_or_404(workflow, project_id, request)
    try:
        return changed_scenes_diff(workflow.store, project_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/projects/{project_id}/bible", response_model=BibleResponse)
async def bible(project_id: str, request: Request):
    from app.export.bible import export_bible

    workflow = _workflow(request)
    _project_or_404(workflow, project_id, request)
    try:
        path = export_bible(workflow, project_id, _bible_path(request, project_id))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"content": path.read_text(encoding="utf-8")}


@router.get("/projects/{project_id}/data-export", response_model=DataExportResponse)
async def export_project_data(project_id: str, request: Request):
    workflow = _workflow(request)
    meta = _project_or_404(workflow, project_id, request)
    state = workflow.store.load_state(project_id)
    return {
        "project": {
            "id": meta.id,
            "name": meta.name,
            "market": meta.market,
            "analyzed": state is not None,
            "data_policy": meta.data_policy,
        },
        "script": meta.script_text,
        "state": state,
        "plans": workflow.store.load_plans(project_id),
        "revisions": workflow.store.list_revisions(project_id),
        "adaptations": [
            item.model_dump(mode="json")
            for item in workflow.store.load_applied(project_id)
        ],
        "target_script": workflow.store.load_target_script(project_id),
        "llm_runs": (
            _run_logger(workflow).entries(project_id)
            if _run_logger(workflow) is not None
            else []
        ),
    }


@router.delete("/projects/{project_id}", response_model=DeleteProjectResponse)
async def delete_project(project_id: str, request: Request):
    workflow = _workflow(request)
    _project_or_404(workflow, project_id, request)
    jobs = request.app.state.jobs
    jobs.delete_for_project(project_id)
    sft_deleted = 0
    run_records_deleted = 0
    llm_client = workflow.rewriter.client
    call_logger = getattr(llm_client, "logger", None)
    if call_logger is not None and hasattr(call_logger, "delete_project"):
        sft_deleted = call_logger.delete_project(project_id)
    run_logger = getattr(llm_client, "run_logger", None)
    if run_logger is not None and hasattr(run_logger, "delete_project"):
        run_records_deleted = run_logger.delete_project(project_id)
    deleted = workflow.store.delete_project(project_id)
    return {
        "deleted": deleted,
        "project_id": project_id,
        "sft_samples_deleted": sft_deleted,
        "run_records_deleted": run_records_deleted,
    }


def _bible_path(request: Request, project_id: str):
    return _workflow(request).store.projects_dir / project_id / "adaptation_bible.md"


class JobSubmitBody(BaseModel):
    kind: JobKind
    culture_mechanism_id: str | None = Field(default=None, pattern=r"^CM\d+$")
    option_label: Literal["A", "B", "C"] | None = None
    based_on_version: int | None = Field(default=None, ge=1)
    idempotency_key: str | None = Field(default=None, min_length=1, max_length=200)

    @model_validator(mode="after")
    def _required_fields_for_kind(self) -> JobSubmitBody:
        if self.kind == JobKind.APPLY and not (
            self.culture_mechanism_id and self.option_label
        ):
            raise ValueError("apply job needs culture_mechanism_id and option_label")
        if self.kind == JobKind.PLAN and not self.culture_mechanism_id:
            raise ValueError("plan job needs culture_mechanism_id")
        return self


@router.post("/projects/{project_id}/jobs", response_model=JobSubmitted)
async def submit_job(project_id: str, body: JobSubmitBody, request: Request):
    workflow = _workflow(request)
    jobs = request.app.state.jobs
    _project_or_404(workflow, project_id, request)
    _enforce_llm_budget(workflow, project_id)
    existing = (
        jobs.find_idempotent(project_id, body.idempotency_key)
        if body.idempotency_key
        else None
    )
    if existing is None:
        owned_project_ids = {
            meta.id
            for meta in workflow.store.list_projects()
            if meta.owner_id == _owner(request)
        }
        usage_guard(request).check_job_submission(
            _owner(request), owned_project_ids, jobs
        )

    if body.kind == JobKind.ANALYZE:
        job = _submit(
            jobs,
            "analyze",
            project_id,
            lambda: workflow.analyze(project_id),
            idempotency_key=body.idempotency_key,
        )
    elif body.kind == JobKind.APPLY:
        assert body.culture_mechanism_id and body.option_label
        if body.based_on_version is not None:
            current_version = workflow.require_state(project_id).version
            if body.based_on_version != current_version:
                raise HTTPException(
                    status_code=409,
                    detail=(
                        f"state version conflict: expected {body.based_on_version}, "
                        f"current version is {current_version}"
                    ),
                )
        job = _submit(
            jobs,
            "apply",
            project_id,
            lambda: workflow.apply_adaptation(
                project_id,
                body.culture_mechanism_id,
                body.option_label,
                based_on_version=body.based_on_version,
                operation_id=body.idempotency_key,
            ),
            idempotency_key=body.idempotency_key,
        )
    elif body.kind == JobKind.VERIFY:
        job = _submit(
            jobs,
            "verify",
            project_id,
            lambda: workflow.verify(project_id),
            idempotency_key=body.idempotency_key,
        )
    elif body.kind == JobKind.PLAN:
        assert body.culture_mechanism_id
        job = _submit(
            jobs,
            "plan",
            project_id,
            lambda: workflow.plan(project_id, body.culture_mechanism_id),
            idempotency_key=body.idempotency_key,
        )
    elif body.kind == JobKind.RENDER:
        job = _submit(
            jobs,
            "render",
            project_id,
            lambda: workflow.render_target_script(project_id),
            idempotency_key=body.idempotency_key,
        )
    return {"job_id": job.id, "status": job.status}


@router.get("/jobs/{job_id}", response_model=JobResponse)
async def get_job(job_id: str, request: Request):
    jobs = request.app.state.jobs
    job = jobs.get(job_id)
    if job is None:
        raise HTTPException(404, f"unknown job: {job_id}")
    _project_or_404(_workflow(request), job.project_id, request)
    return job.serialize()


@router.post("/jobs/{job_id}/cancel", response_model=JobResponse)
async def cancel_job(job_id: str, request: Request):
    jobs = request.app.state.jobs
    job = jobs.get(job_id)
    if job is None:
        raise HTTPException(404, f"unknown job: {job_id}")
    _project_or_404(_workflow(request), job.project_id, request)
    job = jobs.cancel(job_id)
    return job.serialize()


@router.get("/projects/{project_id}/jobs", response_model=list[JobResponse])
async def list_jobs(project_id: str, request: Request):
    jobs = request.app.state.jobs
    _project_or_404(_workflow(request), project_id, request)
    return [j.model_dump(exclude={"result"}) for j in jobs.list_for_project(project_id)]


def _state_summary(state: StoryState) -> dict:
    return {
        "version": state.version,
        "characters": len(state.characters),
        "scenes": len(state.scenes),
        "events": len(state.events),
        "settings": len(state.settings),
        "culture_mechanisms": [cm.model_dump() for cm in state.culture_mechanisms],
        "commitments": [nc.model_dump() for nc in state.commitments],
        "dependencies": len(state.dependencies),
        "high_friction_ids": [cm.id for cm in state.culture_mechanisms if cm.friction_level == "high"],
    }
