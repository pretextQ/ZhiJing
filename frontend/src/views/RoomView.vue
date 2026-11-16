<script setup lang="ts">
import { Headphones, Images } from '@lucide/vue'
import { computed } from 'vue'
import FocusTimer from '../components/FocusTimer.vue'
import { useThemesStore } from '../stores/themes'
import type { ToolId } from '../types'

defineProps<{ tool?: ToolId | null }>()
const emit = defineEmits<{ 'toggle-tool': [event: MouseEvent, id: ToolId] }>()

const themes = useThemesStore()
const appliedName = computed(() => themes.appliedTheme.name)
</script>

<template>
  <main class="focus-main">
    <FocusTimer />
    <footer class="focus-footer">
      <div class="focus-dock" role="group" aria-label="自习室设置">
        <button
          type="button"
          class="focus-glass"
          aria-controls="room-tools"
          :aria-label="'切换场景，当前' + appliedName"
          :aria-expanded="tool === 'scenes'"
          @click="emit('toggle-tool', $event, 'scenes')"
        >
          <Images :size="19" aria-hidden="true" /> {{ appliedName }}
        </button>
        <button
          type="button"
          class="focus-glass"
          aria-controls="room-tools"
          :aria-expanded="tool === 'sound'"
          @click="emit('toggle-tool', $event, 'sound')"
        >
          <Headphones :size="19" aria-hidden="true" /> 声音
        </button>
      </div>
    </footer>
  </main>
</template>
