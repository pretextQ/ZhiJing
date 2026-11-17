<script setup lang="ts">
import { ArrowLeft, ArrowUpRight, BookOpen, Headphones, Images, Maximize, Minimize, Moon, Sun, X } from '@lucide/vue'
import { storeToRefs } from 'pinia'
import { computed, nextTick, onMounted, onUnmounted, ref, watch, watchEffect } from 'vue'
import { RouterLink, RouterView, useRoute, useRouter } from 'vue-router'
import SoundPanel from './components/SoundPanel.vue'
import ThemePanel from './components/ThemePanel.vue'
import { readLocal, writeLocal } from './preferences'
import { useThemesStore } from './stores/themes'
import type { ToolId } from './types'

const route = useRoute()
const router = useRouter()
const themes = useThemesStore()
const { motionClass, preview, sceneVideoUrl, viewTheme } = storeToRefs(themes)

const savedTheme = readLocal<string>('theme')
const dark = ref(
  savedTheme === 'dark' || (savedTheme === null && window.matchMedia('(prefers-color-scheme: dark)').matches),
)
const tool = ref<ToolId | null>(null)
const shell = ref<HTMLElement>()
const soundTitle = ref<HTMLElement>()
const themePanel = ref<InstanceType<typeof ThemePanel>>()
const immersiveButton = ref<HTMLButtonElement>()
const immersive = ref(false)
const inCourses = computed(() => route.name === 'courses')
const soundInWorkspace = computed(() => !inCourses.value && !immersive.value)
let toolTrigger: HTMLElement | undefined
let nativeFullscreen = false

watchEffect(() => {
  document.documentElement.dataset.theme = dark.value ? 'dark' : 'light'
  document.title = inCourses.value ? '看课笔记 · 知径' : '自习室 · 知径'
})

const routerReady = ref(false)

// 只在实际路由切换时移动焦点；首次加载保持默认 Tab 顺序。
watch(
  () => route.name,
  (_to, from) => {
    closeTool(false)
    if (immersive.value) leaveImmersive(false)
    if (!routerReady.value || !from) return
    void nextTick(() => document.getElementById(inCourses.value ? 'course-page-title' : 'room-title')?.focus())
  },
)

onMounted(async () => {
  document.addEventListener('fullscreenchange', syncFullscreen)
  document.addEventListener('keydown', escapeTool)
  themes.init()
  await router.isReady()
  routerReady.value = true
})
onUnmounted(() => {
  document.removeEventListener('fullscreenchange', syncFullscreen)
  document.removeEventListener('keydown', escapeTool)
})

function playSceneVideo(event: Event) {
  void (event.target as HTMLVideoElement).play().catch(() => {})
}

function sceneVideoFailed() {
  themes.markVideoFailed()
}

function toggleTheme() {
  dark.value = !dark.value
  writeLocal('theme', dark.value ? 'dark' : 'light')
}

function syncFullscreen() {
  if (document.fullscreenElement && document.fullscreenElement === shell.value) {
    if (immersive.value) nativeFullscreen = true
    else void document.exitFullscreen().catch(() => {})
  } else if (nativeFullscreen) {
    nativeFullscreen = false
    leaveImmersive()
  }
}

function leaveImmersive(restoreFocus = true) {
  immersive.value = false
  closeTool(false)
  if (document.fullscreenElement && document.fullscreenElement === shell.value) {
    nativeFullscreen = false
    void document.exitFullscreen().catch(() => {})
  }
  if (restoreFocus) immersiveButton.value?.focus()
}

function toggleImmersive() {
  if (immersive.value) {
    leaveImmersive()
    return
  }
  closeTool(false)
  immersive.value = true
  if (document.fullscreenEnabled && !document.fullscreenElement) {
    void shell.value?.requestFullscreen?.().catch(() => {})
  }
}

function closeTool(restoreFocus = true) {
  themes.clearPreview()
  tool.value = null
  if (restoreFocus) toolTrigger?.focus()
  toolTrigger = undefined
}

function toggleTool(event: MouseEvent, id: ToolId) {
  if (tool.value === id) {
    closeTool()
    return
  }
  themes.clearPreview()
  toolTrigger = event.currentTarget as HTMLElement
  tool.value = id
  void nextTick(() => {
    if (id === 'scenes') {
      themePanel.value?.focusFirst()
    } else {
      soundTitle.value?.focus()
    }
  })
}

function escapeTool(event: KeyboardEvent) {
  if (event.key !== 'Escape' || event.defaultPrevented) return
  if (themePanel.value?.handleEscape()) return
  if (tool.value) closeTool()
  else if (immersive.value) leaveImmersive()
}
</script>

