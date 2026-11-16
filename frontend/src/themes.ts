import { CloudRain, Gamepad2, LibraryBig, Sailboat, Sunrise, TrainFront } from '@lucide/vue'
import type { Component } from 'vue'
import library from './assets/library.jpg'
import morning from './assets/morning.jpg'
import pixel from './assets/pixel.jpg'
import rain from './assets/rain.jpg'
import seaside from './assets/seaside.jpg'
import train from './assets/train.jpg'

export interface Theme {
  id: string
  name: string
  backgroundUrl: string
  coverUrl: string
  ambientUrl: string | null
  builtin: boolean
  icon?: Component
}

export const DEFAULT_THEME_ID = 'rain'

export const builtinThemes: readonly Theme[] = [
  { id: 'rain', name: '雨窗', backgroundUrl: rain, coverUrl: rain, ambientUrl: null, builtin: true, icon: CloudRain },
  { id: 'library', name: '夜间图书馆', backgroundUrl: library, coverUrl: library, ambientUrl: null, builtin: true, icon: LibraryBig },
  { id: 'morning', name: '清晨书桌', backgroundUrl: morning, coverUrl: morning, ambientUrl: null, builtin: true, icon: Sunrise },
  { id: 'seaside', name: '海边木屋', backgroundUrl: seaside, coverUrl: seaside, ambientUrl: null, builtin: true, icon: Sailboat },
  { id: 'train', name: '暮色列车', backgroundUrl: train, coverUrl: train, ambientUrl: null, builtin: true, icon: TrainFront },
  { id: 'pixel', name: '像素夏夜', backgroundUrl: pixel, coverUrl: pixel, ambientUrl: null, builtin: true, icon: Gamepad2 },
]

const API = '/api/study/themes'

export class ThemeError extends Error {
  constructor(message: string) {
    super(message)
    this.name = 'ThemeError'
  }
}

export function findTheme(id: string, custom: readonly Theme[] = []): Theme | undefined {
  return builtinThemes.find(item => item.id === id) ?? custom.find(item => item.id === id)
}

export function themeMessage(error: unknown): string {
  return error instanceof ThemeError ? error.message : '无法连接知径，请确认本地服务正在运行'
}

function detailText(detail: unknown): string | null {
  if (typeof detail === 'string' && detail.trim()) return detail
  if (Array.isArray(detail)) {
    const messages = detail
      .map(item => (item && typeof (item as { msg?: unknown }).msg === 'string' ? (item as { msg: string }).msg : ''))
      .filter(message => message.length > 0)
    if (messages.length) return messages.join('；')
  }
  return null
}

async function failure(response: Response): Promise<string> {
  const body = await response.json().catch(() => null)
  return detailText((body as { detail?: unknown } | null)?.detail)
    ?? (response.status === 413 ? '主题包超过上传大小限制' : '主题请求失败，请稍后重试')
}

function toTheme(payload: unknown): Theme | null {
  if (!payload || typeof payload !== 'object') return null
  const item = payload as Record<string, unknown>
  if (typeof item.id !== 'string' || !item.id) return null
  if (typeof item.background_url !== 'string' || !item.background_url) return null
  const coverUrl = typeof item.cover_url === 'string' && item.cover_url ? item.cover_url : item.background_url
  const ambientUrl = typeof item.ambient_url === 'string' && item.ambient_url ? item.ambient_url : null
  const name = typeof item.name === 'string' && item.name.trim() ? item.name : item.id
  return { id: item.id, name, backgroundUrl: item.background_url, coverUrl, ambientUrl, builtin: false }
}

export async function listThemes(): Promise<Theme[]> {
  const response = await fetch(API, { cache: 'no-store' })
  if (!response.ok) throw new ThemeError(await failure(response))
  const payload: unknown = await response.json().catch(() => null)
  if (!Array.isArray(payload)) throw new ThemeError('主题库数据格式不正确')
  return payload.map(toTheme).filter((item): item is Theme => item !== null)
}

export async function importTheme(file: File): Promise<Theme> {
  const response = await fetch(API, {
    method: 'POST',
    headers: { 'Content-Type': 'application/zip' },
    body: file,
  })
  if (!response.ok) throw new ThemeError(await failure(response))
  const theme = toTheme(await response.json().catch(() => null))
  if (!theme) throw new ThemeError('主题包已保存，但返回的主题信息不完整')
  return theme
}

export async function removeTheme(id: string): Promise<void> {
  const response = await fetch(`${API}/${encodeURIComponent(id)}`, { method: 'DELETE' })
  if (!response.ok && response.status !== 404) throw new ThemeError(await failure(response))
}
