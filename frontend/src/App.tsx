import { useEffect, useMemo, useRef, useState } from 'react'
import type { FormEvent, KeyboardEvent } from 'react'
import { api, ApiError } from './api/client'
import { pollJob } from './api/pollJob'
import { ImpactPanel, PlanOptions } from './components/AdaptationPanels'
import {
  CompleteScript,
  DiffPanel,
  RevisionTimeline,
  TargetLanguageScript,
  VerificationPanel,
} from './components/FinalArtifacts'
import { StoryGraphView } from './components/StoryGraphView'
import { ProjectSwitcher } from './components/ProjectSwitcher'
import {
  persistJob,
  persistProject,
  recoveryJobId,
  recoveryProjectId,
} from './state/recovery'
import type {
  AdaptationPlan,
  ApplyResult,
  CultureMechanism,
  EmotionalFunction,
  Job,
  Level,
  PlotFunction,
  PropagationResult,
  ProjectSummary,
  Revision,
  RuntimePolicy,
  SceneDiff,
  SocialFunction,
  StoryGraphResponse,
  StoryState,
  TargetScript,
  VerifyReport,
} from './types/api'
import './App.css'

type AnalyzePhase = 'idle' | 'creating' | 'analyzing' | 'loading-state' | 'done' | 'error'
type AdaptationAction = 'idle' | 'planning' | 'loading-impact' | 'applying' | 'verifying' | 'rendering'
type NarrativeFunction = PlotFunction | SocialFunction | EmotionalFunction

const levelMeta: Record<Level, { label: string; description: string }> = {
  high: { label: '高摩擦', description: '需要重点本土化' },
  medium: { label: '中摩擦', description: '需要语境解释' },
  low: { label: '低摩擦', description: '可直接保留' },
}

const functionLabels: Record<NarrativeFunction, string> = {
  motivation: '人物动机', constraint: '情节约束', conflict: '冲突来源',
  revelation: '信息揭示', foreshadowing: '伏笔铺设', payoff: '承诺回收',
  reversal: '剧情反转', status: '社会地位', power: '权力关系',
  obligation: '社会义务', kinship: '亲缘关系', reputation: '声誉压力',
  institutional_access: '制度准入', economic_security: '经济安全',
  humiliation: '羞辱感', aspiration: '向往感', fear: '恐惧感',
  sympathy: '共情', suspense: '悬念', satisfaction: '满足感',
}

const phaseCopy: Record<AnalyzePhase, string> = {
  idle: '等待输入剧本',
  creating: '正在创建项目…',
  analyzing: 'Agent 正在解析故事与识别文化摩擦…',
  'loading-state': '分析完成，正在读取 Story State…',
  done: '分析完成，可选择文化机制继续改编',
  error: '流程中断',
}

const phaseIndex: Record<AnalyzePhase, number> = {
  idle: 0, creating: 1, analyzing: 2, 'loading-state': 3, done: 4, error: 0,
}

const actionCopy: Record<AdaptationAction, string> = {
  idle: '',
  planning: 'Agent 正在生成 A / B / C 改编方案…',
  'loading-impact': '正在计算传播范围并读取聚焦图谱…',
  applying: '正在改写受影响场景，并执行 Verify / Repair…',
  verifying: '正在重新验证最新 Story State…',
  rendering: '正在将冻结的结构稿渲染为目标语言剧本…',
}

function readableError(caught: unknown) {
  if (caught instanceof DOMException && caught.name === 'AbortError') return ''
  if (caught instanceof ApiError) return `后端返回 ${caught.status}：${caught.message}`
  if (caught instanceof Error) return caught.message
  return '发生未知错误。'
}

function sortMechanisms(mechanisms: CultureMechanism[]) {
  const rank: Record<Level, number> = { high: 3, medium: 2, low: 1 }
  return [...mechanisms].sort(
    (left, right) => rank[right.friction_level] - rank[left.friction_level],
  )
}

function FunctionGroup({ label, values }: { label: string; values: NarrativeFunction[] }) {
  return (
    <div className="function-group">
      <span className="function-group__label">{label}</span>
      <div className="function-group__tags">
        {values.length > 0
          ? values.map((value) => <span key={value}>{functionLabels[value]}</span>)
          : <span className="function-tag--empty">未标注</span>}
      </div>
    </div>
  )
}

interface FrictionCardProps {
  mechanism: CultureMechanism
  order: number
  selected: boolean
  disabled: boolean
  onSelect: () => void
}

