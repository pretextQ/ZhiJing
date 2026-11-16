import { createPinia, setActivePinia } from 'pinia'
import { describe, expect, it, vi } from 'vitest'
import { useStudy } from '../stores/study'

const lesson = {
  id: 7,
  title: '合成课程',
  part: 1,
  seconds: 0,
  original_url: 'https://www.bilibili.com/video/BV1abc123XYZ/?p=2',
  embed_url: 'https://player.bilibili.com/player.html?bvid=BV1abc123XYZ&p=2',
  markdown: '初始笔记',
  revision: 1,
}

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
}

function createFetchMock() {
  return vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input)
    if (url === '/api/study' && (init?.method ?? 'GET') === 'GET') {
      return Promise.resolve(jsonResponse({ lessons: [], active: null, obsidian_enabled: false }))
    }
    if (url === '/api/study/lessons' && init?.method === 'POST') {
      return Promise.resolve(jsonResponse(lesson))
    }
    if (url === '/api/study/lessons/7/note' && init?.method === 'PUT') {
      return Promise.resolve(jsonResponse({ revision: 2 }))
    }
    return Promise.resolve(jsonResponse({ detail: 'unexpected request' }, 500))
  })
}

describe('study store', () => {
  it('is a single Pinia instance shared by every consumer', () => {
    setActivePinia(createPinia())
    expect(useStudy()).toBe(useStudy())
  })

  it('loads a lesson, keeps drafts and flushes them to the API', async () => {
    setActivePinia(createPinia())
    vi.stubGlobal('fetch', createFetchMock())
    const study = useStudy()

    await expect(study.load()).resolves.toBeNull()
    expect(study.lessons).toEqual([])

    const summary = await study.open(lesson.original_url)
    expect(summary.id).toBe(7)
    expect(study.active?.id).toBe(7)
    expect(study.lessons.map((item) => item.id)).toEqual([7])
    expect(study.draft?.text).toBe('初始笔记')
    expect(study.draft?.status).toBe('saved')

    study.edit(7, '更新后的笔记')
    expect(study.draft?.status).toBe('pending')
    await expect(study.flush(7)).resolves.toBe(true)
    expect(study.draft?.status).toBe('saved')
    expect(study.draft?.revision).toBe(2)
    expect(localStorage.getItem('zhijing:draft:https://www.bilibili.com/video/BV1abc123XYZ/?p=2')).toBeNull()
  })

  it('keeps the draft when the save request fails with a conflict', async () => {
    setActivePinia(createPinia())
    const fetchMock = createFetchMock()
    fetchMock.mockImplementation((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input)
      if (url === '/api/study/lessons' && init?.method === 'POST') return Promise.resolve(jsonResponse(lesson))
      if (url === '/api/study/lessons/7/note') {
        return Promise.resolve(jsonResponse({ detail: '另一窗口已保存新版' }, 409))
      }
      return Promise.resolve(jsonResponse({ lessons: [], active: null, obsidian_enabled: false }))
    })
    vi.stubGlobal('fetch', fetchMock)
    const study = useStudy()

    await study.open(lesson.original_url)
    study.edit(7, '冲突草稿')
    await expect(study.flush(7)).resolves.toBe(false)
    expect(study.draft?.status).toBe('conflict')
    expect(study.draft?.text).toBe('冲突草稿')
  })
})
