import { useEffect, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import { api, ApiError } from './api/client'
import { JobFailure, pollJob, wait } from './api/pollJob'
import { PlanOptions } from './components/AdaptationPanels'
import { CopyDownload, DemoPicker, Modal, ShareDialog } from './components/ExperienceDialogs'
import { StoryGraphView } from './components/StoryGraphView'
import { VerificationReview } from './components/VerificationReview'
import { emptyProgress, newDraft, newTask, readSaved, save } from './state/recovery'
import type { AdaptationFlow, Draft, Progress, Stage } from './state/recovery'
import type { AdaptationPlan, ProjectSummary, PropagationResult, RuntimePolicy, StoryGraphResponse, StoryState, VerifyReport } from './types/api'
import './App.css'

type Artifacts = Awaited<ReturnType<typeof api.exportProject>>
const stageCopy: Record<Stage, string> = {
  analyze: '正在读懂故事，识别需要调整的文化背景',
  plan_batch: '正在为所选内容准备改编方案',
  apply_batch: '正在按你的选择改写关联场景',
  verify: '正在检查人物动机、因果和伏笔是否连贯',
  repair: '正在按照检查结果修复矛盾场景并重新检查',
  render: '正在生成完整的目标语言剧本',
}
function currentStageCopy(stage: Stage, flow?: AdaptationFlow) {
  if (stage === 'plan_batch' && flow?.phase === 'culture') return '核心设定已更新，正在重新审查文化背景和名词'
  if (stage === 'apply_batch' && flow?.phase === 'settings' && flow.deferredIds.length) return '正在先统一核心故事设定'
  return stageCopy[stage]
}
const languages = [
  { label: '英语（美国）', language: 'English', locale: 'en-US' },
  { label: '英语（英国）', language: 'English', locale: 'en-GB' },
  { label: '日语（日本）', language: 'Japanese', locale: 'ja-JP' },
  { label: '西班牙语（西班牙）', language: 'Spanish', locale: 'es-ES' },
  { label: '法语（法国）', language: 'French', locale: 'fr-FR' },
  { label: '韩语（韩国）', language: 'Korean', locale: 'ko-KR' },
]
let sessionPromise: ReturnType<typeof api.session> | null = null
function initializeSession() {
  sessionPromise ??= api.session().catch(error => { sessionPromise = null; throw error })
  return sessionPromise
}
function readable(error: unknown) {
  if (error instanceof ApiError) {
    const reset = error.resetsAt ? ` 可于 ${new Date(error.resetsAt).toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai' })}（北京时间）重试。` : ''
    return error.message + reset
  }
  return error instanceof TypeError ? '暂时无法连接，请联网后重试。已保存的内容会保留。' : error instanceof Error ? error.message : '暂未完成，请重试。'
}
function defaultSelection(data: Artifacts): string[] {
  const points = data.state?.culture_mechanisms || []
  if (points.length) return [(points.find(p => p.friction_level === 'high') || points[0]).id]
  return coreSettings(data.state as StoryState | null | undefined).slice(0, 1).map(item => item.id)
}
function coreSettings(state: StoryState | null | undefined) {
  if (!state) return []
  const mustPreserve = new Set(state.commitments.filter(item => item.must_preserve).map(item => item.id))
  const linked = new Set<string>()
  for (const dependency of state.dependencies) {
    if (dependency.source_id.startsWith('SET') && mustPreserve.has(dependency.target_id)) linked.add(dependency.source_id)
    if (dependency.target_id.startsWith('SET') && mustPreserve.has(dependency.source_id)) linked.add(dependency.target_id)
  }
  return state.settings.filter(item => linked.has(item.id) || item.scene_ids.length > 1)
}
function targetSceneIds(state: StoryState, targetId: string) {
  const mechanism = state.culture_mechanisms.find(item => item.id === targetId)
  if (mechanism) return mechanism.scene_ids
  const setting = state.settings.find(item => item.id === targetId)
  if (!setting) return []
  const commitmentIds = new Set(
    state.dependencies.flatMap(dependency => {
      if (dependency.source_id === targetId && dependency.target_id.startsWith('NC')) return [dependency.target_id]
      if (dependency.target_id === targetId && dependency.source_id.startsWith('NC')) return [dependency.source_id]
      return []
    }),
  )
  return [...new Set([
    ...setting.scene_ids,
    ...state.commitments.filter(item => commitmentIds.has(item.id)).flatMap(item => [item.established_at_scene_id, item.payoff_scene_id].filter((id): id is string => !!id)),
  ])]
}
function mergeGraphs(graphs: StoryGraphResponse[]): StoryGraphResponse {
  const nodes = new Map(graphs.flatMap(graph => graph.nodes).map(node => [node.id, node]))
  const edges = new Map(graphs.flatMap(graph => graph.edges).map(edge => [edge.id, edge]))
  return { nodes: [...nodes.values()], edges: [...edges.values()] }
}

function App() {
  const [owner, setOwner] = useState('')
  const [ready, setReady] = useState(false)
  const [draft, setDraft] = useState<Draft>(newDraft)
  const [progress, setProgress] = useState<Progress>(emptyProgress)
  const current = useRef(progress)
  const [artifacts, setArtifacts] = useState<Artifacts | null>(null)
  const [report, setReport] = useState<VerifyReport | null>(null)
  const [policy, setPolicy] = useState<RuntimePolicy | null>(null)
  const [projects, setProjects] = useState<ProjectSummary[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [pause, setPause] = useState('')
  const [storageNote, setStorageNote] = useState('')
  const [dialog, setDialog] = useState<'demo' | 'share' | 'stories' | null>(null)
  const [impacts, setImpacts] = useState<PropagationResult[]>([])
  const [graph, setGraph] = useState<StoryGraphResponse | null>(null)
  const [detailsError, setDetailsError] = useState('')
  const [compare, setCompare] = useState<'source' | 'adapted'>('source')
  const controller = useRef<AbortController | null>(null)
  const state = artifacts?.state as StoryState | null | undefined
  const task = progress.task
  const busy = loading || task?.status === 'running'
  const activeAdaptationIds = progress.adaptationFlow?.activeIds || progress.selected
  const plans = (artifacts?.plans || []).filter(p => p.based_on_version === state?.version && activeAdaptationIds.includes(p.culture_mechanism_id)) as AdaptationPlan[]
  const sorted = [...(state?.culture_mechanisms || [])].sort((a, b) => ({ high: 3, medium: 2, low: 1 }[b.friction_level] - { high: 3, medium: 2, low: 1 }[a.friction_level]))
  const settings = coreSettings(state)
  const target = artifacts?.target_script
  const stagedSettingApply = task?.stage === 'apply_batch'
    && progress.adaptationFlow?.phase === 'settings'
    && !!progress.adaptationFlow.deferredIds.length
  const step = (target && progress.view !== 'choose') || (task && !stagedSettingApply && ['apply_batch', 'verify', 'repair', 'render'].includes(task.stage)) ? 3 : state ? 2 : 1
  const limited = !!policy?.quota && (policy.quota.visitor_used >= policy.quota.visitor_limit || policy.quota.site_used >= policy.quota.site_limit)
  const reviewToken = report?.review_token || ''
  const reviewChoices: Record<string, 'modify' | 'keep'> = {
    ...Object.fromEntries((report?.kept_issue_indexes || []).map(index => [`issue:${index}`, 'keep' as const])),
    ...Object.fromEntries((report?.kept_commitment_ids || []).map(id => [`commitment:${id}`, 'keep' as const])),
    ...(progress.review?.token === reviewToken ? progress.review.choices : {}),
  }
  const repairNote = progress.repairNote || { text: '', sceneId: '' }
  const reviewHasWork = !!repairNote.text.trim() || Object.values(reviewChoices).includes('modify')
    || !!report?.issues.some((item, index) => item.severity === 'error' && reviewChoices[`issue:${index}`] !== 'keep')
    || !!report?.commitment_checks.some(item => item.status === 'violated' && reviewChoices[`commitment:${item.commitment_id}`] !== 'keep')

  function commit(next: Progress) {
    current.current = next
    if (owner) {
      const saved = save(owner, 'active', next)
      if (next.projectId) save(owner, `story.${next.projectId}`, next)
      if (!saved) setStorageNote('浏览器未允许保存草稿，请保持页面打开，并及时复制结果。')
    }
    setProgress(next)
  }
  function flowAfterSelection(selected: string[]): AdaptationFlow | undefined {
    const settingIds = selected.filter(id => id.startsWith('SET'))
    const cultureIds = selected.filter(id => id.startsWith('CM'))
    if (!settingIds.length && !cultureIds.length) return undefined
    return settingIds.length && cultureIds.length
      ? { phase: 'settings', activeIds: settingIds, deferredIds: cultureIds }
      : { phase: settingIds.length ? 'settings' : 'culture', activeIds: selected, deferredIds: [] }
  }
  function transitionAfterApply(next: Progress, operationKey: string) {
    const flow = next.adaptationFlow
    if (flow?.phase === 'settings' && flow.deferredIds.length) {
      const cultureIds = flow.deferredIds
      next.adaptationFlow = { phase: 'culture', activeIds: cultureIds, deferredIds: [] }
      next.view = 'choose'
      next.task = newTask(
        'plan_batch',
        { culture_mechanism_ids: cultureIds },
        false,
        `${operationKey}:culture-plan`,
      )
      return true
    }
    return false
  }
  function edit(values: Partial<Draft>) { setDraft(previous => ({ ...previous, ...values, createKey: crypto.randomUUID() })) }
  async function reloadArtifacts(projectId: string, signal?: AbortSignal) {
    const [data, verification] = await Promise.all([api.exportProject(projectId, signal), api.verification(projectId, signal)])
    if (signal?.aborted) throw new DOMException('Aborted', 'AbortError')
    setArtifacts(data); setReport(verification)
    return data
  }
  useEffect(() => {
    let disposed = false
    const abort = new AbortController()
    async function init() {
      try {
        const session = await initializeSession()
        if (disposed) return
        const visitor = session.visitor_id
        const restored = readSaved<Progress>(visitor, 'active') || emptyProgress()
        restored.custom ||= {}
        setOwner(visitor); setDraft(readSaved<Draft>(visitor, 'draft') || newDraft())
        current.current = restored; setProgress(restored)
        const [nextPolicy, nextProjects] = await Promise.all([api.getRuntimePolicy(abort.signal), api.listProjects(abort.signal)])
        if (disposed) return
        setPolicy(nextPolicy); setProjects(nextProjects)
        if (restored.projectId) {
          if (nextProjects.some(p => p.id === restored.projectId)) await reloadArtifacts(restored.projectId, abort.signal)
          else { const empty = emptyProgress(); current.current = empty; setProgress(empty); save(visitor, 'active', empty) }
        }
        if (!disposed) setReady(true)
      } catch (caught) { if (!disposed) setError(readable(caught)) }
    }
    void init()
    return () => { disposed = true; abort.abort() }
  }, [])
  useEffect(() => {
    if (owner && ready && !save(owner, 'draft', draft)) setStorageNote('浏览器存储已满，请复制你的草稿后继续。')
  }, [owner, ready, draft])
  useEffect(() => {
    if (!ready) return
    const refresh = () => {
      if (!document.hidden && navigator.onLine) api.getRuntimePolicy().then(setPolicy).catch(() => undefined)
    }
    const timer = window.setInterval(refresh, 30000)
    document.addEventListener('visibilitychange', refresh)
    window.addEventListener('online', refresh)
    window.addEventListener('focus', refresh)
    return () => {
      clearInterval(timer); document.removeEventListener('visibilitychange', refresh)
      window.removeEventListener('online', refresh); window.removeEventListener('focus', refresh)
    }
  }, [ready])
  const selectedKey = activeAdaptationIds.join('|')
  useEffect(() => {
    if (!progress.projectId || !plans.length) return
    const abort = new AbortController()
    Promise.all(selectedKey.split('|').filter(Boolean).map(id => api.getPropagation(progress.projectId!, id, abort.signal)))
      .then(setImpacts).catch(() => { if (!abort.signal.aborted) setDetailsError('影响范围暂未读取成功，展开详情可重试。') })
    return () => abort.abort()
  }, [progress.projectId, state?.version, plans.length, selectedKey])
  useEffect(() => {
    if (!ready || !progress.projectId || task?.status !== 'running') return
    const abort = new AbortController(); controller.current = abort
    const projectId = progress.projectId
    const active = { ...task }
    async function run() {
      try {
        // Persisted request keys make uncertain submission safe to repeat.
        if (!active.jobId) {
          while (true) {
            try {
              const submitted = await api.submitJob(projectId, active.request, abort.signal)
              active.jobId = submitted.job_id
              if (abort.signal.aborted) return
              commit({ ...current.current, task: active }); break
            } catch (caught) {
              if (abort.signal.aborted || (caught instanceof ApiError && caught.status < 500)) throw caught
              setPause('连接暂时中断，正在恢复提交。不会重复生成。')
              await wait(2000, abort.signal)
            }
          }
        }
        const completed = await pollJob(active.jobId!, { signal: abort.signal, onPause: setPause })
        let data: Artifacts
        while (true) {
          try { data = await reloadArtifacts(projectId, abort.signal); break }
          catch (caught) {
            if (abort.signal.aborted || (caught instanceof ApiError && caught.status < 500)) throw caught
            setPause('这一步已完成，正在恢复连接以读取结果。'); await wait(2000, abort.signal)
          }
        }
        if (abort.signal.aborted) return
        setPause(''); setError('')
        const next = { ...current.current }
        if (active.stage === 'repair' && active.request.repair_suggestion === next.repairNote?.text.trim()) {
          next.repairNote = { text: '', sceneId: '' }
        }
        if (active.stage === 'analyze') next.selected = defaultSelection(data)
        if (active.stage === 'verify' || active.stage === 'repair') {
          const checked = completed.result as VerifyReport
          setReport(checked)
          if (checked.overall_status === 'fail' || checked.overall_status === 'not_run' || checked.issues.some(i => i.severity === 'error')) {
            next.task = { ...active, status: 'blocked', error: active.stage === 'repair' ? '已经修复并重新检查，但仍有阻塞问题。可以查看剩余问题后继续修复。' : '检查发现阻塞问题，已暂停目标语言生成。请查看下方检查详情并按问题修复。' }
            commit(next); return
          }
        }
        if (active.stage === 'apply_batch' && transitionAfterApply(next, active.key)) {
          // The setting rewrite changed the story. Generate culture/terminology
          // choices only now, against the newly saved state.
        }
        else if (active.chain && active.stage === 'apply_batch') next.task = newTask('verify', {}, true, `${active.key}:verify`)
        else if (active.chain && (active.stage === 'verify' || active.stage === 'repair')) next.task = newTask('render', {}, true, `${active.key}:render`)
        else next.task = { ...active, status: 'done' }
        commit(next)
        api.getRuntimePolicy().then(setPolicy).catch(() => undefined)
      } catch (caught) {
        if (abort.signal.aborted) return
        // A process can stop after committing rewritten scenes but before
        // persisting the task result. Reconcile that narrow window before retry.
        if (active.stage === 'apply_batch') {
          try {
            const recovered = await reloadArtifacts(projectId, abort.signal)
            if (recovered.adaptations.some(item => item.operation_id === active.key)) {
              const next = { ...current.current }
              if (!transitionAfterApply(next, active.key)) next.task = newTask('verify', {}, true, `${active.key}:verify`)
              commit(next)
              return
            }
          } catch { /* The saved stage remains available for a later retry. */ }
        }
        if (abort.signal.aborted) return
        const cancelled = caught instanceof JobFailure && caught.job.status === 'cancelled'
        commit({ ...current.current, task: { ...active, status: cancelled ? 'cancelled' : 'failed', error: readable(caught), resetsAt: caught instanceof ApiError ? caught.resetsAt : undefined } })
        api.getRuntimePolicy().then(setPolicy).catch(() => undefined)
      }
    }
    void run()
    return () => { abort.abort() }
    // A key identifies one durable stage. Recording its server id does not restart it.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ready, progress.projectId, task?.key, task?.status])

  async function analyze(event: FormEvent) {
    event.preventDefault()
    if (busy || !ready || !draft.script.trim()) return
    setLoading(true); setError('')
    try {
      save(owner, 'draft', draft)
      const project = await api.createProject({
        name: draft.name.trim() || draft.script.trim().split('\n')[0].slice(0, 32) || '新的故事',
        script: draft.script, idempotency_key: draft.createKey,
        market: { market: draft.market, audience: draft.audience, genre: draft.genre, format: draft.format,
          target_language: draft.language, target_locale: draft.locale, source_language: 'zh-CN', style_guide: '' },
      })
      commit({ ...emptyProgress(), projectId: project.id, task: newTask('analyze') })
      setProjects(await api.listProjects())
    } catch (caught) { setError(readable(caught)) }
    finally { setLoading(false) }
  }
  function begin(stage: Stage) {
    if (!state || busy) return
    const request = stage === 'plan_batch' ? { culture_mechanism_ids: activeAdaptationIds }
      : stage === 'apply_batch' ? { based_on_version: state.version, auto_verify_and_repair: false,
        adaptations: activeAdaptationIds.map(id => ({ culture_mechanism_id: id, option_label: progress.labels[id] as 'A' | 'B' | 'C' | 'CUSTOM',
          ...(progress.labels[id] === 'CUSTOM' ? { custom_instruction: progress.custom[id] } : {}) })) }
      : stage === 'repair' ? {
        based_on_report: reviewToken,
        repair_suggestion: repairNote.text.trim(),
        repair_scene_ids: repairNote.text.trim() && repairNote.sceneId ? [repairNote.sceneId] : [],
        review_issue_indexes: (report?.issues || []).flatMap((issue, index) => issue.severity !== 'error' && reviewChoices[`issue:${index}`] === 'modify' ? [index] : []),
        review_commitment_ids: (report?.commitment_checks || []).filter(item => item.status === 'needs_review' && reviewChoices[`commitment:${item.commitment_id}`] === 'modify').map(item => item.commitment_id),
      } : {}
    const settingStageHasFollowup = stage === 'apply_batch'
      && progress.adaptationFlow?.phase === 'settings'
      && !!progress.adaptationFlow.deferredIds.length
    setError(''); commit({ ...progress, view: stage === 'plan_batch' || settingStageHasFollowup ? 'choose' : 'result', task: newTask(stage, request, ['verify', 'repair', 'render'].includes(stage) || (stage === 'apply_batch' && !settingStageHasFollowup)) })
  }
  function startPlanning() {
    if (!state || busy || !progress.selected.length) return
    const adaptationFlow = flowAfterSelection(progress.selected)
    if (!adaptationFlow) return
    setError('')
    commit({
      ...progress,
      adaptationFlow,
      labels: {},
      custom: {},
      view: 'choose',
      task: newTask('plan_batch', { culture_mechanism_ids: adaptationFlow.activeIds }),
    })
  }
  async function submitReview() {
    if (!progress.projectId || !report || busy) return
    setLoading(true); setError('')
    try {
      const confirmed = await api.confirmReview(progress.projectId, {
        based_on_report: reviewToken,
        kept_issue_indexes: report.issues.flatMap((_, index) => reviewChoices[`issue:${index}`] === 'keep' ? [index] : []),
        kept_commitment_ids: report.commitment_checks.filter(item => reviewChoices[`commitment:${item.commitment_id}`] === 'keep').map(item => item.commitment_id),
      })
      setReport(confirmed)
      begin(reviewHasWork ? 'repair' : 'render')
    } catch (caught) { setError(readable(caught)) }
    finally { setLoading(false) }
  }
  async function cancel() {
    if (!task?.jobId) return
    try {
      const stopped = await api.cancelJob(task.jobId)
      if (stopped.status === 'done') return
      controller.current?.abort(); setPause('')
      commit({ ...current.current, task: { ...task, status: 'cancelled', error: '已取消。之前完成的内容仍然保留。' } })
    } catch (caught) { setError(readable(caught)) }
  }
  function retry() {
    if (!task || busy) return
    // Only a known terminal failure receives a new key. A rejected submission
    // retains its key, so a response lost in transit cannot duplicate work.
    const next = task.jobId ? newTask(task.stage, task.request, task.chain) : { ...task, status: 'running' as const, error: '' }
    commit({ ...progress, task: next }); setError('')
  }
  function startNew() {
    if (busy) return
    commit(emptyProgress()); setDraft(newDraft()); setArtifacts(null); setReport(null)
    setImpacts([]); setGraph(null); setError(''); setDialog(null)
  }
  async function openStory(id: string) {
    if (busy) return
    setLoading(true); setError('')
    try {
      const data = await reloadArtifacts(id)
      const saved = readSaved<Progress>(owner, `story.${id}`)
      const restored = saved || { ...emptyProgress(), projectId: id, selected: defaultSelection(data) }
      restored.custom ||= {}
      commit(restored)
      setImpacts([]); setGraph(null); setDialog(null)
    } catch (caught) { setError(readable(caught)) }
    finally { setLoading(false) }
  }
  async function deleteStory(id: string) {
    if (!window.confirm('删除这个故事和它的生成结果？当日已使用额度不会恢复。')) return
    try {
      await api.deleteProject(id)
      if (progress.projectId === id) startNew()
      setProjects(await api.listProjects())
    } catch (caught) { setError(readable(caught)) }
  }
  function toggleAdaptation(id: string) {
    const selected = progress.selected.includes(id)
      ? progress.selected.filter(item => item !== id)
      : [...progress.selected, id]
    setImpacts([]); setGraph(null)
    commit({ ...progress, selected, labels: {}, custom: {}, adaptationFlow: undefined, task: null })
  }
  async function loadDetails() {
    if (!progress.projectId) return
    setDetailsError('')
    try {
      const [results, focusedGraphs] = await Promise.all([
        Promise.all(activeAdaptationIds.map(id => api.getPropagation(progress.projectId!, id))),
        Promise.all(activeAdaptationIds.map(id => api.getGraph(progress.projectId!, id, 2))),
      ])
      setImpacts(results); setGraph(mergeGraphs(focusedGraphs))
    } catch (caught) { setDetailsError(readable(caught)) }
  }
  const fullText = target?.scenes.map(s => `${s.title}\n\n${s.text}`).join('\n\n') || ''
  return <div className="app-shell">
    <header className="topbar"><a className="brand" href="#top"><span className="brand-mark">S<span>↗</span></span><span><strong>StoryBridge</strong><small>让好故事走向世界</small></span></a><nav aria-label="主导航"><button type="button" onClick={() => setDialog('stories')} disabled={!ready}>我的故事</button><button type="button" onClick={() => setDialog('share')}>手机扫码体验</button></nav></header>
    <main id="top">
      <section className="hero"><div><p className="eyebrow">STORIES WITHOUT BORDERS</p><h1>换一种文化，<br />保留故事的动人之处。</h1><p>读懂中文故事里的文化背景，选择适合当地观众的表达，<br className="desktop-break" />生成情节连贯的目标语言剧本。</p></div><div className="hero-note"><span>从这里，走向那里</span><strong>故事 · 文化 · 共鸣</strong><p>无需注册、安装或填写模型密钥</p><span className="hero-arrow" aria-hidden="true">↗</span></div></section>
      {policy?.mock_mode && <div className="mock-banner" role="status">开发演示模式：当前使用固定模拟结果，不代表真实模型效果。</div>}
      <ol className="steps" aria-label="体验步骤">{['输入故事', '选择改编方案', '查看结果'].map((label, index) => <li key={label} aria-current={step === index + 1 ? 'step' : undefined} className={step === index + 1 ? 'active' : step > index + 1 ? 'complete' : ''}><span>{step > index + 1 ? '✓' : `0${index + 1}`}</span><strong>{label}</strong></li>)}</ol>
      {!ready && !error && <p role="status">正在准备你的故事空间…</p>}
      {storageNote && <p role="status" className="notice">{storageNote}</p>}
      {error && <div className="error" role="alert"><p>{error}</p>{!ready && <button type="button" onClick={() => location.reload()}>重新连接</button>}</div>}
      {policy?.quota && <div className="quota"><span>今日剩余额度 <strong>{Math.max(0, policy.quota.visitor_limit - policy.quota.visitor_used).toLocaleString('zh-CN')}</strong> tokens</span><small>输入与输出合计 · 北京时间每天 00:00 恢复</small>{limited && <p role="alert">今日额度已用完，已有内容仍可查看、复制和下载。恢复时间：{new Date(policy.quota.resets_at).toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai' })}（北京时间）</p>}</div>}
      {ready && !progress.projectId && <section className="input-card panel">
        <div className="section-heading"><div><p className="eyebrow">YOUR STORY</p><h2>从一个故事开始</h2></div><button type="button" className="text-link" disabled={busy} onClick={() => setDialog('demo')}>试试示例剧本 ↗</button></div>
        <form onSubmit={analyze}><fieldset className="draft-fields" disabled={busy}>
          <label className="story-input"><span>中文剧本</span><textarea required rows={12} value={draft.script} onChange={e => edit({ script: e.target.value })} placeholder="粘贴你的故事、短剧或一个片段。也可以先试试示例，再改成你的版本。" maxLength={policy?.max_script_chars || 500000} /><small>{draft.script.length.toLocaleString('zh-CN')} 字符 · 草稿自动保存在当前浏览器</small></label>
          <div className="fields"><label><span>目标市场</span><input required list="markets" value={draft.market} onChange={e => edit({ market: e.target.value })} /></label><datalist id="markets">{['美国', '英国', '日本', '西班牙', '法国', '韩国'].map(m => <option key={m}>{m}</option>)}</datalist><label><span>目标语言与地区</span><select value={languages.find(l => l.locale === draft.locale && l.language === draft.language)?.locale || 'custom'} onChange={e => { const choice = languages.find(l => l.locale === e.target.value); if (choice) edit({ language: choice.language, locale: choice.locale }); else edit({ locale: '', language: '' }) }}>{languages.map(l => <option value={l.locale} key={l.locale}>{l.label}</option>)}<option value="custom">自定义语言与地区</option></select></label></div>
          <details className="settings" open={!draft.locale || !draft.language ? true : undefined}><summary>更多设置</summary><div className="fields"><label><span>故事名称（留空自动生成）</span><input maxLength={200} value={draft.name} onChange={e => edit({ name: e.target.value })} /></label><label><span>受众</span><input value={draft.audience} onChange={e => edit({ audience: e.target.value })} /></label><label><span>类型</span><input value={draft.genre} onChange={e => edit({ genre: e.target.value })} /></label><label><span>形式</span><input value={draft.format} onChange={e => edit({ format: e.target.value })} /></label><label><span>语言名称</span><input required value={draft.language} onChange={e => edit({ language: e.target.value })} /></label><label><span>语言地区代码（如 en-US）</span><input required value={draft.locale} onChange={e => { const choice = languages.find(l => l.locale === e.target.value); edit({ locale: e.target.value, ...(choice ? { language: choice.language } : {}) }) }} /></label></div></details>
          <div className="privacy-note"><strong>{policy?.model_available ? '默认模型已配置，直接开始即可。' : '默认模型暂不可用，请联系组织者。'}</strong><p>提交后，故事会发送给模型服务用于分析和改编。请使用你有权分享的内容。</p><details><summary>查看数据使用说明</summary><p>故事与结果保存在组织者的服务端；你可以在“我的故事”中删除。默认不收集全文训练样本。运行日志记录用量和摘要，不保存模型请求全文。当前模型：{policy?.model}。清除 Cookie 或更换网站地址后，不能自动找回原身份。tokens 额度不等于固定金额的费用上限。</p></details></div>
          <div className="bottom-action"><span>接下来：看看哪些内容需要调整</span><button type="submit" className="primary" disabled={!ready || busy || limited || !draft.script.trim() || !policy?.model_available}>{loading ? '正在保存故事…' : '开始分析'} <span aria-hidden="true">→</span></button></div>
        </fieldset></form>
      </section>}
      {progress.projectId && <div className="story-heading"><div><p className="eyebrow">MY STORY</p><h2>{artifacts?.project.name || '正在准备故事'}</h2></div><button type="button" disabled={busy} onClick={startNew}>开始新故事</button></div>}
      {task && task.status !== 'done' && <div className={`task-status ${task.status === 'running' ? 'running' : 'attention'}`} role={task.status === 'running' ? 'status' : 'alert'}>
        <div><strong>{task.status === 'running' ? currentStageCopy(task.stage, progress.adaptationFlow) : '这一步还未完成'}</strong><p>{task.status === 'running' ? pause || '你可以切换应用，回来后会继续显示进度。生成可能需要几分钟。' : task.error}</p></div>
        {task.status === 'running' ? <button type="button" disabled={!task.jobId} onClick={() => void cancel()}>取消</button> : <button type="button" disabled={busy || limited} onClick={task.status === 'blocked' && (task.stage === 'verify' || task.stage === 'repair') ? () => void submitReview() : retry}>{task.status === 'blocked' && (task.stage === 'verify' || task.stage === 'repair') ? (reviewHasWork ? '按检查结果修复' : '确认保留并继续') : '重试当前步骤'}</button>}
      </div>}
      {state && step === 2 && <section className="panel adaptation">
        <div className="section-heading"><div><p className="eyebrow">MAKE IT RESONATE</p><h2>哪些内容需要调整</h2></div><span className="muted">{state.scenes.length} 个场景 · {state.characters.length} 位角色</span></div>
        <p className="muted">选择一个或多个文化背景或核心故事设定，保留关键情节与人物动机。</p>
        {sorted.length > 0 && <><h3 className="target-group-title">文化背景</h3><div className="friction-list">{sorted.map(point => <label className={`friction-card ${progress.selected.includes(point.id) ? 'selected' : ''}`} key={point.id}>
          <input type="checkbox" checked={progress.selected.includes(point.id)} disabled={busy} onChange={() => toggleAdaptation(point.id)} />
          <div><header><h3>{point.name}</h3><span className={`tag ${point.friction_level}`}>{point.friction_level === 'high' ? '优先调整' : point.friction_level === 'medium' ? '建议解释' : '可保留'}</span></header><p>{point.description}</p>{point.surface_text.length > 0 && <blockquote>{point.surface_text.join(' / ')}</blockquote>}<small>影响场景：{point.scene_ids.map(id => state.scenes.find(s => s.id === id)?.title || '关联场景').join('、')}</small></div>
        </label>)}</div></>}
        {settings.length > 0 && <><h3 className="target-group-title">核心故事设定</h3><p className="muted target-group-note">这些规则关系到故事如何成立，也可以保留、替换或重新设计。</p><div className="friction-list">{settings.map(setting => <label className={`friction-card setting-card ${progress.selected.includes(setting.id) ? 'selected' : ''}`} key={setting.id}>
          <input type="checkbox" checked={progress.selected.includes(setting.id)} disabled={busy} onChange={() => toggleAdaptation(setting.id)} />
          <div><header><h3>{setting.name}</h3><span className="tag core">核心设定</span></header><p>{setting.description}</p><small>影响场景：{targetSceneIds(state, setting.id).map(id => state.scenes.find(scene => scene.id === id)?.title || '关联场景').join('、') || '将在生成方案时判断'}</small></div>
        </label>)}</div></>}
        {sorted.length + settings.length === 0 ? <div className="notice"><p>未发现需要特别调整的内容，可以直接检查并生成目标语言剧本。</p><button className="primary" type="button" disabled={busy || limited} onClick={() => begin('verify')}>检查并生成剧本 →</button></div> : <button type="button" className="primary" disabled={busy || limited || !progress.selected.length} onClick={startPlanning}>{plans.length ? '重新生成方案' : '生成方案'} →</button>}
        {plans.length > 0 && <div className="plans">
          {progress.adaptationFlow?.phase === 'settings' && progress.adaptationFlow.deferredIds.length > 0
            ? <div className="notice phase-notice"><strong>第 1 步：先统一核心设定</strong><p>应用后，系统会基于新版故事重新审查你选中的文化背景和名词，再让你选择下一批方案。</p></div>
            : progress.adaptationFlow?.phase === 'culture' && progress.selected.some(id => id.startsWith('SET'))
              ? <div className="notice phase-notice"><strong>第 2 步：复核文化背景与名词</strong><p>下面的方案已根据刚刚更新的核心设定重新生成，不会沿用旧世界观里的名词方案。</p></div>
              : null}
          <h2>{progress.adaptationFlow?.phase === 'settings' ? '为核心设定选择方案' : '为每项内容选择方案'}</h2><p className="muted">可以选择 A/B/C，也可以写下自己的改编要求。</p>{plans.map(plan => <section className="point-plan" key={plan.culture_mechanism_id}><h3>{plan.original_name}</h3><PlanOptions plan={plan} disabled={busy} selectedLabel={progress.labels[plan.culture_mechanism_id] || null} customValue={progress.custom[plan.culture_mechanism_id] || ''} onSelect={label => commit({ ...progress, labels: { ...progress.labels, [plan.culture_mechanism_id]: label } })} onCustomChange={value => commit({ ...progress, custom: { ...progress.custom, [plan.culture_mechanism_id]: value }, labels: { ...progress.labels, [plan.culture_mechanism_id]: 'CUSTOM' } })} /></section>)}
          <div className="impact-summary"><strong>改编将联动这些场景</strong><p>{[...new Set(impacts.length ? impacts.flatMap(i => i.affected_scenes.map(s => s.scene_id)) : activeAdaptationIds.flatMap(id => targetSceneIds(state, id)))].map(id => state.scenes.find(s => s.id === id)?.title || '关联场景').join('、')}。相关动机和伏笔也会一起检查。</p></div>
          <details onToggle={e => { if (e.currentTarget.open) void loadDetails() }}><summary>展开关联路径、图谱和详细依据</summary>{detailsError && <p role="alert">{detailsError}</p>}{impacts.map((impact, i) => <div className="relation-list" key={i}><p>{impact.summary}</p><ul>{impact.affected_scenes.map(s => <li key={s.scene_id}><strong>{state.scenes.find(scene => scene.id === s.scene_id)?.title}</strong>：{s.evidence || '与所选文化点存在情节关联'}</li>)}</ul></div>)}{graph && <details><summary>查看关系图</summary><div className="graph-container"><StoryGraphView graph={graph} affectedIds={new Set(impacts.flatMap(i => i.affected_scenes.map(s => s.scene_id)))} focusIds={new Set(activeAdaptationIds)} /></div></details>}</details>
          <div className="bottom-action"><span>{progress.adaptationFlow?.phase === 'settings' && progress.adaptationFlow.deferredIds.length ? '接下来：先改设定，再重新审查文化名词' : '接下来：自动改写、检查并生成目标语言'}</span><button className="primary" type="button" disabled={busy || limited || plans.length !== activeAdaptationIds.length || !activeAdaptationIds.every(id => progress.labels[id] && (progress.labels[id] !== 'CUSTOM' || progress.custom[id]?.trim()))} onClick={() => begin('apply_batch')}>{progress.adaptationFlow?.phase === 'settings' && progress.adaptationFlow.deferredIds.length ? '先应用核心设定 →' : '生成改编剧本 →'}</button></div>
        </div>}
      </section>}
      {state && step === 3 && <section className="panel results">
        <div className="section-heading"><div><p className="eyebrow">A STORY, REIMAGINED</p><h2>{target ? `${target.target_language} 完整剧本` : '你的改编正在成形'}</h2></div>{target && <span className="tag">{target.target_locale}</span>}</div>
        {report?.overall_status === 'needs_review' && <p className="notice" role="status">有些项目需要你确认是否修改，请在检查详情中选择。</p>}
        {target ? <><CopyDownload text={fullText} filename={`${artifacts?.project.name || 'StoryBridge'}-${target.target_locale}.txt`} /><div className="script-scenes">{target.scenes.map(scene => <article key={scene.id}><h3>{scene.title}</h3><p>{scene.text}</p></article>)}</div></> : <p className="muted">{task?.stage === 'apply_batch' ? '改写完成后会继续检查故事，再生成目标语言全文。' : '已完成的改编稿保存在下面，目标语言全文将在这里显示。'}</p>}
        <details><summary>原文对比与中文改编稿</summary><div className="tabs" aria-label="对比内容"><button aria-pressed={compare === 'source'} type="button" onClick={() => setCompare('source')}>原文</button><button aria-pressed={compare === 'adapted'} type="button" onClick={() => setCompare('adapted')}>中文改编稿</button></div><pre className="story-text">{compare === 'source' ? artifacts?.script : state.scenes.map(s => `${s.title}\n${s.text}`).join('\n\n')}</pre></details>
        <details open={report?.overall_status === 'fail' || report?.overall_status === 'needs_review'}><summary>检查详情{report?.overall_status === 'needs_review' ? ' · 待确认是否修改' : report?.overall_status === 'fail' ? ' · 存在阻塞问题' : ''}</summary>{report ? <VerificationReview report={report} choices={reviewChoices} note={repairNote} scenes={state.scenes} baseline={state.repair_baseline} onNoteChange={note => commit({ ...progress, repairNote: note })} disabled={busy || limited} onDecide={(key, choice) => commit({ ...progress, review: { token: reviewToken, choices: { ...reviewChoices, [key]: choice } } })} onRepair={() => void submitReview()} onContinue={() => void submitReview()} onVerify={() => begin('verify')} /> : <p>检查尚未完成。</p>}</details>
        <details><summary>版本历史</summary><ol className="history">{artifacts?.revisions.map(r => <li key={r.revision_id}>版本 {r.state_version} · {r.kind === 'initial_parse' ? '完成故事分析' : '保存改编结果'} · {r.changed_scene_ids?.length || 0} 个场景更新</li>)}</ol></details>
        <div className="actions"><button type="button" disabled={busy} onClick={() => commit({ ...progress, labels: {}, custom: {}, adaptationFlow: undefined, task: null, view: 'choose' })}>重新选择改编方案</button><button type="button" disabled={busy} onClick={startNew}>开始新故事</button></div>
      </section>}
      {ready && progress.projectId && !state && !busy && !task && <button className="primary" type="button" disabled={limited} onClick={() => commit({ ...progress, task: newTask('analyze') })}>继续分析故事</button>}
    </main>
    <footer><strong>StoryBridge</strong><span>让故事被理解，让情感有回响。</span></footer>
    {dialog === 'demo' && !progress.projectId && <DemoPicker hasText={!!draft.script.trim()} onClose={() => setDialog(null)} onImport={(text, title) => { edit({ script: text, name: title }); setDialog(null) }} />}
    {dialog === 'share' && <ShareDialog url={policy?.public_url || ''} onClose={() => setDialog(null)} />}
    {dialog === 'stories' && <Modal title="我的故事" onClose={() => setDialog(null)}><p className="muted">这些故事属于当前浏览器。清除 Cookie 或更换网站地址后，不能自动找回。</p><button className="primary" type="button" disabled={busy} onClick={startNew}>开始新故事</button><ul className="story-list">{projects.map(project => <li key={project.id}><button type="button" disabled={busy} onClick={() => void openStory(project.id)}><strong>{project.name || '未命名故事'}</strong><small>{new Date(project.created_at).toLocaleDateString('zh-CN')}</small></button><button type="button" disabled={busy} onClick={() => void deleteStory(project.id)} aria-label={`删除 ${project.name}`}>删除</button></li>)}</ul>{!projects.length && <p>还没有保存的故事，从一个新故事开始吧。</p>}</Modal>}
  </div>
}
export default App
