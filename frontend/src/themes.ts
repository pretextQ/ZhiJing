import { CloudRain, Moon, Sunrise, Trees, Waves } from '@lucide/vue'
import type { Component } from 'vue'
import { API_BASE, errorDetail } from './api/http'
import type { ThemeCardDto, ThemeLimitsDto } from './api/types'
import animeLoop from './assets/anime-loop.mp4'
import animePoster from './assets/anime-poster.jpg'
import forest from './assets/forest.jpg'
import palms from './assets/palms.jpg'
import waterLoop from './assets/water-loop.mp4'
import waterPoster from './assets/water-poster.jpg'
import whitecat from './assets/whitecat.jpg'

export type ThemeMotion = 'zoom' | 'drift' | 'none'

export interface Theme {
  id: string
  name: string
  backgroundUrl: string
  coverUrl: string
  backgroundVideoUrl: string | null
  ambientUrl: string | null
  builtin: boolean
  motion: ThemeMotion
  icon?: Component
}

export interface ThemeLimits {
  maxArchiveMb: number
  maxExpandedMb: number
  maxEntries: number
}

export interface ExportedTheme {
  blob: Blob
  filename: string
}

export const DEFAULT_THEME_ID = 'forest'

/** Fallbacks mirror the backend defaults when GET /limits is unavailable. */
export const DEFAULT_THEME_LIMITS: ThemeLimits = { maxArchiveMb: 32, maxExpandedMb: 64, maxEntries: 32 }

export const builtinThemes: readonly Theme[] = [
  {
    id: 'forest',
    name: '森林小船',
    backgroundUrl: forest,
    coverUrl: forest,
    backgroundVideoUrl: null,
    ambientUrl: null,
    builtin: true,
    motion: 'drift',
    icon: Trees,
  },
  {
    id: 'palms',
    name: '椰林夜海',
    backgroundUrl: palms,
    coverUrl: palms,
    backgroundVideoUrl: null,
    ambientUrl: null,
    builtin: true,
    motion: 'drift',
    icon: Moon,
  },
  {
    id: 'whitecat',
    name: '雨窗小猫',
    backgroundUrl: whitecat,
    coverUrl: whitecat,
    backgroundVideoUrl: null,
    ambientUrl: null,
    builtin: true,
    motion: 'drift',
    icon: CloudRain,
  },
  {
    id: 'water',
    name: '水面治愈',
    backgroundUrl: waterPoster,
    coverUrl: waterPoster,
    backgroundVideoUrl: waterLoop,
    ambientUrl: null,
    builtin: true,
    motion: 'none',
    icon: Waves,
  },
  {
    id: 'anime',
    name: '动画光斑',
    backgroundUrl: animePoster,
    coverUrl: animePoster,
    backgroundVideoUrl: animeLoop,
    ambientUrl: null,
    builtin: true,
    motion: 'none',
    icon: Sunrise,
  },
]

const API = `${API_BASE}/study/themes`

export class ThemeError extends Error {
  constructor(message: string) {
    super(message)
    this.name = 'ThemeError'
  }
}

export function findTheme(id: string, custom: readonly Theme[] = []): Theme | undefined {
  return builtinThemes.find((item) => item.id === id) ?? custom.find((item) => item.id === id)
}

export function themeMessage(error: unknown): string {
  return error instanceof ThemeError ? error.message : '无法连接知径，请确认本地服务正在运行'
}

async function failure(response: Response): Promise<string> {
  const body = await response.json().catch(() => null)
  return errorDetail(body) ?? (response.status === 413 ? '主题包超过上传大小限制' : '主题请求失败，请稍后重试')
}

/**
 * 把生成类型 ThemeCardDto 映射成前端主题模型。
 * 后端契约由 openapi-typescript 生成，此处只做 snake_case → camelCase 与运行时兜底。
 */
function toTheme(payload: ThemeCardDto | null | undefined): Theme | null {
  if (!payload || typeof payload !== 'object') return null
  const item = payload as Partial<ThemeCardDto>
  if (typeof item.id !== 'string' || !item.id) return null
  if (typeof item.background_url !== 'string' || !item.background_url) return null
  const coverUrl = typeof item.cover_url === 'string' && item.cover_url ? item.cover_url : item.background_url
  const ambientUrl = typeof item.ambient_url === 'string' && item.ambient_url ? item.ambient_url : null
  const backgroundVideoUrl =
    typeof item.background_video_url === 'string' && item.background_video_url ? item.background_video_url : null
  const name = typeof item.name === 'string' && item.name.trim() ? item.name : item.id
  return {
    id: item.id,
    name,
    backgroundUrl: item.background_url,
    coverUrl,
    backgroundVideoUrl,
    ambientUrl,
    builtin: false,
    motion: 'none',
  }
}

