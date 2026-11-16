<script setup lang="ts">
import { defaultKeymap, history, historyKeymap, isolateHistory } from '@codemirror/commands'
import { markdown } from '@codemirror/lang-markdown'
import { EditorState } from '@codemirror/state'
import { EditorView, keymap, placeholder } from '@codemirror/view'
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'

const props = defineProps<{ lessonId: number; initialText: string }>()
const emit = defineEmits<{
  edit: [id: number, text: string]
  timestamp: []
  save: []
}>()
const host = ref<HTMLDivElement>()
const states = new Map<number, EditorState>()
let view: EditorView

function makeState(doc: string) {
  return EditorState.create({
    doc,
    extensions: [
      history(),
      markdown(),
      EditorView.lineWrapping,
      EditorView.contentAttributes.of({ 'aria-label': '课程笔记', spellcheck: 'false' }),
      placeholder('用 Markdown 记录疑问、要点和自己的理解…'),
      keymap.of([
        { key: 'Alt-t', run: () => { emit('timestamp'); return true } },
        { key: 'Mod-s', run: () => { emit('save'); return true } },
        ...historyKeymap,
        ...defaultKeymap,
      ]),
      EditorView.updateListener.of(update => {
        if (update.docChanged) emit('edit', props.lessonId, update.state.doc.toString())
      }),
    ],
  })
}

onMounted(() => { view = new EditorView({ state: makeState(props.initialText), parent: host.value }) })
onBeforeUnmount(() => view.destroy())
watch(() => props.lessonId, (id, previousId) => {
  states.set(previousId, view.state)
  view.setState(states.get(id) ?? makeState(props.initialText))
})

function insert(text: string) {
  view.dispatch({
    ...view.state.replaceSelection(text),
    annotations: isolateHistory.of('full'),
    scrollIntoView: true,
  })
  view.focus()
}

function replace(text: string) {
  view.dispatch({
    changes: { from: 0, to: view.state.doc.length, insert: text },
    annotations: isolateHistory.of('full'),
  })
}

defineExpose({ insert, replace })
</script>

<template>
  <div ref="host" class="note-editor"></div>
</template>
