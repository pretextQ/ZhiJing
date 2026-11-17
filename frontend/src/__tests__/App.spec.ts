import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { nextTick } from 'vue'
import { createMemoryHistory, createRouter, type Router } from 'vue-router'
import { afterEach, describe, expect, it, vi } from 'vitest'
import App from '../App.vue'
import CoursesView from '../views/CoursesView.vue'
import RoomView from '../views/RoomView.vue'

const room = { lessons: [], active: null, obsidian_enabled: false }
const wrappers: VueWrapper[] = []

function jsonResponse(body: unknown) {
  return new Response(JSON.stringify(body), { status: 200, headers: { 'Content-Type': 'application/json' } })
}

function stubApi() {
  vi.stubGlobal(
    'fetch',
    vi.fn((input: RequestInfo | URL) => {
      const url = String(input)
      if (url === '/api/study') return Promise.resolve(jsonResponse(room))
      if (url === '/api/study/themes') return Promise.resolve(jsonResponse([]))
      if (url.endsWith('/limits')) {
        return Promise.resolve(jsonResponse({ max_archive_mb: 32, max_expanded_mb: 64, max_entries: 32 }))
      }
      return Promise.resolve(jsonResponse({ detail: 'unexpected request' }))
    }),
  )
  vi.spyOn(window, 'scrollTo').mockImplementation(() => {})
}

async function mountApp(path = '/'): Promise<{ wrapper: VueWrapper; router: Router }> {
  stubApi()
  const pinia = createPinia()
  setActivePinia(pinia)
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', name: 'room', component: RoomView },
      { path: '/courses', name: 'courses', component: CoursesView },
    ],
    scrollBehavior: () => ({ top: 0 }),
  })
  await router.push(path)
  await router.isReady()
  const wrapper = mount(App, { global: { plugins: [pinia, router] }, attachTo: document.body })
  wrappers.push(wrapper)
  await flushPromises()
  return { wrapper, router }
}

afterEach(() => {
  for (const wrapper of wrappers) wrapper.unmount()
  wrappers.length = 0
  document.body.innerHTML = ''
})

