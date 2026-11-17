import { describe, expect, it, vi } from 'vitest'
import {
  DEFAULT_THEME_ID,
  DEFAULT_THEME_LIMITS,
  ThemeError,
  builtinThemes,
  findTheme,
  getThemeLimits,
  importTheme,
  listThemes,
  themeMessage,
} from '../themes'

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
}

describe('builtin theme catalogue', () => {
  it('keeps the built-in themes in product order with stable ids', () => {
    expect(builtinThemes.map((theme) => theme.id)).toEqual(['forest', 'palms', 'whitecat', 'water', 'anime'])
    expect(builtinThemes.map((theme) => theme.name)).toEqual([
      '森林小船',
      '椰林夜海',
      '雨窗小猫',
      '水面治愈',
      '动画光斑',
    ])
    expect(builtinThemes.every((theme) => theme.builtin && theme.coverUrl.length > 0 && theme.icon)).toBe(true)
    expect(builtinThemes.every((theme) => theme.ambientUrl === null)).toBe(true)
    const animated = builtinThemes.filter((theme) => theme.backgroundVideoUrl !== null)
    expect(animated.map((theme) => theme.id)).toEqual(['water', 'anime'])
    // The still used as the poster must not be the video itself.
    expect(builtinThemes.every((theme) => !theme.coverUrl.endsWith('.mp4'))).toBe(true)
  })

  it('uses the forest scene as the default theme', () => {
    expect(DEFAULT_THEME_ID).toBe('forest')
    expect(builtinThemes[0].id).toBe('forest')
  })

  it('finds built-in and custom themes by id', () => {
    expect(findTheme('forest')?.name).toBe('森林小船')
    expect(findTheme('rain')).toBeUndefined()
    expect(findTheme('missing')).toBeUndefined()
    const custom = { ...builtinThemes[0], id: 'abc123abc123', name: '合成主题', builtin: false, icon: undefined }
    expect(findTheme('abc123abc123', [custom])?.name).toBe('合成主题')
  })
})

describe('getThemeLimits fallbacks', () => {
  it('returns backend defaults when the request fails', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('offline')))
    await expect(getThemeLimits()).resolves.toEqual(DEFAULT_THEME_LIMITS)
  })

  it('returns backend defaults when the endpoint is unavailable', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse({ detail: 'not found' }, 404)))
    await expect(getThemeLimits()).resolves.toEqual(DEFAULT_THEME_LIMITS)
  })

  it('merges valid fields and falls back for missing or invalid ones', async () => {
    vi.stubGlobal(
      'fetch',
      vi
        .fn()
        .mockResolvedValue(jsonResponse({ max_archive_mb: 16, max_expanded_mb: 0, max_entries: 12.5, unknown: true })),
    )
    await expect(getThemeLimits()).resolves.toEqual({ maxArchiveMb: 16, maxExpandedMb: 64, maxEntries: 32 })
  })

  it('returns backend defaults for a non-object payload', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse([])))
    await expect(getThemeLimits()).resolves.toEqual(DEFAULT_THEME_LIMITS)
  })
})

describe('custom theme API mapping', () => {
  it('maps snake_case payloads and drops malformed entries', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        jsonResponse([
          {
            id: 'abc123abc123',
            name: '合成主题',
            background_url: '/api/study/themes/abc123abc123/background',
            cover_url: '/api/study/themes/abc123abc123/cover',
            ambient_url: '/api/study/themes/abc123abc123/ambient',
            background_video_url: '/api/study/themes/abc123abc123/video',
          },
          { id: '', background_url: '/x' },
          { id: 'nocover', background_url: '/bg' },
        ]),
      ),
    )
    const themes = await listThemes()
    expect(themes).toHaveLength(2)
    expect(themes[0]).toMatchObject({
      id: 'abc123abc123',
      name: '合成主题',
      builtin: false,
      motion: 'none',
      ambientUrl: '/api/study/themes/abc123abc123/ambient',
      backgroundVideoUrl: '/api/study/themes/abc123abc123/video',
    })
    expect(themes[1]).toMatchObject({ id: 'nocover', coverUrl: '/bg', ambientUrl: null, backgroundVideoUrl: null })
  })

  it('rejects a non-array payload', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse({ detail: 'nope' })))
    await expect(listThemes()).rejects.toBeInstanceOf(ThemeError)
  })

  it('passes detail messages from the API through to the UI', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(jsonResponse({ detail: [{ msg: '缺少背景文件' }, { msg: '清单版本不受支持' }] }, 422)),
    )
    await expect(importTheme(new File(['zip'], 'theme.zip', { type: 'application/zip' }))).rejects.toThrow(
      '缺少背景文件；清单版本不受支持',
    )
  })

  it('keeps the generic theme error message for network failures', () => {
    expect(themeMessage(new ThemeError('主题请求失败'))).toBe('主题请求失败')
    expect(themeMessage(new Error('offline'))).toBe('无法连接知径，请确认本地服务正在运行')
  })
})
