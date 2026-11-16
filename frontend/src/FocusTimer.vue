<script setup lang="ts">
import { Pause, Play, RotateCcw } from '@lucide/vue'
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { readLocal, writeLocal } from './preferences'
import { formatTime } from './study'

interface Session {
  minutes: number
  remaining: number
  deadline: number | null
  goal: string
}

const saved = readLocal<Session>('focus-session')
const minutes = ref(saved && validDuration(saved.minutes) ? saved.minutes : 25)
const duration = computed(() => minutes.value * 60_000)
const restoredRemaining = saved?.remaining
const remaining = ref(typeof restoredRemaining === 'number' && Number.isFinite(restoredRemaining)
  ? Math.min(duration.value, Math.max(0, restoredRemaining)) : duration.value)
const deadline = ref(saved && Number.isFinite(saved.deadline) ? saved.deadline : null)
const goal = ref(typeof saved?.goal === 'string' ? saved.goal : '')
const running = computed(() => deadline.value !== null)
const time = computed(() => formatTime(Math.ceil(remaining.value / 1000)))
let interval: number | undefined

function validDuration(value: number) {
  return Number.isInteger(value) && value >= 1 && value <= 180
}

function persist() {
  writeLocal('focus-session', {
    minutes: minutes.value, remaining: remaining.value, deadline: deadline.value, goal: goal.value,
  } satisfies Session)
}

function refresh() {
  if (deadline.value === null) return
  remaining.value = Math.max(0, Math.min(duration.value, deadline.value - Date.now()))
  if (remaining.value === 0) {
    deadline.value = null
    persist()
  }
}

function changeDuration(event: Event) {
  const input = event.target as HTMLInputElement
  const value = input.valueAsNumber
  if (validDuration(value)) {
    minutes.value = value
    reset()
  } else {
    input.value = String(minutes.value)
  }
}

function toggle() {
  if (running.value) {
    refresh()
    deadline.value = null
  } else {
    if (remaining.value === 0) remaining.value = duration.value
    deadline.value = Date.now() + remaining.value
  }
  persist()
}

function reset() {
  deadline.value = null
  remaining.value = duration.value
  persist()
}

watch(goal, persist, { flush: 'sync' })
watch(running, active => {
  window.clearInterval(interval)
  interval = active ? window.setInterval(refresh, 250) : undefined
}, { immediate: true })
onMounted(refresh)
onUnmounted(() => window.clearInterval(interval))
</script>

<template>
  <section class="focus-session" aria-labelledby="room-title">
    <h1 id="room-title" tabindex="-1">自习室</h1>
    <div class="focus-clock" role="timer" aria-label="专注剩余时间">{{ time }}</div>
    <input v-model="goal" type="text" maxlength="120" aria-label="本轮目标" placeholder="这一轮想完成什么？">
    <div class="focus-timer-actions">
      <button type="button" class="focus-start" @click="toggle">
        <Pause v-if="running" :size="18" aria-hidden="true" />
        <Play v-else :size="18" aria-hidden="true" />
        {{ running ? '暂停' : remaining === duration ? '开始专注' : remaining ? '继续专注' : '再开始一轮' }}
      </button>
      <button
        type="button"
        class="focus-glass focus-icon"
        title="重置计时"
        aria-label="重置计时"
        :disabled="remaining === duration && !running"
        @click="reset"
      ><RotateCcw :size="18" aria-hidden="true" /></button>
      <label class="focus-duration focus-glass">
        <input
          type="number"
          min="1"
          max="180"
          step="1"
          aria-label="专注时长（分钟）"
          :disabled="running"
          :value="minutes"
          @change="changeDuration"
        >
        <span aria-hidden="true">分钟</span>
      </label>
    </div>
    <p v-if="!remaining" class="focus-complete" role="status">本轮专注完成</p>
  </section>
</template>