function safeZipName(value: string): string {
  const base = value.split(/[\\/]/).pop()?.trim() || 'theme'
  return /\.zip$/i.test(base) ? base : `${base}.zip`
}

/** Prefer RFC 5987 filename*, then a quoted filename, then the theme name. */
function downloadName(header: string | null, fallbackName: string): string {
  if (header) {
    const extended = /filename\*\s*=\s*([^;]+)/i.exec(header)
    if (extended) {
      const raw = extended[1].trim().replace(/^"|"$/g, '')
      const parts = /^[^']*'[^']*'(.*)$/.exec(raw)
      if (parts) {
        try {
          const decoded = decodeURIComponent(parts[1])
          if (decoded.trim()) return safeZipName(decoded)
        } catch {
          // Fall through to the plain filename parameter.
        }
      }
    }
    const plain = /filename\s*=\s*("([^"]*)"|[^;]+)/i.exec(header)
    if (plain) {
      const raw = (plain[2] ?? plain[1]).trim()
      try {
        const decoded = decodeURIComponent(raw)
        if (decoded.trim()) return safeZipName(decoded)
      } catch {
        // Fall through to the theme name.
      }
    }
  }
  return safeZipName(fallbackName)
}

function positiveInteger(value: unknown): number | null {
  return typeof value === 'number' && Number.isInteger(value) && value > 0 ? value : null
}

export async function listThemes(): Promise<Theme[]> {
  const response = await fetch(API, { cache: 'no-store' })
  if (!response.ok) throw new ThemeError(await failure(response))
  const payload: unknown = await response.json().catch(() => null)
  if (!Array.isArray(payload)) throw new ThemeError('主题库数据格式不正确')
  return payload.map((item) => toTheme(item as ThemeCardDto)).filter((item): item is Theme => item !== null)
}

export async function importTheme(file: File): Promise<Theme> {
  const response = await fetch(API, {
    method: 'POST',
    headers: { 'Content-Type': 'application/zip' },
    body: file,
  })
  if (!response.ok) throw new ThemeError(await failure(response))
  const theme = toTheme((await response.json().catch(() => null)) as ThemeCardDto | null)
  if (!theme) throw new ThemeError('主题包已保存，但返回的主题信息不完整')
  return theme
}

export async function removeTheme(id: string): Promise<void> {
  const response = await fetch(`${API}/${encodeURIComponent(id)}`, { method: 'DELETE' })
  if (!response.ok && response.status !== 404) throw new ThemeError(await failure(response))
}

export async function renameTheme(id: string, name: string): Promise<Theme> {
  const response = await fetch(`${API}/${encodeURIComponent(id)}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name }),
  })
  if (!response.ok) throw new ThemeError(await failure(response))
  const theme = toTheme((await response.json().catch(() => null)) as ThemeCardDto | null)
  if (!theme) throw new ThemeError('主题已重命名，但返回的主题信息不完整')
  return theme
}

export async function exportTheme(id: string, fallbackName: string): Promise<ExportedTheme> {
  const response = await fetch(`${API}/${encodeURIComponent(id)}/export`, { cache: 'no-store' })
  if (!response.ok) throw new ThemeError(await failure(response))
  const blob = await response.blob()
  if (!blob.size) throw new ThemeError('导出的主题包为空，请稍后重试')
  return { blob, filename: downloadName(response.headers.get('Content-Disposition'), fallbackName) }
}

export async function getThemeLimits(): Promise<ThemeLimits> {
  try {
    const response = await fetch(`${API}/limits`, { cache: 'no-store' })
    if (!response.ok) return { ...DEFAULT_THEME_LIMITS }
    const payload: unknown = await response.json().catch(() => null)
    if (!payload || typeof payload !== 'object') return { ...DEFAULT_THEME_LIMITS }
    const item = payload as Partial<ThemeLimitsDto>
    return {
      maxArchiveMb: positiveInteger(item.max_archive_mb) ?? DEFAULT_THEME_LIMITS.maxArchiveMb,
      maxExpandedMb: positiveInteger(item.max_expanded_mb) ?? DEFAULT_THEME_LIMITS.maxExpandedMb,
      maxEntries: positiveInteger(item.max_entries) ?? DEFAULT_THEME_LIMITS.maxEntries,
    }
  } catch {
    return { ...DEFAULT_THEME_LIMITS }
  }
}
