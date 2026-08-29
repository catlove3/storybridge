import type { ChildProcessWithoutNullStreams } from 'node:child_process'
import { spawn } from 'node:child_process'
import { rm } from 'node:fs/promises'
import { join, resolve } from 'node:path'
import { tmpdir } from 'node:os'

function captureOutput(child: ChildProcessWithoutNullStreams): () => string {
  let output = ''
  const append = (chunk: Buffer) => {
    output = `${output}${chunk.toString()}`.slice(-20_000)
  }
  child.stdout.on('data', append)
  child.stderr.on('data', append)
  return () => output
}

function hasExited(child: ChildProcessWithoutNullStreams): boolean {
  return child.exitCode !== null || child.signalCode !== null
}

async function waitForHttp(
  child: ChildProcessWithoutNullStreams,
  url: string,
  label: string,
  output: () => string,
): Promise<void> {
  const deadline = Date.now() + 30_000
  while (Date.now() < deadline) {
    if (hasExited(child)) {
      const reason = child.exitCode !== null ? `code ${child.exitCode}` : child.signalCode
      throw new Error(`${label} exited with ${reason}:\n${output()}`)
    }
    try {
      const response = await fetch(url, { signal: AbortSignal.timeout(1_000) })
      if (response.ok) return
    } catch {
      // The service may still be starting.
    }
    await new Promise((resolveWait) => setTimeout(resolveWait, 200))
  }
  throw new Error(`${label} did not become ready at ${url}:\n${output()}`)
}

async function terminate(child: ChildProcessWithoutNullStreams): Promise<void> {
  if (hasExited(child)) return
  child.kill('SIGTERM')
  await Promise.race([
    new Promise<void>((resolveExit) => child.once('exit', () => resolveExit())),
    new Promise<void>((resolveTimeout) => setTimeout(resolveTimeout, 3_000)),
  ])
  if (!hasExited(child)) {
    child.kill('SIGKILL')
    await new Promise<void>((resolveExit) => {
      if (hasExited(child)) resolveExit()
      else child.once('exit', () => resolveExit())
    })
  }
}

function failOnSpawn(child: ChildProcessWithoutNullStreams, label: string): Promise<never> {
  return new Promise((_, reject) => {
    child.once('error', (error) => {
      reject(new Error(`${label} failed to start: ${error.message}`))
    })
  })
}

async function waitForServices(
  api: ChildProcessWithoutNullStreams,
  web: ChildProcessWithoutNullStreams,
  apiOutput: () => string,
  webOutput: () => string,
): Promise<void> {
  await Promise.race([
    Promise.all([
      waitForHttp(api, 'http://127.0.0.1:8100/healthz', 'mock API', apiOutput),
      waitForHttp(web, 'http://127.0.0.1:4173/', 'Vite', webOutput),
    ]),
    failOnSpawn(api, 'mock API'),
    failOnSpawn(web, 'Vite'),
  ])
}

function backendPython(backendRoot: string): string {
  const configured = process.env.STORYBRIDGE_E2E_PYTHON?.trim()
  if (configured) return configured
  return join(
    backendRoot,
    process.platform === 'win32' ? '.venv/Scripts/python.exe' : '.venv/bin/python',
  )
}

export default async function globalSetup() {
  const frontendRoot = resolve(import.meta.dirname, '..')
  const backendRoot = resolve(frontendRoot, '../backend')
  const e2eRoot = join(tmpdir(), `storybridge-e2e-${process.pid}`)
  const cleanEnv = { ...process.env }
  for (const name of [
    'HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY',
    'http_proxy', 'https_proxy', 'all_proxy',
  ]) {
    delete cleanEnv[name]
  }
  cleanEnv.NO_PROXY = '127.0.0.1,localhost'
  cleanEnv.no_proxy = '127.0.0.1,localhost'

  const api = spawn(
    backendPython(backendRoot),
    ['-m', 'uvicorn', 'app.mock_main:app', '--host', '127.0.0.1', '--port', '8100'],
    {
      cwd: backendRoot,
      env: {
        ...cleanEnv,
        STORYBRIDGE_PROJECTS_DIR: join(e2eRoot, 'projects'),
        STORYBRIDGE_JOBS_FILE: join(e2eRoot, 'jobs.json'),
        STORYBRIDGE_SFT_LOG_DIR: join(e2eRoot, 'sft'),
        STORYBRIDGE_RUN_LOG_DIR: join(e2eRoot, 'runs'),
      },
    },
  )
  const web = spawn(
    process.execPath,
    ['node_modules/vite/bin/vite.js', '--host', '127.0.0.1', '--port', '4173', '--strictPort'],
    {
      cwd: frontendRoot,
      env: { ...cleanEnv, VITE_API_TARGET: 'http://127.0.0.1:8100' },
    },
  )
  const apiOutput = captureOutput(api)
  const webOutput = captureOutput(web)

  try {
    await waitForServices(api, web, apiOutput, webOutput)
  } catch (error) {
    await Promise.all([terminate(api), terminate(web)])
    await rm(e2eRoot, { recursive: true, force: true })
    throw error
  }

  return async () => {
    await Promise.all([terminate(api), terminate(web)])
    await rm(e2eRoot, { recursive: true, force: true })
  }
}
