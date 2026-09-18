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
  await page.getByText('展开关联路径、图谱和详细依据', { exact: true }).click()
  await page.getByText('查看关系图', { exact: true }).click()
  const graphEdge = page.locator('.graph-edges path').first()
  await expect(graphEdge).toHaveAttribute('fill', 'none')
  expect(await graphEdge.evaluate(path => getComputedStyle(path).stroke)).not.toBe('none')
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

test('custom adaptation is persisted and sent to the rewrite job', async ({ page }) => {
  await ready(page)
  await importDemo(page)
  await page.getByRole('button', { name: '开始分析' }).click()
  await expect(page.getByRole('heading', { name: '哪些内容需要调整' })).toBeVisible({ timeout: 30000 })
  await page.getByRole('button', { name: '生成方案', exact: false }).click()
  const custom = '保留冲突强度，但改成社区医院的终身聘用岗位，并让家长明确说出养老金保障。'
  await page.getByLabel('写清楚希望保留、替换或重构成什么').first().fill(custom)
  await expect(page.getByRole('button', { name: '已选择自定义方案' }).first()).toBeVisible()
  const submission = page.waitForRequest(request =>
    request.method() === 'POST'
    && request.url().endsWith('/jobs')
    && request.postDataJSON().kind === 'apply_batch',
  )
  await page.getByRole('button', { name: '生成改编剧本' }).click()
  const body = (await submission).postDataJSON()
  expect(body.adaptations[0]).toMatchObject({ option_label: 'CUSTOM', custom_instruction: custom })
  const saved = await active(page)
  expect(saved.custom[saved.selected[0]]).toBe(custom)
})

