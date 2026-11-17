<script setup lang="ts">
import { Pause, Play, RotateCcw, Target } from '@lucide/vue'
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { readLocal, writeLocal } from '../preferences'
import { formatTime } from '../study'

const presets = [
  { id: 'focus', label: '专注', minutes: 25 },
  { id: 'short', label: '短休息', minutes: 5 },
  { id: 'long', label: '长休息', minutes: 15 },
] as const
type Mode = (typeof presets)[number]['id']

interface Session {
  minutes: number
  remaining: number
  deadline: number | null
  goal: string
  mode?: Mode
  durations?: Record<Mode, number>
}

const emit = defineEmits<{ complete: [minutes: number, deadline: number] }>()
const saved = readLocal<Session>('focus-session')
const mode = ref(presets.find((preset) => preset.id === saved?.mode)?.id ?? 'focus')
const durations = ref<Record<Mode, number>>({
  focus: savedDuration('focus', 25),
  short: savedDuration('short', 5),
  long: savedDuration('long', 15),
})
const minutes = computed(() => durations.value[mode.value])
const duration = computed(() => minutes.value * 60_000)
const restoredRemaining = saved?.remaining
const remaining = ref(
  typeof restoredRemaining === 'number' && Number.isFinite(restoredRemaining)
    ? Math.min(duration.value, Math.max(0, restoredRemaining))
    : duration.value,
)
const deadline = ref(saved && Number.isFinite(saved.deadline) ? saved.deadline : null)
const goal = ref(typeof saved?.goal === 'string' ? saved.goal : '')
const running = computed(() => deadline.value !== null)
const time = computed(() => formatTime(Math.ceil(remaining.value / 1000)))
const rest = computed(() => mode.value !== 'focus')
const progress = computed(() => remaining.value / duration.value)
const status = computed(() => {
  if (running.value) return rest.value ? '休息中' : '专注中'
  if (!remaining.value) return '已完成'
  return remaining.value < duration.value ? '已暂停' : '待开始'
})
const action = computed(() => {
  if (running.value) return '暂停'
  if (!remaining.value) return '再开始一轮'
  if (remaining.value < duration.value) return rest.value ? '继续休息' : '继续专注'
  return rest.value ? '开始休息' : '开始专注'
})
let interval: number | undefined

function validDuration(value: unknown): value is number {
  return typeof value === 'number' && Number.isInteger(value) && value >= 1 && value <= 180
}

function savedDuration(id: Mode, fallback: number) {
  const value = saved?.durations?.[id] ?? (id === mode.value ? saved?.minutes : undefined)
  return validDuration(value) ? value : fallback
}

function persist() {
  writeLocal('focus-session', {
    minutes: minutes.value,
    remaining: remaining.value,
    deadline: deadline.value,
    goal: goal.value,
    mode: mode.value,
    durations: durations.value,
  } satisfies Session)
}

function refresh() {
  const end = deadline.value
  if (end === null) return
  remaining.value = Math.max(0, Math.min(duration.value, end - Date.now()))
  if (remaining.value === 0) {
    deadline.value = null
    persist()
    if (!rest.value) emit('complete', minutes.value, end)
  }
}

function changeDuration(event: Event) {
  const input = event.target as HTMLInputElement
  const value = input.valueAsNumber
  if (validDuration(value)) {
    durations.value[mode.value] = value
    reset()
  } else {
    input.value = String(minutes.value)
  }
}

function selectMode(nextMode: Mode) {
  if (mode.value === nextMode || running.value) return
  mode.value = nextMode
  reset()
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
watch(
  running,
  (active) => {
    window.clearInterval(interval)
    interval = active ? window.setInterval(refresh, 250) : undefined
  },
  { immediate: true },
)
onMounted(refresh)
onUnmounted(() => window.clearInterval(interval))
</script>

<template>
  <section class="focus-session" aria-label="番茄计时">
    <div class="timer-modes" role="group" aria-label="计时模式">
      <button
        v-for="preset in presets"
        :key="preset.id"
        type="button"
        :aria-pressed="mode === preset.id"
        :disabled="running && mode !== preset.id"
        @click="selectMode(preset.id)"
      >
        {{ preset.label }}
      </button>
    </div>
    <div class="timer-face" :style="{ '--timer-progress': progress }">
      <span class="timer-caption" :class="{ 'is-running': running }">{{ status }}</span>
      <div class="focus-clock" role="timer" :aria-label="rest ? '休息剩余时间' : '专注剩余时间'">{{ time }}</div>
      <div class="timer-progress" aria-hidden="true"></div>
      <label class="focus-duration">
        <input
          type="number"
          min="1"
          max="180"
          step="1"
          :aria-label="rest ? '休息时长（分钟）' : '专注时长（分钟）'"
          :disabled="running"
          :value="minutes"
          @change="changeDuration"
        />
        <span aria-hidden="true">分钟</span>
      </label>
    </div>
    <div class="focus-timer-actions">
      <button type="button" class="focus-start" @click="toggle">
        <Pause v-if="running" :size="16" aria-hidden="true" />
        <Play v-else :size="16" aria-hidden="true" />
        {{ action }}
      </button>
      <button
        type="button"
        class="focus-glass focus-icon"
        title="重置计时"
        aria-label="重置计时"
        :disabled="remaining === duration && !running"
        @click="reset"
      >
        <RotateCcw :size="18" aria-hidden="true" />
      </button>
    </div>
    <label v-show="!rest" class="timer-goal">
      <Target :size="17" aria-hidden="true" />
      <input v-model="goal" type="text" maxlength="120" aria-label="本轮目标" placeholder="这一轮想完成什么？" />
    </label>
    <span v-if="!remaining" class="visually-hidden" role="status">{{ rest ? '本轮休息完成' : '本轮专注完成' }}</span>
  </section>
</template>
