<script setup lang="ts">
import { ArrowLeft, ArrowUpRight, BookOpen, Download, Headphones, Images, Moon, Pencil, Sun, Trash2, Upload, X } from '@lucide/vue'
import { computed, nextTick, onMounted, onUnmounted, ref, shallowRef, watchEffect } from 'vue'
import CourseWorkspace from './CourseWorkspace.vue'
import FocusTimer from './FocusTimer.vue'
import SoundPanel from './SoundPanel.vue'
import { readLocal, writeLocal } from './preferences'
import {
  DEFAULT_THEME_ID, DEFAULT_THEME_LIMITS, builtinThemes, exportTheme, findTheme, getThemeLimits, importTheme,
  listThemes, removeTheme, renameTheme, themeMessage, type Theme, type ThemeLimits,
} from './themes'

const savedScene = readLocal<string>('scene')
const appliedId = ref(typeof savedScene === 'string' && savedScene ? savedScene : DEFAULT_THEME_ID)
const customThemes = shallowRef<Theme[]>([])
const preview = ref<Theme | null>(null)
const appliedTheme = computed(() => findTheme(appliedId.value, customThemes.value) ?? builtinThemes[0])
const viewTheme = computed(() => preview.value ?? appliedTheme.value)
const canApply = computed(() => preview.value !== null && preview.value.id !== appliedId.value)
const theme = readLocal<string>('theme')
const dark = ref(theme === 'dark' || (theme === null && matchMedia('(prefers-color-scheme: dark)').matches))
const inCourses = ref(location.pathname.replace(/\/$/, '') === '/courses')
const visitedCourses = ref(inCourses.value)
const tool = ref<'scenes' | 'sound' | null>(null)
const toolTitle = ref<HTMLElement>()
const toolsPanel = ref<HTMLElement>()
const themeFile = ref<HTMLInputElement>()
const importing = ref(false)
const deletingId = ref('')
const confirmDeleteId = ref('')
const sceneError = ref('')
const sceneNotice = ref('')
const sceneLimits = ref<ThemeLimits>({ ...DEFAULT_THEME_LIMITS })
const motionEnabled = ref(readLocal<boolean>('motion') !== false)
const reducedMotion = ref(false)
const failedVideoUrl = ref('')
const renamingId = ref('')
const renameValue = ref('')
const exportingId = ref('')
const reduceMotionQuery = matchMedia('(prefers-reduced-motion: reduce)')
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
const limitsText = computed(() =>
  `ZIP ≤ ${sceneLimits.value.maxArchiveMb} MiB · 解压 ≤ ${sceneLimits.value.maxExpandedMb} MiB · 最多 ${sceneLimits.value.maxEntries} 个文件`,
)
let toolTrigger: HTMLElement | undefined

watchEffect(() => {
  document.documentElement.dataset.theme = dark.value ? 'dark' : 'light'
  document.title = inCourses.value ? '看课笔记 · 知径' : '自习室 · 知径'
})

