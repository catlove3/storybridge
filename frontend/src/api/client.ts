import type {
  CreateProjectRequest,
  CreateProjectResponse,
  Job,
  PropagationResult,
  Revision,
  SceneDiff,
  StoryGraphResponse,
  StoryState,
  SubmitJobRequest,
  SubmitJobResponse,
  TargetScript,
} from '../types/api'

const API_ROOT = '/api'

export class ApiError extends Error {
  readonly status: number

  constructor(message: string, status: number) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers)
  if (init?.body) {
    headers.set('Content-Type', 'application/json')
  }

  const response = await fetch(`${API_ROOT}${path}`, { ...init, headers })
  if (!response.ok) {
    let detail = `${response.status} ${response.statusText}`
    try {
      const payload = (await response.json()) as { detail?: unknown }
      if (typeof payload.detail === 'string') {
        detail = payload.detail
      } else if (payload.detail) {
        detail = JSON.stringify(payload.detail)
      }
    } catch {
      // Keep the HTTP fallback when the response is not JSON.
    }
    throw new ApiError(detail, response.status)
  }

  return (await response.json()) as T
}

export const api = {
  createProject(body: CreateProjectRequest, signal?: AbortSignal) {
    return request<CreateProjectResponse>('/projects', {
      method: 'POST',
      body: JSON.stringify(body),
      signal,
    })
  },

  submitJob(projectId: string, body: SubmitJobRequest, signal?: AbortSignal) {
    return request<SubmitJobResponse>(`/projects/${projectId}/jobs`, {
      method: 'POST',
      body: JSON.stringify(body),
      signal,
    })
  },

  getJob<TResult = unknown>(jobId: string, signal?: AbortSignal) {
    return request<Job<TResult>>(`/jobs/${jobId}`, { signal })
  },

  cancelJob<TResult = unknown>(jobId: string, signal?: AbortSignal) {
    return request<Job<TResult>>(`/jobs/${jobId}/cancel`, { method: 'POST', signal })
  },

  getStoryState(projectId: string, signal?: AbortSignal) {
    return request<StoryState>(`/projects/${projectId}/state`, { signal })
  },

  getPropagation(projectId: string, mechanismId: string, signal?: AbortSignal) {
    const query = new URLSearchParams({ mechanism: mechanismId })
    return request<PropagationResult>(`/projects/${projectId}/propagate?${query}`, { signal })
  },

  getGraph(
    projectId: string,
    focus?: string,
    depth = 3,
    signal?: AbortSignal,
  ) {
    const query = new URLSearchParams({ depth: String(depth) })
    if (focus) query.set('focus', focus)
    return request<StoryGraphResponse>(`/projects/${projectId}/graph?${query}`, { signal })
  },

  getDiff(projectId: string, signal?: AbortSignal) {
    return request<SceneDiff[]>(`/projects/${projectId}/diff`, { signal })
  },

  getRevisions(projectId: string, signal?: AbortSignal) {
    return request<Revision[]>(`/projects/${projectId}/revisions`, { signal })
  },

  getTargetScript(projectId: string, signal?: AbortSignal) {
    return request<TargetScript>(`/projects/${projectId}/target-script`, { signal })
  },
}
