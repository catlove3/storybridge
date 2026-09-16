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
  credentials: 'same-origin',
  headers: API_KEY ? { 'X-API-Key': API_KEY } : {},
})
let csrfToken = ''
client.use({
  onRequest({ request }) {
    if (csrfToken && !['GET', 'HEAD'].includes(request.method)) request.headers.set('X-CSRF-Token', csrfToken)
    return request
  },
})

export class ApiError extends Error {
  readonly status: number
  readonly code: string
  readonly resetsAt?: string

  constructor(message: string, status: number, code = '', resetsAt?: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
    this.resetsAt = resetsAt
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
    const detail = (result.error as { detail?: { message?: string; code?: string; resets_at?: string } }).detail
    if (detail && typeof detail === 'object' && detail.message) {
      throw new ApiError(detail.message, result.response.status, detail.code, detail.resets_at)
    }
    throw new ApiError(errorDetail(result.error, result.response), result.response.status)
  }
  if (result.data === undefined) {
    throw new ApiError('后端未返回 JSON 响应。', result.response.status)
  }
  return result.data as TResult
}

export const api = {
  async session(signal?: AbortSignal) {
    const session = unwrap<import('./generated/schema').components['schemas']['SessionResponse']>(
      await client.POST('/api/session', { signal }),
    )
    csrfToken = session.csrf_token
    return session
  },
  async demoScripts(signal?: AbortSignal) {
    return unwrap<import('./generated/schema').components['schemas']['DemoSummary'][]>(
      await client.GET('/api/demo-scripts', { signal }),
    )
  },
  async demoScript(scriptId: string, signal?: AbortSignal) {
    return unwrap<import('./generated/schema').components['schemas']['DemoDetail']>(
      await client.GET('/api/demo-scripts/{script_id}', { params: { path: { script_id: scriptId } }, signal }),
    )
  },
  async exportProject(projectId: string, signal?: AbortSignal) {
    return unwrap<import('./generated/schema').components['schemas']['DataExportResponse']>(
      await client.GET('/api/projects/{project_id}/data-export', { params: { path: { project_id: projectId } }, signal }),
    )
  },
  async deleteProject(projectId: string) {
    return unwrap(await client.DELETE('/api/projects/{project_id}', { params: { path: { project_id: projectId } } }))
  },
  async verification(projectId: string, signal?: AbortSignal) {
    return unwrap<import('../types/api').VerifyReport | null>(await client.GET('/api/projects/{project_id}/verification', {
      params: { path: { project_id: projectId } }, signal,
    }))
  },
  async shareCode() {
    const response = await fetch('/api/share-code', { headers: API_KEY ? { 'X-API-Key': API_KEY } : {} })
    if (!response.ok) throw new Error('请使用分享模式启动，再打开二维码。')
    return response.blob()
  },
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
