import { useEffect, useRef, useState } from 'react'
import type { ReactNode } from 'react'
import { api } from '../api/client'
import type { components } from '../api/generated/schema'

export function Modal({ title, onClose, children }: { title: string; onClose: () => void; children: ReactNode }) {
  const ref = useRef<HTMLDialogElement>(null)
  useEffect(() => { ref.current?.showModal() }, [])
  return <dialog ref={ref} aria-label={title} onCancel={onClose} className="modal">
    <header><h2>{title}</h2><button type="button" onClick={onClose} aria-label="关闭">×</button></header>
    {children}
  </dialog>
}

export function DemoPicker({ hasText, onImport, onClose }: {
  hasText: boolean; onImport: (text: string, title: string) => void; onClose: () => void
}) {
  const [entries, setEntries] = useState<components['schemas']['DemoSummary'][]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [pending, setPending] = useState<string | null>(null)
  const [reading, setReading] = useState(false)
  const alive = useRef(true)
  useEffect(() => {
    alive.current = true
    const controller = new AbortController()
    api.demoScripts(controller.signal).then(setEntries).catch((e: Error) => {
      if (!controller.signal.aborted) setError(e.message)
    }).finally(() => { if (!controller.signal.aborted) setLoading(false) })
    return () => { alive.current = false; controller.abort() }
  }, [])
  async function load(id: string) {
    setReading(true); setError('')
    try {
      const entry = await api.demoScript(id)
      if (alive.current) onImport(entry.text, entry.title)
    } catch (e) { if (alive.current) setError(e instanceof Error ? e.message : '读取失败，原文已保留。') }
    finally { if (alive.current) { setReading(false); setPending(null) } }
  }
  return <Modal title="试试示例剧本" onClose={onClose}>
    <p className="muted">选择后可自由修改。导入不会开始分析，也不会消耗模型额度。</p>
    {loading && <p role="status">正在读取示例…</p>}
    {error && <p role="alert" className="error">{error}</p>}
    {!loading && !entries.length && !error && <p>暂时没有启用的示例，你可以直接粘贴故事。</p>}
    <div className="demo-list">{entries.map(entry => <button type="button" disabled={reading} key={entry.id} onClick={() => hasText ? setPending(entry.id) : void load(entry.id)}>
      <span className="tag">{entry.genre}</span><strong>{entry.title}</strong><span>{entry.summary}</span><span className="text-link">使用这个故事 →</span>
    </button>)}</div>
    {pending && <div className="replacement" role="alert"><p>输入框里已有内容，是否用这个示例替换？</p><div className="actions"><button type="button" disabled={reading} onClick={() => setPending(null)}>保留原文</button><button className="primary" type="button" disabled={reading} onClick={() => void load(pending)}>确认替换</button></div></div>}
    {reading && <p role="status">正在读取完整正文…</p>}
  </Modal>
}

function downloadText(text: string, filename: string) {
  downloadBlob(new Blob(['\ufeff', text], { type: 'text/plain;charset=utf-8' }), filename)
}
function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a'); a.href = url; a.download = filename
  document.body.append(a); a.click(); a.remove()
  setTimeout(() => URL.revokeObjectURL(url), 10000)
}
export function CopyDownload({ text, filename }: { text: string; filename: string }) {
  const [manual, setManual] = useState(false)
  const [message, setMessage] = useState('')
  async function copy() {
    try { await navigator.clipboard.writeText(text); setMessage('已复制完整剧本。') }
    catch { setManual(true); setMessage('请长按下方文字，选择全选并复制。') }
  }
  return <><div className="actions"><button className="primary" type="button" onClick={() => void copy()}>复制完整剧本</button><button type="button" onClick={() => {
    try { downloadText(text, filename); setMessage('已发起下载。如果微信未保存，请用右上角菜单在浏览器打开，或复制全文。') }
    catch { setManual(true); setMessage('当前浏览器不支持下载，请手动复制。') }
  }}>下载 .txt</button></div>{message && <p role="status" className="muted">{message}</p>}
    {manual && <textarea aria-label="手动复制完整剧本" readOnly value={text} rows={8} onFocus={e => e.currentTarget.select()} />}</>
}

export function ShareDialog({ url, onClose }: { url: string; onClose: () => void }) {
  const [blob, setBlob] = useState<Blob | null>(null)
  const [image, setImage] = useState('')
  const [large, setLarge] = useState(false)
  const [error, setError] = useState('')
  useEffect(() => {
    let disposed = false; let objectUrl = ''
    if (url) api.shareCode().then(value => {
      if (disposed) return
      objectUrl = URL.createObjectURL(value); setImage(objectUrl); setBlob(value)
    }).catch(() => { if (!disposed) setError('二维码读取失败，请关闭后重试。') })
    return () => { disposed = true; if (objectUrl) URL.revokeObjectURL(objectUrl) }
  }, [url])
  return <Modal title="手机扫码体验" onClose={onClose}>
    {url ? <div className="share-body"><p>用手机相机或微信扫码，开始自己的故事。</p>
      {image && <button type="button" className={`qr ${large ? 'qr-large' : ''}`} aria-label={large ? '缩小二维码' : '放大二维码'} onClick={() => setLarge(!large)}><img src={image} alt="StoryBridge 首页体验二维码" /></button>}
      {!image && !error && <p role="status">正在生成二维码…</p>}
      <a href={`${url}/`} target="_blank" rel="noreferrer">{url}/</a>
      <div className="actions"><button type="button" disabled={!blob} onClick={() => { if (blob) { downloadBlob(blob, 'storybridge-qr.svg'); setError('如微信未保存，请长按二维码或在浏览器打开。') } }}>下载二维码</button></div>
      <p className="muted">二维码只打开首页，不包含你的故事和身份。请保持主机运行；临时地址可能随重启变化。</p>
    </div> : <p>当前为本地运行。组织者使用 <code>./speed_run.sh --share</code> 启动后，这里会显示可扫码的 HTTPS 地址。</p>}
    {error && <p role="status">{error}</p>}
  </Modal>
}
