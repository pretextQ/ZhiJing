<script setup lang="ts">
import {
  AudioLines,
  ChevronDown,
  Disc3,
  ListMusic,
  Pause,
  Play,
  Plus,
  SkipBack,
  SkipForward,
  Trash2,
  Volume2,
  VolumeX,
} from '@lucide/vue'
import { computed, nextTick, onBeforeUnmount, onMounted, ref, shallowRef, watch } from 'vue'
import { type Track, readTracks, saveTracks } from '../playlist'
import { readLocal, writeLocal } from '../preferences'
import { formatTime } from '../study'
import type { Theme } from '../themes'

const props = defineProps<{ theme?: Theme | null }>()

const noises = [
  { id: 'off', label: '静音' },
  { id: 'white', label: '白噪音' },
  { id: 'pink', label: '粉噪音' },
  { id: 'brown', label: '棕噪音' },
] as const
type Noise = (typeof noises)[number]['id'] | 'theme'
const noise = ref<Noise>('off')
const ambientAudio = ref<HTMLAudioElement>()
const ambientUrl = computed(() => props.theme?.ambientUrl ?? null)
const noiseOptions = computed<{ id: Noise; label: string }[]>(() => {
  const options: { id: Noise; label: string }[] = noises.map((item) => ({ id: item.id, label: item.label }))
  if (ambientUrl.value) options.push({ id: 'theme', label: '主题环境音' })
  return options
})
const volume = ref(readLocal<number>('noise-volume') ?? 25)
const tracks = shallowRef<Track[]>([])
const trackId = ref('')
const trackUrl = ref('')
const audio = ref<HTMLAudioElement>()
const playing = ref(false)
const position = ref(0)
const trackDuration = ref(0)
const trackVolume = ref(readLocal<number>('track-volume') ?? 70)
const fileInput = ref<HTMLInputElement>()
const loading = ref(true)
const updating = ref(false)
const noiseError = ref('')
const playlistError = ref('')
const currentIndex = computed(() => tracks.value.findIndex((track) => track.id === trackId.value))
const currentTrack = computed(() => tracks.value[currentIndex.value])
const canSeek = computed(() => trackDuration.value > 0)
let context: AudioContext | undefined
let source: AudioBufferSourceNode | undefined
let gain: GainNode | undefined
let soundChange = 0

function makeNoise(audioContext: AudioContext, kind: Exclude<Noise, 'off' | 'theme'>) {
  const buffer = audioContext.createBuffer(1, audioContext.sampleRate * 12, audioContext.sampleRate)
  const data = buffer.getChannelData(0)
  let previous = 0
  let low = 0
  let middle = 0
  let high = 0
  for (let i = 0; i < data.length; i++) {
    const white = Math.random() * 2 - 1
    if (kind === 'brown') {
      previous = (previous + 0.02 * white) / 1.02
      data[i] = previous * 3.5
    } else if (kind === 'pink') {
      low = 0.99765 * low + white * 0.099046
      middle = 0.963 * middle + white * 0.2965164
      high = 0.57 * high + white * 1.0526913
      data[i] = (low + middle + high + white * 0.1848) * 0.15
    } else {
      data[i] = white * 0.35
    }
  }
  // Bring the endpoints to zero so looping does not add a click.
  const fade = Math.round(audioContext.sampleRate * 0.015)
  for (let i = 0; i < fade; i++) {
    data[i] *= i / fade
    data[data.length - 1 - i] *= i / fade
  }
  return buffer
}

function stopNoise() {
  source?.stop()
  source?.disconnect()
  source = undefined
}

async function playAmbient(change: number) {
  await nextTick()
  const element = ambientAudio.value
  if (!element || !ambientUrl.value) {
    if (change === soundChange) noise.value = 'off'
    return
  }
  element.volume = volume.value / 100
  try {
    element.currentTime = 0
    await element.play()
  } catch {
    if (change !== soundChange) return
    noise.value = 'off'
    noiseError.value = '主题环境音无法播放'
  }
}

async function changeNoise(event: Event) {
  const kind = (event.target as HTMLSelectElement).value as Noise
  const change = ++soundChange
  noise.value = kind
  noiseError.value = ''
  stopNoise()
  ambientAudio.value?.pause()
  if (kind === 'off') return
  if (kind === 'theme') {
    await playAmbient(change)
    return
  }
  try {
    context ??= new AudioContext()
    if (!gain) {
      gain = context.createGain()
      gain.connect(context.destination)
    }
    if (context.state !== 'running') await context.resume()
    if (change !== soundChange) return
    gain.gain.value = volume.value / 100
    source = context.createBufferSource()
    source.buffer = makeNoise(context, kind)
    source.loop = true
    source.connect(gain)
    source.start()
  } catch {
    if (change !== soundChange) return
    noise.value = 'off'
    noiseError.value = '环境音启动失败'
  }
}

