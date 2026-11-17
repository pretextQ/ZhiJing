<script setup lang="ts">
import { CalendarDays, ChartNoAxesColumnIncreasing, ClipboardList, Plus, X } from '@lucide/vue'
import { computed, onMounted, onUnmounted, ref } from 'vue'
import FocusTimer from '../components/FocusTimer.vue'
import { readLocal, writeLocal } from '../preferences'

interface Task {
  id: string
  text: string
  done: boolean
}

interface DailyFocus {
  date: string
  minutes: number
  sessions: number
}

const tasks = ref(readLocal<Task[]>('study-tasks') ?? [])
const taskInput = ref<HTMLInputElement>()
const draft = ref('')
const done = computed(() => tasks.value.filter((task) => task.done).length)
const dailyFocus = ref(readLocal<DailyFocus>('daily-focus'))
const now = ref(new Date())
const today = computed(() => now.value.toDateString())
const todayLabel = computed(() =>
  now.value.toLocaleDateString('zh-CN', { month: 'long', day: 'numeric', weekday: 'long' }),
)
const stats = computed(() => (dailyFocus.value?.date === today.value ? dailyFocus.value : null))
let dayInterval: number | undefined

function saveTasks(next: Task[]) {
  tasks.value = next
  writeLocal('study-tasks', next)
}

function addTask() {
  const text = draft.value.trim()
  if (!text) return
  const id = crypto.getRandomValues(new Uint32Array(4)).join('-')
  saveTasks([...tasks.value, { id, text, done: false }])
  draft.value = ''
}

function toggleTask(id: string) {
  saveTasks(tasks.value.map((task) => (task.id === id ? { ...task, done: !task.done } : task)))
}

function removeTask(id: string) {
  saveTasks(tasks.value.filter((task) => task.id !== id))
  taskInput.value?.focus()
}

function recordFocus(minutes: number, deadline: number) {
  now.value = new Date()
  if (new Date(deadline).toDateString() !== today.value) return
  dailyFocus.value = {
    date: today.value,
    minutes: (stats.value?.minutes ?? 0) + minutes,
    sessions: (stats.value?.sessions ?? 0) + 1,
  }
  writeLocal('daily-focus', dailyFocus.value)
}

onMounted(() => {
  dayInterval = window.setInterval(() => (now.value = new Date()), 30_000)
})
onUnmounted(() => window.clearInterval(dayInterval))
</script>

<template>
  <main class="focus-main">
    <header class="room-heading">
      <h1 id="room-title" tabindex="-1">自习室</h1>
      <span><CalendarDays :size="15" aria-hidden="true" /> {{ todayLabel }}</span>
    </header>

    <FocusTimer @complete="recordFocus" />

    <div class="room-activity">
      <section class="room-card task-card" aria-labelledby="tasks-title">
        <div class="room-card-heading">
          <h2 id="tasks-title"><ClipboardList :size="17" aria-hidden="true" /> 学习待办</h2>
          <span v-if="tasks.length" class="room-card-detail">{{ done }} / {{ tasks.length }} 已完成</span>
        </div>
        <ul v-if="tasks.length" class="task-list">
          <li v-for="task in tasks" :key="task.id">
            <label :class="{ 'task-done': task.done }">
              <input type="checkbox" :checked="task.done" @change="toggleTask(task.id)" />
              <span>{{ task.text }}</span>
            </label>
            <button type="button" class="room-icon" :aria-label="'删除待办：' + task.text" @click="removeTask(task.id)">
              <X :size="15" aria-hidden="true" />
            </button>
          </li>
        </ul>
        <form class="task-form" @submit.prevent="addTask">
          <input
            ref="taskInput"
            v-model="draft"
            type="text"
            maxlength="120"
            aria-label="新待办"
            placeholder="写下要做的事"
          />
          <button type="submit" class="room-icon" aria-label="添加待办" title="添加待办" :disabled="!draft.trim()">
            <Plus :size="18" aria-hidden="true" />
          </button>
        </form>
      </section>

      <section class="room-card stats-card" aria-labelledby="stats-title">
        <div class="room-card-heading">
          <h2 id="stats-title"><ChartNoAxesColumnIncreasing :size="17" aria-hidden="true" /> 今日专注</h2>
        </div>
        <dl class="stats-values">
          <div>
            <dt>专注分钟</dt>
            <dd>{{ stats?.minutes ?? 0 }}</dd>
          </div>
          <div>
            <dt>完成轮次</dt>
            <dd>{{ stats?.sessions ?? 0 }}</dd>
          </div>
        </dl>
      </section>
    </div>
  </main>
</template>