function FrictionCard({ mechanism, order, selected, disabled, onSelect }: FrictionCardProps) {
  const meta = levelMeta[mechanism.friction_level]
  function handleKeyDown(event: KeyboardEvent<HTMLElement>) {
    if (!disabled && (event.key === 'Enter' || event.key === ' ')) {
      event.preventDefault()
      onSelect()
    }
  }

  return (
    <article
      aria-disabled={disabled}
      aria-pressed={selected}
      className={`friction-card friction-card--${mechanism.friction_level}${selected ? ' is-selected' : ''}`}
      onClick={disabled ? undefined : onSelect}
      onKeyDown={handleKeyDown}
      role="button"
      tabIndex={disabled ? -1 : 0}
    >
      <header className="friction-card__header">
        <div className="friction-card__identity">
          <span className="friction-card__order">{String(order + 1).padStart(2, '0')}</span>
          <div>
            <div className="friction-card__title-line">
              <h3>{mechanism.name}</h3><code>{mechanism.id}</code>
              {mechanism.adapted_to && <span className="adapted-badge">已改编</span>}
            </div>
            <p>{mechanism.description || '后端未提供机制说明'}</p>
          </div>
        </div>
        <div className={`level-badge level-badge--${mechanism.friction_level}`}>
          <strong>{meta.label}</strong><span>{meta.description}</span>
        </div>
      </header>

      <div className="friction-card__evidence">
        <div>
          <span className="detail-label">原文证据</span>
          <div className="quote-list">
            {mechanism.surface_text.length > 0
              ? mechanism.surface_text.map((quote, index) => <q key={`${quote}-${index}`}>{quote}</q>)
              : <span className="muted">无直接文本证据</span>}
          </div>
        </div>
        <div>
          <span className="detail-label">叙事重要度</span>
          <p className="scene-list">{levelMeta[mechanism.narrative_importance].label}</p>
          <span className="detail-label detail-label--spaced">出现位置</span>
          <p className="scene-list">
            {mechanism.scene_ids.length > 0 ? mechanism.scene_ids.join(' · ') : '未关联场景'}
          </p>
        </div>
      </div>

      <div className="narrative-functions">
        <div className="narrative-functions__heading">
          <span className="detail-label">Narrative Functions</span>
          <span>改编时必须保住的叙事作用</span>
        </div>
        <FunctionGroup label="剧情" values={mechanism.functions.plot} />
        <FunctionGroup label="社会" values={mechanism.functions.social} />
        <FunctionGroup label="情绪" values={mechanism.functions.emotional} />
      </div>

      <div className="friction-card__selection">
        <span>{selected ? '当前改编对象' : '点击选择并进入改编'}</span>
        <span aria-hidden="true">{selected ? '✓' : '→'}</span>
      </div>
    </article>
  )
}

