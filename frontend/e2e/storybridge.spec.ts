import { expect, test } from '@playwright/test'

test('mock backend full flow survives a page reload', async ({ page }) => {
  await page.goto('/', { waitUntil: 'domcontentloaded' })
  await page.getByLabel('项目名称').fill('E2E 恢复测试')
  await page.getByLabel('中文剧本').fill('S01：相亲饭局。\nS02：父亲反对婚事。')
  await page.getByRole('button', { name: '创建项目并分析' }).click()

  await expect(page.getByText('分析完成，可选择文化机制继续改编')).toBeVisible({ timeout: 30_000 })
  await expect(page).toHaveURL(/\?project=[a-f0-9]{32}/)
  const projectId = new URL(page.url()).searchParams.get('project')
  expect(projectId).toBeTruthy()
  expect(await page.evaluate(() => localStorage.getItem('storybridge.activeProjectId'))).toBe(projectId)

  await page.reload()
  await expect(page.getByText(`Project ${projectId}`)).toBeVisible({ timeout: 30_000 })
  await expect(page.getByRole('heading', { name: '从文化机制到完整改编' })).toBeVisible()

  await page.getByRole('button').filter({ hasText: '彩礼' }).click()
  await expect(page.getByText('2 个文化点', { exact: true })).toBeVisible()
  await page.getByRole('button', { name: '为 2 个点生成方案' }).click()
  const firstPlan = page.locator('.batch-plan').filter({ hasText: 'CM01' })
  const secondPlan = page.locator('.batch-plan').filter({ hasText: 'CM02' })
  await expect(firstPlan.getByRole('button', { name: '选择方案 B' })).toBeVisible({ timeout: 30_000 })
  await firstPlan.getByRole('button', { name: '选择方案 B' }).click()
  await secondPlan.getByRole('button', { name: '选择方案 C' }).click()
  await expect(page.getByText(/个场景需要联动改写/)).toHaveCount(2)
  await expect(page.getByText(/条关系的文字说明/)).toBeVisible()

  await page.getByRole('button', { name: '批量改编 2 个文化点' }).click()
  await expect(page.getByRole('heading', { name: '一致性验证结果' })).toBeVisible({ timeout: 45_000 })
  await expect(page.getByText(/Overall Status/)).toBeVisible()
  await expect(page.getByText('2 个文化点 · 7 个场景已更新')).toBeVisible()

  await page.reload()
  await expect(page.getByText('2 个文化点 · 7 个场景已更新')).toBeVisible({ timeout: 30_000 })
  await expect(page.getByRole('heading', { name: '一致性验证结果' })).toBeVisible()

  await page.getByRole('button', { name: /生成 English 剧本/ }).click()
  await expect(page.getByRole('heading', { name: 'English 完整剧本' })).toBeVisible({ timeout: 30_000 })
  await expect(page.getByText('v2', { exact: true })).toBeVisible()
})
