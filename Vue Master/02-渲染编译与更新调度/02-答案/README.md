# 答案与复盘

## 题 1

索引 key 把第 1 个位置的新商品与旧组件实例绑定，实例内未提交状态因此留在位置而不是商品上。正确修复是 `:key="product.id"`，并进一步判断编辑草稿应属于行组件本地状态还是按 `productId` 管理的显式状态。随机 key 每次 render 都变化，Vue 只能卸载并重建全部节点，焦点、局部状态与性能一起丢失。

```ts
it('draft follows product identity after sort', async () => {
  const wrapper = mount(ProductTable, { props: { products } })
  const inputs = wrapper.findAll('input')
  await inputs[1].setValue('draft-B')
  await wrapper.get('[data-test=sort]').trigger('click')
  const rowB = wrapper.get('[data-product-id="b"]')
  expect((rowB.get('input').element as HTMLInputElement).value).toBe('draft-B')
})
```

测试应从用户可见 DOM 定位业务实体，不能断言组件内部 `vm.draft`。

## 题 2

三处高收益改动示例：父组件给每行传布尔值 `:selected="row.id === selectedId"`，而非把持续变化的 selectedId 传给全部行；稳定事件处理函数，不在模板创建包含变化闭包的对象；分页或窗口化只渲染可视区域。若行数据由每次计算产生新对象，先保证引用稳定。

证明过程：优化前后记录相同交互的 Vue Devtools performance timeline；在 Row 临时使用 `onRenderTriggered` 确认触发键；浏览器 Performance 比较 scripting、rendering、节点数与长任务。只报“感觉快了”不合格。

虚拟列表减少 DOM 数量、布局/绘制和 VNode patch 范围；它不能修复每行昂贵计算、事件泄漏、网络过量、错误的响应式依赖。若 30 个可视行仍每次做重型排序，窗口化也救不了架构问题。

