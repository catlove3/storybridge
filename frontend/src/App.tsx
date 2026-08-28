import { useEffect, useMemo, useRef, useState } from 'react'
import type { CSSProperties, FormEvent, KeyboardEvent } from 'react'
import { api, ApiError } from './api/client'
import { pollJob } from './api/pollJob'
import { StoryGraphView } from './components/StoryGraphView'
import type {
  AdaptationOption,
  AdaptationPlan,
  ApplyResult,
  CultureMechanism,
  EmotionalFunction,
  ImpactKind,
  Job,
  Level,
  PlotFunction,
  PropagationResult,
  Revision,
  SceneDiff,
  SocialFunction,
  StoryGraphResponse,
  StoryState,
  VerifyReport,
} from './types/api'
import './App.css'

type AnalyzePhase = 'idle' | 'creating' | 'analyzing' | 'loading-state' | 'done' | 'error'
type AdaptationAction = 'idle' | 'planning' | 'loading-impact' | 'applying' | 'verifying'
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

const impactLabels: Record<ImpactKind, string> = {
  direct_reference: '直接引用', motivation: '人物动机', causal: '因果链',
  payoff: '伏笔回收', structural: '结构影响',
}

const strategyLabels: Record<AdaptationOption['strategy'], string> = {
  preserve: '保留并解释',
  functional_replacement: '功能性替换',
  plot_reconstruction: '情节重构',
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

function PlanOptions({ plan, selectedLabel, disabled, onSelect }: {
  plan: AdaptationPlan
  selectedLabel: string | null
  disabled: boolean
  onSelect: (label: string) => void
}) {
  return (
    <div className="option-grid">
      {plan.options.map((option) => {
        const selected = option.option_label === selectedLabel
        return (
          <article className={`option-card${selected ? ' is-selected' : ''}`} key={option.option_label}>
            <header><span className="option-card__label">{option.option_label}</span><span className="option-card__strategy">{strategyLabels[option.strategy]}</span></header>
            <h4>{option.title}</h4>
            <p className="option-card__definition">{option.replacement_definition}</p>
            <p>{option.rationale}</p>
            <div className="option-card__facts">
              <div><span>保留功能</span><p>{option.preserved_functions.join(' · ') || '未列出'}</p></div>
              <div><span>潜在风险</span><p>{option.risks.join(' · ') || '无显著风险'}</p></div>
            </div>
            <button className="option-card__select" disabled={disabled} onClick={() => onSelect(option.option_label)} type="button">
              {selected ? '已选择此方案' : `选择方案 ${option.option_label}`}
            </button>
          </article>
        )
      })}
    </div>
  )
}

function ImpactPanel({ propagation }: { propagation: PropagationResult }) {
  return (
    <div className="impact-panel">
      <div className="impact-summary">
        <strong>{propagation.affected_scenes.length}</strong><span>个场景需要联动改写</span>
        <p>{propagation.summary}</p>
      </div>
      <div className="affected-scenes">
        {propagation.affected_scenes.map((affected) => (
          <article key={affected.scene_id}>
            <header><strong>{affected.scene_id}</strong><div>{affected.impact_kinds.map((kind) => <span key={kind}>{impactLabels[kind]}</span>)}</div></header>
            <p>{affected.evidence || '由 Story Graph 依赖路径判定为受影响场景。'}</p>
            <code>{affected.reason_path.join(' → ')}</code>
          </article>
        ))}
      </div>
      {propagation.related_commitment_ids.length > 0 && <p className="related-commitments">必须复核的叙事承诺：{propagation.related_commitment_ids.join(' · ')}</p>}
    </div>
  )
}

function DiffPanel({ diffs }: { diffs: SceneDiff[] }) {
  if (diffs.length === 0) return <div className="inline-empty">Diff 接口未返回发生变化的场景。</div>
  return (
    <div className="diff-list">
      {diffs.map((item) => (
        <article className="diff-card" key={item.scene_id}>
          <header><strong>{item.scene_id}</strong><span>{item.diff.filter((line) => line.startsWith('+') && !line.startsWith('+++')).length} 行新增</span></header>
          <div className="before-after">
            <div><span>BEFORE</span><p>{item.before}</p></div>
            <div><span>AFTER</span><p>{item.after}</p></div>
          </div>
        </article>
      ))}
    </div>
  )
}

function VerificationPanel({ report, applyResult, disabled, onVerify }: {
  report: VerifyReport
  applyResult: ApplyResult
  disabled: boolean
  onVerify: () => void
}) {
  const score = Math.round(report.consistency_score * 100)
  const scoreStyle = { '--score': `${score}%` } as CSSProperties
  const errors = report.issues.filter((issue) => issue.severity === 'error').length
  const warnings = report.issues.filter((issue) => issue.severity === 'warning').length
  const statusCopy = {
    not_run: '尚未运行验证',
    pass: '验证通过',
    needs_review: '需要人工复核',
    fail: '存在阻塞问题',
  }[report.overall_status]
  return (
    <div className="verification-panel">
      <div className={`score-card score-card--${report.overall_status}`}>
        <div className="score-ring" style={scoreStyle}><strong>{score}</strong><span>/ 100</span></div>
        <div>
          <span className="detail-label">Overall Status · {report.overall_status.toUpperCase()}</span>
          <h4>{statusCopy}</h4>
          <p>自动修复 {applyResult.repair_rounds} 轮{applyResult.repaired_scene_ids.length > 0 ? `，涉及 ${applyResult.repaired_scene_ids.join('、')}` : '，无需额外修复'}</p>
          <div className="verification-coverage">
            <span>静态检查 <strong>{report.static_checks_passed}/{report.static_checks_total}</strong></span>
            <span>承诺已验证 <strong>{report.commitments_verified}/{report.commitments_total}</strong></span>
            <span>场景覆盖 <strong>{report.scenes_checked}/{report.scenes_total}</strong></span>
            <span>语义问题 <strong>{errors} error · {warnings} warning</strong></span>
          </div>
        </div>
        <button className="secondary-action" disabled={disabled} onClick={onVerify} type="button">{disabled ? '验证中…' : '重新验证最新状态'}</button>
      </div>

      <div className="verification-columns">
        <div>
          <h4>Commitment Checks</h4>
          {report.commitment_checks.length > 0 ? (
            <div className="check-list">
              {report.commitment_checks.map((check) => (
                <article className={`check-item check-item--${check.status}`} key={check.commitment_id}>
                  <header><strong>{check.commitment_id}</strong><span>{check.status}</span></header>
                  <p>{check.explanation || '后端未提供额外说明。'}</p>
                </article>
              ))}
            </div>
          ) : <div className="inline-empty">没有需要检查的叙事承诺。</div>}
        </div>
        <div>
          <h4>Verification Issues</h4>
          {report.issues.length > 0 ? (
            <div className="issue-list">
              {report.issues.map((issue, index) => (
                <article className={`issue-item issue-item--${issue.severity}`} key={`${issue.issue_type}-${issue.scene_id}-${index}`}>
                  <header><strong>{issue.issue_type}</strong><span>{issue.severity}</span></header>
                  <p>{issue.description}</p>{issue.scene_id && <code>{issue.scene_id}</code>}
                </article>
              ))}
            </div>
          ) : <div className="inline-empty inline-empty--success">没有未解决的一致性问题。</div>}
        </div>
      </div>
    </div>
  )
}

function RevisionTimeline({ revisions }: { revisions: Revision[] }) {
  return (
    <ol className="revision-timeline">
      {revisions.map((revision) => (
        <li key={revision.revision_id}>
          <span>rev{String(revision.revision_id).padStart(3, '0')}</span>
          <div><strong>{revision.kind}</strong><p>{revision.description || '无修订说明'}</p>{revision.changed_scene_ids.length > 0 && <small>{revision.changed_scene_ids.join(' · ')}</small>}</div>
        </li>
      ))}
    </ol>
  )
}

function CompleteScript({ state }: { state: StoryState }) {
  return (
    <div className="complete-script">
      <header>
        <div><span className="detail-label">LATEST STORY STATE</span><h3>完整改编后剧本</h3></div>
        <div><strong>{state.scenes.length}</strong><span>个场景</span></div>
      </header>
      <div className="complete-script__adaptations">
        {state.culture_mechanisms.filter((mechanism) => mechanism.adapted_to).map((mechanism) => <span key={mechanism.id}>{mechanism.name} → {mechanism.adapted_to}</span>)}
      </div>
      <div className="script-scenes">
        {state.scenes.map((scene) => (
          <article key={scene.id}>
            <header><code>{scene.id}</code><div><h4>{scene.title || scene.id}</h4><p>{scene.summary}</p></div></header>
            <p className="script-scene__text">{scene.text}</p>
          </article>
        ))}
      </div>
    </div>
  )
}

function App() {
  const [name, setName] = useState('跨文化分析 Demo')
  const [script, setScript] = useState('')
  const [market, setMarket] = useState('United States')
  const [audience, setAudience] = useState('18–30')
  const [format, setFormat] = useState('Short drama')
  const [genre, setGenre] = useState('Urban drama')
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

  useEffect(() => () => controllerRef.current?.abort(), [])

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
        market: { market: market.trim(), audience: audience.trim(), format: format.trim(), genre: genre.trim() },
      }, controller.signal)
      setProject(created)
      setPhase('analyzing')
      const submitted = await api.submitJob(created.id, { kind: 'analyze' }, controller.signal)
      await pollJob(submitted.job_id, { signal: controller.signal, timeoutMs: 15 * 60_000, onUpdate: setAnalyzeJob })
      setPhase('loading-state')
      const state = await api.getStoryState(created.id, controller.signal)
      setStoryState(state)
      setSelectedMechanismId(sortMechanisms(state.culture_mechanisms)[0]?.id ?? null)
      setRevisions(await api.getRevisions(created.id, controller.signal))
      setPhase('done')
    } catch (caught) {
      const message = readableError(caught)
      if (!message) return
      setError(message)
      setPhase('error')
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
      const submitted = await api.submitJob(project.id, { kind: 'plan', culture_mechanism_id: selectedMechanism.id }, controller.signal)
      const completed = await pollJob<AdaptationPlan>(submitted.job_id, { signal: controller.signal, timeoutMs: 15 * 60_000, onUpdate: setActiveJob })
      if (!completed.result) throw new Error('Plan job 已完成，但没有返回 Adaptation Plan。')
      setPlan(completed.result)
      setActionMessage(`已为 ${selectedMechanism.name} 生成 ${completed.result.options.length} 个真实方案。`)
    } catch (caught) {
      const message = readableError(caught)
      if (message) setActionError(message)
    } finally {
      setAction('idle')
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
    }
  }

  async function handleApply() {
    if (!project || !selectedMechanism || !selectedOption || !propagation || actionBusy) return
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
      }, controller.signal)
      const completed = await pollJob<ApplyResult>(submitted.job_id, { signal: controller.signal, timeoutMs: 30 * 60_000, onUpdate: setActiveJob })
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
      setActionMessage(`Apply 完成：改写 ${completed.result.applied.rewritten_scene_ids.length} 个场景，自动修复 ${completed.result.repair_rounds} 轮。`)
    } catch (caught) {
      const message = readableError(caught)
      if (message) setActionError(message)
    } finally {
      setAction('idle')
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
      const submitted = await api.submitJob(project.id, { kind: 'verify' }, controller.signal)
      const completed = await pollJob<VerifyReport>(submitted.job_id, { signal: controller.signal, timeoutMs: 15 * 60_000, onUpdate: setActiveJob })
      if (!completed.result) throw new Error('Verify job 已完成，但没有返回 Verify Report。')
      setVerifyReport(completed.result)
      setActionMessage('最新 Story State 已重新验证。')
    } catch (caught) {
      const message = readableError(caught)
      if (message) setActionError(message)
    } finally {
      setAction('idle')
    }
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
            </div></fieldset>
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
            <div className={`status-line status-line--${phase}`} aria-live="polite"><span className="status-line__pulse" /><div><strong>{phaseCopy[phase]}</strong>{project && <small>Project {project.id}</small>}{analyzeJob && <small>Job {analyzeJob.id} · {analyzeJob.status}</small>}</div></div>
            {error && <div className="error-message" role="alert"><strong>没有得到 Story State</strong><p>{error}</p><span>请确认 FastAPI 已在 localhost:8000 启动，并查看后端日志。</span></div>}
            {!storyState && !error && <div className="empty-state"><div className="empty-state__orb"><span>故事</span><i /><span>文化</span></div><h3>{analyzeBusy ? 'Agent 正在搭建故事的结构地图' : '分析结果将在这里展开'}</h3><p>完成后可点击真实 Culture Friction，继续生成方案、传播分析、改写和验证。</p></div>}
            {storyState && <div className="results">
              <div className="result-summary"><div><strong>{storyState.scenes.length}</strong><span>场景</span></div><div><strong>{storyState.characters.length}</strong><span>角色</span></div><div><strong>{storyState.culture_mechanisms.length}</strong><span>文化机制</span></div><div><strong>{storyState.dependencies.length}</strong><span>依赖关系</span></div></div>
              <div className="result-context"><span>目标市场</span><strong>{storyState.target_market || market}</strong>{(storyState.audience || audience) && <small>{storyState.audience || audience}</small>}</div>
              {sortedMechanisms.length > 0 ? <div className="friction-list">{sortedMechanisms.map((mechanism, index) => <FrictionCard disabled={actionBusy} key={mechanism.id} mechanism={mechanism} onSelect={() => handleSelectMechanism(mechanism.id)} order={index} selected={selectedMechanismId === mechanism.id} />)}</div> : <div className="no-frictions">当前 Story State 没有保留下来的文化摩擦点。</div>}
            </div>}
          </div>
        </section>

        {storyState && selectedMechanism && <section className="adaptation-workbench" id="adapt" aria-label="改编工作台">
          <div className="workbench-heading"><div className="section-heading"><span>03</span><div><p className="eyebrow">ADAPTATION WORKBENCH</p><h2>从文化机制到完整改编</h2></div></div><p>当前对象 <strong>{selectedMechanism.id} · {selectedMechanism.name}</strong></p></div>
          <ol className="adaptation-pipeline" aria-label="改编进度">{['选择机制', '生成方案', '传播与图谱', '改写场景', '验证完成'].map((label, index) => <li className={adaptationStep > index ? 'is-complete' : adaptationStep === index ? 'is-active' : ''} key={label}><span>{adaptationStep > index ? '✓' : index + 1}</span><strong>{label}</strong></li>)}</ol>
          {(action !== 'idle' || actionMessage || activeJob) && <div className={`action-status${action !== 'idle' ? ' is-running' : ''}`} aria-live="polite"><span className="status-line__pulse" /><div><strong>{action !== 'idle' ? actionCopy[action] : actionMessage}</strong>{activeJob && <small>Job {activeJob.id} · {activeJob.kind} · {activeJob.status}</small>}</div></div>}
          {actionError && <div className="error-message action-error" role="alert"><strong>改编流程暂未完成</strong><p>{actionError}</p></div>}

          <div className="selected-mechanism-panel">
            <div><span className="detail-label">SELECTED CULTURE MECHANISM</span><h3>{selectedMechanism.name}<code>{selectedMechanism.id}</code></h3><p>{selectedMechanism.description}</p>{selectedMechanism.adapted_to && <p className="adapted-to">已改编为：<strong>{selectedMechanism.adapted_to}</strong></p>}</div>
            <div className="selected-mechanism-functions"><FunctionGroup label="剧情" values={selectedMechanism.functions.plot} /><FunctionGroup label="社会" values={selectedMechanism.functions.social} /><FunctionGroup label="情绪" values={selectedMechanism.functions.emotional} /></div>
            <button className="primary-action compact-action" disabled={actionBusy} onClick={handlePlan} type="button"><span>{plan ? '重新生成 Adaptation Plan' : '生成 Adaptation Plan'}</span><span>→</span></button>
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
          </div>}
        </section>}
      </main>

      <footer><span>StoryBridge · Full Demo Loop</span><span>Analyze → Plan → Propagate → Graph → Apply → Diff → Verify / Repair</span></footer>
    </div>
  )
}

export default App
