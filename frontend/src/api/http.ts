const API_BASE = '/api'

export class RequestError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message)
    this.name = 'RequestError'
  }
}

export interface RequestOptions {
  method?: string
  body?: object
}

export function errorDetail(body: unknown): string | null {
  if (!body || typeof body !== 'object') return null
  const detail = (body as { detail?: unknown }).detail
  if (typeof detail === 'string' && detail.trim()) return detail
  if (Array.isArray(detail)) {
    const messages = detail
      .map((item) => (item && typeof (item as { msg?: unknown }).msg === 'string' ? (item as { msg: string }).msg : ''))
      .filter((message) => message.length > 0)
    return messages.length ? messages.join('；') : null
  }
  return null
}

/**
 * 统一的 JSON 请求入口。接入 OpenAPI 生成类型后，用生成模型替换泛型 T
 * （或在此函数内部改用生成的客户端），调用方无需改动。
 */
export async function requestJson<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = 'GET', body } = options
  const response = await fetch(`${API_BASE}${path}`, {
    method,
    cache: 'no-store',
    headers: body ? { 'Content-Type': 'application/json' } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  })
  if (!response.ok) {
    const payload = await response.json().catch(() => null)
    throw new RequestError(errorDetail(payload) ?? '请求失败，请检查输入后重试', response.status)
  }
  return response.json() as Promise<T>
}

export { API_BASE }
