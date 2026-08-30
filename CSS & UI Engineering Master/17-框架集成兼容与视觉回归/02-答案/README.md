# 答案与复盘

## 题 1

主题 token 放全局 tokens layer，因此 portal/Teleport 只要仍在带主题属性的 document 范围即可继承。组件结构样式随组件发布；第三方 adapter 放 vendor/overrides 的限定 root。Vue 子组件用 props/class/token 公开契约，`:deep()` 只作为有 owner 的临时边界。

SSR 在服务端从 cookie/请求偏好输出 `data-theme`，客户端使用同一初值 hydrate；不要 mounted 后才决定。CSS layer 的声明顺序在入口预注册，即使 route chunk 后到也进入正确层。

## 题 2

```ts
test.use({ colorScheme: 'dark', reducedMotion: 'reduce' })

test('dashboard dark 768', async ({ page }) => {
  await page.goto('/fixtures/dashboard?locale=ar&density=compact')
  await page.evaluate(() => document.fonts.ready)
  await expect(page).toHaveScreenshot('dashboard-ar-dark-768.png', {
    animations: 'disabled',
  })
})
```

项目需在固定 OS/浏览器镜像生成 baseline。组件矩阵全覆盖高风险状态，页面测试只覆盖关键组合，避免笛卡尔爆炸。非零 diff 先关联需求/浏览器更新，由人确认后更新；记录批准者和原因。视觉测试之外仍跑 DOM 行为、axe 和人工键盘检查。