watch(volume, (value) => {
  writeLocal('noise-volume', value)
  if (context && gain) gain.gain.setTargetAtTime(value / 100, context.currentTime, 0.025)
  if (ambientAudio.value) ambientAudio.value.volume = value / 100
})

watch(ambientUrl, (url) => {
  ambientAudio.value?.pause()
  if (noise.value !== 'theme') return
  if (!url) {
    noise.value = 'off'
    return
  }
  void playAmbient(++soundChange)
})

function ambientFailed() {
  if (noise.value !== 'theme') return
  noise.value = 'off'
  noiseError.value = '主题环境音无法播放'
}

function selectTrackFromEvent(event: Event) {
  playlistError.value = ''
  void selectTrack((event.target as HTMLSelectElement).value, true)
}

async function selectTrack(id: string, play = false) {
  const track = tracks.value.find((item) => item.id === id)
  if (trackId.value !== id || !trackUrl.value) {
    audio.value?.pause()
    playing.value = false
    position.value = 0
    trackDuration.value = 0
    if (trackUrl.value) URL.revokeObjectURL(trackUrl.value)
    trackId.value = id
    trackUrl.value = track ? URL.createObjectURL(track.file) : ''
    writeLocal('track', track?.id ?? null)
  }
  if (play && track) {
    await nextTick()
    try {
      await audio.value?.play()
    } catch {
      if (trackId.value === id) playlistError.value = '无法播放这首曲目，请检查音频格式'
    }
  }
}

async function importTracks(event: Event) {
  const input = event.target as HTMLInputElement
  const imported = Array.from(input.files ?? []).filter(
    (file) => file.type.startsWith('audio/') || /\.(mp3|wav|ogg|opus|m4a|aac|flac|webm)$/i.test(file.name),
  )
  input.value = ''
  if (!imported.length) {
    playlistError.value = '请选择音频文件'
    return
  }
  const entries = imported.map((file) => ({ id: crypto.randomUUID(), file }))
  await updateTracks([...tracks.value, ...entries], trackId.value || entries[0].id)
}

async function updateTracks(next: Track[], selected: string) {
  updating.value = true
  playlistError.value = ''
  try {
    await saveTracks(next)
    tracks.value = next
    await selectTrack(selected)
  } catch {
    playlistError.value = '歌单保存失败，请检查浏览器存储空间'
  } finally {
    updating.value = false
  }
}

function removeTrack() {
  const index = currentIndex.value
  const next = tracks.value.filter((track) => track.id !== trackId.value)
  return updateTracks(next, next[Math.min(index, next.length - 1)]?.id ?? '')
}

function stepTrack(offset: number) {
  const count = tracks.value.length
  const next = tracks.value[(currentIndex.value + offset + count) % count]
  if (next) {
    playlistError.value = ''
    void selectTrack(next.id, true)
  }
}

function handleTrackEnd() {
  syncPlayback()
  stepTrack(1)
}

function togglePlayback() {
  if (!currentTrack.value || !audio.value) return
  if (!audio.value.paused) {
    audio.value.pause()
    return
  }
  playlistError.value = ''
  void selectTrack(currentTrack.value.id, true)
}

function syncPlayback() {
  if (!audio.value) return
  playing.value = !audio.value.paused && !audio.value.ended
  position.value = audio.value.currentTime
  trackDuration.value = Number.isFinite(audio.value.duration) ? audio.value.duration : 0
}

function seek(event: Event) {
  if (!audio.value || !canSeek.value) return
  audio.value.currentTime = (event.target as HTMLInputElement).valueAsNumber
  syncPlayback()
}

watch(trackVolume, (value) => {
  writeLocal('track-volume', value)
  if (audio.value) audio.value.volume = value / 100
})

onMounted(async () => {
  if (audio.value) audio.value.volume = trackVolume.value / 100
  try {
    tracks.value = await readTracks()
    const remembered = readLocal<string>('track')
    const selected = tracks.value.find((track) => track.id === remembered) ?? tracks.value[0]
    if (selected) await selectTrack(selected.id)
  } catch {
    playlistError.value = '无法读取本地歌单'
  } finally {
    loading.value = false
  }
})

onBeforeUnmount(() => {
  ++soundChange
  ambientAudio.value?.pause()
  stopNoise()
  void context?.close()
  if (trackUrl.value) URL.revokeObjectURL(trackUrl.value)
})
</script>

