import type { Scene, StoryState, VerifyReport } from '../types/api'

export function VerificationReview({ report, choices, note, scenes, baseline, disabled, onNoteChange, onDecide, onRepair, onContinue, onVerify }: {
  report: VerifyReport
  choices: Record<string, 'modify' | 'keep'>
  note: { text: string; sceneId: string }
  scenes: Scene[]
  baseline?: StoryState['repair_baseline']
  onNoteChange: (note: { text: string; sceneId: string }) => void
  disabled: boolean
  onDecide: (key: string, choice: 'modify' | 'keep') => void
  onRepair: () => void
  onContinue: () => void
  onVerify: () => void
}) {
  const hasErrors = report.issues.some((item, index) => item.severity === 'error' && choices[`issue:${index}`] !== 'keep')
    || report.commitment_checks.some(item => item.status === 'violated' && choices[`commitment:${item.commitment_id}`] !== 'keep')
  const hasSelected = Object.values(choices).includes('modify')
  function decision(key: string, defaultModify = false) {
    const selected = choices[key] || (defaultModify ? 'modify' : undefined)
    return <div className="review-choice" role="group" aria-label="确认是否需要修改">
      <button type="button" disabled={disabled} aria-pressed={selected === 'modify'} onClick={() => onDecide(key, 'modify')}>需要修改</button>
      <button type="button" disabled={disabled} aria-pressed={selected === 'keep'} onClick={() => onDecide(key, 'keep')}>无需修改</button>
      <span>{selected === 'modify' ? '已加入修复范围' : selected === 'keep' ? '已确认保留' : '待你确认'}</span>
    </div>
  }
  return <>
    <p>已检查 {report.scenes_checked} / {report.scenes_total} 个场景，确认 {report.commitments_verified} / {report.commitments_total} 个伏笔与承诺。</p>
    <p className="muted">每项都可以确认是否修改，包括模型标记的错误。“无需修改”会记录为人工确认；修复只处理仍需修改的项目。</p>
    {baseline && <details><summary>本轮修复采用的全篇事实</summary>
      <p className="muted">修复和检查共用这些事实。如果理解有误，请在下方建议框写明正确的时间线、人物和变化前后状态。</p>
      <ul>{baseline.facts?.map((fact, index) => <li key={index}>{fact.timeline} · {fact.subject} · {fact.attribute} · {fact.phase}：{fact.value}<p className="muted">依据：{fact.basis}</p></li>)}</ul>
      <ul>{baseline.rules?.map((rule, index) => <li key={index}>{rule}</li>)}</ul>
    </details>}
    {!report.issues.length && report.overall_status === 'pass' && <p>未发现未解决的一致性问题。</p>}
    <ul className="verification-items">
      {report.issues.map((issue, index) => <li key={`issue:${index}`}>
        <p><strong>{issue.severity === 'error' ? '需要解决：' : '待确认是否修改：'}</strong>{issue.description}</p>
        {decision(`issue:${index}`, issue.severity === 'error')}
      </li>)}
      {report.commitment_checks.filter(item => item.status !== 'preserved').map(item => <li key={`commitment:${item.commitment_id}`}>
        <p><strong>{item.status === 'violated' ? '需要解决：' : '待确认是否修改：'}</strong>{item.explanation || '有故事承诺需要复核。'}</p>
        {decision(`commitment:${item.commitment_id}`, item.status === 'violated')}
      </li>)}
    </ul>
    <div className="review-suggestion">
      <label><span>补充问题或改进建议</span><textarea rows={4} maxLength={4000} disabled={disabled} value={note.text} onChange={event => onNoteChange({ ...note, text: event.target.value })} placeholder="例如：结尾反转太突然，请补充前面的铺垫；女主这段台词可以更坚定。也可以指出检查器漏掉的矛盾。" /></label>
      <label><span>建议适用范围</span><select disabled={disabled} value={note.sceneId} onChange={event => onNoteChange({ ...note, sceneId: event.target.value })}><option value="">整篇故事</option>{scenes.map((scene, index) => <option key={scene.id} value={scene.id}>第 {index + 1} 场 · {scene.title || scene.summary.slice(0, 30)}</option>)}</select></label>
      <p className="muted">{note.sceneId ? '建议用于所选场景；明确错误和已确认的问题仍会一起修复。' : '选择整篇故事时，会先统一事实，再修改相关场景。'} 修改后会重新检查并生成目标语言剧本。{note.text.length} / 4000</p>
    </div>
    <div className="actions">
      {(hasErrors || hasSelected || note.text.trim()) && <button className="primary" type="button" disabled={disabled} onClick={onRepair}>{note.text.trim() ? '按问题和建议修改' : '修复错误及已确认项目'}</button>}
      {!hasErrors && !hasSelected && !note.text.trim() && Object.values(choices).includes('keep') && <button className="primary" type="button" disabled={disabled} onClick={onContinue}>确认保留并继续</button>}
      <button type="button" disabled={disabled} onClick={onVerify}>重新检查</button>
    </div>
  </>
}
