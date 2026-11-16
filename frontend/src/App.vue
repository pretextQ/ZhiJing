<script setup lang="ts">
import { ArrowLeft, ArrowUpRight, BookOpen, Headphones, Images, Moon, Sun, Trash2, Upload, X } from '@lucide/vue'
import { computed, nextTick, onMounted, onUnmounted, ref, shallowRef, watchEffect } from 'vue'
import CourseWorkspace from './CourseWorkspace.vue'
import FocusTimer from './FocusTimer.vue'
import SoundPanel from './SoundPanel.vue'
import { readLocal, writeLocal } from './preferences'
import {
  DEFAULT_THEME_ID, builtinThemes, findTheme, importTheme, listThemes, removeTheme, themeMessage, type Theme,
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
  if (!tool.value) return
  if (confirmDeleteId.value) {
    confirmDeleteId.value = ''
    return
  }
  closeTool()
}

onMounted(() => {
  window.addEventListener('popstate', syncPage)
  void loadCustomThemes()
})
onUnmounted(() => window.removeEventListener('popstate', syncPage))
</script>

<template>
  <div class="app-shell" :class="{ 'focus-shell': !inCourses }" @keydown.esc="escapeTool">
    <div
      v-if="!inCourses"
      class="focus-backdrop"
      :data-previewing="preview ? 'true' : undefined"
      :style="{ backgroundImage: 'url(' + viewTheme.backgroundUrl + ')' }"
      aria-hidden="true"
    ></div>

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
              <button
                v-if="confirmDeleteId !== item.id"
                type="button"
                class="scene-delete icon-button"
                :aria-label="`删除主题 ${item.name}`"
                title="删除主题"
                @click="askDelete(item)"
              ><Trash2 :size="15" aria-hidden="true" /></button>
              <div v-else class="scene-confirm" role="group" :aria-label="`删除主题 ${item.name}`">
                <span>删除这个主题？</span>
                <button type="button" class="text-button scene-confirm-delete" :disabled="deletingId === item.id" @click="deleteTheme(item)">确认删除</button>
                <button type="button" class="text-button" @click="cancelDelete">取消</button>
              </div>
            </li>
          </ul>
        </section>

        <div class="scene-footer">
          <button type="button" class="quiet-button scene-import" :disabled="importing" @click="themeFile?.click()">
            <Upload :size="16" aria-hidden="true" /> {{ importing ? '正在导入…' : '导入主题包' }}
          </button>
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