function clearSceneMessages() {
  sceneError.value = ''
  sceneNotice.value = ''
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

function previewTheme(item: Theme) {
  preview.value = item
  confirmDeleteId.value = ''
  clearSceneMessages()
}

function applyScene() {
  const item = preview.value
  if (!item) return
  appliedId.value = item.id
  writeLocal('scene', item.id)
  closeTool()
}

function askDelete(item: Theme) {
  renamingId.value = ''
  renameValue.value = ''
  confirmDeleteId.value = item.id
  clearSceneMessages()
}

function cancelDelete() {
  confirmDeleteId.value = ''
}

async function importThemePackage(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  if (!file) return
  clearSceneMessages()
  confirmDeleteId.value = ''
  importing.value = true
  try {
    const imported = await importTheme(file)
    const existing = customThemes.value.find(item => item.id === imported.id)
    if (existing) {
      sceneNotice.value = '该主题包已在主题库中'
      preview.value = existing
    } else {
      customThemes.value = [imported, ...customThemes.value]
      sceneNotice.value = `已导入：${imported.name}`
      preview.value = imported
    }
    void nextTick(() => {
      toolsPanel.value?.querySelector<HTMLElement>('[data-preview="true"]')?.scrollIntoView({ block: 'center' })
    })
  } catch (error) {
    sceneError.value = themeMessage(error)
  } finally {
    importing.value = false
  }
}

async function deleteTheme(item: Theme) {
  deletingId.value = item.id
  clearSceneMessages()
  try {
    await removeTheme(item.id)
    customThemes.value = customThemes.value.filter(theme => theme.id !== item.id)
    if (preview.value?.id === item.id) preview.value = null
    if (appliedId.value === item.id) {
      appliedId.value = DEFAULT_THEME_ID
      writeLocal('scene', DEFAULT_THEME_ID)
    }
    confirmDeleteId.value = ''
    sceneNotice.value = `已删除：${item.name}`
    void nextTick(() => {
      if (!document.activeElement || document.activeElement === document.body) {
        toolsPanel.value?.querySelector<HTMLElement>('.scene-pick')?.focus()
      }
    })
  } catch (error) {
    sceneError.value = themeMessage(error)
  } finally {
    deletingId.value = ''
  }
}

function syncReducedMotion() {
  reducedMotion.value = reduceMotionQuery.matches
}

function toggleMotion() {
  writeLocal('motion', motionEnabled.value)
}

function playSceneVideo(event: Event) {
  void (event.target as HTMLVideoElement).play().catch(() => {})
}

function sceneVideoFailed() {
  if (sceneVideoUrl.value) failedVideoUrl.value = sceneVideoUrl.value
}

async function loadLimits() {
  sceneLimits.value = await getThemeLimits()
}

function startRename(item: Theme) {
  confirmDeleteId.value = ''
  clearSceneMessages()
  renamingId.value = item.id
  renameValue.value = item.name
  void nextTick(() => {
    const input = toolsPanel.value?.querySelector<HTMLInputElement>('input[aria-label="主题名称"]')
    input?.focus()
    input?.select()
  })
}

function cancelRename() {
  renamingId.value = ''
  renameValue.value = ''
}

async function saveRename(item: Theme) {
  if (renamingId.value !== item.id) return
  const name = renameValue.value.trim()
  renamingId.value = ''
  renameValue.value = ''
  if (!name || name === item.name) return
  clearSceneMessages()
  try {
    const updated = await renameTheme(item.id, name)
    customThemes.value = customThemes.value.map(theme => (theme.id === updated.id ? updated : theme))
    if (preview.value?.id === updated.id) preview.value = updated
    sceneNotice.value = `已重命名：${updated.name}`
    void nextTick(() => {
      toolsPanel.value?.querySelector<HTMLElement>(`[data-theme-id="${updated.id}"] .scene-pick`)?.focus()
    })
  } catch (error) {
    sceneError.value = themeMessage(error)
  }
}

async function exportThemeFile(item: Theme) {
  if (exportingId.value) return
  exportingId.value = item.id
  renamingId.value = ''
  renameValue.value = ''
  clearSceneMessages()
  try {
    const { blob, filename } = await exportTheme(item.id, item.name)
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = filename
    link.rel = 'noopener'
    document.body.append(link)
    link.click()
    link.remove()
    window.setTimeout(() => URL.revokeObjectURL(url), 10000)
    sceneNotice.value = `已导出：${filename}`
  } catch (error) {
    sceneError.value = themeMessage(error)
  } finally {
    exportingId.value = ''
  }
}

function toggleTheme() {
  dark.value = !dark.value
  writeLocal('theme', dark.value ? 'dark' : 'light')
}

function syncPage() {
  inCourses.value = location.pathname.replace(/\/$/, '') === '/courses'
  if (inCourses.value) visitedCourses.value = true
  closeTool(false)
  window.scrollTo(0, 0)
  void nextTick(() => document.getElementById(inCourses.value ? 'course-page-title' : 'room-title')?.focus())
}

function navigate(event: MouseEvent, path: '/' | '/courses') {
  if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return
  event.preventDefault()
  if (location.pathname !== path) {
    history.pushState(null, '', path)
    syncPage()
  }
}

function closeTool(restoreFocus = true) {
  preview.value = null
  confirmDeleteId.value = ''
  renamingId.value = ''
  renameValue.value = ''
  clearSceneMessages()
  tool.value = null
  if (restoreFocus) toolTrigger?.focus()
  toolTrigger = undefined
}

function toggleTool(event: MouseEvent, id: 'scenes' | 'sound') {
  if (tool.value === id) {
    closeTool()
    return
  }
  preview.value = null
  confirmDeleteId.value = ''
  renamingId.value = ''
  renameValue.value = ''
  clearSceneMessages()
  toolTrigger = event.currentTarget as HTMLElement
  tool.value = id
  void nextTick(() => {
    if (id === 'scenes') {
      (toolsPanel.value?.querySelector<HTMLElement>('.scene-pick') ?? toolTitle.value)?.focus()
    } else {
      toolTitle.value?.focus()
    }
  })
}

function escapeTool() {
  if (renamingId.value) {
    cancelRename()
    return
  }
  if (!tool.value) return
  if (confirmDeleteId.value) {
    confirmDeleteId.value = ''
    return
  }
  closeTool()
}

onMounted(() => {
  window.addEventListener('popstate', syncPage)
  syncReducedMotion()
  reduceMotionQuery.addEventListener('change', syncReducedMotion)
  void loadCustomThemes()
  void loadLimits()
})
onUnmounted(() => {
  window.removeEventListener('popstate', syncPage)
  reduceMotionQuery.removeEventListener('change', syncReducedMotion)
})
</script>

<template>
  <div class="app-shell" :class="{ 'focus-shell': !inCourses }" @keydown.esc="escapeTool">
    <div
      v-if="!inCourses"
      class="focus-backdrop"
      :class="motionClass"
      :data-previewing="preview ? 'true' : undefined"
      :style="{ backgroundImage: 'url(' + viewTheme.backgroundUrl + ')' }"
      aria-hidden="true"
    >
      <video
        v-if="sceneVideoUrl"
        :key="sceneVideoUrl"
        class="scene-video"
        :src="sceneVideoUrl"
        :poster="viewTheme.backgroundUrl"
        autoplay
        muted
        loop
        playsinline
        data-theme-video
        aria-hidden="true"
        @canplay="playSceneVideo"
        @error="sceneVideoFailed"
      ></video>
    </div>

    <header class="topbar">
      <div class="topbar-inner">
        <div class="header-leading">
          <a href="/" class="brand" aria-label="知径自习室" @click="navigate($event, '/')">
            <span class="brand-icon"><BookOpen :size="19" :stroke-width="1.8" aria-hidden="true" /></span>
            <span>知径</span>
          </a>
          <a v-if="inCourses" href="/" class="quiet-button back-to-room" @click="navigate($event, '/')">
            <ArrowLeft :size="16" aria-hidden="true" /> 返回自习室
          </a>
        </div>
        <nav class="header-actions" aria-label="页面导航">
          <button
            v-if="inCourses"
            type="button"
            class="icon-button"
            aria-label="声音"
            title="声音"
            aria-controls="room-tools"
            :aria-expanded="tool === 'sound'"
            @click="toggleTool($event, 'sound')"
          ><Headphones :size="18" aria-hidden="true" /></button>
          <a v-else href="/courses" class="course-entry focus-glass" @click="navigate($event, '/courses')">
            看课笔记 <ArrowUpRight :size="16" aria-hidden="true" />
          </a>
          <button
            type="button"
            class="icon-button theme-button"
            :aria-label="dark ? '切换到浅色模式' : '切换到深色模式'"
            :title="dark ? '切换到浅色模式' : '切换到深色模式'"
            @click="toggleTheme"
          ><Sun v-if="dark" :size="18" aria-hidden="true" /><Moon v-else :size="18" aria-hidden="true" /></button>
        </nav>
      </div>
    </header>

    <main v-show="!inCourses" class="focus-main">
      <FocusTimer />
      <footer class="focus-footer">
        <div class="focus-dock" role="group" aria-label="自习室设置">
          <button
            type="button"
            class="focus-glass"
            aria-controls="room-tools"
            :aria-label="'切换场景，当前' + appliedTheme.name"
            :aria-expanded="tool === 'scenes'"
            @click="toggleTool($event, 'scenes')"
          ><Images :size="19" aria-hidden="true" /> {{ appliedTheme.name }}</button>
          <button
            type="button"
            class="focus-glass"
            aria-controls="room-tools"
            :aria-expanded="tool === 'sound'"
            @click="toggleTool($event, 'sound')"
          ><Headphones :size="19" aria-hidden="true" /> 声音</button>
        </div>
      </footer>
    </main>

    <CourseWorkspace v-if="visitedCourses" v-show="inCourses" :visible="inCourses" />

    <section
      id="room-tools"
      v-show="tool"
      ref="toolsPanel"
      class="room-tools"
      aria-labelledby="tool-title"
    >
      <div class="tools-heading">
        <h2 id="tool-title" ref="toolTitle" tabindex="-1">{{ tool === 'scenes' ? '选择场景' : '声音设置' }}</h2>
        <button type="button" class="icon-button" aria-label="关闭设置" @click="closeTool()"><X :size="17" aria-hidden="true" /></button>
      </div>

      <div v-if="tool === 'scenes'" class="scene-panel">
        <section class="scene-section" aria-labelledby="builtin-scenes-title">
          <h3 id="builtin-scenes-title" class="scene-heading">内置主题</h3>
          <ul class="scene-grid">
            <li
              v-for="item in builtinThemes"
              :key="item.id"
              class="scene-card"
              :data-theme-id="item.id"
              data-kind="builtin"
              :data-applied="appliedId === item.id ? 'true' : undefined"
              :data-preview="preview?.id === item.id ? 'true' : undefined"
            >
              <button
                type="button"
                class="scene-pick"
                :aria-label="item.name"
                :aria-pressed="appliedId === item.id"
                @click="previewTheme(item)"
              >
                <img :src="item.coverUrl" alt="">
                <span class="scene-name">
                  <component :is="item.icon" v-if="item.icon" :size="16" aria-hidden="true" />
                  {{ item.name }}
                </span>
              </button>
              <span v-if="appliedId === item.id" class="scene-badge">使用中</span>
              <span v-else-if="preview?.id === item.id" class="scene-badge">预览</span>
            </li>
          </ul>
        </section>

        <div class="scene-motion">
          <label class="scene-motion-toggle">
            <input
              v-model="motionEnabled"
              type="checkbox"
              aria-label="背景动效"
              :title="reducedMotion ? '系统已开启减少动态效果，背景动效已停用' : '让场景背景缓慢平移或缩放'"
              @change="toggleMotion"
            >
            <span>背景动效</span>
          </label>
          <span v-if="reducedMotion" class="scene-motion-note">系统已要求减少动态效果，动效已停用</span>
        </div>

        <section class="scene-section" aria-labelledby="my-themes-title">
          <h3 id="my-themes-title" class="scene-heading">我的主题</h3>
          <p v-if="!customThemes.length" class="scene-empty">还没有导入主题，可从电脑选择 ZIP 主题包。</p>
          <ul v-else class="scene-grid">
            <li
              v-for="item in customThemes"
              :key="item.id"
              class="scene-card"
              :data-theme-id="item.id"
              data-kind="custom"
              :data-applied="appliedId === item.id ? 'true' : undefined"
              :data-preview="preview?.id === item.id ? 'true' : undefined"
            >
              <button
                type="button"
                class="scene-pick"
                :aria-label="item.name"
                :aria-pressed="appliedId === item.id"
                @click="previewTheme(item)"
              >
                <img :src="item.coverUrl" alt="">
                <span class="scene-name">{{ item.name }}</span>
              </button>
              <span v-if="appliedId === item.id" class="scene-badge">使用中</span>
              <span v-else-if="preview?.id === item.id" class="scene-badge">预览</span>
              <div class="scene-tools">
                <button
                  type="button"
                  class="icon-button scene-tool"
                  :aria-label="`导出主题 ${item.name}`"
                  title="导出主题包"
                  :disabled="exportingId === item.id"
                  @click="exportThemeFile(item)"
                ><Download :size="15" aria-hidden="true" /></button>
                <button
                  type="button"
                  class="icon-button scene-tool"
                  :aria-label="`重命名主题 ${item.name}`"
                  title="重命名主题"
                  :disabled="renamingId === item.id"
                  @click="startRename(item)"
                ><Pencil :size="15" aria-hidden="true" /></button>
                <button
                  v-if="confirmDeleteId !== item.id"
                  type="button"
                  class="scene-delete icon-button"
                  :aria-label="`删除主题 ${item.name}`"
                  title="删除主题"
                  @click="askDelete(item)"
                ><Trash2 :size="15" aria-hidden="true" /></button>
              </div>
              <div v-if="confirmDeleteId === item.id" class="scene-confirm" role="group" :aria-label="`删除主题 ${item.name}`">
                <span>删除这个主题？</span>
                <button type="button" class="text-button scene-confirm-delete" :disabled="deletingId === item.id" @click="deleteTheme(item)">确认删除</button>
                <button type="button" class="text-button" @click="cancelDelete">取消</button>
              </div>
              <input
                v-if="renamingId === item.id"
                v-model="renameValue"
                type="text"
                class="scene-rename-input"
                aria-label="主题名称"
                maxlength="60"
                autocomplete="off"
                spellcheck="false"
                @keydown.enter.prevent="saveRename(item)"
                @keydown.esc.stop.prevent="cancelRename()"
                @blur="saveRename(item)"
              >
            </li>
          </ul>
        </section>

        <div class="scene-footer">
          <div class="scene-import-area">
            <button type="button" class="quiet-button scene-import" :disabled="importing" @click="themeFile?.click()">
              <Upload :size="16" aria-hidden="true" /> {{ importing ? '正在导入…' : '导入主题包' }}
            </button>
            <p class="scene-limits">{{ limitsText }}</p>
          </div>
          <div class="scene-apply">
            <span v-if="preview" class="scene-preview-status" role="status">正在预览：{{ preview.name }}</span>
            <button type="button" class="primary-button" :disabled="!canApply" @click="applyScene">应用此场景</button>
          </div>
        </div>
        <p v-if="sceneError" class="error scene-message" role="alert">{{ sceneError }}</p>
        <p v-else-if="sceneNotice" class="note-message scene-message" role="status">{{ sceneNotice }}</p>
        <input
          ref="themeFile"
          type="file"
          accept=".zip,application/zip"
          :disabled="importing"
          hidden
          @change="importThemePackage"
        >
      </div>

      <SoundPanel v-show="tool === 'sound'" :theme="appliedTheme" />
    </section>
  </div>
</template>
