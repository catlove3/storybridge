"""One frozen, whole-script baseline; no retries chosen for presentation quality."""
import asyncio, hashlib, json
from dataclasses import asdict
from run_case import ROOT, Recorder, dump, get_config, build_router, project_data_context
from app.llm.base import LLMRequest
from app.storage import ProjectMeta

async def main():
    dest = ROOT / 'evidence/naive_full.md'
    if dest.exists():
        raise RuntimeError('The first result already exists; refusing to overwrite it.')
    source = (ROOT / 'source.md').read_text()
    profile = json.loads((ROOT / 'evidence/paired_brief.json').read_text())
    project = ProjectMeta.model_validate_json((ROOT / 'evidence/project.json').read_text())
    config = get_config()
    for step in config.llm.step_routes:
        config.llm.step_routes[step] = config.llm.default_profile
    request = LLMRequest(
        step='baseline_naive_full',
        system_prompt='你是一名编剧。',
        user_prompt='请根据完整原稿与下面全部改编要求，直接改编成美国背景的完整英语剧本，保留 S01–S07 顺序。你可以附上必要的改编说明。\n\n【完整原稿】\n' + source + '\n\n【全部改编要求与同一选定方案】\n' + json.dumps(profile, ensure_ascii=False, indent=2),
        json_mode=False,
    )
    dump('naive_protocol.json', {
        'protocol': 'Full source + same complete profile, brief and selected creative plan, one call for a complete English adaptation. No restriction on which scenes can change; optional explanations allowed.',
        'selection': 'Use the first completed response, irrespective of comparative outcome. No response edits.',
        'model': config.llm.profile_for_step('baseline_naive_full').model,
        'source_sha256': hashlib.sha256(source.encode()).hexdigest(),
        'shared_profile_sha256': hashlib.sha256(json.dumps(profile, ensure_ascii=False, sort_keys=True).encode()).hexdigest(),
        'request': asdict(request),
        'comparison': 'One illustrative case. Same model and creative inputs; workflows and call budgets differ. Not a benchmark.',
    })
    (ROOT / 'evidence/naive_prompt.md').write_text('系统提示：' + request.system_prompt + '\n\n' + request.user_prompt)
    client = Recorder(build_router()); client.group = 'naive_full'
    with project_data_context(project.id, project.data_policy):
        response = await client.complete(request)
    dump('naive_response.json', asdict(response))
    dest.write_text(response.text)
    if response.finish_reason == 'length':
        raise RuntimeError('Output was truncated; preserve and report rather than presenting as complete.')
    print('Saved first response:', dest, 'finish_reason=', response.finish_reason, flush=True)

if __name__ == '__main__':
    asyncio.run(main())
