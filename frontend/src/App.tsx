import { useEffect, useMemo, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import { api, ApiError } from './api/client'
import { pollJob } from './api/pollJob'
import type {
  CultureMechanism,
  EmotionalFunction,
  Job,
  Level,
  PlotFunction,
  SocialFunction,
  StoryState,
} from './types/api'
import './App.css'

type Phase = 'idle' | 'creating' | 'analyzing' | 'loading-state' | 'done' | 'error'
type NarrativeFunction = PlotFunction | SocialFunction | EmotionalFunction

const levelMeta: Record<Level, { label: string; description: string }> = {
  high: { label: '高摩擦', description: '需要重点本土化' },
  medium: { label: '中摩擦', description: '需要语境解释' },
  low: { label: '低摩擦', description: '可直接保留' },
}

const functionLabels: Record<NarrativeFunction, string> = {
  motivation: '人物动机',
  constraint: '情节约束',
  conflict: '冲突来源',
  revelation: '信息揭示',
  foreshadowing: '伏笔铺设',
  payoff: '承诺回收',
  reversal: '剧情反转',
  status: '社会地位',
  power: '权力关系',
  obligation: '社会义务',
  kinship: '亲缘关系',
  reputation: '声誉压力',
  institutional_access: '制度准入',
  economic_security: '经济安全',
  humiliation: '羞辱感',
  aspiration: '向往感',
  fear: '恐惧感',
  sympathy: '共情',
  suspense: '悬念',
  satisfaction: '满足感',
}

const phaseCopy: Record<Phase, string> = {
  idle: '等待输入剧本',
  creating: '正在创建项目…',
  analyzing: 'Agent 正在解析故事与识别文化摩擦…',
  'loading-state': '分析完成，正在读取 Story State…',
  done: '分析完成',
  error: '流程中断',
}

const phaseIndex: Record<Phase, number> = {
  idle: 0,
  creating: 1,
  analyzing: 2,
  'loading-state': 3,
  done: 4,
  error: 0,
}

function FunctionGroup({
  label,
  values,
}: {
  label: string
  values: NarrativeFunction[]
}) {
  return (
    <div className="function-group">
      <span className="function-group__label">{label}</span>
      <div className="function-group__tags">
        {values.length > 0 ? (
          values.map((value) => <span key={value}>{functionLabels[value]}</span>)
        ) : (
          <span className="function-tag--empty">未标注</span>
        )}
      </div>
    </div>
  )
}

function FrictionCard({ mechanism, order }: { mechanism: CultureMechanism; order: number }) {
  const meta = levelMeta[mechanism.friction_level]

  return (
    <article className={`friction-card friction-card--${mechanism.friction_level}`}>
      <header className="friction-card__header">
        <div className="friction-card__identity">
          <span className="friction-card__order">{String(order + 1).padStart(2, '0')}</span>
          <div>
            <div className="friction-card__title-line">
              <h3>{mechanism.name}</h3>
              <code>{mechanism.id}</code>
            </div>
            <p>{mechanism.description || '后端未提供机制说明'}</p>
          </div>
        </div>
        <div className={`level-badge level-badge--${mechanism.friction_level}`}>
          <strong>{meta.label}</strong>
          <span>{meta.description}</span>
        </div>
      </header>

      <div className="friction-card__evidence">
        <div>
          <span className="detail-label">原文证据</span>
          <div className="quote-list">
            {mechanism.surface_text.length > 0 ? (
              mechanism.surface_text.map((quote, index) => (
                <q key={`${quote}-${index}`}>{quote}</q>
              ))
            ) : (
              <span className="muted">无直接文本证据</span>
            )}
          </div>
        </div>
        <div>
          <span className="detail-label">出现位置</span>
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
  const [phase, setPhase] = useState<Phase>('idle')
  const [project, setProject] = useState<{ id: string; name: string } | null>(null)
  const [job, setJob] = useState<Job | null>(null)
  const [storyState, setStoryState] = useState<StoryState | null>(null)
  const [error, setError] = useState('')
  const controllerRef = useRef<AbortController | null>(null)

  const sortedMechanisms = useMemo(() => {
    const rank: Record<Level, number> = { high: 3, medium: 2, low: 1 }
    return [...(storyState?.culture_mechanisms ?? [])].sort(
      (left, right) => rank[right.friction_level] - rank[left.friction_level],
    )
  }, [storyState])

  useEffect(() => () => controllerRef.current?.abort(), [])

  const isBusy = phase === 'creating' || phase === 'analyzing' || phase === 'loading-state'
  const currentPhaseIndex = phaseIndex[phase]

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!script.trim() || isBusy) return

    controllerRef.current?.abort()
    const controller = new AbortController()
    controllerRef.current = controller
    setError('')
    setStoryState(null)
    setProject(null)
    setJob(null)

    try {
      setPhase('creating')
      const created = await api.createProject(
        {
          name: name.trim(),
          script: script.trim(),
          market: {
            market: market.trim(),
            audience: audience.trim(),
            format: format.trim(),
            genre: genre.trim(),
          },
        },
        controller.signal,
      )
      setProject(created)

      setPhase('analyzing')
      const submitted = await api.submitJob(created.id, { kind: 'analyze' }, controller.signal)
      await pollJob(submitted.job_id, {
        signal: controller.signal,
        onUpdate: setJob,
      })

      setPhase('loading-state')
      const state = await api.getStoryState(created.id, controller.signal)
      setStoryState(state)
      setPhase('done')
    } catch (caught) {
      if (caught instanceof DOMException && caught.name === 'AbortError') return
      const message =
        caught instanceof ApiError
          ? `后端返回 ${caught.status}：${caught.message}`
          : caught instanceof Error
            ? caught.message
            : '发生未知错误。'
      setError(message)
      setPhase('error')
    }
  }

  return (
    <div className="app-shell">
      <header className="topbar">
        <a className="brand" href="#top" aria-label="StoryBridge 首页">
          <span className="brand__mark">SB</span>
          <span>
            <strong>StoryBridge</strong>
            <small>跨文化故事改编智能体</small>
          </span>
        </a>
        <div className="connection-note">
          <span className="connection-note__dot" />
          数据来自当前后端 /api
        </div>
      </header>

      <main id="top">
        <section className="hero-copy">
          <div>
            <p className="eyebrow">STORY → STATE → CULTURAL INSIGHT</p>
            <h1>
              先理解故事的作用，
              <br />
              再跨越文化的边界。
            </h1>
          </div>
          <p className="hero-copy__intro">
            输入中文剧本，StoryBridge 会构建 Story State，识别目标市场中的文化摩擦点，
            并显式标注它们承担的剧情、社会与情绪功能。
          </p>
        </section>

        <section className="workspace" aria-label="剧本分析工作区">
          <form className="script-form" onSubmit={handleSubmit}>
            <div className="section-heading">
              <span>01</span>
              <div>
                <p className="eyebrow">SOURCE SCRIPT</p>
                <h2>输入剧本</h2>
              </div>
            </div>

            <label>
              <span>项目名称</span>
              <input value={name} onChange={(event) => setName(event.target.value)} />
            </label>

            <label className="script-field">
              <span>中文剧本</span>
              <textarea
                value={script}
                onChange={(event) => setScript(event.target.value)}
                placeholder="粘贴完整剧本或试演片段。前端不会填入隐藏的 mock 结果。"
                rows={15}
                required
              />
              <small>{script.length.toLocaleString('zh-CN')} 字符</small>
            </label>

            <fieldset>
              <legend>目标市场画像</legend>
              <div className="field-grid">
                <label>
                  <span>市场</span>
                  <input value={market} onChange={(event) => setMarket(event.target.value)} />
                </label>
                <label>
                  <span>受众</span>
                  <input value={audience} onChange={(event) => setAudience(event.target.value)} />
                </label>
                <label>
                  <span>形式</span>
                  <input value={format} onChange={(event) => setFormat(event.target.value)} />
                </label>
                <label>
                  <span>类型</span>
                  <input value={genre} onChange={(event) => setGenre(event.target.value)} />
                </label>
              </div>
            </fieldset>

            <button className="primary-action" type="submit" disabled={!script.trim() || isBusy}>
              <span>{isBusy ? '分析进行中' : '创建项目并分析'}</span>
              <span aria-hidden="true">→</span>
            </button>

            <p className="mock-disclosure">
              页面不内置分析结果。若后端以 mock 模式启动，LLM 解析与摩擦识别使用仓库 fixtures；
              项目创建、HTTP 请求、job 轮询和 Story State 获取仍走真实接口。
            </p>
          </form>

          <div className="analysis-panel">
            <div className="section-heading">
              <span>02</span>
              <div>
                <p className="eyebrow">FRICTION MAP</p>
                <h2>文化摩擦图谱</h2>
              </div>
            </div>

            <ol className="pipeline" aria-label="分析进度" aria-live="polite">
              {['创建项目', 'Analyze job', '读取 Story State'].map((label, index) => {
                const step = index + 1
                const isComplete = currentPhaseIndex > step
                const isActive = currentPhaseIndex === step
                return (
                  <li
                    className={isComplete ? 'is-complete' : isActive ? 'is-active' : ''}
                    key={label}
                  >
                    <span>{isComplete ? '✓' : step}</span>
                    {label}
                  </li>
                )
              })}
            </ol>

            <div className={`status-line status-line--${phase}`} aria-live="polite">
              <span className="status-line__pulse" />
              <div>
                <strong>{phaseCopy[phase]}</strong>
                {project && <small>Project {project.id}</small>}
                {job && <small>Job {job.id} · {job.status}</small>}
              </div>
            </div>

            {error && (
              <div className="error-message" role="alert">
                <strong>没有得到 Story State</strong>
                <p>{error}</p>
                <span>请确认 FastAPI 已在 localhost:8000 启动，并查看后端日志。</span>
              </div>
            )}

            {!storyState && !error && (
              <div className="empty-state">
                <div className="empty-state__orb">
                  <span>故事</span>
                  <i />
                  <span>文化</span>
                </div>
                <h3>{isBusy ? 'Agent 正在搭建故事的结构地图' : '分析结果将在这里展开'}</h3>
                <p>
                  完成后将展示真实 Story State 中的 Culture Frictions 与 Narrative Functions。
                </p>
              </div>
            )}

            {storyState && (
              <div className="results">
                <div className="result-summary">
                  <div>
                    <strong>{storyState.scenes.length}</strong>
                    <span>场景</span>
                  </div>
                  <div>
                    <strong>{storyState.characters.length}</strong>
                    <span>角色</span>
                  </div>
                  <div>
                    <strong>{storyState.culture_mechanisms.length}</strong>
                    <span>文化机制</span>
                  </div>
                  <div>
                    <strong>{storyState.dependencies.length}</strong>
                    <span>依赖关系</span>
                  </div>
                </div>

                <div className="result-context">
                  <span>目标市场</span>
                  <strong>{storyState.target_market || market}</strong>
                  {(storyState.audience || audience) && (
                    <small>{storyState.audience || audience}</small>
                  )}
                </div>

                {sortedMechanisms.length > 0 ? (
                  <div className="friction-list">
                    {sortedMechanisms.map((mechanism, index) => (
                      <FrictionCard key={mechanism.id} mechanism={mechanism} order={index} />
                    ))}
                  </div>
                ) : (
                  <div className="no-frictions">当前 Story State 没有保留下来的文化摩擦点。</div>
                )}
              </div>
            )}
          </div>
        </section>
      </main>

      <footer>
        <span>StoryBridge · Phase 1 Demo</span>
        <span>当前范围：Analyze → Story State → Friction Map</span>
      </footer>
    </div>
  )
}

export default App
