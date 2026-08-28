import type { ChildProcessWithoutNullStreams } from 'node:child_process'
import { spawn } from 'node:child_process'
import { join, resolve } from 'node:path'
import { tmpdir } from 'node:os'

function waitForOutput(
  child: ChildProcessWithoutNullStreams,
  pattern: RegExp,
  label: string,
): Promise<void> {
  return new Promise((resolveReady, reject) => {
    let output = ''
    const timer = setTimeout(() => reject(new Error(`${label} did not become ready:\n${output}`)), 15_000)
    const inspect = (chunk: Buffer) => {
      output += chunk.toString()
      if (pattern.test(output)) {
        clearTimeout(timer)
        resolveReady()
      }
    }
    child.stdout.on('data', inspect)
    child.stderr.on('data', inspect)
    child.once('exit', (code) => {
      clearTimeout(timer)
      reject(new Error(`${label} exited with ${code}:\n${output}`))
    })
  })
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
    join(backendRoot, '.venv/bin/python'),
    ['-m', 'uvicorn', 'app.mock_main:app', '--host', '127.0.0.1', '--port', '8100'],
    {
      cwd: backendRoot,
      env: {
        ...cleanEnv,
        STORYBRIDGE_PROJECTS_DIR: join(e2eRoot, 'projects'),
        STORYBRIDGE_JOBS_FILE: join(e2eRoot, 'jobs.json'),
        STORYBRIDGE_SFT_LOG_DIR: join(e2eRoot, 'sft'),
      },
    },
  )
  const web = spawn(
    process.execPath,
    ['node_modules/vite/bin/vite.js', '--host', '127.0.0.1', '--port', '4173'],
    {
      cwd: frontendRoot,
      env: { ...cleanEnv, VITE_API_TARGET: 'http://127.0.0.1:8100' },
    },
  )

  try {
    await Promise.all([
      waitForOutput(api, /Application startup complete/, 'mock API'),
      waitForOutput(web, /Local:\s+http:\/\/127\.0\.0\.1:4173/, 'Vite'),
    ])
  } catch (error) {
    api.kill('SIGTERM')
    web.kill('SIGTERM')
    throw error
  }

  return async () => {
    api.kill('SIGTERM')
    web.kill('SIGTERM')
  }
}
