<script setup lang="ts">
import { ArrowLeft, ArrowUpRight, BookOpen, Headphones, Moon, Sun, X } from '@lucide/vue'
import { storeToRefs } from 'pinia'
import { computed, nextTick, onMounted, ref, watch, watchEffect } from 'vue'
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
const toolTitle = ref<HTMLElement>()
const themePanel = ref<InstanceType<typeof ThemePanel>>()
const inCourses = computed(() => route.name === 'courses')
const routeProps = computed(() => (inCourses.value ? {} : { tool: tool.value, onToggleTool: toggleTool }))
let toolTrigger: HTMLElement | undefined

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
    if (!routerReady.value || !from) return
    void nextTick(() => document.getElementById(inCourses.value ? 'course-page-title' : 'room-title')?.focus())
  },
)

onMounted(async () => {
  themes.init()
  await router.isReady()
  routerReady.value = true
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
      toolTitle.value?.focus()
    }
  })
}

function escapeTool() {
  if (themePanel.value?.handleEscape()) return
  if (!tool.value) return
  closeTool()
}
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
          <RouterLink to="/" class="brand" aria-label="知径自习室">
            <span class="brand-icon"><BookOpen :size="19" :stroke-width="1.8" aria-hidden="true" /></span>
            <span>知径</span>
          </RouterLink>
          <RouterLink v-if="inCourses" to="/" class="quiet-button back-to-room">
            <ArrowLeft :size="16" aria-hidden="true" /> 返回自习室
          </RouterLink>
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

    <RouterView v-slot="{ Component }">
      <KeepAlive>
        <component :is="Component" v-bind="routeProps" />
      </KeepAlive>
    </RouterView>

    <section id="room-tools" v-show="tool" class="room-tools" aria-labelledby="tool-title">
      <div class="tools-heading">
        <h2 id="tool-title" ref="toolTitle" tabindex="-1">{{ tool === 'scenes' ? '选择场景' : '声音设置' }}</h2>
        <button type="button" class="icon-button" aria-label="关闭设置" @click="closeTool()">
          <X :size="17" aria-hidden="true" />
        </button>
      </div>

      <ThemePanel v-if="tool === 'scenes'" ref="themePanel" @close="closeTool()" />
      <SoundPanel v-show="tool === 'sound'" :theme="themes.appliedTheme" />
    </section>
  </div>
</template>
