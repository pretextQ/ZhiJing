/**
 * OpenAPI 生成类型（唯一后端契约来源）。
 *
 * 更新流程：
 *   uv run --locked --no-sync python dev/export_openapi.py
 *   npm.cmd --prefix frontend run gen:api
 *
 * 生成的 schema.d.ts 由 openapi-typescript 产出，请勿手改。
 */
import type { components } from './schema'

export type { components }

export type ApiSchemas = components['schemas']

/** 课程与会话 */
export type LessonSummaryDto = ApiSchemas['LessonSummary']
export type LessonDto = ApiSchemas['Lesson']
export type RoomDto = ApiSchemas['Room']
export type LessonUpdateDto = ApiSchemas['LessonUpdate']
export type NoteUpdateDto = ApiSchemas['NoteUpdate']
export type RevisionDto = ApiSchemas['Revision']

/** 主题包 */
export type ThemeCardDto = ApiSchemas['ThemeCard']
export type ThemeLimitsDto = ApiSchemas['ThemeLimits']

/** 润色接口（迁移期兼容层） */
export type PolishRequestDto = ApiSchemas['PolishRequest']
