import { expect, test } from '@playwright/test'
import type { Page } from '@playwright/test'

async function ready(page: Page) {
  await page.goto('/')
  await expect(page.getByLabel('中文剧本')).toBeVisible()
  await expect(page.getByText('默认模型已配置，直接开始即可。')).toBeVisible()
}
async function importDemo(page: Page) {
  await page.getByRole('button', { name: '试试示例剧本' }).click()
  await page.getByRole('button', { name: /拜见岳父大人/ }).click()
  await expect(page.getByLabel('中文剧本')).toHaveValue(/上门提亲/)
}
async function analyzeAndPlan(page: Page, multiple = false) {
  await page.getByRole('button', { name: '开始分析' }).click()
  await expect(page.getByRole('heading', { name: '哪些内容需要调整' })).toBeVisible({ timeout: 30000 })
  if (multiple) await page.getByRole('checkbox').nth(1).check()
  await page.getByRole('button', { name: '生成方案', exact: false }).click()
  await expect(page.getByRole('button', { name: '选择方案 B' }).first()).toBeVisible({ timeout: 30000 })
  await page.getByRole('button', { name: '选择方案 B' }).first().click()
  if (multiple) await page.getByRole('button', { name: '选择方案 C' }).nth(1).click()
}
async function active(page: Page) {
  return page.evaluate(() => {
    const key = Object.keys(localStorage).find(key => key.startsWith('storybridge.v2.') && key.endsWith('.active'))!
    return JSON.parse(localStorage.getItem(key)!)
  })
}

test('edited demo completes the real HTTP flow, restores, compares and downloads', async ({ page }) => {
  await ready(page)
  const mutations: string[] = []
  page.on('request', r => { if (r.method() === 'POST' && !r.url().endsWith('/session')) mutations.push(r.url()) })
  await importDemo(page)
  expect(mutations).toHaveLength(0)
  const edited = (await page.getByLabel('中文剧本').inputValue()) + '\n【用户修改】女主决定与男主一起创业。'
  await page.getByLabel('中文剧本').fill(edited)
  await page.reload()
  await expect(page.getByLabel('中文剧本')).toHaveValue(edited)
  const submission = page.waitForRequest(r => r.method() === 'POST' && r.url().endsWith('/api/projects'))
  await analyzeAndPlan(page, true)
  expect((await submission).postDataJSON().script).toBe(edited)
  await page.reload()
  await expect(page.getByRole('button', { name: '已选择此方案' })).toHaveCount(2)
  await page.getByRole('button', { name: '生成改编剧本' }).click()
  await page.reload()
  await expect(page.getByRole('heading', { name: 'English 完整剧本' })).toBeVisible({ timeout: 45000 })
  const saved = await active(page)
  expect(saved.task.stage).toBe('render')
  expect(saved.task.status).toBe('done')
  expect(new URL(page.url()).search).toBe('')
  await page.getByText('原文对比与中文改编稿', { exact: true }).click()
  await expect(page.locator('.story-text')).toContainText('【用户修改】')
  await page.getByRole('button', { name: '中文改编稿', exact: true }).click()
  await expect(page.locator('.story-text')).not.toContainText('【用户修改】')
  const download = page.waitForEvent('download')
  await page.getByRole('button', { name: '下载 .txt', exact: true }).click()
  expect((await download).suggestedFilename()).toMatch(/en-US.txt$/)
  await page.screenshot({ path: `/tmp/storybridge-result-${test.info().project.name}.png`, fullPage: true })
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  await page.getByRole('button', { name: '开始新故事', exact: true }).first().click()
  await expect(page.getByLabel('中文剧本')).toHaveValue('')
  await page.reload()
  await expect(page.getByLabel('中文剧本')).toHaveValue('')
  await page.getByRole('button', { name: '我的故事', exact: true }).click()
  await page.getByRole('button', { name: /^拜见岳父大人/ }).click()
  await expect(page.getByRole('heading', { name: 'English 完整剧本' })).toBeVisible()
})

