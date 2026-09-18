import type { SubmitJobRequest } from '../types/api'

export type Stage = 'analyze' | 'plan_batch' | 'apply_batch' | 'refresh_culture' | 'verify' | 'repair' | 'render'
export interface Task {
  stage: Stage
  key: string
  jobId?: string
  request: SubmitJobRequest
  chain: boolean
  status: 'running' | 'failed' | 'blocked' | 'cancelled' | 'done'
  error?: string
  resetsAt?: string
}
export interface Draft {
  name: string; script: string; market: string; language: string; locale: string
  audience: string; genre: string; format: string; createKey: string
}
export interface AdaptationFlow {
  phase: 'settings' | 'refresh' | 'culture'
  activeIds: string[]
  deferredIds: string[]
  refreshedAfterSettings?: boolean
}
export interface Progress {
  projectId: string | null
  selected: string[]
  labels: Record<string, string>
  custom: Record<string, string>
  review?: { token: string; choices: Record<string, 'modify' | 'keep'> }
  repairNote?: { text: string; sceneId: string }
  adaptationFlow?: AdaptationFlow
  task: Task | null
  view?: 'choose' | 'result'
}
export const emptyProgress = (): Progress => ({ projectId: null, selected: [], labels: {}, custom: {}, task: null })
export const newDraft = (): Draft => ({
  name: '', script: '', market: '美国', language: 'English', locale: 'en-US',
  audience: '大众观众', genre: '', format: '短剧', createKey: crypto.randomUUID(),
})

export function readSaved<T>(owner: string, key: string): T | null {
  try { return JSON.parse(localStorage.getItem(`storybridge.v2.${owner}.${key}`) || 'null') as T | null }
  catch { return null }
}
export function save(owner: string, key: string, value: unknown): boolean {
  try { localStorage.setItem(`storybridge.v2.${owner}.${key}`, JSON.stringify(value)); return true }
  catch { return false }
}
export function newTask(stage: Stage, request: Partial<SubmitJobRequest> = {}, chain = false, key: string = crypto.randomUUID()): Task {
  return { stage, key, request: { auto_verify_and_repair: true, repair_suggestion: '', ...request, kind: stage, idempotency_key: key }, chain, status: 'running' }
}
