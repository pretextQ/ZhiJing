import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { nextTick } from 'vue'
import { describe, expect, it, vi } from 'vitest'
import ThemePanel from '../components/ThemePanel.vue'
import { useThemesStore } from '../stores/themes'
import type { Theme } from '../themes'

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
}

function mountPanel() {
  const pinia = createPinia()
  setActivePinia(pinia)
  const store = useThemesStore()
  const wrapper = mount(ThemePanel, { global: { plugins: [pinia] } })
  return { store, wrapper }
}

const customTheme: Theme = {
  id: 'abc123abc123',
  name: '合成主题',
  backgroundUrl: '/api/study/themes/abc123abc123/background',
  coverUrl: '/api/study/themes/abc123abc123/cover',
  backgroundVideoUrl: null,
  ambientUrl: null,
  builtin: false,
  motion: 'none',
}

describe('ThemePanel', () => {
  it('renders the built-in cards, applied badge and default import limits', () => {
    const { wrapper } = mountPanel()
    const cards = wrapper.findAll('[data-theme-id]')
    expect(cards).toHaveLength(11)
    expect(cards.map((card) => card.attributes('data-theme-id'))).toEqual([
      'forest',
      'rain',
      'library',
      'morning',
      'seaside',
      'train',
      'pixel',
      'palms',
      'whitecat',
      'water',
      'anime',
    ])
    expect(cards.every((card) => card.attributes('data-kind') === 'builtin')).toBe(true)
    expect(wrapper.get('[data-theme-id="forest"]').attributes('data-applied')).toBe('true')
    expect(wrapper.get('[data-theme-id="rain"]').attributes('data-applied')).toBeUndefined()
    expect(wrapper.get('[data-theme-id="forest"] .scene-badge').text()).toBe('使用中')
    expect(wrapper.text()).toContain('夜间图书馆')
    expect(wrapper.text()).toContain('ZIP ≤ 32 MiB · 解压 ≤ 64 MiB · 最多 32 个文件')
    expect(wrapper.text()).toContain('还没有导入主题，可从电脑选择 ZIP 主题包。')
    const motion = wrapper.get('input[aria-label="背景动效"]')
    expect((motion.element as HTMLInputElement).checked).toBe(true)
    expect(wrapper.get('.scene-apply .primary-button').attributes('disabled')).toBeDefined()
  })

  it('previews a card and applies the selection through the store', async () => {
    const { store, wrapper } = mountPanel()
    await wrapper.get('[data-theme-id="morning"] .scene-pick').trigger('click')
    expect(wrapper.text()).toContain('正在预览：清晨书桌')
    expect(wrapper.get('[data-theme-id="morning"]').attributes('data-preview')).toBe('true')
    expect(wrapper.get('[data-theme-id="morning"] .scene-badge').text()).toBe('预览')
    const apply = wrapper.get('.scene-apply .primary-button')
    expect(apply.attributes('disabled')).toBeUndefined()
    await apply.trigger('click')
    expect(store.appliedId).toBe('morning')
    expect(JSON.parse(localStorage.getItem('zhijing:scene') ?? 'null')).toBe('morning')
    expect(wrapper.emitted('close')).toHaveLength(1)
  })

  it('loads limits and custom themes from the API and mirrors motion preferences', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn((input: RequestInfo | URL) => {
        const url = String(input)
        if (url.endsWith('/limits')) {
          return Promise.resolve(jsonResponse({ max_archive_mb: 16, max_expanded_mb: 24, max_entries: 12 }))
        }
        return Promise.resolve(
          jsonResponse([
            {
              id: customTheme.id,
              name: customTheme.name,
              background_url: customTheme.backgroundUrl,
              cover_url: customTheme.coverUrl,
            },
          ]),
        )
      }),
    )
    const { store, wrapper } = mountPanel()
    store.init()
    await flushPromises()
    expect(wrapper.text()).toContain('ZIP ≤ 16 MiB · 解压 ≤ 24 MiB · 最多 12 个文件')
    const custom = wrapper.get('[data-kind="custom"]')
    expect(custom.attributes('data-theme-id')).toBe(customTheme.id)
    expect(custom.text()).toContain('合成主题')

    store.reducedMotion = true
    store.motionEnabled = false
    await nextTick()
    expect(wrapper.text()).toContain('系统已要求减少动态效果，动效已停用')
    expect((wrapper.get('input[aria-label="背景动效"]').element as HTMLInputElement).checked).toBe(false)
    expect(wrapper.get('input[aria-label="背景动效"]').attributes('title')).toContain('系统已开启减少动态效果')
  })

  it('imports a package through the API, previews it and reports duplicates', async () => {
    vi.stubGlobal(
      'fetch',
      vi
        .fn()
        .mockResolvedValue(
          jsonResponse({ id: customTheme.id, name: '合成导入', background_url: '/assets/background.png' }),
        ),
    )
    const { store, wrapper } = mountPanel()
    const input = wrapper.get('input[type="file"]')
    Object.defineProperty(input.element, 'files', {
      configurable: true,
      value: [new File(['zip'], 'theme.zip', { type: 'application/zip' })],
    })
    await input.trigger('change')
    await flushPromises()
    expect(wrapper.text()).toContain('已导入：合成导入')
    expect(wrapper.text()).toContain('正在预览：合成导入')
    expect(store.customThemes).toHaveLength(1)
    expect(wrapper.get('[data-kind="custom"]').attributes('data-preview')).toBe('true')
  })

  it('keeps rename and delete-confirm Escape handling inside the panel', async () => {
    const { store, wrapper } = mountPanel()
    store.customThemes = [customTheme]
    await nextTick()
    const exposed = wrapper.vm as unknown as { handleEscape: () => boolean }

    await wrapper.get('button[aria-label^="重命名主题"]').trigger('click')
    expect(wrapper.find('input[aria-label="主题名称"]').exists()).toBe(true)
    expect(exposed.handleEscape()).toBe(true)
    await nextTick()
    expect(wrapper.find('input[aria-label="主题名称"]').exists()).toBe(false)

    await wrapper.get('button[aria-label^="删除主题"]').trigger('click')
    expect(wrapper.text()).toContain('删除这个主题？')
    expect(exposed.handleEscape()).toBe(true)
    await nextTick()
    expect(wrapper.text()).not.toContain('删除这个主题？')
    expect(exposed.handleEscape()).toBe(false)
  })

  it('exposes focusFirst for the shell trigger', () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    const wrapper = mount(ThemePanel, { attachTo: document.body, global: { plugins: [pinia] } })
    ;(wrapper.vm as unknown as { focusFirst: () => void }).focusFirst()
    expect(document.activeElement?.classList.contains('scene-pick')).toBe(true)
    wrapper.unmount()
  })
})
