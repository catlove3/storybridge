const PROJECT_KEY = 'storybridge.activeProjectId'
const JOB_KEY = 'storybridge.activeJobId'

export function recoveryProjectId(): string | null {
  const fromUrl = new URL(window.location.href).searchParams.get('project')
  return fromUrl || window.localStorage.getItem(PROJECT_KEY)
}

export function persistProject(projectId: string): void {
  window.localStorage.setItem(PROJECT_KEY, projectId)
  const url = new URL(window.location.href)
  url.searchParams.set('project', projectId)
  window.history.replaceState({}, '', url)
}

export function clearProjectRecovery(): void {
  window.localStorage.removeItem(PROJECT_KEY)
  const url = new URL(window.location.href)
  url.searchParams.delete('project')
  window.history.replaceState({}, '', url)
}

export function persistJob(jobId: string | null): void {
  if (jobId) window.localStorage.setItem(JOB_KEY, jobId)
  else window.localStorage.removeItem(JOB_KEY)
}

export function recoveryJobId(): string | null {
  return window.localStorage.getItem(JOB_KEY)
}
