from __future__ import annotations

import hashlib
import logging
from typing import Literal
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
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
from app.api.security import generation_admission, require_owner, usage_guard
from app.config import api_key_for, api_key_owners, get_config
from app.demo_scripts import DemoDetail, DemoSummary, catalog, detail
from app.graph import StoryGraph
from app.llm.router import LLMBudgetExceeded
from app.public_usage import PublicLimitError, public_usage
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
    AdaptationSelection,
    ApplyResult,
    BatchApplyResult,
    DuplicateOperation,
    StateVersionConflict,
    StoryBridgeWorkflow,
    VerificationBlocked,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", dependencies=[Depends(require_owner), Depends(generation_admission)])


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
    if isinstance(exc, VerificationBlocked):
        return HTTPException(409, {"code": "verification_blocked", "message": str(exc)})
    if isinstance(exc, PublicLimitError):
        return HTTPException(status_code=429, detail=exc.detail())
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
    if get_config().share.enabled:
        return
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
    idempotency_key: str | None = Field(default=None, min_length=1, max_length=200)


class PlanBody(BaseModel):
    culture_mechanism_id: str = Field(pattern=r"^CM\d+$")


class ApplyBody(BaseModel):
    culture_mechanism_id: str = Field(pattern=r"^CM\d+$")
    option_label: Literal["A", "B", "C"]
    auto_verify_and_repair: bool = Field(
        default=False,
        description="Only run automatic verification and repair when explicitly authorized.",
    )
    based_on_version: int | None = Field(default=None, ge=1)
    operation_id: str | None = Field(default=None, min_length=1, max_length=200)


class BatchPlanBody(BaseModel):
    culture_mechanism_ids: list[str] = Field(min_length=1, max_length=20)

    @model_validator(mode="after")
    def _validate_ids(self) -> BatchPlanBody:
        if any(
            not item.startswith("CM") or not item[2:].isdigit()
            for item in self.culture_mechanism_ids
        ):
            raise ValueError("culture mechanism ids must match CM followed by digits")
        if len(self.culture_mechanism_ids) != len(set(self.culture_mechanism_ids)):
            raise ValueError("culture mechanism ids must be unique")
        return self


class BatchApplyBody(BaseModel):
    adaptations: list[AdaptationSelection] = Field(min_length=1, max_length=20)
    auto_verify_and_repair: bool = Field(
        default=False,
        description="Only run automatic verification and repair when explicitly authorized.",
    )
    based_on_version: int | None = Field(default=None, ge=1)
    operation_id: str | None = Field(default=None, min_length=1, max_length=200)

    @model_validator(mode="after")
    def _validate_unique_mechanisms(self) -> BatchApplyBody:
        ids = [item.culture_mechanism_id for item in self.adaptations]
        if len(ids) != len(set(ids)):
            raise ValueError("each culture mechanism can only appear once in a batch")
        return self


@router.get("/runtime-policy", response_model=RuntimePolicyResponse)
async def runtime_policy(request: Request):
    config = get_config()
    profile = config.llm.profiles[config.llm.default_profile]
    endpoint = urlsplit(profile.base_url)
    mock = getattr(request.app.state, "mock_mode", False)
    try:
        available = mock or bool(api_key_for(profile))
    except ValueError:
        available = False
    return {
        "authentication_required": bool(api_key_owners(config)),
        "provider_endpoint": f"{endpoint.scheme}://{endpoint.hostname}",
        "model": profile.model,
        "sft_collection_enabled": config.logging.sft_log_enabled,
        "sft_redaction_enabled": config.logging.sft_redact_pii,
        "sft_retention_days": config.logging.sft_retention_days,
        "max_script_chars": config.security.max_script_chars,
        "max_project_llm_tokens": 0 if config.share.enabled else config.security.max_project_llm_tokens,
        "public_mode": config.share.enabled,
        "public_url": config.share.public_url,
        "model_available": available,
        "mock_mode": mock,
        "quota": public_usage().status(_owner(request)) if config.share.enabled else None,
    }


@router.get("/demo-scripts", response_model=list[DemoSummary])
async def demo_scripts():
    return catalog()


@router.get("/demo-scripts/{script_id}", response_model=DemoDetail)
async def demo_script(script_id: str):
    return detail(script_id)


