import createClient from 'openapi-fetch'
import type { paths } from './generated/schema'
import type {
  CreateProjectRequest,
  CreateProjectResponse,
  Job,
  ProjectDetail,
  ProjectSummary,
  PropagationResult,
  Revision,
  RuntimePolicy,
  SceneDiff,
  StoryGraphResponse,
  StoryState,
  SubmitJobRequest,
  SubmitJobResponse,
  TargetScript,
} from '../types/api'

const API_KEY = import.meta.env.VITE_STORYBRIDGE_API_KEY as string | undefined
const client = createClient<paths>({
  baseUrl: '',
  headers: API_KEY ? { 'X-API-Key': API_KEY } : {},
})

export class ApiError extends Error {
  readonly status: number

  constructor(message: string, status: number) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

type ApiResult = {
  data?: unknown
  error?: unknown
  response: Response
}

function errorDetail(error: unknown, response: Response) {
  if (typeof error === 'object' && error !== null && 'detail' in error) {
    const detail = error.detail
    if (typeof detail === 'string') return detail
    if (detail !== undefined) return JSON.stringify(detail)
  }
  return `${response.status} ${response.statusText}`
}

function unwrap<TResult>(result: ApiResult): TResult {
  if (result.error !== undefined) {
    throw new ApiError(errorDetail(result.error, result.response), result.response.status)
  }
  if (result.data === undefined) {
    throw new ApiError('后端未返回 JSON 响应。', result.response.status)
  }
  return result.data as TResult
}

export const api = {
  async getRuntimePolicy(signal?: AbortSignal) {
    return unwrap<RuntimePolicy>(await client.GET('/api/runtime-policy', { signal }))
  },

  async listProjects(signal?: AbortSignal) {
    return unwrap<ProjectSummary[]>(await client.GET('/api/projects', { signal }))
  },

  async getProject(projectId: string, signal?: AbortSignal) {
    return unwrap<ProjectDetail>(await client.GET('/api/projects/{project_id}', {
      params: { path: { project_id: projectId } },
      signal,
    }))
  },

  async createProject(body: CreateProjectRequest, signal?: AbortSignal) {
    return unwrap<CreateProjectResponse>(await client.POST('/api/projects', { body, signal }))
  },

  async submitJob(projectId: string, body: SubmitJobRequest, signal?: AbortSignal) {
    return unwrap<SubmitJobResponse>(await client.POST('/api/projects/{project_id}/jobs', {
      params: { path: { project_id: projectId } },
      body,
      signal,
    }))
  },

  async getJob<TResult = unknown>(jobId: string, signal?: AbortSignal) {
    return unwrap<Job<TResult>>(await client.GET('/api/jobs/{job_id}', {
      params: { path: { job_id: jobId } },
      signal,
    }))
  },

  async cancelJob<TResult = unknown>(jobId: string, signal?: AbortSignal) {
    return unwrap<Job<TResult>>(await client.POST('/api/jobs/{job_id}/cancel', {
      params: { path: { job_id: jobId } },
      signal,
    }))
  },

  async listJobs(projectId: string, signal?: AbortSignal) {
    return unwrap<Job[]>(await client.GET('/api/projects/{project_id}/jobs', {
      params: { path: { project_id: projectId } },
      signal,
    }))
  },

  async getStoryState(projectId: string, signal?: AbortSignal) {
    return unwrap<StoryState>(await client.GET('/api/projects/{project_id}/state', {
      params: { path: { project_id: projectId } },
      signal,
    }))
  },

  async getPropagation(projectId: string, mechanismId: string, signal?: AbortSignal) {
    return unwrap<PropagationResult>(await client.GET('/api/projects/{project_id}/propagate', {
      params: {
        path: { project_id: projectId },
        query: { mechanism: mechanismId },
      },
      signal,
    }))
  },

  async getGraph(projectId: string, focus?: string, depth = 3, signal?: AbortSignal) {
    return unwrap<StoryGraphResponse>(await client.GET('/api/projects/{project_id}/graph', {
      params: {
        path: { project_id: projectId },
        query: { focus, depth },
      },
      signal,
    }))
  },

  async getDiff(projectId: string, signal?: AbortSignal) {
    return unwrap<SceneDiff[]>(await client.GET('/api/projects/{project_id}/diff', {
      params: { path: { project_id: projectId } },
      signal,
    }))
  },

  async getRevisions(projectId: string, signal?: AbortSignal) {
    return unwrap<Revision[]>(await client.GET('/api/projects/{project_id}/revisions', {
      params: { path: { project_id: projectId } },
      signal,
    }))
  },

  async getTargetScript(projectId: string, signal?: AbortSignal) {
    return unwrap<TargetScript>(await client.GET('/api/projects/{project_id}/target-script', {
      params: { path: { project_id: projectId } },
      signal,
    }))
  },
}
