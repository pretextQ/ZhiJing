import { defineStore } from 'pinia'
import { computed, reactive, ref } from 'vue'
import { RequestError, requestJson } from '../api/http'
import { writeLocal } from '../preferences'
import { persistDraftCopy, readDraftCopy, type Draft, type Lesson, type LessonSummary, type Room } from '../study'

/**
 * 自习室课程与草稿的唯一状态源。
 *
 * 之前 useStudy() 每次调用都会新建一套 ref/Map，导致课程笔记草稿在组件重建时丢失；
 * 现在改为 Pinia setup store，全应用共享同一个实例，草稿 Map 与在途保存也唯一。
 */
export const useStudy = defineStore('study', () => {
  const lessons = ref<LessonSummary[]>([])
  const active = ref<LessonSummary | null>(null)
  const obsidianEnabled = ref(false)
  const drafts = reactive(new Map<number, Draft>())
  const draft = computed(() => (active.value ? drafts.get(active.value.id) : undefined))
  const timers = new Map<number, number>()
  const writes = new Map<number, Promise<boolean>>()

  function cache(note: Draft) {
    persistDraftCopy(note)
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
          const result = await requestJson<{ revision: number }>(`/study/lessons/${lessonId}/note`, {
            method: 'PUT',
            body: { markdown, revision: note.revision },
          })
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
    timers.set(
      lessonId,
      window.setTimeout(() => void flush(lessonId), 350),
    )
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
      const copy = readDraftCopy(key)
      const hasCopy = typeof copy?.text === 'string' && typeof copy.revision === 'number'
      const text = hasCopy ? copy.text : lesson.markdown
      const recovered = text !== lesson.markdown
      const acknowledged = copy?.submitted === lesson.markdown && copy.revision + 1 === lesson.revision
      const conflict = recovered && hasCopy && copy.revision !== lesson.revision && !acknowledged
      drafts.set(lesson.id, {
        key,
        text,
        savedText: lesson.markdown,
        revision: lesson.revision,
        status: conflict ? 'conflict' : recovered ? 'pending' : 'saved',
        cached: true,
      })
      if (recovered && !conflict) schedule(lesson.id)
      if (!recovered && hasCopy) writeLocal(key, null)
    }
    const { markdown: _markdown, revision: _revision, ...summary } = lesson
    active.value = summary
    lessons.value = [summary, ...lessons.value.filter((item) => item.id !== lesson.id)]
    return summary
  }

  async function load() {
    const room = await requestJson<Room>('/study')
    lessons.value = room.lessons
    obsidianEnabled.value = room.obsidian_enabled
    if (room.active) return activate(room.active)
    return null
  }

  async function open(url: string) {
    return activate(await requestJson<Lesson>('/study/lessons', { method: 'POST', body: { url } }))
  }

  async function reopen(lessonId: number) {
    return activate(await requestJson<Lesson>(`/study/lessons/${lessonId}/open`, { method: 'POST' }))
  }

  async function update(lessonId: number, details: { title?: string; seconds?: number }) {
    const lesson = await requestJson<LessonSummary>(`/study/lessons/${lessonId}`, { method: 'PATCH', body: details })
    lessons.value = lessons.value.map((item) => (item.id === lessonId ? lesson : item))
    if (active.value?.id === lessonId) active.value = lesson
    return lesson
  }

  async function restore(lessonId: number) {
    const note = drafts.get(lessonId)
    if (!note) return null
    const before = note.text
    const latest = await requestJson<Lesson>(`/study/lessons/${lessonId}`)
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
    if (!note || !(await flush(lessonId))) {
      throw new RequestError('保存笔记后才能写入 Obsidian，可先下载当前草稿', 409)
    }
    return requestJson<{ filename: string }>(`/study/lessons/${lessonId}/export`, {
      method: 'POST',
      body: { revision: note.revision },
    })
  }

  return { lessons, active, obsidianEnabled, draft, load, open, reopen, update, edit, flush, restore, exportNote }
})
