import type { ProjectSummary } from '../types/api'

interface ProjectSwitcherProps {
  activeProjectId: string | null
  busy: boolean
  onOpen: (projectId: string) => void
  projects: ProjectSummary[]
}

export function ProjectSwitcher({ activeProjectId, busy, onOpen, projects }: ProjectSwitcherProps) {
  if (projects.length === 0) return null
  return (
    <aside className="project-switcher" aria-label="已有项目">
      <span>恢复已有项目</span>
      <div>
        {projects.map((project) => (
          <button
            className={project.id === activeProjectId ? 'is-active' : ''}
            disabled={busy}
            key={project.id}
            onClick={() => onOpen(project.id)}
            type="button"
          >
            <strong>{project.name || '未命名项目'}</strong>
            <small>{project.id.slice(0, 8)}</small>
          </button>
        ))}
      </div>
    </aside>
  )
}
