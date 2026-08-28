import type {
  AdaptationOption,
  AdaptationPlan,
  ImpactKind,
  PropagationResult,
} from '../types/api'

const strategyLabels: Record<AdaptationOption['strategy'], string> = {
  preserve: '保留并解释',
  functional_replacement: '功能性替换',
  plot_reconstruction: '情节重构',
}

const impactLabels: Record<ImpactKind, string> = {
  direct_reference: '直接引用', motivation: '人物动机', causal: '因果链',
  payoff: '伏笔回收', structural: '结构影响',
}

export function PlanOptions({ plan, selectedLabel, disabled, onSelect }: {
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

export function ImpactPanel({ propagation }: { propagation: PropagationResult }) {
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
