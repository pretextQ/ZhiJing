<script setup lang="ts">
import { onActivated, onDeactivated, ref } from 'vue'
import { useRoute } from 'vue-router'
import CourseWorkspace from '../components/CourseWorkspace.vue'

const route = useRoute()
const visible = ref(route.name === 'courses')

onActivated(() => {
  visible.value = route.name === 'courses'
})
onDeactivated(() => {
  visible.value = false
})
</script>

<template>
  <CourseWorkspace :visible="visible" />
</template>
