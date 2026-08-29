import { useEffect } from 'react'
import type { ProjectSummary } from '../types/api'

interface ProjectSwitcherProps {
  activeProjectId: string | null
  busy: boolean
  onClose: () => void
  onNew: () => void
  onOpen: (projectId: string) => void
  open: boolean
  projects: ProjectSummary[]
}

function formatCreatedAt(value: string): string {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '时间未知'
  return new Intl.DateTimeFormat('zh-CN', {
    month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit',
  }).format(date)
}

export function ProjectSwitcher({
  activeProjectId, busy, onClose, onNew, onOpen, open, projects,
}: ProjectSwitcherProps) {
  useEffect(() => {
    if (!open) return undefined
    const handleKeyDown = (event: globalThis.KeyboardEvent) => {
      if (event.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [onClose, open])

  if (!open) return null
  return (
    <>
      <button aria-label="关闭项目侧栏" className="project-sidebar__backdrop" onClick={onClose} type="button" />
      <aside aria-label="项目管理" aria-modal="true" className="project-sidebar" id="project-sidebar" role="dialog">
        <header className="project-sidebar__header">
          <div><span>WORKSPACE</span><h2>项目</h2></div>
          <button aria-label="关闭项目侧栏" className="project-sidebar__close" onClick={onClose} type="button">×</button>
        </header>

        <button className="project-sidebar__new" disabled={busy} onClick={onNew} type="button">
          <span aria-hidden="true">＋</span>
          <span><strong>新建项目</strong><small>从一份新的中文剧本开始</small></span>
        </button>

        <section className="project-sidebar__history" aria-labelledby="project-history-title">
          <header><h3 id="project-history-title">历史记录</h3><span>{projects.length}</span></header>
          {projects.length > 0
            ? <ol>{projects.map((project) => (
              <li key={project.id}>
                <button
                  aria-current={project.id === activeProjectId ? 'page' : undefined}
                  className={project.id === activeProjectId ? 'is-active' : ''}
                  disabled={busy}
                  onClick={() => onOpen(project.id)}
                  type="button"
                >
                  <span><strong>{project.name || '未命名项目'}</strong><small>{formatCreatedAt(project.created_at)}</small></span>
                  <code>{project.id.slice(0, 8)}</code>
                </button>
              </li>
            ))}</ol>
            : <div className="project-sidebar__empty"><strong>还没有历史项目</strong><p>创建并分析后，项目会出现在这里。</p></div>}
        </section>
      </aside>
    </>
  )
}
