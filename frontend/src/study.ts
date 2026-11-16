import { RequestError } from './api/http'
import type { LessonDto, LessonSummaryDto, RoomDto } from './api/types'
import { readLocal, writeLocal } from './preferences'

export type LessonSummary = LessonSummaryDto
export type Lesson = LessonDto
export type Room = RoomDto

export type SaveStatus = 'saved' | 'pending' | 'saving' | 'offline' | 'conflict'

export interface Draft {
  key: string
  text: string
  savedText: string
  revision: number
  status: SaveStatus
  cached: boolean
  submitted?: string
}

export interface DraftCopy {
  revision: number
  text: string
  submitted?: string
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

export function persistDraftCopy(note: Draft): boolean {
  const clean = note.text === note.savedText && note.submitted === undefined
  const copy: DraftCopy | null = clean ? null : { text: note.text, revision: note.revision, submitted: note.submitted }
  note.cached = writeLocal(note.key, copy)
  return note.cached
}

export function readDraftCopy(key: string): DraftCopy | null {
  return readLocal<DraftCopy>(key)
}
