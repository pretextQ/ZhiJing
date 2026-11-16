<script setup lang="ts">
import {
  ArrowDownToLine,
  ArrowDownRight,
  ArrowRight,
  ArrowUpRight,
  BookOpen,
  Check,
  ChevronDown,
  CircleHelp,
  Clock3,
  ExternalLink,
  Link,
  PencilLine,
  Play,
  Save,
  Video,
} from '@lucide/vue'
import { storeToRefs } from 'pinia'
import { computed, defineAsyncComponent, onMounted, ref, watch } from 'vue'
import {
  type LessonSummary,
  downloadNote,
  formatTime,
  messageFor,
  noteTimes,
  playerAt,
  secondsFromInput,
  sourceAt,
} from '../study'
import { useStudy } from '../stores/study'

const props = defineProps<{ visible: boolean }>()
const NoteEditor = defineAsyncComponent(() => import('./NoteEditor.vue'))

const study = useStudy()
const { lessons, active, obsidianEnabled, draft } = storeToRefs(study)
const { load, open, reopen, update, edit, flush, restore, exportNote } = study
const editor = ref<InstanceType<typeof NoteEditor>>()
const courseUrl = ref('')
const timeInput = ref('')
const loading = ref(true)
const switching = ref(false)
const updating = ref(false)
const exporting = ref(false)
const restoring = ref(false)
const courseError = ref('')
const noteError = ref('')
const noteMessage = ref('')
const stampError = ref('')
const playerUrl = ref<string | null>(null)
const playerInstance = ref(0)
const bookmarked = computed(() => (active.value ? formatTime(active.value.seconds) : '00:00'))
const timestamps = computed(() => (active.value && draft.value ? noteTimes(active.value, draft.value.text) : []))
const noteStatus = computed(() => {
  switch (draft.value?.status) {
    case 'saved':
      return '已保存'
    case 'pending':
      return '待保存'
    case 'saving':
      return '保存中'
    case 'offline':
      return draft.value.cached ? '草稿留在浏览器，可重试' : '未保存，请重试或下载'
    case 'conflict':
      return '另一窗口已保存新版'
    default:
      return ''
  }
})

function seek(lesson: LessonSummary, seconds: number, play: boolean) {
  playerUrl.value = playerAt(lesson, seconds, play)
  ++playerInstance.value
}

watch(
  () => props.visible,
  (visible) => {
    const lesson = active.value
    if (!visible && lesson) {
      seek(lesson, lesson.seconds, false)
      void flush(lesson.id)
    }
  },
)

function showLesson(lesson: LessonSummary) {
  timeInput.value = ''
  noteError.value = ''
  noteMessage.value = ''
  stampError.value = ''
  seek(lesson, lesson.seconds, false)
}

async function loadRoom() {
  loading.value = true
  courseError.value = ''
  try {
    const lesson = await load()
    if (lesson) showLesson(lesson)
  } catch (error) {
    courseError.value = messageFor(error)
  } finally {
    loading.value = false
  }
}

onMounted(loadRoom)

async function openLesson(action: () => Promise<LessonSummary>) {
  switching.value = true
  courseError.value = ''
  try {
    showLesson(await action())
    return true
  } catch (error) {
    courseError.value = messageFor(error)
    return false
  } finally {
    switching.value = false
  }
}

async function addLesson() {
  const url = courseUrl.value.trim()
  if (url && (await openLesson(() => open(url)))) courseUrl.value = ''
}

async function chooseLesson(event: Event) {
  const select = event.target as HTMLSelectElement
  const opened = await openLesson(() => reopen(Number(select.value)))
  if (!opened) select.value = String(active.value?.id ?? '')
}

async function rename(event: Event) {
  const field = event.target as HTMLInputElement
  const lesson = active.value
  if (!lesson) return
  const title = field.value.trim()
  if (!title || title === lesson.title) {
    field.value = lesson.title
    return
  }
  courseError.value = ''
  try {
    const renamed = await update(lesson.id, { title })
    field.value = renamed.title
  } catch (error) {
    field.value = lesson.title
    courseError.value = messageFor(error)
  }
}

function readStamp() {
  const seconds = secondsFromInput(timeInput.value)
  stampError.value = seconds === null ? '请输入秒数或分:秒，例如 12:34' : ''
  return seconds
}

function insertTime() {
  const lesson = active.value
  if (!lesson) return
  const seconds = readStamp()
  if (seconds !== null) editor.value?.insert(`[${formatTime(seconds)}](${sourceAt(lesson, seconds)})`)
}