test('replacement cancel, failed read, and failed catalog keep the draft and market', async ({ page }) => {
  await ready(page)
  await page.getByLabel('中文剧本').fill('我原来的故事。')
  await page.getByLabel('目标市场', { exact: true }).fill('日本')
  await page.getByLabel('目标语言与地区').selectOption('ja-JP')
  await page.getByRole('button', { name: '试试示例剧本' }).click()
  await page.getByRole('button', { name: /嫡女归来/ }).click()
  await page.getByRole('button', { name: '保留原文' }).click()
  await page.getByRole('button', { name: '关闭', exact: true }).click()
  await expect(page.getByLabel('中文剧本')).toHaveValue('我原来的故事。')
  await page.route('**/api/demo-scripts/daughter_returns', route => route.fulfill({ status: 503, json: { detail: { message: '示例读取失败，原文已保留。' } } }))
  await page.getByRole('button', { name: '试试示例剧本' }).click()
  await page.getByRole('button', { name: /嫡女归来/ }).click()
  await page.getByRole('button', { name: '确认替换' }).click()
  await expect(page.getByRole('alert')).toContainText('原文已保留')
  await page.getByRole('button', { name: '关闭', exact: true }).click()
  await expect(page.getByLabel('中文剧本')).toHaveValue('我原来的故事。')
  await expect(page.getByLabel('目标市场', { exact: true })).toHaveValue('日本')
  await expect(page.getByLabel('目标语言与地区')).toHaveValue('ja-JP')
  await page.route('**/api/demo-scripts', route => route.fulfill({ status: 503, json: { detail: { message: '示例暂不可用' } } }))
  await page.getByRole('button', { name: '试试示例剧本' }).click()
  await expect(page.getByRole('alert')).toContainText('示例暂不可用')
  await page.getByRole('button', { name: '关闭', exact: true }).click()
  await expect(page.getByRole('button', { name: '开始分析' })).toBeEnabled()
})

test('independent visitors cannot see stories or inherit a cleared-cookie draft', async ({ page, browser }) => {
  await ready(page)
  await page.getByLabel('中文剧本').fill('浏览器甲的故事')
  await page.getByRole('button', { name: '开始分析' }).click()
  await expect(page.getByRole('heading', { name: '哪些内容需要调整' })).toBeVisible()
  const pid = (await active(page)).projectId
  const second = await browser.newContext()
  const other = await second.newPage()
  await ready(other)
  await other.getByRole('button', { name: '我的故事' }).click()
  await expect(other.getByText('还没有保存的故事，从一个新故事开始吧。')).toBeVisible()
  expect(await other.evaluate(async id => (await fetch(`/api/projects/${id}/data-export`)).status, pid)).toBe(404)
  await page.context().clearCookies()
  await page.reload()
  await expect(page.getByLabel('中文剧本')).toHaveValue('')
  await second.close()
})

test('disconnect and background pauses never cancel generation; reload resumes', async ({ page, context }) => {
  await ready(page); await importDemo(page); await analyzeAndPlan(page)
  let cancelled = 0
  page.on('request', r => { if (r.url().endsWith('/cancel')) cancelled++ })
  await page.route('**/api/jobs/*', async route => {
    if (route.request().method() === 'GET') await new Promise(resolve => setTimeout(resolve, 500))
    await route.continue()
  })
  await page.getByRole('button', { name: '生成改编剧本' }).click()
  await expect.poll(async () => (await active(page)).task?.jobId).toBeTruthy()
  await context.setOffline(true)
  await expect(page.getByText(/已暂停查询|连接暂时中断/)).toBeVisible()
  await context.setOffline(false)
  await page.reload()
  await expect(page.getByRole('heading', { name: 'English 完整剧本' })).toBeVisible({ timeout: 45000 })
  expect(cancelled).toBe(0)
})

test('failed language stage retries alone and copy has a manual fallback', async ({ page }) => {
  await ready(page); await importDemo(page); await analyzeAndPlan(page)
  const stages: string[] = []
  let fail = true
  await page.route('**/api/projects/*/jobs', async route => {
    if (route.request().method() !== 'POST') { await route.continue(); return }
    const stage = route.request().postDataJSON().kind
    stages.push(stage)
    if (stage === 'render' && fail) {
      fail = false
      await route.fulfill({ status: 429, json: { detail: { code: 'site_rate_limit', message: '稍后重试，已保留改编稿。', resets_at: '2030-01-01T00:00:00+08:00' } } })
    } else await route.continue()
  })
  await page.getByRole('button', { name: '生成改编剧本' }).click()
  await expect(page.getByRole('alert')).toContainText('已保留改编稿')
  await page.reload()
  await expect(page.getByRole('button', { name: '重试当前步骤' })).toBeVisible()
  await page.getByRole('button', { name: '重试当前步骤' }).click()
  await expect(page.getByRole('heading', { name: 'English 完整剧本' })).toBeVisible({ timeout: 30000 })
  expect(stages.filter(s => s === 'apply_batch')).toHaveLength(1)
  expect(stages.filter(s => s === 'verify')).toHaveLength(1)
  expect(stages.filter(s => s === 'render')).toHaveLength(2)
  await page.evaluate(() => Object.defineProperty(navigator, 'clipboard', { value: { writeText: () => Promise.reject(new Error('denied')) } }))
  await page.getByRole('button', { name: '复制完整剧本' }).click()
  await expect(page.getByLabel('手动复制完整剧本')).toHaveValue(/\S/)
})

