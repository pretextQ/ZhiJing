import { describe, expect, it } from 'vitest'
import { RequestError } from '../api/http'
import { formatTime, messageFor, noteTimes, secondsFromInput, sourceAt, type LessonSummary } from '../study'

const lesson: LessonSummary = {
  id: 1,
  title: '合成课程',
  part: 2,
  seconds: 754,
  original_url: 'https://www.bilibili.com/video/BV1abc123XYZ/?p=2',
  embed_url: 'https://player.bilibili.com/player.html?bvid=BV1abc123XYZ&p=2',
}

describe('secondsFromInput', () => {
  it('accepts seconds, mm:ss and hh:mm:ss forms', () => {
    expect(secondsFromInput('0')).toBe(0)
    expect(secondsFromInput('45')).toBe(45)
    expect(secondsFromInput('00:00')).toBe(0)
    expect(secondsFromInput('12:34')).toBe(754)
    expect(secondsFromInput('1:02:03')).toBe(3723)
    expect(secondsFromInput(' 12:34 ')).toBe(754)
    expect(secondsFromInput('359999')).toBe(359999)
  })

  it('rejects malformed or out-of-range input', () => {
    expect(secondsFromInput('')).toBeNull()
    expect(secondsFromInput('abc')).toBeNull()
    expect(secondsFromInput('1:2')).toBeNull()
    expect(secondsFromInput('12:60')).toBeNull()
    expect(secondsFromInput('1:60:00')).toBeNull()
    expect(secondsFromInput('1234567')).toBeNull()
    expect(secondsFromInput('360000')).toBeNull()
  })
})

describe('formatTime', () => {
  it('formats durations with an hour component only when needed', () => {
    expect(formatTime(0)).toBe('00:00')
    expect(formatTime(59)).toBe('00:59')
    expect(formatTime(60)).toBe('01:00')
    expect(formatTime(754)).toBe('12:34')
    expect(formatTime(3599)).toBe('59:59')
    expect(formatTime(3600)).toBe('1:00:00')
    expect(formatTime(3723)).toBe('1:02:03')
    expect(formatTime(215999)).toBe('59:59:59')
  })
})

describe('sourceAt', () => {
  it('adds the timestamp only for embedded lessons with a positive position', () => {
    expect(sourceAt(lesson, 754)).toBe('https://www.bilibili.com/video/BV1abc123XYZ/?p=2&t=754')
    expect(sourceAt(lesson, 0)).toBe('https://www.bilibili.com/video/BV1abc123XYZ/?p=2')
  })

  it('leaves non-embedded lessons unchanged', () => {
    const plain: LessonSummary = { ...lesson, embed_url: null }
    expect(sourceAt(plain, 300)).toBe('https://www.bilibili.com/video/BV1abc123XYZ/?p=2')
  })
})

describe('noteTimes', () => {
  it('collects unique in-note timestamps that point at the lesson', () => {
    const markdown = [
      `开头 [12:34](${sourceAt(lesson, 754)})`,
      `重复 [12:34](${sourceAt(lesson, 754)})`,
      `更长 [1:02:03](${sourceAt(lesson, 3723)})`,
      `外部 [00:10](https://www.bilibili.com/video/BV1abc123XYZ/?p=2&t=11)`,
      '非法 [99:99](https://www.bilibili.com/video/BV1abc123XYZ/?p=2&t=99)',
      '不是链接 12:34',
    ].join('\n')
    expect(noteTimes(lesson, markdown)).toEqual([754, 3723])
  })

  it('returns an empty list without timestamp links', () => {
    expect(noteTimes(lesson, '纯文字笔记')).toEqual([])
  })
})

describe('messageFor', () => {
  it('passes API errors through and falls back for network errors', () => {
    expect(messageFor(new RequestError('保存失败', 409))).toBe('保存失败')
    expect(messageFor(new Error('offline'))).toBe('无法连接知径，请确认本地服务正在运行')
  })
})