describe('App layout shell', () => {
  it('renders the room route with the timer dock and hidden tool panel', async () => {
    const { wrapper } = await mountApp('/')
    expect(document.title).toBe('自习室 · 知径')
    expect(wrapper.get('#room-title').text()).toBe('自习室')
    expect(wrapper.find('.focus-backdrop').exists()).toBe(true)
    expect(wrapper.get('.course-entry').attributes('href')).toBe('/courses')
    expect(wrapper.get('.focus-dock button').attributes('aria-label')).toBe('切换场景，当前森林小船')
    expect(wrapper.get('#room-tools').isVisible()).toBe(false)
  })

  it('navigates between room and courses with route titles, focus and KeepAlive state', async () => {
    const { wrapper, router } = await mountApp('/')
    const roomTitle = wrapper.get('#room-title').element

    await wrapper.get('.course-entry').trigger('click')
    await flushPromises()
    await nextTick()
    expect(router.currentRoute.value.name).toBe('courses')
    expect(document.title).toBe('看课笔记 · 知径')
    expect(wrapper.get('#course-page-title').text()).toBe('看课笔记')
    expect(document.activeElement?.id).toBe('course-page-title')
    expect(wrapper.get('.back-to-room').attributes('href')).toBe('/')
    expect(wrapper.find('.focus-backdrop').exists()).toBe(false)

    await wrapper.get('.back-to-room').trigger('click')
    await flushPromises()
    await nextTick()
    expect(router.currentRoute.value.name).toBe('room')
    expect(document.title).toBe('自习室 · 知径')
    expect(document.activeElement?.id).toBe('room-title')
    expect(wrapper.get('#room-title').element).toBe(roomTitle)
    expect(wrapper.find('.focus-backdrop').exists()).toBe(true)
  })

  it('opens /courses directly with the courses shell', async () => {
    const { wrapper } = await mountApp('/courses')
    expect(document.title).toBe('看课笔记 · 知径')
    expect(wrapper.find('.focus-backdrop').exists()).toBe(false)
    expect(wrapper.find('#course-page-title').exists()).toBe(true)
    expect(wrapper.get('.back-to-room').attributes('href')).toBe('/')
  })

  it('opens the theme panel, focuses the first card and restores focus on Escape', async () => {
    const { wrapper } = await mountApp('/')
    const trigger = wrapper.get('.focus-dock button')

    await trigger.trigger('click')
    await nextTick()
    expect(wrapper.get('#room-tools').isVisible()).toBe(true)
    expect(wrapper.get('#room-tools').get('h2').text()).toBe('选择场景')
    expect(wrapper.findAll('#room-tools [data-theme-id]')).toHaveLength(5)
    expect(wrapper.get('#room-tools').text()).toContain('ZIP ≤ 32 MiB · 解压 ≤ 64 MiB · 最多 32 个文件')
    expect(document.activeElement?.classList.contains('scene-pick')).toBe(true)

    await wrapper.get('.app-shell').trigger('keydown', { key: 'Escape' })
    await nextTick()
    expect(wrapper.get('#room-tools').isVisible()).toBe(false)
    expect(document.activeElement).toBe(trigger.element)
  })

  it('previews and applies a scene, closing the panel and updating the backdrop', async () => {
    const { wrapper } = await mountApp('/')
    const trigger = wrapper.get('.focus-dock button')

    await trigger.trigger('click')
    await nextTick()
    await wrapper.get('[data-theme-id="palms"] .scene-pick').trigger('click')
    expect(wrapper.get('#room-tools').text()).toContain('正在预览：椰林夜海')
    expect(wrapper.get('.focus-backdrop').attributes('data-previewing')).toBe('true')

    await wrapper.get('.scene-apply .primary-button').trigger('click')
    await nextTick()
    expect(localStorage.getItem('zhijing:scene')).toBe('"palms"')
    expect(wrapper.get('.focus-backdrop').attributes('style')).toContain('palms')
    expect(wrapper.get('#room-tools').isVisible()).toBe(false)
    expect(wrapper.get('.focus-dock button').attributes('aria-label')).toBe('切换场景，当前椰林夜海')
  })

  it('keeps the running timer and goal when toggling immersive mode', async () => {
    const { wrapper } = await mountApp()
    const trigger = wrapper.get('[aria-label="沉浸模式"]')
    const timer = wrapper.get('[role="timer"]').element
    await wrapper.get('[aria-label="本轮目标"]').setValue('读完合成练习')
    await wrapper.get('.focus-start').trigger('click')
    await trigger.trigger('click')
    expect(wrapper.get('.app-shell').classes()).toContain('room-immersive')
    expect(trigger.attributes('aria-pressed')).toBe('true')
    expect(wrapper.get('[role="timer"]').element).toBe(timer)
    expect(wrapper.get('.focus-start').text()).toBe('暂停')

    await wrapper.get('.app-shell').trigger('keydown', { key: 'Escape' })
    expect(trigger.attributes('aria-pressed')).toBe('false')
    expect(document.activeElement).toBe(trigger.element)
    expect(wrapper.get<HTMLInputElement>('[aria-label="本轮目标"]').element.value).toBe('读完合成练习')
  })

  it('records a recovered focus timer only once and excludes completed breaks', async () => {
    const pastDeadline = Date.now() - 1
    const saveExpired = (minutes: number, mode?: 'short') => {
      localStorage.setItem(
        'zhijing:focus-session',
        JSON.stringify({ minutes, remaining: 1000, deadline: pastDeadline, mode }),
      )
    }
    saveExpired(18)
    const { wrapper } = await mountApp()
    expect(wrapper.findAll('.stats-values dd').map((value) => value.text())).toEqual(['18', '1'])
    expect(wrapper.get('[role="timer"]').text()).toBe('00:00')

    saveExpired(5, 'short')
    const { wrapper: restored } = await mountApp()
    expect(restored.get('[role="timer"]').attributes('aria-label')).toBe('休息剩余时间')
    expect(restored.findAll('.stats-values dd').map((value) => value.text())).toEqual(['18', '1'])

    const { wrapper: reload } = await mountApp()
    expect(reload.findAll('.stats-values dd').map((value) => value.text())).toEqual(['18', '1'])
  })

  it('restores a completed task and saves its removal', async () => {
    const { wrapper } = await mountApp()
    await wrapper.get('[aria-label="新待办"]').setValue('合成待办')
    await wrapper.get('.task-form').trigger('submit')
    await wrapper.get('.task-list input').setValue(true)
    expect(wrapper.get('.task-card').text()).toContain('1 / 1 已完成')

    const { wrapper: restored } = await mountApp()
    expect(restored.get<HTMLInputElement>('.task-list input').element.checked).toBe(true)
    await restored.get('[aria-label="删除待办：合成待办"]').trigger('click')
    expect(restored.find('.task-list').exists()).toBe(false)
    expect(localStorage.getItem('zhijing:study-tasks')).toBe('[]')
  })
})