test('core settings are applied before culture plans are regenerated', async ({ page }) => {
  await ready(page)
  await importDemo(page)
  const submissions: Array<{ kind: string; culture_mechanism_ids?: string[]; adaptations?: Array<{ culture_mechanism_id: string }> }> = []
  page.on('request', request => {
    if (request.method() === 'POST' && request.url().endsWith('/jobs')) submissions.push(request.postDataJSON())
  })

  await page.getByRole('button', { name: '开始分析' }).click()
  await expect(page.getByRole('heading', { name: '哪些内容需要调整' })).toBeVisible({ timeout: 30000 })
  await page.getByRole('checkbox', { name: /当代中国都市/ }).check()
  await page.getByRole('button', { name: '生成方案', exact: false }).click()

  await expect(page.getByText('第 1 步：先统一核心设定')).toBeVisible({ timeout: 30000 })
  await expect(page.getByRole('heading', { name: '为核心设定选择方案' })).toBeVisible()
  await expect(page.getByRole('button', { name: '选择方案 B' })).toHaveCount(1)
  await page.getByRole('button', { name: '选择方案 B' }).click()
  await page.getByRole('button', { name: '先应用核心设定' }).click()

  await expect(page.getByText('第 2 步：复核文化背景与名词')).toBeVisible({ timeout: 30000 })
  await expect(page.getByRole('button', { name: '选择方案 B' })).toHaveCount(1)
  const planJobs = submissions.filter(item => item.kind === 'plan_batch')
  const applyJobs = submissions.filter(item => item.kind === 'apply_batch')
  expect(planJobs).toHaveLength(2)
  expect(planJobs[0].culture_mechanism_ids).toEqual(['SET01'])
  expect(planJobs[1].culture_mechanism_ids).toEqual(['CM01'])
  expect(applyJobs).toHaveLength(1)
  expect(applyJobs[0].adaptations?.map(item => item.culture_mechanism_id)).toEqual(['SET01'])

  const saved = await active(page)
  expect(saved.adaptationFlow).toEqual({ phase: 'culture', activeIds: ['CM01'], deferredIds: [] })
  const exported = await page.evaluate(async id => (await fetch(`/api/projects/${id}/data-export`)).json(), saved.projectId)
  const culturePlan = exported.plans.find((plan: { culture_mechanism_id: string }) => plan.culture_mechanism_id === 'CM01')
  expect(culturePlan.based_on_version).toBe(exported.state.version)
  expect(exported.state.settings[0].adapted_to).toBeTruthy()
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
  let repairSubmissions = 0
  let blockFirstVerification = true
  page.on('request', request => {
    if (request.method() !== 'POST' || !request.url().endsWith('/jobs')) return
    if (request.postDataJSON().kind === 'render') renderSubmissions++
    if (request.postDataJSON().kind === 'repair') repairSubmissions++
  })
  await page.route('**/api/projects/*/jobs', async route => {
    const body = route.request().postDataJSON()
    if (body.kind === 'repair') {
      await route.continue({ postData: JSON.stringify({ ...body, kind: 'verify' }) })
      return
    }
    await route.continue()
  })
  await page.route('**/api/jobs/*', async route => {
    const response = await route.fetch()
    const data = await response.json()
    if (blockFirstVerification && data.kind === 'verify' && data.status === 'done') {
      blockFirstVerification = false
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
  await page.getByRole('button', { name: '按检查结果修复', exact: true }).first().click()
  await expect(page.getByRole('heading', { name: 'English 完整剧本' })).toBeVisible({ timeout: 30000 })
  expect(repairSubmissions).toBe(1)
  expect(renderSubmissions).toBe(1)
})

test('review choices distinguish keep from modify and survive refresh', async ({ page }) => {
  await ready(page); await importDemo(page); await analyzeAndPlan(page)
  await page.getByRole('button', { name: '生成改编剧本' }).click()
  await expect(page.getByRole('heading', { name: 'English 完整剧本' })).toBeVisible({ timeout: 45000 })
  // Present two uncertain findings to exercise the decision UI independently
  // from the model. Backend scope enforcement has separate workflow tests.
  await page.route('**/api/projects/*/verification', async route => {
    const response = await route.fetch()
    const report = await response.json()
    await route.fulfill({ response, json: { ...report, overall_status: 'needs_review', review_token: 'review-fixture', commitment_checks: [], issues: [
      { severity: 'warning', issue_type: 'fact_conflict', scene_id: 'S01', description: '可能需要调整称谓' },
      { severity: 'warning', issue_type: 'motivation_break', scene_id: null, description: '可能需要重建因果关联' },
    ] } })
  })
  await page.route('**/api/projects/*/verification/review', async route => {
    const body = route.request().postDataJSON()
    expect(body.kept_issue_indexes).toEqual([0])
    await route.fulfill({ json: { review_token: 'review-fixture', issues: [], commitment_checks: [], kept_issue_indexes: [0] } })
  })
  await page.reload()
  await expect(page.getByText('待你确认', { exact: true })).toHaveCount(2)
  await expect(page.getByRole('button', { name: '修复错误及已确认项目' })).toHaveCount(0)
  await page.getByRole('button', { name: '无需修改', exact: true }).first().click()
  await expect(page.getByText('已确认保留', { exact: true })).toBeVisible()
  await expect(page.getByRole('button', { name: '修复错误及已确认项目' })).toHaveCount(0)
  await page.getByRole('button', { name: '需要修改', exact: true }).nth(1).click()
  await page.reload()
  await expect(page.getByRole('button', { name: '无需修改', exact: true }).first()).toHaveAttribute('aria-pressed', 'true')
  await expect(page.getByRole('button', { name: '需要修改', exact: true }).nth(1)).toHaveAttribute('aria-pressed', 'true')
  await page.route('**/api/projects/*/jobs', async route => {
    await route.fulfill({ status: 429, json: { detail: { message: '测试暂停提交' } } })
  })
  const submitted = page.waitForRequest(request => request.method() === 'POST' && request.url().endsWith('/jobs'))
  await page.getByRole('button', { name: '修复错误及已确认项目' }).click()
  expect((await submitted).postDataJSON()).toMatchObject({
    kind: 'repair', based_on_report: 'review-fixture', review_issue_indexes: [1], review_commitment_ids: [],
  })
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
})

test('personal suggestion alone survives reload and creates a revised result', async ({ page }) => {
  await ready(page); await importDemo(page); await analyzeAndPlan(page)
  await page.getByRole('button', { name: '生成改编剧本' }).click()
  await expect(page.getByRole('heading', { name: 'English 完整剧本' })).toBeVisible({ timeout: 45000 })
  await page.getByText('检查详情', { exact: true }).click()
  const note = '女主这段台词更坚定，保留双方关系。'
  await page.getByLabel('补充问题或改进建议').fill('   ')
  await expect(page.getByRole('button', { name: '按问题和建议修改' })).toHaveCount(0)
  await page.getByLabel('补充问题或改进建议').fill(note)
  await page.getByLabel('建议适用范围').selectOption('S03')
  await page.reload()
  await page.getByText('检查详情', { exact: true }).click()
  await expect(page.getByLabel('补充问题或改进建议')).toHaveValue(note)
  await expect(page.getByLabel('建议适用范围')).toHaveValue('S03')
  const submission = page.waitForRequest(request => request.method() === 'POST' && request.url().endsWith('/jobs') && request.postDataJSON().kind === 'repair')
  await page.getByRole('button', { name: '按问题和建议修改' }).click()
  expect((await submission).postDataJSON()).toMatchObject({ repair_suggestion: note, repair_scene_ids: ['S03'] })
  await expect.poll(async () => (await active(page)).repairNote?.text).toBe('')
  await expect.poll(async () => (await active(page)).task?.status).toBe('done')
  await expect(page.getByRole('heading', { name: 'English 完整剧本' })).toBeVisible()
  const pid = (await active(page)).projectId
  const data = await page.evaluate(async id => (await fetch(`/api/projects/${id}/data-export`)).json(), pid)
  expect(data.revisions.at(-1)).toMatchObject({ kind: 'repair', changed_scene_ids: ['S03'], applied_option: { repair_suggestion: note } })
  expect(data.target_script.source_state_version).toBe(data.state.version)
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
})

test('blocking errors and violated commitments can be kept without rewriting', async ({ page }) => {
  await ready(page); await importDemo(page); await analyzeAndPlan(page)
  await page.getByRole('button', { name: '生成改编剧本' }).click()
  await expect(page.getByRole('heading', { name: 'English 完整剧本' })).toBeVisible({ timeout: 45000 })
  await page.route('**/api/projects/*/verification', async route => {
    const response = await route.fetch()
    const report = await response.json()
    await route.fulfill({ response, json: { ...report, overall_status: 'fail', issues: [
      { severity: 'error', issue_type: 'fact_conflict', scene_id: 'S01', description: '前世与重生后的成绩不同' },
    ], commitment_checks: [{ commitment_id: 'NC01', status: 'violated', explanation: '前世事件没有在重生后重演' }] } })
  })
  await page.reload()
  await expect(page.getByRole('button', { name: '需要修改', exact: true })).toHaveCount(2)
  await page.getByRole('button', { name: '无需修改', exact: true }).first().click()
  await page.getByRole('button', { name: '无需修改', exact: true }).nth(1).click()
  await page.reload()
  await expect(page.getByRole('button', { name: '无需修改', exact: true }).first()).toHaveAttribute('aria-pressed', 'true')
  const submittedKinds: string[] = []
  page.on('request', request => {
    if (request.method() === 'POST' && request.url().endsWith('/jobs')) submittedKinds.push(request.postDataJSON().kind)
  })
  await page.route('**/api/projects/*/verification/review', async route => {
    const body = route.request().postDataJSON()
    expect(body.kept_issue_indexes).toEqual([0])
    expect(body.kept_commitment_ids).toEqual(['NC01'])
    await route.fulfill({ json: { review_token: body.based_on_report, overall_status: 'pass', issues: [], commitment_checks: [], ...body } })
  })
  await page.getByRole('button', { name: '确认保留并继续' }).click()
  await expect.poll(async () => (await active(page)).task?.status).toBe('done')
  expect(submittedKinds).toEqual(['render'])
})