function App() {
  const [name, setName] = useState('跨文化分析 Demo')
  const [script, setScript] = useState('')
  const [market, setMarket] = useState('United States')
  const [audience, setAudience] = useState('18–30')
  const [format, setFormat] = useState('Short drama')
  const [genre, setGenre] = useState('Urban drama')
  const [targetLanguage, setTargetLanguage] = useState('English')
  const [targetLocale, setTargetLocale] = useState('en-US')
  const [sftOptIn, setSftOptIn] = useState(false)
  const [contentSource, setContentSource] = useState('')
  const [contentLicense, setContentLicense] = useState('')
  const [consentNote, setConsentNote] = useState('')
  const [runtimePolicy, setRuntimePolicy] = useState<RuntimePolicy | null>(null)
  const [projects, setProjects] = useState<ProjectSummary[]>([])
  const [phase, setPhase] = useState<AnalyzePhase>('idle')
  const [project, setProject] = useState<{ id: string; name: string } | null>(null)
  const [analyzeJob, setAnalyzeJob] = useState<Job | null>(null)
  const [storyState, setStoryState] = useState<StoryState | null>(null)
  const [error, setError] = useState('')
  const [selectedMechanismId, setSelectedMechanismId] = useState<string | null>(null)
  const [plan, setPlan] = useState<AdaptationPlan | null>(null)
  const [selectedOptionLabel, setSelectedOptionLabel] = useState<string | null>(null)
  const [propagation, setPropagation] = useState<PropagationResult | null>(null)
  const [graph, setGraph] = useState<StoryGraphResponse | null>(null)
  const [action, setAction] = useState<AdaptationAction>('idle')
  const [actionMessage, setActionMessage] = useState('')
  const [actionError, setActionError] = useState('')
  const [activeJob, setActiveJob] = useState<Job | null>(null)
  const [lastApply, setLastApply] = useState<{ mechanismId: string; result: ApplyResult } | null>(null)
  const [verifyReport, setVerifyReport] = useState<VerifyReport | null>(null)
  const [diffs, setDiffs] = useState<SceneDiff[]>([])
  const [revisions, setRevisions] = useState<Revision[]>([])
  const [targetScript, setTargetScript] = useState<TargetScript | null>(null)
  const controllerRef = useRef<AbortController | null>(null)

  const sortedMechanisms = useMemo(() => sortMechanisms(storyState?.culture_mechanisms ?? []), [storyState])
  const selectedMechanism = useMemo(
    () => storyState?.culture_mechanisms.find((item) => item.id === selectedMechanismId) ?? null,
    [selectedMechanismId, storyState],
  )
  const selectedOption = useMemo(
    () => plan?.options.find((option) => option.option_label === selectedOptionLabel) ?? null,
    [plan, selectedOptionLabel],
  )
  const affectedIds = useMemo(() => {
    const ids = new Set<string>()
    if (selectedMechanismId) ids.add(selectedMechanismId)
    propagation?.affected_scenes.forEach((scene) => {
      ids.add(scene.scene_id)
      scene.reason_path.forEach((id) => ids.add(id))
    })
    propagation?.related_commitment_ids.forEach((id) => ids.add(id))
    return ids
  }, [propagation, selectedMechanismId])

  useEffect(() => {
    const controller = new AbortController()
    controllerRef.current = controller
    api.getRuntimePolicy(controller.signal).then(setRuntimePolicy).catch(() => undefined)
    api.listProjects(controller.signal).then((items) => {
      setProjects(items)
      const recoverId = recoveryProjectId()
      if (recoverId && items.some((item) => item.id === recoverId)) {
        void restoreProject(recoverId, controller)
      }
    }).catch(() => undefined)
    return () => {
      controller.abort()
      controllerRef.current?.abort()
    }
  }, [])

  const analyzeBusy = ['creating', 'analyzing', 'loading-state'].includes(phase)
  const actionBusy = action !== 'idle'
  const currentPhaseIndex = phaseIndex[phase]
  const adaptationStep = lastApply ? 5 : propagation && selectedOption ? 3 : plan ? 2 : selectedMechanism ? 1 : 0

  function nextController() {
    controllerRef.current?.abort()
    const controller = new AbortController()
    controllerRef.current = controller
    return controller
  }

  function trackAnalyzeJob(job: Job) {
    setAnalyzeJob(job)
    persistJob(job.status === 'queued' || job.status === 'running' ? job.id : null)
  }

  function trackActiveJob(job: Job) {
    setActiveJob(job)
    persistJob(job.status === 'queued' || job.status === 'running' ? job.id : null)
  }

  function resetAdaptation() {
    setSelectedMechanismId(null)
    setPlan(null)
    setSelectedOptionLabel(null)
    setPropagation(null)
    setGraph(null)
    setAction('idle')
    setActionMessage('')
    setActionError('')
    setActiveJob(null)
    setLastApply(null)
    setVerifyReport(null)
    setDiffs([])
    setRevisions([])
    setTargetScript(null)
  }

  async function restoreProject(projectId: string, providedController?: AbortController) {
    const controller = providedController ?? nextController()
    setError('')
    setActionError('')
    setPhase('loading-state')
    resetAdaptation()
    try {
      const detail = await api.getProject(projectId, controller.signal)
      setProject({ id: detail.id, name: detail.name })
      setName(detail.name)
      setMarket(detail.market.market)
      setAudience(detail.market.audience)
      setFormat(detail.market.format)
      setGenre(detail.market.genre)
      setTargetLanguage(detail.market.target_language ?? 'English')
      setTargetLocale(detail.market.target_locale ?? 'en-US')
      setSftOptIn(detail.data_policy.sft_opt_in)
      setContentSource(detail.data_policy.content_source)
      setContentLicense(detail.data_policy.license)
      setConsentNote(detail.data_policy.consent_note)
      persistProject(projectId)

      let jobs = await api.listJobs(projectId, controller.signal)
      const rememberedJobId = recoveryJobId()
      const active = jobs.find((job) => job.id === rememberedJobId && (job.status === 'queued' || job.status === 'running'))
        ?? [...jobs].reverse().find((job) => job.status === 'queued' || job.status === 'running')
      if (active) {
        persistJob(active.id)
        if (active.kind === 'analyze') {
          setPhase('analyzing')
          await pollJob(active.id, { signal: controller.signal, timeoutMs: 15 * 60_000, onUpdate: trackAnalyzeJob })
        } else {
          setAction(active.kind === 'apply' ? 'applying' : active.kind === 'verify' ? 'verifying' : active.kind === 'render' ? 'rendering' : 'planning')
          await pollJob(active.id, { signal: controller.signal, timeoutMs: 30 * 60_000, onUpdate: trackActiveJob })
          setAction('idle')
        }
        jobs = await api.listJobs(projectId, controller.signal)
      }
      persistJob(null)

      const state = await api.getStoryState(projectId, controller.signal)
      const [nextRevisions, nextDiffs, restoredTarget] = await Promise.all([
        api.getRevisions(projectId, controller.signal),
        api.getDiff(projectId, controller.signal).catch(() => [] as SceneDiff[]),
        api.getTargetScript(projectId, controller.signal).catch(() => null),
      ])
      const completedApply = [...jobs].reverse().find((job) => job.kind === 'apply' && job.status === 'done')
      const applyJob = completedApply
        ? await api.getJob<ApplyResult>(completedApply.id, controller.signal)
        : null
      const completedPlan = [...jobs].reverse().find((job) => job.kind === 'plan' && job.status === 'done')
      const planJob = completedPlan
        ? await api.getJob<AdaptationPlan>(completedPlan.id, controller.signal)
        : null

      setStoryState(state)
      setRevisions(nextRevisions)
      setDiffs(nextDiffs)
      setTargetScript(restoredTarget)
      if (applyJob?.result) {
        setLastApply({
          mechanismId: applyJob.result.applied.plan_culture_mechanism_id,
          result: applyJob.result,
        })
        setVerifyReport(applyJob.result.report)
      }
      if (planJob?.result && planJob.result.based_on_version === state.version) {
        setPlan(planJob.result)
      }
      const restoredMechanismId = applyJob?.result?.applied.plan_culture_mechanism_id
        ?? planJob?.result?.culture_mechanism_id
        ?? sortMechanisms(state.culture_mechanisms)[0]?.id
        ?? null
      setSelectedMechanismId(restoredMechanismId)
      setPhase('done')
    } catch (caught) {
      const message = readableError(caught)
      if (!message) return
      setError(`恢复项目失败：${message}`)
      setPhase('error')
      setAction('idle')
    }
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!script.trim() || analyzeBusy || actionBusy) return
    const controller = nextController()
    setError('')
    setStoryState(null)
    setProject(null)
    setAnalyzeJob(null)
    resetAdaptation()

    try {
      setPhase('creating')
      const created = await api.createProject({
        name: name.trim(), script: script.trim(),
        market: {
          market: market.trim(), audience: audience.trim(), format: format.trim(), genre: genre.trim(),
          source_language: 'zh-CN', target_language: targetLanguage.trim(), target_locale: targetLocale.trim(),
        },
        data_policy: {
          sft_opt_in: sftOptIn,
          content_source: sftOptIn ? contentSource.trim() : '',
          license: sftOptIn ? contentLicense.trim() : '',
          consent_note: sftOptIn ? consentNote.trim() : '',
          retention_days: runtimePolicy?.sft_retention_days ?? 30,
        },
      }, controller.signal)
      setProject(created)
      persistProject(created.id)
      setProjects((items) => [
        { id: created.id, name: created.name, created_at: new Date().toISOString() },
        ...items.filter((item) => item.id !== created.id),
      ])
      setPhase('analyzing')
      const submitted = await api.submitJob(created.id, { kind: 'analyze', idempotency_key: crypto.randomUUID() }, controller.signal)
      persistJob(submitted.job_id)
      await pollJob(submitted.job_id, { signal: controller.signal, timeoutMs: 15 * 60_000, onUpdate: trackAnalyzeJob })
      setPhase('loading-state')
      const state = await api.getStoryState(created.id, controller.signal)
      setStoryState(state)
      setSelectedMechanismId(sortMechanisms(state.culture_mechanisms)[0]?.id ?? null)
      setRevisions(await api.getRevisions(created.id, controller.signal))
      setPhase('done')
      persistJob(null)
    } catch (caught) {
      const message = readableError(caught)
      if (!message) return
      setError(message)
      setPhase('error')
      persistJob(null)
    }
  }

  function handleSelectMechanism(mechanismId: string) {
    if (actionBusy) return
    setSelectedMechanismId(mechanismId)
    setPlan(null)
    setSelectedOptionLabel(null)
    setPropagation(null)
    setGraph(null)
    setLastApply(null)
    setVerifyReport(null)
    setDiffs([])
    setTargetScript(null)
    setActionMessage('')
    setActionError('')
  }

  async function handlePlan() {
    if (!project || !selectedMechanism || actionBusy) return
    const controller = nextController()
    setAction('planning')
    setActionError('')
    setActionMessage('')
    setActiveJob(null)
    setPlan(null)
    setSelectedOptionLabel(null)
    setPropagation(null)
    setGraph(null)
    setLastApply(null)
    setVerifyReport(null)
    setDiffs([])
    try {
      const submitted = await api.submitJob(project.id, {
        kind: 'plan', culture_mechanism_id: selectedMechanism.id, idempotency_key: crypto.randomUUID(),
      }, controller.signal)
      persistJob(submitted.job_id)
      const completed = await pollJob<AdaptationPlan>(submitted.job_id, { signal: controller.signal, timeoutMs: 15 * 60_000, onUpdate: trackActiveJob })
      if (!completed.result) throw new Error('Plan job 已完成，但没有返回 Adaptation Plan。')
      setPlan(completed.result)
      setActionMessage(`已为 ${selectedMechanism.name} 生成 ${completed.result.options.length} 个真实方案。`)
      persistJob(null)
    } catch (caught) {
      const message = readableError(caught)
      if (message) setActionError(message)
    } finally {
      setAction('idle')
      persistJob(null)
    }
  }

  async function handleSelectOption(optionLabel: string) {
    if (!project || !selectedMechanism || actionBusy) return
    const controller = nextController()
    setSelectedOptionLabel(optionLabel)
    setAction('loading-impact')
    setActionError('')
    setActionMessage('')
    setPropagation(null)
    setGraph(null)
    try {
      const [nextPropagation, nextGraph] = await Promise.all([
        api.getPropagation(project.id, selectedMechanism.id, controller.signal),
        api.getGraph(project.id, selectedMechanism.id, 4, controller.signal),
      ])
      setPropagation(nextPropagation)
      setGraph(nextGraph)
      setActionMessage(`方案 ${optionLabel} 已选定；传播范围与聚焦图谱已加载。`)
    } catch (caught) {
      const message = readableError(caught)
      if (message) setActionError(message)
    } finally {
      setAction('idle')
      persistJob(null)
    }
  }

  async function handleApply() {
    if (!project || !selectedMechanism || !selectedOption || !plan || !propagation || actionBusy) return
    const controller = nextController()
    setAction('applying')
    setActionError('')
    setActionMessage('')
    setActiveJob(null)
    setLastApply(null)
    setVerifyReport(null)
    try {
      const submitted = await api.submitJob(project.id, {
        kind: 'apply', culture_mechanism_id: selectedMechanism.id, option_label: selectedOption.option_label,
        based_on_version: plan.based_on_version, idempotency_key: crypto.randomUUID(),
      }, controller.signal)
      persistJob(submitted.job_id)
      const completed = await pollJob<ApplyResult>(submitted.job_id, { signal: controller.signal, timeoutMs: 30 * 60_000, onUpdate: trackActiveJob })
      if (!completed.result) throw new Error('Apply job 已完成，但没有返回改写与验证结果。')
      const [nextState, nextDiffs, nextRevisions, nextGraph] = await Promise.all([
        api.getStoryState(project.id, controller.signal),
        api.getDiff(project.id, controller.signal),
        api.getRevisions(project.id, controller.signal),
        api.getGraph(project.id, selectedMechanism.id, 4, controller.signal),
      ])
      setStoryState(nextState)
      setDiffs(nextDiffs)
      setRevisions(nextRevisions)
      setGraph(nextGraph)
      setLastApply({ mechanismId: selectedMechanism.id, result: completed.result })
      setVerifyReport(completed.result.report)
      setTargetScript(null)
      setActionMessage(`Apply 完成：改写 ${completed.result.applied.rewritten_scene_ids.length} 个场景，自动修复 ${completed.result.repair_rounds} 轮。`)
      persistJob(null)
    } catch (caught) {
      const message = readableError(caught)
      if (message) setActionError(message)
    } finally {
      setAction('idle')
      persistJob(null)
    }
  }

  async function handleVerify() {
    if (!project || actionBusy) return
    const controller = nextController()
    setAction('verifying')
    setActionError('')
    setActionMessage('')
    setActiveJob(null)
    try {
      const submitted = await api.submitJob(project.id, { kind: 'verify', idempotency_key: crypto.randomUUID() }, controller.signal)
      persistJob(submitted.job_id)
      const completed = await pollJob<VerifyReport>(submitted.job_id, { signal: controller.signal, timeoutMs: 15 * 60_000, onUpdate: trackActiveJob })
      if (!completed.result) throw new Error('Verify job 已完成，但没有返回 Verify Report。')
      setVerifyReport(completed.result)
      setActionMessage('最新 Story State 已重新验证。')
      persistJob(null)
    } catch (caught) {
      const message = readableError(caught)
      if (message) setActionError(message)
    } finally {
      setAction('idle')
      persistJob(null)
    }
  }

  async function handleRenderTarget() {
    if (!project || !storyState || actionBusy) return
    const controller = nextController()
    setAction('rendering')
    setActionError('')
    setActionMessage('')
    setActiveJob(null)
    try {
      const submitted = await api.submitJob(project.id, {
        kind: 'render', idempotency_key: `render-v${storyState.version}`,
      }, controller.signal)
      persistJob(submitted.job_id)
      await pollJob<TargetScript>(submitted.job_id, {
        signal: controller.signal, timeoutMs: 15 * 60_000, onUpdate: trackActiveJob,
      })
      const rendered = await api.getTargetScript(project.id, controller.signal)
      setTargetScript(rendered)
      setActionMessage(`目标语言剧本已生成，并绑定 Story State v${rendered.source_state_version}。`)
      persistJob(null)
    } catch (caught) {
      const message = readableError(caught)
      if (message) setActionError(message)
    } finally {
      setAction('idle')
      persistJob(null)
    }
  }

  async function handleCancelJob() {
    const job = activeJob?.status === 'queued' || activeJob?.status === 'running'
      ? activeJob
      : analyzeJob?.status === 'queued' || analyzeJob?.status === 'running'
        ? analyzeJob
        : null
    if (!job) return
    const cancelled = await api.cancelJob(job.id).catch(() => null)
    controllerRef.current?.abort()
    persistJob(null)
    if (cancelled) {
      if (cancelled.kind === 'analyze') setAnalyzeJob(cancelled)
      else setActiveJob(cancelled)
    }
    setAction('idle')
    setPhase(storyState ? 'done' : 'idle')
    setActionMessage(`Job ${job.id} 已取消。`)
  }

  return (
    <div className="app-shell">
      <header className="topbar">
        <a className="brand" href="#top" aria-label="StoryBridge 首页"><span className="brand__mark">SB</span><span><strong>StoryBridge</strong><small>跨文化故事改编智能体</small></span></a>
        <nav className="topbar__nav" aria-label="页面导航"><a href="#analyze">故事分析</a><a href="#adapt">改编工作台</a><a href="#final-script">完整剧本</a></nav>
        <div className="connection-note"><span className="connection-note__dot" />数据来自当前后端 /api</div>
      </header>

      <main id="top">
        <section className="hero-copy">
          <div><p className="eyebrow">STORY → STATE → ADAPTATION → VERIFICATION</p><h1>保住故事的作用，<br />再跨越文化的边界。</h1></div>
          <p className="hero-copy__intro">从真实 Story State 出发，沿 Dependency Graph 找到受影响场景，选择改编策略，自动改写并验证叙事承诺，最后得到可直接查看的完整改编剧本。</p>
        </section>

        <ProjectSwitcher activeProjectId={project?.id ?? null} busy={analyzeBusy || actionBusy} onOpen={(projectId) => void restoreProject(projectId)} projects={projects} />

        <section className="workspace" id="analyze" aria-label="剧本分析工作区">
          <form className="script-form" onSubmit={handleSubmit}>
            <div className="section-heading"><span>01</span><div><p className="eyebrow">SOURCE SCRIPT</p><h2>输入剧本</h2></div></div>
            <label><span>项目名称</span><input value={name} onChange={(event) => setName(event.target.value)} /></label>
            <label className="script-field"><span>中文剧本</span><textarea value={script} onChange={(event) => setScript(event.target.value)} placeholder="粘贴完整剧本或试演片段。前端不会填入隐藏的 mock 结果。" rows={15} required /><small>{script.length.toLocaleString('zh-CN')} 字符</small></label>
            <fieldset><legend>目标市场画像</legend><div className="field-grid">
              <label><span>市场</span><input value={market} onChange={(event) => setMarket(event.target.value)} /></label>
              <label><span>受众</span><input value={audience} onChange={(event) => setAudience(event.target.value)} /></label>
              <label><span>形式</span><input value={format} onChange={(event) => setFormat(event.target.value)} /></label>
              <label><span>类型</span><input value={genre} onChange={(event) => setGenre(event.target.value)} /></label>
              <label><span>目标语言</span><input required value={targetLanguage} onChange={(event) => setTargetLanguage(event.target.value)} /></label>
              <label><span>目标 locale</span><input required value={targetLocale} onChange={(event) => setTargetLocale(event.target.value)} /></label>
            </div></fieldset>
            <fieldset><legend>数据与 SFT 政策</legend><div className="field-grid">
              <label><span>运行时模型</span><input readOnly value={runtimePolicy ? `${runtimePolicy.model} · ${runtimePolicy.provider_endpoint}` : '正在读取后端政策…'} /></label>
              <label><span>服务端采集状态</span><input readOnly value={runtimePolicy?.sft_collection_enabled ? `可选开启 · 脱敏 ${runtimePolicy.sft_redaction_enabled ? '开' : '关'} · ${runtimePolicy.sft_retention_days} 天` : '关闭（不保存 SFT 全文）'} /></label>
              <label><span>授权 SFT 采集</span><input checked={sftOptIn} disabled={!runtimePolicy?.sft_collection_enabled} onChange={(event) => setSftOptIn(event.target.checked)} type="checkbox" /></label>
              {sftOptIn && <>
                <label><span>内容来源</span><input required value={contentSource} onChange={(event) => setContentSource(event.target.value)} /></label>
                <label><span>授权 / License</span><input required value={contentLicense} onChange={(event) => setContentLicense(event.target.value)} /></label>
                <label><span>明确同意说明</span><input required value={consentNote} onChange={(event) => setConsentNote(event.target.value)} /></label>
              </>}
            </div><p className="mock-disclosure">未勾选时不会把完整 prompt 或 completion 写入 SFT 数据；运行日志仅记录 BLAKE2b 摘要、耗时和 token metadata。</p></fieldset>
            <button className="primary-action" type="submit" disabled={!script.trim() || analyzeBusy || actionBusy}><span>{analyzeBusy ? '分析进行中' : '创建项目并分析'}</span><span aria-hidden="true">→</span></button>
            <p className="mock-disclosure">页面不内置分析结果。mock 模式仅替换 LLM 响应；项目、HTTP、job、Graph、Propagation、Diff 与 revisions 均走真实后端代码。</p>
          </form>

          <div className="analysis-panel">
            <div className="section-heading"><span>02</span><div><p className="eyebrow">FRICTION MAP</p><h2>文化摩擦与叙事功能</h2></div></div>
            <ol className="pipeline" aria-label="分析进度" aria-live="polite">
              {['创建项目', 'Analyze job', '读取 Story State'].map((label, index) => {
                const step = index + 1
                const isComplete = currentPhaseIndex > step
                const isActive = currentPhaseIndex === step
                return <li className={isComplete ? 'is-complete' : isActive ? 'is-active' : ''} key={label}><span>{isComplete ? '✓' : step}</span>{label}</li>
              })}
            </ol>
            <div className={`status-line status-line--${phase}`} aria-live="polite"><span className="status-line__pulse" /><div><strong>{phaseCopy[phase]}</strong>{project && <small>Project {project.id}</small>}{analyzeJob && <small>Job {analyzeJob.id} · {analyzeJob.status}</small>}</div>{analyzeJob && (analyzeJob.status === 'queued' || analyzeJob.status === 'running') && <button className="secondary-action" onClick={() => void handleCancelJob()} type="button">取消任务</button>}</div>
            {error && <div className="error-message" role="alert"><strong>没有得到 Story State</strong><p>{error}</p><span>请确认 FastAPI 已在 localhost:8000 启动，并查看后端日志。</span></div>}
            {!storyState && !error && <div className="empty-state"><div className="empty-state__orb"><span>故事</span><i /><span>文化</span></div><h3>{analyzeBusy ? 'Agent 正在搭建故事的结构地图' : '分析结果将在这里展开'}</h3><p>完成后可点击真实 Culture Friction，继续生成方案、传播分析、改写和验证。</p></div>}
            {storyState && <div className="results">
              <div className="result-summary"><div><strong>{storyState.scenes.length}</strong><span>场景</span></div><div><strong>{storyState.characters.length}</strong><span>角色</span></div><div><strong>{storyState.culture_mechanisms.length}</strong><span>文化机制</span></div><div><strong>{storyState.dependencies.length}</strong><span>依赖关系</span></div></div>
              <div className="result-context"><span>目标市场与语言</span><strong>{storyState.target_market || market}</strong>{(storyState.audience || audience) && <small>{storyState.audience || audience} · {storyState.target_language} ({storyState.target_locale})</small>}</div>
              {sortedMechanisms.length > 0 ? <div className="friction-list">{sortedMechanisms.map((mechanism, index) => <FrictionCard disabled={actionBusy} key={mechanism.id} mechanism={mechanism} onSelect={() => handleSelectMechanism(mechanism.id)} order={index} selected={selectedMechanismId === mechanism.id} />)}</div> : <div className="no-frictions">当前 Story State 没有保留下来的文化摩擦点。</div>}
            </div>}
          </div>
        </section>

        {storyState && selectedMechanism && <section className="adaptation-workbench" id="adapt" aria-label="改编工作台">
          <div className="workbench-heading"><div className="section-heading"><span>03</span><div><p className="eyebrow">ADAPTATION WORKBENCH</p><h2>从文化机制到完整改编</h2></div></div><p>当前对象 <strong>{selectedMechanism.id} · {selectedMechanism.name}</strong></p></div>
          <ol className="adaptation-pipeline" aria-label="改编进度">{['选择机制', '生成方案', '传播与图谱', '改写场景', '验证完成'].map((label, index) => <li className={adaptationStep > index ? 'is-complete' : adaptationStep === index ? 'is-active' : ''} key={label}><span>{adaptationStep > index ? '✓' : index + 1}</span><strong>{label}</strong></li>)}</ol>
          {(action !== 'idle' || actionMessage || activeJob) && <div className={`action-status${action !== 'idle' ? ' is-running' : ''}`} aria-live="polite"><span className="status-line__pulse" /><div><strong>{action !== 'idle' ? actionCopy[action] : actionMessage}</strong>{activeJob && <small>Job {activeJob.id} · {activeJob.kind} · {activeJob.status}</small>}</div>{activeJob && (activeJob.status === 'queued' || activeJob.status === 'running') && <button className="secondary-action" onClick={() => void handleCancelJob()} type="button">取消任务</button>}</div>}
          {actionError && <div className="error-message action-error" role="alert"><strong>改编流程暂未完成</strong><p>{actionError}</p></div>}

          <div className="selected-mechanism-panel">
            <div><span className="detail-label">SELECTED CULTURE MECHANISM</span><h3>{selectedMechanism.name}<code>{selectedMechanism.id}</code></h3><p>{selectedMechanism.description}</p>{selectedMechanism.adapted_to && <p className="adapted-to">已改编为：<strong>{selectedMechanism.adapted_to}</strong></p>}</div>
            <div className="selected-mechanism-functions"><FunctionGroup label="剧情" values={selectedMechanism.functions.plot} /><FunctionGroup label="社会" values={selectedMechanism.functions.social} /><FunctionGroup label="情绪" values={selectedMechanism.functions.emotional} /></div>
            <button className="primary-action compact-action" disabled={actionBusy} onClick={handlePlan} type="button"><span>{plan ? '读取当前版本 Adaptation Plan' : '生成 Adaptation Plan'}</span><span>→</span></button>
          </div>

          {plan && <section className="workbench-section"><div className="subsection-heading"><span>04</span><div><p className="eyebrow">A / B / C OPTIONS</p><h3>选择改编方案</h3></div><p>方案直接来自 Adaptation Plan API</p></div><PlanOptions disabled={actionBusy} onSelect={handleSelectOption} plan={plan} selectedLabel={selectedOptionLabel} /></section>}

          {selectedOption && propagation && graph && <>
            <section className="workbench-section"><div className="subsection-heading"><span>05</span><div><p className="eyebrow">DEPENDENCY PROPAGATION</p><h3>影响范围与原因</h3></div><p>选定 {selectedOption.option_label} · {selectedOption.title}</p></div><ImpactPanel propagation={propagation} /></section>
            <section className="workbench-section graph-section"><div className="subsection-heading"><span>06</span><div><p className="eyebrow">STORY GRAPH</p><h3>聚焦依赖图谱</h3></div><p>高亮当前机制及传播路径节点</p></div><StoryGraphView affectedIds={affectedIds} focusId={selectedMechanism.id} graph={graph} /></section>
            <section className="apply-gate"><div><span className="detail-label">READY TO APPLY</span><h3>确认以方案 {selectedOption.option_label} 改写 {propagation.affected_scenes.length} 个场景</h3><p>Apply job 会依次执行 Rewrite → Verify → 必要时自动 Repair。</p></div><button className="primary-action compact-action" disabled={actionBusy} onClick={handleApply} type="button"><span>{action === 'applying' ? '改写进行中…' : '开始完整改编'}</span><span>→</span></button></section>
          </>}

          {lastApply && storyState && verifyReport && <div className="post-apply-results">
            <section className="workbench-section"><div className="subsection-heading"><span>07</span><div><p className="eyebrow">REWRITE RESULT</p><h3>改写后的场景</h3></div><p>{lastApply.result.applied.rewritten_scene_ids.length} 个场景已更新</p></div><div className="rewrite-list">{lastApply.result.applied.rewritten_scene_ids.map((sceneId) => { const scene = storyState.scenes.find((item) => item.id === sceneId); return scene ? <article key={scene.id}><header><code>{scene.id}</code><div><h4>{scene.title}</h4><p>{scene.summary}</p></div></header><p>{scene.text}</p></article> : null })}</div></section>
            <section className="workbench-section"><div className="subsection-heading"><span>08</span><div><p className="eyebrow">BEFORE / AFTER</p><h3>场景 Diff</h3></div><p>相对于 initial_parse 基线</p></div><DiffPanel diffs={diffs} /></section>
            <section className="workbench-section"><div className="subsection-heading"><span>09</span><div><p className="eyebrow">VERIFY / REPAIR</p><h3>一致性验证结果</h3></div><p>Apply job 内置自动验证与修复</p></div><VerificationPanel applyResult={lastApply.result} disabled={actionBusy} onVerify={handleVerify} report={verifyReport} /></section>
            <section className="workbench-section"><div className="subsection-heading"><span>10</span><div><p className="eyebrow">REVISION HISTORY</p><h3>改编修订记录</h3></div><p>{revisions.length} 个已保存版本</p></div><RevisionTimeline revisions={revisions} /></section>
            <section className="workbench-section" id="final-script"><div className="subsection-heading"><span>11</span><div><p className="eyebrow">FINAL SCRIPT</p><h3>完整演示产物</h3></div><p>由最新 Story State 场景顺序组装</p></div><CompleteScript state={storyState} /></section>
            <section className="workbench-section"><div className="subsection-heading"><span>12</span><div><p className="eyebrow">TARGET-LANGUAGE ARTIFACT</p><h3>目标语言交付稿</h3></div><button className="secondary-action" disabled={actionBusy} onClick={handleRenderTarget} type="button">{targetScript ? '读取当前版本语言稿' : `生成 ${storyState.target_language} 剧本`}</button></div>{targetScript ? <TargetLanguageScript script={targetScript} /> : <div className="inline-empty">结构改编稿已冻结；点击生成与当前状态版本绑定的目标语言剧本。</div>}</section>
          </div>}
        </section>}
      </main>

      <footer><span>StoryBridge · Full Demo Loop</span><span>Analyze → Plan → Propagate → Graph → Apply → Diff → Verify / Repair</span></footer>
    </div>
  )
}

export default App
