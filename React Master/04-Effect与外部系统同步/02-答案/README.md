# 第 04 章参考答案

## 练习一：Abort + 身份双保险

```tsx
type SearchState =
  | {status: 'idle'}
  | {status: 'loading'; query: string}
  | {status: 'success'; query: string; users: User[]}
  | {status: 'error'; query: string; message: string}

function useUserSearch(query: string) {
  const [state, setState] = useState<SearchState>({status: 'idle'})

  useEffect(() => {
    const normalized = query.trim()
    if (!normalized) {
      setState({status: 'idle'})
      return
    }

    const controller = new AbortController()
    let current = true
    const timer = window.setTimeout(async () => {
      setState({status: 'loading', query: normalized})
      try {
        const response = await fetch(`/api/users?q=${encodeURIComponent(normalized)}`, {
          signal: controller.signal,
        })
        if (!response.ok) throw new Error(`HTTP ${response.status}`)
        const users: User[] = await response.json()
        if (current) setState({status: 'success', query: normalized, users})
      } catch (error) {
        if (!current || controller.signal.aborted) return
        setState({
          status: 'error',
          query: normalized,
          message: error instanceof Error ? error.message : '未知错误',
        })
      }
    }, 300)

    return () => {
      current = false
      window.clearTimeout(timer)
      controller.abort()
    }
  }, [query])

  return state
}
```

这解决组件级请求，但没有跨组件缓存、去重、预取、失效、SSR、后台刷新和统一重试。真实应用优先让路由/Query 层拥有远端状态，组件只声明数据依赖。

竞态测试的关键是让 A、B Promise 由测试手动 resolve，而不是依赖真实时间；断言 B resolve 后显示 B，随后 A resolve 也不改变 UI。

## 练习二：React 19.2

```tsx
function Chat({roomId, theme, mutedWords}: Props) {
  const onConnected = useEffectEvent(() => showToast('已连接', theme))
  const onMessage = useEffectEvent((message: Message) => {
    if (!mutedWords.some(word => message.text.includes(word))) appendMessage(message)
  })

  useEffect(() => {
    const connection = createConnection(roomId)
    connection.on('connected', onConnected)
    connection.on('message', onMessage)
    connection.connect()
    return () => {
      connection.off('connected', onConnected)
      connection.off('message', onMessage)
      connection.disconnect()
    }
  }, [roomId])
}
```

`onConnected/onMessage` 是由 Effect 中外部资源触发的事件；它们读取最新非响应式数据，却不把 theme/mutedWords 变成连接生命周期依赖。

React 18 兼容可封装 latest ref，避免在每处随手使用：

```tsx
function useLatest<T>(value: T) {
  const ref = useRef(value)
  useLayoutEffect(() => { ref.current = value }, [value])
  return ref
}

const themeRef = useLatest(theme)
const mutedRef = useLatest(mutedWords)

useEffect(() => {
  const connection = createConnection(roomId)
  const connected = () => showToast('已连接', themeRef.current)
  const message = (m: Message) => {
    if (!mutedRef.current.some(w => m.text.includes(w))) appendMessage(m)
  }
  connection.on('connected', connected)
  connection.on('message', message)
  connection.connect()
  return () => {
    connection.off('connected', connected)
    connection.off('message', message)
    connection.disconnect()
  }
}, [roomId])
```

ref 方案隐藏了依赖，必须限于“最新事件数据”并有测试；不要用它让本该重同步的 roomId 逃离依赖。

