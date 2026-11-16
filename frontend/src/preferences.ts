export function readLocal<T>(key: string): T | null {
  try {
    const value = localStorage.getItem(`zhijing:${key}`)
    return value ? JSON.parse(value) : null
  } catch {
    return null
  }
}

export function writeLocal(key: string, value: unknown): boolean {
  try {
    if (value === null) localStorage.removeItem(`zhijing:${key}`)
    else localStorage.setItem(`zhijing:${key}`, JSON.stringify(value))
    return true
  } catch {
    return false
  }
}