test('small screens keep primary controls usable and locale selection consistent', async ({ page }) => {
  await ready(page)
  for (const width of [320, 375, 390, 430]) {
    await page.setViewportSize({ width, height: 844 })
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  }
  await page.getByLabel('目标语言与地区').selectOption('en-GB')
  await page.getByText('更多设置', { exact: true }).click()
  await expect(page.getByLabel('语言地区代码（如 en-US）')).toHaveValue('en-GB')
  await page.getByLabel('语言地区代码（如 en-US）').fill('ja-JP')
  await expect(page.getByLabel('语言名称', { exact: true })).toHaveValue('Japanese')
  await expect(page.getByLabel('目标语言与地区')).toHaveValue('ja-JP')
  await page.screenshot({ path: `/tmp/storybridge-input-${test.info().project.name}.png`, fullPage: true })
  const height = await page.getByRole('button', { name: '开始分析' }).evaluate(el => el.getBoundingClientRect().height)
  expect(height).toBeGreaterThanOrEqual(44)
})

test('lost submission response reuses one operation across refresh', async ({ page }) => {
  await ready(page); await importDemo(page); await analyzeAndPlan(page)
  const keys: string[] = []
  let lose = true
  await page.route('**/api/projects/*/jobs', async route => {
    const request = route.request()
    if (request.method() === 'POST' && request.postDataJSON().kind === 'apply_batch') {
      keys.push(request.postDataJSON().idempotency_key)
      if (lose) {
        lose = false
        await route.fetch()
        await route.abort('connectionreset')
        return
      }
    }
    await route.continue()
  })
  await page.getByRole('button', { name: '生成改编剧本' }).click()
  await expect(page.getByText('连接暂时中断，正在恢复提交。不会重复生成。')).toBeVisible()
  await page.reload()
  await expect(page.getByRole('heading', { name: 'English 完整剧本' })).toBeVisible({ timeout: 30000 })
  expect(keys.length).toBeGreaterThanOrEqual(2)
  expect(new Set(keys).size).toBe(1)
  const pid = (await active(page)).projectId
  const jobs = await page.evaluate(async id => (await fetch(`/api/projects/${id}/jobs`)).json(), pid)
  expect(jobs.filter((job: { kind: string }) => job.kind === 'apply_batch')).toHaveLength(1)
})

test('background query pauses and blocking verification stops language generation', async ({ page }) => {
  await ready(page); await importDemo(page); await analyzeAndPlan(page)
  let renderSubmissions = 0
  let block = true
  page.on('request', request => {
    if (request.method() === 'POST' && request.url().endsWith('/jobs') && request.postDataJSON().kind === 'render') renderSubmissions++
  })
  await page.route('**/api/jobs/*', async route => {
    const response = await route.fetch()
    const data = await response.json()
    if (block && data.kind === 'verify' && data.status === 'done') {
      data.result.overall_status = 'fail'
      data.result.issues = [{ severity: 'error', issue_type: 'fact_conflict', description: '主角动机仍有冲突，需要复核。' }]
    }
    await route.fulfill({ response, json: data })
  })
  await page.evaluate(() => { Object.defineProperty(document, 'hidden', { configurable: true, get: () => true }); document.dispatchEvent(new Event('visibilitychange')) })
  await page.getByRole('button', { name: '生成改编剧本' }).click()
  await expect(page.getByText(/已暂停查询/)).toBeVisible()
  await page.evaluate(() => { Object.defineProperty(document, 'hidden', { configurable: true, get: () => false }); document.dispatchEvent(new Event('visibilitychange')) })
  await expect(page.getByRole('alert')).toContainText('检查发现阻塞问题')
  await expect(page.getByText('主角动机仍有冲突，需要复核。')).toBeVisible()
  expect(renderSubmissions).toBe(0)
  block = false
  await page.getByRole('button', { name: '再次检查', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'English 完整剧本' })).toBeVisible({ timeout: 30000 })
  expect(renderSubmissions).toBe(1)
})
