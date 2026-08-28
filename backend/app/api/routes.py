from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.graph import StoryGraph
from app.schemas import StoryState, VerifyReport
from app.storage import MarketProfile
from app.workflow.engine import ApplyResult, StoryBridgeWorkflow

router = APIRouter(prefix="/api")


def _workflow(request: Request) -> StoryBridgeWorkflow:
    return request.app.state.workflow


def _project_or_404(workflow: StoryBridgeWorkflow, project_id: str):
    meta = workflow.store.load_meta(project_id)
    if meta is None:
        raise HTTPException(status_code=404, detail=f"unknown project: {project_id}")
    return meta


class CreateProjectBody(BaseModel):
    name: str = ""
    script: str
    market: MarketProfile = MarketProfile()


class PlanBody(BaseModel):
    culture_mechanism_id: str


class ApplyBody(BaseModel):
    culture_mechanism_id: str
    option_label: str
    auto_verify_and_repair: bool = True


@router.post("/projects")
async def create_project(body: CreateProjectBody, request: Request):
    workflow = _workflow(request)
    meta = await workflow.create_project(body.name, body.script, body.market)
    return {"id": meta.id, "name": meta.name}


@router.get("/projects")
async def list_projects(request: Request):
    return [
        {"id": m.id, "name": m.name, "created_at": m.created_at}
        for m in _workflow(request).store.list_projects()
    ]


@router.get("/projects/{project_id}")
async def get_project(project_id: str, request: Request):
    workflow = _workflow(request)
    meta = _project_or_404(workflow, project_id)
    state = workflow.store.load_state(project_id)
    return {"id": meta.id, "name": meta.name, "market": meta.market, "analyzed": state is not None}


@router.post("/projects/{project_id}/analyze")
async def analyze(project_id: str, request: Request):
    workflow = _workflow(request)
    _project_or_404(workflow, project_id)
    try:
        state = await workflow.analyze(project_id)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"analyze failed: {exc}") from exc
    return _state_summary(state)


@router.get("/projects/{project_id}/state")
async def get_state(project_id: str, request: Request):
    workflow = _workflow(request)
    _project_or_404(workflow, project_id)
    try:
        state = workflow.require_state(project_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return state.model_dump()


@router.get("/projects/{project_id}/graph")
async def get_graph(project_id: str, request: Request, focus: str | None = None, depth: int = 2):
    workflow = _workflow(request)
    _project_or_404(workflow, project_id)
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
            "source": u,
            "target": v,
            "relation": d.get("relation", ""),
            "evidence": d.get("evidence", ""),
        }
        for u, v, d in sub.edges(data=True)
    ]
    return {"nodes": nodes, "edges": edges}


@router.get("/projects/{project_id}/propagate")
async def propagate(project_id: str, request: Request, mechanism: str):
    workflow = _workflow(request)
    _project_or_404(workflow, project_id)
    try:
        result = workflow.propagate(project_id, mechanism)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return result.model_dump()


@router.post("/projects/{project_id}/adaptations/plan")
async def create_plan(project_id: str, body: PlanBody, request: Request):
    workflow = _workflow(request)
    _project_or_404(workflow, project_id)
    try:
        plan = await workflow.plan(project_id, body.culture_mechanism_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"planning failed: {exc}") from exc
    return plan.model_dump()


@router.post("/projects/{project_id}/adaptations/apply")
async def apply_adaptation(project_id: str, body: ApplyBody, request: Request):
    workflow = _workflow(request)
    _project_or_404(workflow, project_id)
    try:
        result: ApplyResult = await workflow.apply_adaptation(
            project_id,
            body.culture_mechanism_id,
            body.option_label,
            auto_verify_and_repair=body.auto_verify_and_repair,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"apply failed: {exc}") from exc
    return result.model_dump()


@router.post("/projects/{project_id}/verify")
async def verify(project_id: str, request: Request):
    workflow = _workflow(request)
    _project_or_404(workflow, project_id)
    report: VerifyReport = await workflow.verify(project_id)
    return report.model_dump()


@router.get("/projects/{project_id}/revisions")
async def revisions(project_id: str, request: Request):
    workflow = _workflow(request)
    _project_or_404(workflow, project_id)
    return [r.model_dump() for r in workflow.store.list_revisions(project_id)]


@router.get("/projects/{project_id}/diff")
async def diff(project_id: str, request: Request):
    from app.export import changed_scenes_diff

    workflow = _workflow(request)
    _project_or_404(workflow, project_id)
    try:
        return changed_scenes_diff(workflow.store, project_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/projects/{project_id}/bible")
async def bible(project_id: str, request: Request):
    from app.export.bible import export_bible

    workflow = _workflow(request)
    _project_or_404(workflow, project_id)
    try:
        text = export_bible(workflow, project_id, _bible_path(request, project_id))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"saved": str(text)}


def _bible_path(request: Request, project_id: str):

    from app.config import get_config

    out = get_config().storage.projects_dir / project_id / "adaptation_bible.md"
    return out


class JobSubmitBody(BaseModel):
    kind: str
    culture_mechanism_id: str | None = None
    option_label: str | None = None


@router.post("/projects/{project_id}/jobs")
async def submit_job(project_id: str, body: JobSubmitBody, request: Request):
    workflow = _workflow(request)
    jobs = request.app.state.jobs
    _project_or_404(workflow, project_id)

    if body.kind == "analyze":
        job = jobs.submit(
            "analyze", project_id, lambda: workflow.analyze(project_id)
        )
    elif body.kind == "apply":
        if not body.culture_mechanism_id or not body.option_label:
            raise HTTPException(400, "apply job needs culture_mechanism_id + option_label")
        job = jobs.submit(
            "apply",
            project_id,
            lambda: workflow.apply_adaptation(
                project_id, body.culture_mechanism_id, body.option_label
            ),
        )
    elif body.kind == "verify":
        job = jobs.submit("verify", project_id, lambda: workflow.verify(project_id))
    elif body.kind == "plan":
        if not body.culture_mechanism_id:
            raise HTTPException(400, "plan job needs culture_mechanism_id")
        job = jobs.submit(
            "plan",
            project_id,
            lambda: workflow.plan(project_id, body.culture_mechanism_id),
        )
    else:
        raise HTTPException(400, f"unknown job kind: {body.kind}")

    return {"job_id": job.id, "status": job.status}


@router.get("/jobs/{job_id}")
async def get_job(job_id: str, request: Request):
    jobs = request.app.state.jobs
    job = jobs.get(job_id)
    if job is None:
        raise HTTPException(404, f"unknown job: {job_id}")
    return job.serialize()


@router.get("/projects/{project_id}/jobs")
async def list_jobs(project_id: str, request: Request):
    jobs = request.app.state.jobs
    return [j.model_dump(exclude={"result"}) for j in jobs.list_for_project(project_id)]


def _state_summary(state: StoryState) -> dict:
    return {
        "characters": len(state.characters),
        "scenes": len(state.scenes),
        "events": len(state.events),
        "settings": len(state.settings),
        "culture_mechanisms": [cm.model_dump() for cm in state.culture_mechanisms],
        "commitments": [nc.model_dump() for nc in state.commitments],
        "dependencies": len(state.dependencies),
        "high_friction_ids": [cm.id for cm in state.culture_mechanisms if cm.friction_level == "high"],
    }
