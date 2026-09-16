import { api, ApiError } from './client'
import type { Job } from '../types/api'

export class JobFailure extends ApiError {
  readonly job: Job
  constructor(job: Job) {
    super(job.error_code === 'service_restarted' ? '服务重新启动了。已保存之前的结果，请重试当前步骤。' : job.error && job.error !== 'job_execution_failed' ? job.error : '这一步未能完成，已保存之前的结果。请重试当前步骤。',
      422, job.error_code || 'generation_failed', job.resets_at || undefined)
    this.job = job
  }
}

export function wait(ms: number, signal?: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    if (signal?.aborted) { reject(new DOMException('Aborted', 'AbortError')); return }
    const abort = () => { clearTimeout(timer); reject(new DOMException('Aborted', 'AbortError')) }
    const timer = window.setTimeout(() => { signal?.removeEventListener('abort', abort); resolve() }, ms)
    signal?.addEventListener('abort', abort, { once: true })
  })
}

export async function pollJob<TResult = unknown>(jobId: string, {
  signal, onUpdate, onPause, intervalMs = 1500,
}: {
  signal?: AbortSignal
  onUpdate?: (job: Job<TResult>) => void
  onPause?: (message: string) => void
  intervalMs?: number
} = {}): Promise<Job<TResult>> {
  while (true) {
    if (!navigator.onLine || document.hidden) {
      onPause?.('已暂停查询；回到页面并联网后自动继续，后台生成仍在进行。')
      await wait(intervalMs, signal)
      continue
    }
    try {
      const job = await api.getJob<TResult>(jobId, signal)
      onPause?.('')
      onUpdate?.(job)
      if (job.status === 'done') return job
      if (job.status === 'failed' || job.status === 'cancelled') throw new JobFailure(job)
    } catch (error) {
      if (error instanceof JobFailure || (error instanceof ApiError && error.status < 500) || signal?.aborted) throw error
      onPause?.('连接暂时中断，正在等待恢复。已完成内容会保留。')
    }
    await wait(intervalMs, signal)
  }
}
