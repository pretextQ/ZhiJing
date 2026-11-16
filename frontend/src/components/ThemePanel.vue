<script setup lang="ts">
import { Download, Pencil, Trash2, Upload } from '@lucide/vue'
import { storeToRefs } from 'pinia'
import { nextTick, ref } from 'vue'
import { useThemesStore } from '../stores/themes'
import { builtinThemes, themeMessage, type Theme } from '../themes'

const emit = defineEmits<{ close: [] }>()

const themes = useThemesStore()
const { appliedId, canApply, customThemes, limitsText, motionEnabled, preview, reducedMotion } = storeToRefs(themes)

const panel = ref<HTMLElement>()
const themeFile = ref<HTMLInputElement>()
const importing = ref(false)
const deletingId = ref('')
const confirmDeleteId = ref('')
const sceneError = ref('')
const sceneNotice = ref('')
const renamingId = ref('')
const renameValue = ref('')
const exportingId = ref('')

function clearSceneMessages() {
  sceneError.value = ''
  sceneNotice.value = ''
}

function focusFirst() {
  panel.value?.querySelector<HTMLElement>('.scene-pick')?.focus()
}

function selectPreview(item: Theme) {
  themes.previewTheme(item)
  confirmDeleteId.value = ''
  clearSceneMessages()
}

function applyScene() {
  if (!canApply.value) return
  themes.applyTheme()
  emit('close')
}

function toggleMotion(event: Event) {
  themes.setMotionEnabled((event.target as HTMLInputElement).checked)
}