@router.get("/share-code")
async def share_code():
    import io

    import qrcode
    import qrcode.image.svg

    from app.api.sessions import validate_public_url

    url = get_config().share.public_url
    try:
        validate_public_url(url)
    except ValueError:
        raise HTTPException(409, "请用 ./speed_run.sh --share 启动手机体验。") from None
    output = io.BytesIO()
    qrcode.make(url + "/", image_factory=qrcode.image.svg.SvgPathFillImage, border=4).save(output)
    return Response(output.getvalue(), media_type="image/svg+xml", headers={
        "Content-Disposition": 'inline; filename="storybridge-qr.svg"',
        "Cache-Control": "no-store",
    })


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
    if body.idempotency_key:
        request_hash = hashlib.sha256(body.model_dump_json().encode()).hexdigest()
        with public_usage().database.transaction() as connection:
            previous = connection.execute(
                "SELECT project_id,request_hash FROM project_requests WHERE owner_id=? AND request_key=?",
                (_owner(request), body.idempotency_key),
            ).fetchone()
        if previous:
            if previous["request_hash"] and previous["request_hash"] != request_hash:
                raise HTTPException(409, {"code": "idempotency_conflict", "message": "内容已变化，请重新提交。"})
            meta = _project_or_404(workflow, previous["project_id"], request)
            return {"id": meta.id, "name": meta.name}
    meta = await workflow.create_project(
        body.name,
        body.script,
        body.market,
        owner_id=_owner(request),
        data_policy=body.data_policy,
    )
    if body.idempotency_key:
        with public_usage().database.transaction(immediate=True) as connection:
            connection.execute(
                "INSERT INTO project_requests VALUES(?,?,?,?)",
                (_owner(request), body.idempotency_key, meta.id, request_hash),
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


@router.post(
    "/projects/{project_id}/adaptations/plan-batch",
    response_model=list[AdaptationPlan],
)
async def create_batch_plan(project_id: str, body: BatchPlanBody, request: Request):
    workflow = _workflow(request)
    _project_or_404(workflow, project_id, request)
    _enforce_llm_budget(workflow, project_id)
    try:
        plans = await workflow.plan_many(project_id, body.culture_mechanism_ids)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise _upstream_failure("batch planning", project_id, exc) from exc
    return [plan.model_dump() for plan in plans]


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


@router.post(
    "/projects/{project_id}/adaptations/apply-batch",
    response_model=BatchApplyResult,
)
async def apply_adaptation_batch(
    project_id: str, body: BatchApplyBody, request: Request
):
    workflow = _workflow(request)
    _project_or_404(workflow, project_id, request)
    _enforce_llm_budget(workflow, project_id)
    try:
        result = await workflow.apply_adaptations(
            project_id,
            body.adaptations,
            auto_verify_and_repair=body.auto_verify_and_repair,
            based_on_version=body.based_on_version,
            operation_id=body.operation_id,
        )
    except (StateVersionConflict, DuplicateOperation) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise _upstream_failure("batch apply", project_id, exc) from exc
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


@router.get("/projects/{project_id}/verification", response_model=VerifyReport | None)
async def get_verification(project_id: str, request: Request):
    workflow = _workflow(request)
    _project_or_404(workflow, project_id, request)
    return workflow.latest_report(project_id)


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
    culture_mechanism_ids: list[str] | None = Field(
        default=None, min_length=1, max_length=20
    )
    adaptations: list[AdaptationSelection] | None = Field(
        default=None, min_length=1, max_length=20
    )
    based_on_version: int | None = Field(default=None, ge=1)
    idempotency_key: str | None = Field(default=None, min_length=1, max_length=200)
    auto_verify_and_repair: bool = Field(
        default=False,
        description="Only run automatic verification and repair when explicitly authorized.",
    )

    @model_validator(mode="after")
    def _required_fields_for_kind(self) -> JobSubmitBody:
        if self.kind == JobKind.APPLY and not (
            self.culture_mechanism_id and self.option_label
        ):
            raise ValueError("apply job needs culture_mechanism_id and option_label")
        if self.kind == JobKind.PLAN and not self.culture_mechanism_id:
            raise ValueError("plan job needs culture_mechanism_id")
        if self.kind == JobKind.PLAN_BATCH and not self.culture_mechanism_ids:
            raise ValueError("plan_batch job needs culture_mechanism_ids")
        if self.kind == JobKind.APPLY_BATCH and not self.adaptations:
            raise ValueError("apply_batch job needs adaptations")
        if self.culture_mechanism_ids and len(self.culture_mechanism_ids) != len(
            set(self.culture_mechanism_ids)
        ):
            raise ValueError("culture mechanism ids must be unique")
        if self.adaptations:
            ids = [item.culture_mechanism_id for item in self.adaptations]
            if len(ids) != len(set(ids)):
                raise ValueError("each culture mechanism can only appear once in a batch")
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
    request_hash = hashlib.sha256(body.model_dump_json().encode()).hexdigest()
    if existing is not None:
        if existing.kind != body.kind or (existing.request_hash and existing.request_hash != request_hash):
            raise HTTPException(409, {"code": "idempotency_conflict", "message": "请求已用于其他步骤。"})
        return {"job_id": existing.id, "status": existing.status}
    if body.kind in {JobKind.APPLY, JobKind.APPLY_BATCH} and body.based_on_version is not None:
        current_version = workflow.require_state(project_id).version
        if body.based_on_version != current_version:
            raise HTTPException(409, "state version conflict: 故事已更新，请刷新后重试。")

    factories = {
        JobKind.ANALYZE: lambda: workflow.analyze(project_id),
        JobKind.PLAN: lambda: workflow.plan(project_id, body.culture_mechanism_id),
        JobKind.PLAN_BATCH: lambda: workflow.plan_many(project_id, body.culture_mechanism_ids or []),
        JobKind.APPLY: lambda: workflow.apply_adaptation(
            project_id, body.culture_mechanism_id, body.option_label,
            auto_verify_and_repair=body.auto_verify_and_repair,
            based_on_version=body.based_on_version, operation_id=body.idempotency_key,
        ),
        JobKind.APPLY_BATCH: lambda: workflow.apply_adaptations(
            project_id, body.adaptations or [],
            auto_verify_and_repair=body.auto_verify_and_repair,
            based_on_version=body.based_on_version, operation_id=body.idempotency_key,
        ),
        JobKind.VERIFY: lambda: workflow.verify(project_id),
        JobKind.RENDER: lambda: workflow.render_target_script(project_id),
    }
    slot = None
    if get_config().share.enabled:
        try:
            slot = public_usage().admit(_owner(request))
        except PublicLimitError as exc:
            raise HTTPException(429, exc.detail()) from exc
    else:
        owned = {m.id for m in workflow.store.list_projects() if m.owner_id == _owner(request)}
        usage_guard(request).check_job_submission(_owner(request), owned, jobs)
    try:
        job = _submit(
            jobs, body.kind.value, project_id, factories[body.kind],
            idempotency_key=body.idempotency_key,
            on_finished=(lambda: public_usage().release(slot)) if slot else None,
            request_hash=request_hash,
        )
    except BaseException:
        if slot:
            public_usage().release(slot)
        raise
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
