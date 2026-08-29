import type { CSSProperties } from 'react'
import type {
  Revision,
  SceneDiff,
  StoryState,
  TargetScript,
  VerifyReport,
} from '../types/api'

export function DiffPanel({ diffs }: { diffs: SceneDiff[] }) {
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

export function VerificationPanel({ report, applyResult, disabled, onVerify }: {
  report: VerifyReport
  applyResult: { repair_rounds: number; repaired_scene_ids: string[] }
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

export function RevisionTimeline({ revisions }: { revisions: Revision[] }) {
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

export function CompleteScript({ state }: { state: StoryState }) {
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

export function TargetLanguageScript({ script }: { script: TargetScript }) {
  return (
    <div className="complete-script target-script">
      <header>
        <div><span className="detail-label">VERSIONED TARGET ARTIFACT</span><h3>{script.target_language} 完整剧本</h3></div>
        <div><strong>v{script.source_state_version}</strong><span>{script.target_locale || script.target_language}</span></div>
      </header>
      <div className="script-scenes">
        {script.scenes.map((scene) => (
          <article key={scene.id}>
            <header><code>{scene.id}</code><div><h4>{scene.title || scene.id}</h4><p>{scene.summary}</p></div></header>
            <p className="script-scene__text">{scene.text}</p>
          </article>
        ))}
      </div>
    </div>
  )
}