function askDelete(item: Theme) {
  renamingId.value = ''
  renameValue.value = ''
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
    const { theme, existing } = await themes.importThemePackage(file)
    if (existing) {
      sceneNotice.value = '该主题包已在主题库中'
    } else {
      sceneNotice.value = `已导入：${theme.name}`
    }
    themes.previewTheme(theme)
    void nextTick(() => {
      // jsdom 等非浏览器环境没有 scrollIntoView，保留可选调用。
      panel.value?.querySelector<HTMLElement>('[data-preview="true"]')?.scrollIntoView?.({ block: 'center' })
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
    await themes.deleteTheme(item)
    confirmDeleteId.value = ''
    sceneNotice.value = `已删除：${item.name}`
    void nextTick(() => {
      if (!document.activeElement || document.activeElement === document.body) {
        panel.value?.querySelector<HTMLElement>('.scene-pick')?.focus()
      }
    })
  } catch (error) {
    sceneError.value = themeMessage(error)
  } finally {
    deletingId.value = ''
  }
}

function startRename(item: Theme) {
  confirmDeleteId.value = ''
  clearSceneMessages()
  renamingId.value = item.id
  renameValue.value = item.name
  void nextTick(() => {
    const input = panel.value?.querySelector<HTMLInputElement>('input[aria-label="主题名称"]')
    input?.focus()
    input?.select()
  })
}

function cancelRename() {
  renamingId.value = ''
  renameValue.value = ''
}

async function saveRename(item: Theme) {
  if (renamingId.value !== item.id) return
  const name = renameValue.value.trim()
  renamingId.value = ''
  renameValue.value = ''
  if (!name || name === item.name) return
  clearSceneMessages()
  try {
    const updated = await themes.renameTheme(item.id, name)
    sceneNotice.value = `已重命名：${updated.name}`
    void nextTick(() => {
      panel.value?.querySelector<HTMLElement>(`[data-theme-id="${updated.id}"] .scene-pick`)?.focus()
    })
  } catch (error) {
    sceneError.value = themeMessage(error)
  }
}

async function exportThemeFile(item: Theme) {
  if (exportingId.value) return
  exportingId.value = item.id
  renamingId.value = ''
  renameValue.value = ''
  clearSceneMessages()
  try {
    const { blob, filename } = await themes.exportTheme(item.id, item.name)
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = filename
    link.rel = 'noopener'
    document.body.append(link)
    link.click()
    link.remove()
    window.setTimeout(() => URL.revokeObjectURL(url), 10000)
    sceneNotice.value = `已导出：${filename}`
  } catch (error) {
    sceneError.value = themeMessage(error)
  } finally {
    exportingId.value = ''
  }
}

/**
 * 面板自己的键盘优先级：先取消重命名，再取消删除确认。
 * 返回 false 时交给 App 关闭整个设置面板。
 */
function handleEscape(): boolean {
  if (renamingId.value) {
    cancelRename()
    return true
  }
  if (confirmDeleteId.value) {
    confirmDeleteId.value = ''
    return true
  }
  return false
}

defineExpose({ focusFirst, handleEscape })
</script>

<template>
  <div ref="panel" class="scene-panel">
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
            @click="selectPreview(item)"
          >
            <img :src="item.coverUrl" alt="" />
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

    <div class="scene-motion">
      <label class="scene-motion-toggle">
        <input
          :checked="motionEnabled"
          type="checkbox"
          aria-label="背景动效"
          :title="reducedMotion ? '系统已开启减少动态效果，背景动效已停用' : '让场景背景缓慢平移或缩放'"
          @change="toggleMotion"
        />
        <span>背景动效</span>
      </label>
      <span v-if="reducedMotion" class="scene-motion-note">系统已要求减少动态效果，动效已停用</span>
    </div>

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
            @click="selectPreview(item)"
          >
            <img :src="item.coverUrl" alt="" />
            <span class="scene-name">{{ item.name }}</span>
          </button>
          <span v-if="appliedId === item.id" class="scene-badge">使用中</span>
          <span v-else-if="preview?.id === item.id" class="scene-badge">预览</span>
          <div class="scene-tools">
            <button
              type="button"
              class="icon-button scene-tool"
              :aria-label="`导出主题 ${item.name}`"
              title="导出主题包"
              :disabled="exportingId === item.id"
              @click="exportThemeFile(item)"
            >
              <Download :size="15" aria-hidden="true" />
            </button>
            <button
              type="button"
              class="icon-button scene-tool"
              :aria-label="`重命名主题 ${item.name}`"
              title="重命名主题"
              :disabled="renamingId === item.id"
              @click="startRename(item)"
            >
              <Pencil :size="15" aria-hidden="true" />
            </button>
            <button
              v-if="confirmDeleteId !== item.id"
              type="button"
              class="scene-delete icon-button"
              :aria-label="`删除主题 ${item.name}`"
              title="删除主题"
              @click="askDelete(item)"
            >
              <Trash2 :size="15" aria-hidden="true" />
            </button>
          </div>
          <div
            v-if="confirmDeleteId === item.id"
            class="scene-confirm"
            role="group"
            :aria-label="`删除主题 ${item.name}`"
          >
            <span>删除这个主题？</span>
            <button
              type="button"
              class="text-button scene-confirm-delete"
              :disabled="deletingId === item.id"
              @click="deleteTheme(item)"
            >
              确认删除
            </button>
            <button type="button" class="text-button" @click="cancelDelete">取消</button>
          </div>
          <input
            v-if="renamingId === item.id"
            v-model="renameValue"
            type="text"
            class="scene-rename-input"
            aria-label="主题名称"
            maxlength="60"
            autocomplete="off"
            spellcheck="false"
            @keydown.enter.prevent="saveRename(item)"
            @keydown.esc.stop.prevent="cancelRename()"
            @blur="saveRename(item)"
          />
        </li>
      </ul>
    </section>

    <div class="scene-footer">
      <div class="scene-import-area">
        <button type="button" class="quiet-button scene-import" :disabled="importing" @click="themeFile?.click()">
          <Upload :size="16" aria-hidden="true" /> {{ importing ? '正在导入…' : '导入主题包' }}
        </button>
        <p class="scene-limits">{{ limitsText }}</p>
      </div>
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
    />
  </div>
</template>