async function saveBookmark() {
  const lesson = active.value
  const seconds = readStamp()
  if (!lesson || seconds === null) return
  updating.value = true
  try {
    await update(lesson.id, { seconds })
    if (active.value?.id === lesson.id) noteMessage.value = `续播点已设为 ${formatTime(seconds)}`
  } catch (error) {
    if (active.value?.id === lesson.id) stampError.value = messageFor(error)
  } finally {
    updating.value = false
  }
}

function saveDraft() {
  if (active.value) void flush(active.value.id)
}

function onNoteEdit(id: number, text: string) {
  noteMessage.value = ''
  edit(id, text)
}

async function exportToObsidian() {
  const id = active.value?.id
  if (!id) return
  noteError.value = ''
  exporting.value = true
  try {
    const result = await exportNote(id)
    if (active.value?.id === id) noteMessage.value = `已写入 ${result.filename}`
  } catch (error) {
    if (active.value?.id === id) noteError.value = messageFor(error)
  } finally {
    exporting.value = false
  }
}

async function restoreDraft() {
  const id = active.value?.id
  if (!id) return
  restoring.value = true
  try {
    const text = await restore(id)
    if (text !== null && active.value?.id === id) editor.value?.replace(text)
  } catch (error) {
    if (active.value?.id === id) noteError.value = messageFor(error)
  } finally {
    restoring.value = false
  }
}
</script>

