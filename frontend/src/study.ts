import { computed, reactive, ref } from 'vue'

export interface LessonSummary {
  id: number
  title: string
  part: number
  seconds: number
  original_url: string
  embed_url: string | null
}

interface Lesson extends LessonSummary {
  markdown: string
  revision: number
}

interface Room {
  lessons: LessonSummary[]
  active: Lesson | null
  obsidian_enabled: boolean
}

type SaveStatus = 'saved' | 'pending' | 'saving' | 'offline' | 'conflict'

interface Draft {
  key: string
  text: string
  savedText: string
  revision: number
  status: SaveStatus
  cached: boolean
  submitted?: string
}

interface DraftCopy {
  revision: number
  text: string
  submitted?: string
}

const API = '/api/study'

class RequestError extends Error {
  constructor(message: string, readonly status: number) {
    super(message)
  }
}

async function request<T>(path = '', method = 'GET', data?: object): Promise<T> {
  const response = await fetch(`${API}${path}`, {
    method,
    cache: 'no-store',
    headers: data ? { 'Content-Type': 'application/json' } : undefined,
    body: data ? JSON.stringify(data) : undefined,
  })
  if (!response.ok) {
    const body = await response.json().catch(() => null)
    const message = typeof body?.detail === 'string' ? body.detail : '请求失败，请检查输入后重试'
    throw new RequestError(message, response.status)
  }
  return response.json()
}

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

export function secondsFromInput(value: string): number | null {
  const text = value.trim()
  if (!/^\d{1,6}(?::[0-5]\d){0,2}$/.test(text)) return null
  const parts = text.split(':').map(Number)
  const seconds = parts.reduce((total, part) => total * 60 + part, 0)
  return seconds <= 359999 ? seconds : null
}

export function formatTime(seconds: number): string {
  const hours = Math.floor(seconds / 3600)
  const minutes = `${Math.floor(seconds / 60) % 60}`.padStart(2, '0')
  const remainder = `${seconds % 60}`.padStart(2, '0')
  return hours ? `${hours}:${minutes}:${remainder}` : `${minutes}:${remainder}`
}

export function sourceAt(lesson: LessonSummary, seconds: number): string {
  const url = new URL(lesson.original_url)
  if (lesson.embed_url && seconds > 0) url.searchParams.set('t', String(seconds))
  return url.href
}

export function playerAt(lesson: LessonSummary, seconds: number, play: boolean): string | null {
  if (!lesson.embed_url) return null
  const url = new URL(lesson.embed_url)
  url.searchParams.set('t', String(seconds))
  url.searchParams.set('autoplay', play ? '1' : '0')
  return url.href
}

export function noteTimes(lesson: LessonSummary, markdown: string): number[] {
  const matches = markdown.matchAll(/\[(\d{1,2}(?::[0-5]\d){1,2})\]\((https:\/\/www\.bilibili\.com\/[^\s)]+)\)/g)
  const times = new Set<number>()
  for (const [, time, url] of matches) {
    const seconds = secondsFromInput(time)
    if (seconds !== null && sourceAt(lesson, seconds) === url) times.add(seconds)
  }
  return [...times]
}

export function downloadNote(lesson: LessonSummary, markdown: string) {
  const content = `# ${lesson.title}\n\n[在 B 站打开](${lesson.original_url})\n\n${markdown}\n`
  const url = URL.createObjectURL(new Blob([content], { type: 'text/markdown;charset=utf-8' }))
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = `${lesson.title.replace(/[<>:"/\\|?*]/g, '_')}-P${lesson.part}.md`
  document.body.append(anchor)
  anchor.click()
  anchor.remove()
  window.setTimeout(() => URL.revokeObjectURL(url), 1000)
}

export function messageFor(error: unknown): string {
  return error instanceof RequestError ? error.message : '无法连接知径，请确认本地服务正在运行'
}