<template>
  <div
    ref="shell"
    class="app-shell"
    :class="{ 'focus-shell': !inCourses, 'course-shell': inCourses, 'room-immersive': immersive }"
  >
    <div
      class="focus-backdrop"
      :class="inCourses ? undefined : motionClass"
      :data-previewing="preview && !inCourses ? 'true' : undefined"
      :style="{ backgroundImage: 'url(' + viewTheme.backgroundUrl + ')' }"
      aria-hidden="true"
    >
      <video
        v-if="sceneVideoUrl && !inCourses"
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
          <RouterLink to="/" class="brand" aria-label="知径自习室">
            <span class="brand-icon"><BookOpen :size="19" :stroke-width="1.8" aria-hidden="true" /></span>
            <span>知径</span>
          </RouterLink>
          <RouterLink v-if="inCourses" to="/" class="quiet-button back-to-room">
            <ArrowLeft :size="16" aria-hidden="true" /> 返回自习室
          </RouterLink>
        </div>
        <nav class="header-actions" aria-label="页面导航">
          <div v-if="!inCourses" class="focus-dock" role="group" aria-label="自习室设置">
            <button
              type="button"
              class="focus-glass scene-trigger"
              aria-controls="room-tools"
              :aria-label="'切换场景，当前' + themes.appliedTheme.name"
              :title="'切换场景，当前' + themes.appliedTheme.name"
              :aria-expanded="tool === 'scenes'"
              @click="toggleTool($event, 'scenes')"
            >
              <Images :size="17" aria-hidden="true" /> <span>{{ themes.appliedTheme.name }}</span>
            </button>
            <button
              type="button"
              class="focus-glass sound-trigger"
              aria-controls="room-sound"
              :aria-expanded="immersive ? tool === 'sound' : undefined"
              :class="{ 'sound-active': tool === 'sound' }"
              aria-label="声音"
              title="声音"
              @click="toggleTool($event, 'sound')"
            >
              <Headphones :size="17" aria-hidden="true" /> <span>声音</span>
            </button>
            <button
              ref="immersiveButton"
              type="button"
              class="focus-glass immersive-trigger"
              aria-label="沉浸模式"
              :aria-pressed="immersive"
              :title="immersive ? '退出沉浸模式' : '沉浸模式'"
              @click="toggleImmersive"
            >
              <Minimize v-if="immersive" :size="17" aria-hidden="true" />
              <Maximize v-else :size="17" aria-hidden="true" />
              <span>{{ immersive ? '退出沉浸' : '沉浸模式' }}</span>
            </button>
          </div>
          <button
            v-if="inCourses"
            type="button"
            class="icon-button"
            aria-label="声音"
            title="声音"
            aria-controls="room-sound"
            :aria-expanded="tool === 'sound'"
            @click="toggleTool($event, 'sound')"
          >
            <Headphones :size="18" aria-hidden="true" />
          </button>
          <RouterLink v-else to="/courses" class="course-entry focus-glass">
            看课笔记 <ArrowUpRight :size="16" aria-hidden="true" />
          </RouterLink>
          <button
            type="button"
            class="icon-button theme-button"
            :aria-label="dark ? '切换到浅色模式' : '切换到深色模式'"
            :title="dark ? '切换到浅色模式' : '切换到深色模式'"
            @click="toggleTheme"
          >
            <Sun v-if="dark" :size="18" aria-hidden="true" /><Moon v-else :size="18" aria-hidden="true" />
          </button>
        </nav>
      </div>
    </header>

    <div class="workspace-layout">
      <RouterView v-slot="{ Component }">
        <KeepAlive>
          <component :is="Component" />
        </KeepAlive>
      </RouterView>

      <aside
        id="room-sound"
        v-show="soundInWorkspace || tool === 'sound'"
        class="room-sound"
        :class="{ 'sound-in-workspace': soundInWorkspace }"
        aria-labelledby="sound-title"
      >
        <div class="sound-heading">
          <h2 id="sound-title" ref="soundTitle" tabindex="-1"><Headphones :size="17" aria-hidden="true" /> 声音</h2>
          <button
            v-if="!soundInWorkspace"
            type="button"
            class="room-icon"
            aria-label="关闭声音设置"
            @click="closeTool()"
          >
            <X :size="17" aria-hidden="true" />
          </button>
        </div>
        <SoundPanel :theme="themes.appliedTheme" />
      </aside>
    </div>

    <section
      v-if="!inCourses"
      id="room-tools"
      v-show="tool === 'scenes'"
      class="room-tools"
      aria-labelledby="tool-title"
    >
      <div class="tools-heading">
        <h2 id="tool-title" tabindex="-1">选择场景</h2>
        <button type="button" class="icon-button" aria-label="关闭设置" @click="closeTool()">
          <X :size="17" aria-hidden="true" />
        </button>
      </div>

      <ThemePanel v-if="tool === 'scenes'" ref="themePanel" @close="closeTool()" />
    </section>
  </div>
</template>
