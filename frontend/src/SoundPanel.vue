<script setup lang="ts">
import { ChevronDown, Headphones, ListMusic, Plus, Trash2, Volume2, VolumeX } from '@lucide/vue'
import { computed, nextTick, onBeforeUnmount, onMounted, ref, shallowRef, watch } from 'vue'
import { type Track, readTracks, saveTracks } from './playlist'
import { readLocal, writeLocal } from './study'

const noises = [
  { id: 'off', label: '静音' },
  { id: 'white', label: '白噪音' },
  { id: 'pink', label: '粉噪音' },
  { id: 'brown', label: '棕噪音' },
] as const
type Noise = typeof noises[number]['id']
const noise = ref<Noise>('off')
const volume = ref(readLocal<number>('noise-volume') ?? 25)
const tracks = shallowRef<Track[]>([])
const trackId = ref('')
const trackUrl = ref('')
const audio = ref<HTMLAudioElement>()
const fileInput = ref<HTMLInputElement>()
const loading = ref(true)
const updating = ref(false)
const noiseError = ref('')
const playlistError = ref('')
const currentIndex = computed(() => tracks.value.findIndex(track => track.id === trackId.value))
let context: AudioContext | undefined
let source: AudioBufferSourceNode | undefined
let gain: GainNode | undefined
let soundChange = 0

function makeNoise(audioContext: AudioContext, kind: Exclude<Noise, 'off'>) {
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
      low = .99765 * low + white * .099046
      middle = .963 * middle + white * .2965164
      high = .57 * high + white * 1.0526913
      data[i] = (low + middle + high + white * .1848) * .15
    } else {
      data[i] = white * .35
    }
  }
  // Bring the endpoints to zero so looping does not add a click.
  const fade = Math.round(audioContext.sampleRate * .015)
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

async function changeNoise(event: Event) {
  const kind = (event.target as HTMLSelectElement).value as Noise
  const change = ++soundChange
  noise.value = kind
  noiseError.value = ''
  stopNoise()
  if (kind === 'off') return
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

watch(volume, value => {
  writeLocal('noise-volume', value)
  if (context && gain) gain.gain.setTargetAtTime(value / 100, context.currentTime, .025)
})

async function selectTrack(id: string, play = false) {
  const track = tracks.value.find(item => item.id === id)
  if (trackId.value !== id || !trackUrl.value) {
    audio.value?.pause()
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
  const imported = Array.from(input.files ?? []).filter(file =>
    file.type.startsWith('audio/') || /\.(mp3|wav|ogg|opus|m4a|aac|flac|webm)$/i.test(file.name),
  )
  input.value = ''
  if (!imported.length) {
    playlistError.value = '请选择音频文件'
    return
  }
  const entries = imported.map(file => ({ id: crypto.randomUUID(), file }))
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
  const next = tracks.value.filter(track => track.id !== trackId.value)
  return updateTracks(next, next[Math.min(index, next.length - 1)]?.id ?? '')
}

function playNext() {
  const next = tracks.value[(currentIndex.value + 1) % tracks.value.length]
  if (next) {
    playlistError.value = ''
    void selectTrack(next.id, true)
  }
}

onMounted(async () => {
  try {
    tracks.value = await readTracks()
    const remembered = readLocal<string>('track')
    const selected = tracks.value.find(track => track.id === remembered) ?? tracks.value[0]
    if (selected) await selectTrack(selected.id)
  } catch {
    playlistError.value = '无法读取本地歌单'
  } finally {
    loading.value = false
  }
})

onBeforeUnmount(() => {
  ++soundChange
  stopNoise()
  void context?.close()
  if (trackUrl.value) URL.revokeObjectURL(trackUrl.value)
})
</script>

<template>
  <section class="sound-bar" aria-label="声音设置">
    <div class="sound-group ambience">
      <span class="sound-icon"><Headphones :size="19" /></span>
      <label for="noise-kind">环境音</label>
      <span class="select-wrap">
        <select id="noise-kind" :value="noise" @change="changeNoise">
          <option v-for="item in noises" :key="item.id" :value="item.id">{{ item.label }}</option>
        </select>
        <ChevronDown :size="14" aria-hidden="true" />
      </span>
      <div class="volume-control">
        <VolumeX v-if="noise === 'off' || volume === 0" :size="16" aria-hidden="true" />
        <Volume2 v-else :size="16" aria-hidden="true" />
        <input v-model.number="volume" type="range" min="0" max="100" aria-label="环境音音量">
      </div>
    </div>
    <div class="sound-group playlist">
      <span class="sound-icon"><ListMusic :size="19" /></span>
      <label for="track-select">本地歌单</label>
      <span v-if="tracks.length" class="select-wrap track-select">
        <select
          id="track-select"
          :value="trackId"
          @change="playlistError = ''; selectTrack(($event.target as HTMLSelectElement).value, true)"
        >
          <option v-for="track in tracks" :key="track.id" :value="track.id">{{ track.file.name }}</option>
        </select>
        <ChevronDown :size="14" aria-hidden="true" />
      </span>
      <audio
        v-show="tracks.length"
        :src="trackUrl || undefined"
        controls
        preload="metadata"
        aria-label="本地歌单播放器"
        @ended="playNext"
        @error="trackUrl && (playlistError = '无法播放这首曲目，请检查音频格式')"
      ></audio>
      <button
        v-if="tracks.length"
        type="button"
        class="icon-button track-remove"
        aria-label="移除当前曲目"
        title="移除当前曲目"
        :disabled="updating"
        @click="removeTrack"
      ><Trash2 :size="16" aria-hidden="true" /></button>
      <button
        type="button"
        class="quiet-button add-audio"
        :disabled="loading || updating"
        @click="fileInput?.click()"
      ><Plus :size="17" aria-hidden="true" /> 添加音乐</button>
      <input ref="fileInput" type="file" accept="audio/*,.flac,.opus" multiple hidden @change="importTracks">
    </div>
    <p v-if="noiseError || playlistError" class="sound-error" role="status">{{ noiseError || playlistError }}</p>
  </section>
</template>