<template>
  <main class="course-room">
    <div class="course-page-heading">
      <h1 id="course-page-title" tabindex="-1">看课笔记</h1>
      <button
        v-if="active?.embed_url && active.seconds > 0"
        type="button"
        class="quiet-button"
        @click="seek(active, active.seconds, true)"
      >
        <Play :size="15" aria-hidden="true" /> 从 {{ bookmarked }} 继续
      </button>
    </div>
    <div class="workspace">
      <section class="panel course-panel" aria-labelledby="course-heading">
        <div class="panel-header">
          <h2 id="course-heading"><Video :size="20" aria-hidden="true" /> 视频课程</h2>
          <span v-if="lessons.length" class="select-wrap recent-select">
            <select aria-label="最近课程" :value="active?.id" :disabled="switching || restoring" @change="chooseLesson">
              <option v-for="lesson in lessons" :key="lesson.id" :value="lesson.id">
                {{ lesson.title }}{{ lesson.embed_url ? ' · P' + lesson.part : '' }}
              </option>
            </select>
            <ChevronDown :size="14" aria-hidden="true" />
          </span>
        </div>

        <form class="link-form" @submit.prevent="addLesson">
          <label class="link-field">
            <Link :size="17" aria-hidden="true" />
            <input
              v-model="courseUrl"
              type="text"
              inputmode="url"
              autocomplete="off"
              spellcheck="false"
              maxlength="2048"
              aria-label="B 站视频链接"
              placeholder="粘贴 B 站视频链接"
              required
            />
          </label>
          <button type="submit" class="primary-button" :disabled="loading || switching || restoring">
            打开 <ArrowRight :size="16" aria-hidden="true" />
          </button>
        </form>

        <p v-if="courseError" class="error course-error" role="alert">{{ courseError }}</p>
        <div class="video-space" :class="{ 'video-loaded': playerUrl }">
          <iframe
            v-if="visible && playerUrl"
            :key="playerInstance"
            :src="playerUrl"
            title="B 站课程播放器"
            allow="autoplay; fullscreen; encrypted-media; picture-in-picture"
            allowfullscreen
          ></iframe>
          <div v-else class="video-empty">
            <span class="video-illustration"><Play :size="27" :stroke-width="1.7" aria-hidden="true" /></span>
            <h3>{{ loading ? '正在打开自习室' : active ? '前往 B 站观看此课程' : '打开一节 B 站课' }}</h3>
            <a v-if="active" class="quiet-button" :href="active.original_url" target="_blank" rel="noopener noreferrer"
              >在 B 站打开 <ArrowUpRight :size="15" aria-hidden="true"
            /></a>
            <p v-else-if="!loading">支持视频、短链接和多 P 选集</p>
          </div>
        </div>

        <div v-if="active" class="course-footer">
          <div class="course-meta">
            <span v-if="active.embed_url" class="part-label">P{{ active.part }}</span>
            <input
              :key="active.id"
              class="rename-field"
              aria-label="课程名称"
              title="点击修改课程名称"
              :value="active.title"
              maxlength="80"
              @change="rename"
              @keydown.enter.prevent="($event.target as HTMLInputElement).blur()"
            />
            <PencilLine :size="14" aria-hidden="true" class="rename-icon" />
          </div>
          <div class="course-actions">
            <button
              v-if="active.embed_url"
              type="button"
              class="text-button"
              :aria-label="'从续播点 ' + bookmarked + ' 播放'"
              @click="seek(active, active.seconds, true)"
            >
              <Clock3 :size="15" aria-hidden="true" /> {{ bookmarked }}
            </button>
            <a
              v-if="active.embed_url"
              class="text-button"
              :href="sourceAt(active, active.seconds)"
              target="_blank"
              rel="noopener noreferrer"
              >B 站原页 <ExternalLink :size="14" aria-hidden="true"
            /></a>
          </div>
        </div>
      </section>

      <section class="panel note-panel" aria-labelledby="note-heading">
        <div class="panel-header">
          <h2 id="note-heading"><PencilLine :size="19" aria-hidden="true" /> 课程笔记</h2>
          <span
            v-if="draft"
            class="save-status"
            :class="{ 'save-warning': draft.status === 'conflict' || draft.status === 'offline' }"
            role="status"
          >
            <Check v-if="draft.status === 'saved'" :size="15" aria-hidden="true" /> {{ noteStatus }}
          </span>
        </div>

        <template v-if="active && draft">
          <form class="stamp-form" @submit.prevent="insertTime">
            <label class="stamp-field">
              <Clock3 :size="17" aria-hidden="true" />
              <input
                v-model="timeInput"
                type="text"
                aria-label="时间点"
                autocomplete="off"
                placeholder="分:秒"
                maxlength="8"
                @input="stampError = ''"
              />
            </label>
            <button type="submit" class="quiet-button" title="插入时间点（Alt+T）">
              <ArrowDownRight :size="15" aria-hidden="true" /> 插入
            </button>
            <button
              v-if="active.embed_url"
              type="button"
              class="quiet-button mark-button"
              :disabled="updating"
              @click="saveBookmark"
            >
              设为续播点
            </button>
          </form>
          <p v-if="stampError" class="error" role="alert">{{ stampError }}</p>
          <NoteEditor
            ref="editor"
            :lesson-id="active.id"
            :initial-text="draft.text"
            @edit="onNoteEdit"
            @timestamp="insertTime"
            @save="saveDraft"
          />
          <div v-if="timestamps.length" class="timestamps" aria-label="笔记时间点">
            <template v-for="seconds in timestamps" :key="seconds">
              <button
                v-if="active.embed_url"
                type="button"
                class="time-chip"
                :aria-label="'跳到 ' + formatTime(seconds)"
                @click="seek(active, seconds, true)"
              >
                <Play :size="11" aria-hidden="true" /> {{ formatTime(seconds) }}
              </button>
              <span v-else class="time-chip"><Clock3 :size="12" aria-hidden="true" /> {{ formatTime(seconds) }}</span>
            </template>
          </div>
          <div v-if="draft.status === 'conflict' || draft.status === 'offline'" class="recovery">
            <span v-if="draft.status === 'conflict'">可先下载当前草稿，再载入已保存版。</span>
            <button
              v-if="draft.status === 'conflict'"
              type="button"
              class="text-button"
              :disabled="restoring"
              @click="restoreDraft"
            >
              载入已保存版
            </button>
            <button v-else type="button" class="text-button" @click="saveDraft">重试保存</button>
          </div>
          <p v-if="noteError" class="error" role="alert">{{ noteError }}</p>
          <p v-if="noteMessage" class="note-message" role="status">{{ noteMessage }}</p>
          <div class="note-footer">
            <button
              type="button"
              :class="obsidianEnabled ? 'quiet-button' : 'primary-button'"
              @click="downloadNote(active, draft.text)"
            >
              <ArrowDownToLine :size="16" aria-hidden="true" /> 下载 Markdown
            </button>
            <button
              v-if="obsidianEnabled"
              type="button"
              class="primary-button"
              :disabled="exporting || restoring"
              @click="exportToObsidian"
            >
              <Save :size="16" aria-hidden="true" /> {{ exporting ? '写入中' : '保存到 Obsidian' }}
            </button>
            <span v-else class="export-help" title="在 .env 设置 ZHIJING_STUDY_OBSIDIAN_DIR，可直接保存到 Obsidian">
              <CircleHelp :size="15" aria-hidden="true" /> 或配置 Obsidian 目录
            </span>
          </div>
        </template>
        <div v-else class="note-empty">
          <span><BookOpen :size="24" :stroke-width="1.5" aria-hidden="true" /></span>
          <p>打开课程后开始记笔记</p>
        </div>
      </section>
    </div>
  </main>
</template>
