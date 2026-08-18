// 统一的请求工具：自动带登录凭证，凭证失效自动退出登录
export async function apiFetch(url, options = {}) {
  const token = localStorage.getItem('token')
  const headers = { ...options.headers }

  if (options.body && !headers['Content-Type']) {
    headers['Content-Type'] = 'application/json'
  }
  if (token) {
    headers['Authorization'] = 'Bearer ' + token
  }

  const res = await fetch(url, { ...options, headers })

  if (res.status === 401) {
    // 登录已失效：清除本地登录状态并刷新回登录页
    localStorage.removeItem('token')
    localStorage.removeItem('username')
    window.location.reload()
    throw new Error('登录已失效')
  }
  return res
}