<template>
  <div class="sound-bar">
    <section class="room-card playlist" aria-labelledby="playlist-title">
      <div class="room-card-heading">
        <h3 id="playlist-title"><ListMusic :size="17" aria-hidden="true" /> 本地歌单</h3>
        <button
          type="button"
          class="room-icon"
          aria-label="添加音乐"
          title="添加音乐"
          :disabled="loading || updating"
          @click="fileInput?.click()"
        >
          <Plus :size="18" aria-hidden="true" />
        </button>
      </div>
      <div class="track-summary">
        <div class="track-art" aria-hidden="true">
          <img v-if="theme" :src="theme.coverUrl" alt="" />
          <Disc3 :size="24" />
        </div>
        <div class="track-caption">
          <strong :title="currentTrack?.file.name">{{
            currentTrack?.file.name ?? (loading ? '正在读取歌单' : '还没有音乐')
          }}</strong>
          <span v-if="tracks.length">{{ tracks.length }} 首曲目</span>
          <button v-else-if="!loading" type="button" class="track-add" :disabled="updating" @click="fileInput?.click()">
            导入本地音频
          </button>
        </div>
      </div>
      <div class="track-timeline">
        <input
          type="range"
          min="0"
          :max="trackDuration || 1"
          step="0.1"
          :value="position"
          :disabled="!canSeek"
          aria-label="播放进度"
          @input="seek"
        />
        <div>
          <span>{{ formatTime(Math.floor(position)) }}</span><span>{{ formatTime(Math.floor(trackDuration)) }}</span>
        </div>
      </div>
      <div class="track-controls">
        <button
          type="button"
          class="room-icon"
          aria-label="上一首"
          :disabled="tracks.length < 2"
          @click="stepTrack(-1)"
        >
          <SkipBack :size="17" aria-hidden="true" />
        </button>
        <button
          type="button"
          class="room-icon music-play"
          :aria-label="playing ? '暂停音乐' : '播放音乐'"
          :disabled="!currentTrack"
          @click="togglePlayback"
        >
          <Pause v-if="playing" :size="19" aria-hidden="true" />
          <Play v-else :size="19" aria-hidden="true" />
        </button>
        <button type="button" class="room-icon" aria-label="下一首" :disabled="tracks.length < 2" @click="stepTrack(1)">
          <SkipForward :size="17" aria-hidden="true" />
        </button>
      </div>
      <div v-if="tracks.length" class="track-picker">
        <span class="select-wrap">
          <select aria-labelledby="playlist-title" :value="trackId" @change="selectTrackFromEvent">
            <option v-for="track in tracks" :key="track.id" :value="track.id">{{ track.file.name }}</option>
          </select>
          <ChevronDown :size="14" aria-hidden="true" />
        </span>
        <button
          type="button"
          class="room-icon"
          aria-label="移除当前曲目"
          title="移除当前曲目"
          :disabled="updating"
          @click="removeTrack"
        >
          <Trash2 :size="16" aria-hidden="true" />
        </button>
      </div>
      <div class="sound-volume">
        <Volume2 :size="16" aria-hidden="true" />
        <input
          v-model.number="trackVolume"
          type="range"
          min="0"
          max="100"
          aria-label="音乐音量"
          :disabled="!tracks.length"
        />
        <span>{{ trackVolume }}%</span>
      </div>
      <audio
        ref="audio"
        :src="trackUrl || undefined"
        preload="metadata"
        aria-label="本地歌单播放器"
        hidden
        @loadedmetadata="syncPlayback"
        @timeupdate="syncPlayback"
        @play="syncPlayback"
        @pause="syncPlayback"
        @ended="handleTrackEnd"
        @error="trackUrl && (playlistError = '无法播放这首曲目，请检查音频格式')"
      ></audio>
      <input ref="fileInput" type="file" accept="audio/*,.flac,.opus" multiple hidden @change="importTracks" />
      <p v-if="playlistError" class="sound-error" role="status">{{ playlistError }}</p>
    </section>
    <section class="room-card ambience">
      <div class="room-card-heading">
        <h3><AudioLines :size="17" aria-hidden="true" /> <label for="noise-kind">环境音</label></h3>
        <span class="room-card-detail">{{ noise === 'off' ? '已关闭' : '播放中' }}</span>
      </div>
      <span class="select-wrap">
        <select id="noise-kind" :value="noise" @change="changeNoise">
          <option v-for="item in noiseOptions" :key="item.id" :value="item.id">{{ item.label }}</option>
        </select>
        <ChevronDown :size="14" aria-hidden="true" />
      </span>
      <div class="sound-volume">
        <VolumeX v-if="noise === 'off' || volume === 0" :size="16" aria-hidden="true" />
        <Volume2 v-else :size="16" aria-hidden="true" />
        <input v-model.number="volume" type="range" min="0" max="100" aria-label="环境音音量" />
        <span>{{ volume }}%</span>
      </div>
      <p v-if="noiseError" class="sound-error" role="status">{{ noiseError }}</p>
    </section>
    <audio
      v-if="ambientUrl"
      ref="ambientAudio"
      :src="ambientUrl"
      loop
      preload="auto"
      aria-label="主题环境音"
      data-theme-ambient
      hidden
      @error="ambientFailed"
    ></audio>
  </div>
</template>
