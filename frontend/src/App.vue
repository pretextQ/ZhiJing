<script setup lang="ts">
import { ArrowLeft, ArrowUpRight, BookOpen, CloudRain, Headphones, Images, LibraryBig, Moon, Sun, X } from '@lucide/vue'
import { nextTick, onMounted, onUnmounted, ref, shallowRef, watchEffect } from 'vue'
import CourseWorkspace from './CourseWorkspace.vue'
import FocusTimer from './FocusTimer.vue'
import SoundPanel from './SoundPanel.vue'
import library from './assets/library.jpg'
import rain from './assets/rain.jpg'
import { readLocal, writeLocal } from './preferences'

const scenes = [
  { id: 'rain', label: '雨窗', image: rain, icon: CloudRain },
  { id: 'library', label: '夜间图书馆', image: library, icon: LibraryBig },
] as const
const rememberedScene = readLocal<string>('scene')
const scene = shallowRef(scenes.find(item => item.id === rememberedScene) ?? scenes[0])
const theme = readLocal<string>('theme')
const dark = ref(theme === 'dark' || (theme === null && matchMedia('(prefers-color-scheme: dark)').matches))
const inCourses = ref(location.pathname.replace(/\/$/, '') === '/courses')
const visitedCourses = ref(inCourses.value)
const tool = ref<'scenes' | 'sound' | null>(null)
const toolTitle = ref<HTMLElement>()
let toolTrigger: HTMLElement | undefined

watchEffect(() => {
  document.documentElement.dataset.theme = dark.value ? 'dark' : 'light'
  document.title = inCourses.value ? '看课笔记 · 知径' : '自习室 · 知径'
})

function setScene(item: typeof scenes[number]) {
  scene.value = item
  writeLocal('scene', item.id)
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
  tool.value = null
  if (restoreFocus) toolTrigger?.focus()
  toolTrigger = undefined
}

function toggleTool(event: MouseEvent, id: 'scenes' | 'sound') {
  if (tool.value === id) {
    closeTool()
    return
  }
  toolTrigger = event.currentTarget as HTMLElement
  tool.value = id
  void nextTick(() => toolTitle.value?.focus())
}

onMounted(() => window.addEventListener('popstate', syncPage))
onUnmounted(() => window.removeEventListener('popstate', syncPage))
</script>

<template>
  <div class="app-shell" :class="{ 'focus-shell': !inCourses }" @keydown.esc="tool && closeTool()">
    <div
      v-if="!inCourses"
      class="focus-backdrop"
      :style="{ backgroundImage: 'url(' + scene.image + ')' }"
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
            :aria-label="'切换场景，当前' + scene.label"
            :aria-expanded="tool === 'scenes'"
            @click="toggleTool($event, 'scenes')"
          ><Images :size="19" aria-hidden="true" /> {{ scene.label }}</button>
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

    <section id="room-tools" v-show="tool" class="room-tools" aria-labelledby="tool-title">
      <div class="tools-heading">
        <h2 id="tool-title" ref="toolTitle" tabindex="-1">{{ tool === 'scenes' ? '选择场景' : '声音设置' }}</h2>
        <button type="button" class="icon-button" aria-label="关闭设置" @click="closeTool()"><X :size="17" aria-hidden="true" /></button>
      </div>
      <div v-if="tool === 'scenes'" class="scene-choices">
        <button
          v-for="item in scenes"
          :key="item.id"
          type="button"
          :aria-pressed="scene.id === item.id"
          @click="setScene(item)"
        >
          <img :src="item.image" alt="">
          <span><component :is="item.icon" :size="16" aria-hidden="true" /> {{ item.label }}</span>
        </button>
      </div>
      <SoundPanel v-show="tool === 'sound'" />
    </section>
  </div>
</template>
