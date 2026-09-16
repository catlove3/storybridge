import { readFileSync } from 'node:fs'
import { spawnSync } from 'node:child_process'

const files = ['openapi.json', 'src/api/generated/schema.ts']
const before = files.map(file => readFileSync(file))
const generated = spawnSync('npm', ['run', 'openapi:generate'], { stdio: 'inherit', shell: process.platform === 'win32' })
if (generated.status !== 0) process.exit(generated.status || 1)
const changed = files.filter((file, i) => !readFileSync(file).equals(before[i]))
if (changed.length) {
  console.error(`OpenAPI 契约已变化，请检查并提交重新生成的文件：${changed.join(', ')}`)
  process.exit(1)
}
console.log('OpenAPI schema and generated types are current.')