export function useStudy() {
  const lessons = ref<LessonSummary[]>([])
  const active = ref<LessonSummary | null>(null)
  const obsidianEnabled = ref(false)
  const drafts = reactive(new Map<number, Draft>())
  const draft = computed(() => active.value ? drafts.get(active.value.id) : undefined)
  const timers = new Map<number, number>()
  const writes = new Map<number, Promise<boolean>>()

  function cache(note: Draft) {
    const clean = note.text === note.savedText && note.submitted === undefined
    const copy = clean ? null : { text: note.text, revision: note.revision, submitted: note.submitted }
    note.cached = writeLocal(note.key, copy)
  }

  function clearTimer(lessonId: number) {
    window.clearTimeout(timers.get(lessonId))
    timers.delete(lessonId)
  }

  function flush(lessonId: number): Promise<boolean> {
    clearTimer(lessonId)
    const inProgress = writes.get(lessonId)
    if (inProgress) return inProgress
    const note = drafts.get(lessonId)
    if (!note || note.status === 'conflict') return Promise.resolve(false)
    const save = async () => {
      while (note.text !== note.savedText) {
        const markdown = note.text
        note.status = 'saving'
        note.submitted = markdown
        cache(note)
        try {
          const result = await request<{ revision: number }>(
            `/lessons/${lessonId}/note`, 'PUT', { markdown, revision: note.revision },
          )
          note.revision = result.revision
          note.savedText = markdown
          note.submitted = undefined
          cache(note)
        } catch (error) {
          note.status = error instanceof RequestError && error.status === 409 ? 'conflict' : 'offline'
          return false
        }
      }
      note.status = 'saved'
      note.submitted = undefined
      cache(note)
      return true
    }
    const pending = save().finally(() => writes.delete(lessonId))
    writes.set(lessonId, pending)
    return pending
  }

  function schedule(lessonId: number) {
    clearTimer(lessonId)
    timers.set(lessonId, window.setTimeout(() => void flush(lessonId), 350))
  }

  function edit(lessonId: number, text: string) {
    const note = drafts.get(lessonId)
    if (!note) return
    note.text = text
    cache(note)
    if (note.status !== 'conflict') {
      if (!writes.has(lessonId)) note.status = text === note.savedText ? 'saved' : 'pending'
      schedule(lessonId)
    }
  }

  function activate(lesson: Lesson) {
    const previous = active.value
    if (previous && previous.id !== lesson.id) void flush(previous.id)
    if (!drafts.has(lesson.id)) {
      const key = `draft:${lesson.original_url}`
      const copy = readLocal<DraftCopy>(key)
      const hasCopy = typeof copy?.text === 'string' && typeof copy.revision === 'number'
      const text = hasCopy ? copy.text : lesson.markdown
      const recovered = text !== lesson.markdown
      const acknowledged = copy?.submitted === lesson.markdown && copy.revision + 1 === lesson.revision
      const conflict = recovered && hasCopy && copy.revision !== lesson.revision && !acknowledged
      drafts.set(lesson.id, {
        key, text, savedText: lesson.markdown, revision: lesson.revision,
        status: conflict ? 'conflict' : recovered ? 'pending' : 'saved', cached: true,
      })
      if (recovered && !conflict) schedule(lesson.id)
      if (!recovered && hasCopy) writeLocal(key, null)
    }
    const { markdown: _markdown, revision: _revision, ...summary } = lesson
    active.value = summary
    lessons.value = [summary, ...lessons.value.filter(item => item.id !== lesson.id)]
    return summary
  }

  async function load() {
    const room = await request<Room>()
    lessons.value = room.lessons
    obsidianEnabled.value = room.obsidian_enabled
    if (room.active) return activate(room.active)
    return null
  }

  async function open(url: string) {
    return activate(await request<Lesson>('/lessons', 'POST', { url }))
  }

  async function reopen(lessonId: number) {
    return activate(await request<Lesson>(`/lessons/${lessonId}/open`, 'POST'))
  }

  async function update(lessonId: number, details: { title?: string; seconds?: number }) {
    const lesson = await request<LessonSummary>(`/lessons/${lessonId}`, 'PATCH', details)
    lessons.value = lessons.value.map(item => item.id === lessonId ? lesson : item)
    if (active.value?.id === lessonId) active.value = lesson
    return lesson
  }

  async function restore(lessonId: number) {
    const note = drafts.get(lessonId)
    if (!note) return null
    const before = note.text
    const latest = await request<Lesson>(`/lessons/${lessonId}`)
    if (note.text !== before) return null
    note.text = latest.markdown
    note.savedText = latest.markdown
    note.revision = latest.revision
    note.status = 'saved'
    note.submitted = undefined
    cache(note)
    return latest.markdown
  }

  async function exportNote(lessonId: number) {
    const note = drafts.get(lessonId)
    if (!note || !await flush(lessonId)) {
      throw new RequestError('保存笔记后才能写入 Obsidian，可先下载当前草稿', 409)
    }
    return request<{ filename: string }>(`/lessons/${lessonId}/export`, 'POST', { revision: note.revision })
  }

  return { lessons, active, obsidianEnabled, draft, load, open, reopen, update, edit, flush, restore, exportNote }
}
