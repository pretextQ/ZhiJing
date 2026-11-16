import { defineStore } from 'pinia'
import { computed, ref, shallowRef } from 'vue'
import { readLocal, writeLocal } from '../preferences'
import {
  DEFAULT_THEME_ID,
  DEFAULT_THEME_LIMITS,
  builtinThemes,
  exportTheme as requestThemeExport,
  findTheme,
  getThemeLimits,
  importTheme as requestThemeImport,
  listThemes,
  removeTheme as requestThemeRemoval,
  renameTheme as requestThemeRename,
  type ExportedTheme,
  type Theme,
  type ThemeLimits,
} from '../themes'

export interface ImportedTheme {
  theme: Theme
  existing: boolean
}

/**
 * 主题目录、自定义主题库、导入/导出限制与当前场景的唯一状态源。
 * 组件只消费这里的响应式状态，不再各自 fetch。
 */
export const useThemesStore = defineStore('themes', () => {
  const savedScene = readLocal<string>('scene')
  const appliedId = ref(typeof savedScene === 'string' && savedScene ? savedScene : DEFAULT_THEME_ID)
  const customThemes = shallowRef<Theme[]>([])
  const preview = ref<Theme | null>(null)
  const limits = ref<ThemeLimits>({ ...DEFAULT_THEME_LIMITS })
  const motionEnabled = ref(readLocal<boolean>('motion') !== false)
  const reducedMotion = ref(false)
  const failedVideoUrl = ref('')
  let reduceMotionQuery: MediaQueryList | null = null

  const appliedTheme = computed(() => findTheme(appliedId.value, customThemes.value) ?? builtinThemes[0])
  const viewTheme = computed(() => preview.value ?? appliedTheme.value)
  const canApply = computed(() => preview.value !== null && preview.value.id !== appliedId.value)
  const motionClass = computed(() => {
    if (!motionEnabled.value || reducedMotion.value) return null
    const current = viewTheme.value
    if (!current.builtin || current.motion === 'none') return null
    return current.motion === 'zoom' ? 'motion-zoom' : 'motion-drift'
  })
  const sceneVideoUrl = computed(() => {
    if (!motionEnabled.value || reducedMotion.value) return null
    const current = viewTheme.value
    if (current.builtin || !current.backgroundVideoUrl) return null
    return current.backgroundVideoUrl === failedVideoUrl.value ? null : current.backgroundVideoUrl
  })
  const limitsText = computed(
    () =>
      `ZIP ≤ ${limits.value.maxArchiveMb} MiB · 解压 ≤ ${limits.value.maxExpandedMb} MiB · 最多 ${limits.value.maxEntries} 个文件`,
  )

  function syncReducedMotion() {
    if (reduceMotionQuery) reducedMotion.value = reduceMotionQuery.matches
  }

  async function loadCustomThemes() {
    try {
      const themes = await listThemes()
      customThemes.value = themes
      if (!findTheme(appliedId.value, themes)) {
        appliedId.value = DEFAULT_THEME_ID
        writeLocal('scene', DEFAULT_THEME_ID)
      }
    } catch {
      // Keep the stored selection on failure; a custom theme may load on the next visit.
    }
  }

  async function loadLimits() {
    limits.value = await getThemeLimits()
  }

  function init() {
    if (typeof window === 'undefined') return
    reduceMotionQuery ??= window.matchMedia('(prefers-reduced-motion: reduce)')
    syncReducedMotion()
    reduceMotionQuery.addEventListener('change', syncReducedMotion)
    void loadCustomThemes()
    void loadLimits()
  }

  function previewTheme(item: Theme) {
    preview.value = item
  }

  function clearPreview() {
    preview.value = null
  }

  function applyTheme() {
    const item = preview.value
    if (!item) return
    appliedId.value = item.id
    writeLocal('scene', item.id)
  }

  function setMotionEnabled(value: boolean) {
    motionEnabled.value = value
    writeLocal('motion', value)
  }

  function markVideoFailed() {
    if (sceneVideoUrl.value) failedVideoUrl.value = sceneVideoUrl.value
  }

  async function importThemePackage(file: File): Promise<ImportedTheme> {
    const imported = await requestThemeImport(file)
    const existing = customThemes.value.find((item) => item.id === imported.id)
    if (!existing) customThemes.value = [imported, ...customThemes.value]
    return { theme: existing ?? imported, existing: Boolean(existing) }
  }

  async function deleteTheme(item: Theme): Promise<void> {
    await requestThemeRemoval(item.id)
    customThemes.value = customThemes.value.filter((theme) => theme.id !== item.id)
    if (preview.value?.id === item.id) preview.value = null
    if (appliedId.value === item.id) {
      appliedId.value = DEFAULT_THEME_ID
      writeLocal('scene', DEFAULT_THEME_ID)
    }
  }

  async function renameTheme(id: string, name: string): Promise<Theme> {
    const updated = await requestThemeRename(id, name)
    customThemes.value = customThemes.value.map((theme) => (theme.id === updated.id ? updated : theme))
    if (preview.value?.id === updated.id) preview.value = updated
    return updated
  }

  function exportTheme(id: string, fallbackName: string): Promise<ExportedTheme> {
    return requestThemeExport(id, fallbackName)
  }

  return {
    appliedId,
    customThemes,
    preview,
    limits,
    motionEnabled,
    reducedMotion,
    failedVideoUrl,
    appliedTheme,
    viewTheme,
    canApply,
    motionClass,
    sceneVideoUrl,
    limitsText,
    init,
    loadCustomThemes,
    loadLimits,
    previewTheme,
    clearPreview,
    applyTheme,
    setMotionEnabled,
    markVideoFailed,
    importThemePackage,
    deleteTheme,
    renameTheme,
    exportTheme,
  }
})
