import { api } from './client'
import type { Job } from '../types/api'

interface PollJobOptions<TResult> {
  intervalMs?: number
  timeoutMs?: number
  signal?: AbortSignal
  onUpdate?: (job: Job<TResult>) => void
}

function wait(ms: number, signal?: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    if (signal?.aborted) {
      reject(new DOMException('The operation was aborted.', 'AbortError'))
      return
    }

    const onAbort = () => {
      window.clearTimeout(timer)
      reject(new DOMException('The operation was aborted.', 'AbortError'))
    }
    const timer = window.setTimeout(() => {
      signal?.removeEventListener('abort', onAbort)
      resolve()
    }, ms)
    signal?.addEventListener('abort', onAbort, { once: true })
  })
}

export async function pollJob<TResult = unknown>(
  jobId: string,
  {
    intervalMs = 2_000,
    timeoutMs = 180_000,
    signal,
    onUpdate,
  }: PollJobOptions<TResult> = {},
): Promise<Job<TResult>> {
  const startedAt = Date.now()

  while (Date.now() - startedAt <= timeoutMs) {
    const job = await api.getJob<TResult>(jobId, signal)
    onUpdate?.(job)

    if (job.status === 'done') {
      return job
    }
    if (job.status === 'failed') {
      throw new Error(job.error || '分析任务失败，但后端没有返回错误详情。')
    }
    if (job.status === 'cancelled') {
      throw new Error('任务已取消。')
    }

    await wait(intervalMs, signal)
  }

  throw new Error(`任务轮询超过 ${Math.round(timeoutMs / 1_000)} 秒，请稍后重试。`)
}
