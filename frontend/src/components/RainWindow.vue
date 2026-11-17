<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'

// Match the rain scene's aspect ratio so the layer and photo are cropped together.
const width = 1200
const height = 675
const maxY = height * 0.69
const canvas = ref<HTMLCanvasElement>()

interface Drop {
  x: number
  y: number
  speed: number
  length: number
  opacity: number
}

let frame = 0
let previous: number | undefined

function random(min: number, max: number) {
  return min + Math.random() * (max - min)
}

function windowPane() {
  const pane = new Path2D()
  // Keep moving rain inside the photographed glass and clear of the lamp and desk.
  pane.moveTo(width * 0.034, 0)
  pane.lineTo(width * 0.971, 0)
  pane.lineTo(width * 0.971, height * 0.626)
  pane.lineTo(width * 0.789, height * 0.626)
  pane.lineTo(width * 0.766, height * 0.684)
  pane.lineTo(width * 0.624, height * 0.684)
  pane.lineTo(width * 0.612, height * 0.653)
  pane.lineTo(width * 0.303, height * 0.653)
  pane.lineTo(width * 0.268, height * 0.47)
  pane.lineTo(width * 0.268, height * 0.325)
  pane.lineTo(width * 0.187, height * 0.25)
  pane.lineTo(width * 0.034, height * 0.25)
  pane.closePath()
  return pane
}

function makeDrop(glass: boolean): Drop {
  return {
    x: random(width * 0.035, width * 0.97),
    y: random(-maxY, maxY),
    speed: glass ? random(13, 55) : random(220, 430),
    length: glass ? random(12, 31) : random(9, 25),
    opacity: glass ? random(0.22, 0.58) : random(0.07, 0.23),
  }
}

function drawRain(context: CanvasRenderingContext2D, drops: Drop[], step: number) {
  context.lineWidth = 0.75
  context.strokeStyle = '#d9e9e7'
  for (const drop of drops) {
    drop.y += drop.speed * step
    drop.x -= drop.speed * step * 0.17
    if (drop.y > maxY + drop.length || drop.x < 0) {
      drop.y = -drop.length
      drop.x = random(width * 0.04, width * 1.06)
    }
    context.globalAlpha = drop.opacity
    context.beginPath()
    context.moveTo(drop.x + drop.length * 0.17, drop.y - drop.length)
    context.lineTo(drop.x, drop.y)
    context.stroke()
  }
  context.globalAlpha = 1
}

function drawGlass(context: CanvasRenderingContext2D, drops: Drop[], step: number) {
  for (const drop of drops) {
    drop.y += drop.speed * step
    if (drop.y > maxY + drop.length) {
      drop.y = random(-160, -drop.length)
      drop.x = random(width * 0.05, width * 0.96)
    }
    const bend = Math.sin(drop.y / 12 + drop.x) * 1.7
    const x = drop.x + bend
    const trail = context.createLinearGradient(x, drop.y - drop.length, x, drop.y)
    trail.addColorStop(0, 'transparent')
    trail.addColorStop(1, `rgba(216, 236, 230, ${drop.opacity * 0.62})`)
    context.lineWidth = 0.95
    context.strokeStyle = trail
    context.beginPath()
    context.moveTo(drop.x, drop.y - drop.length)
    context.quadraticCurveTo(x + bend, drop.y - drop.length / 2, x, drop.y)
    context.stroke()

    context.fillStyle = `rgba(15, 38, 34, ${drop.opacity * 0.78})`
    context.beginPath()
    context.ellipse(x + 0.55, drop.y, 1.3, 2.4, 0.13, 0, Math.PI * 2)
    context.fill()
    context.fillStyle = `rgba(240, 251, 240, ${drop.opacity})`
    context.beginPath()
    context.ellipse(x, drop.y - 0.3, 0.68, 1.65, 0.13, 0, Math.PI * 2)
    context.fill()
  }
}

function stop() {
  window.cancelAnimationFrame(frame)
  frame = 0
  previous = undefined
}

let syncVisibility: (() => void) | undefined

onMounted(() => {
  if (typeof Path2D === 'undefined') return
  const context = canvas.value?.getContext('2d')
  if (!context) return
  const pane = windowPane()
  const rain = Array.from({ length: 82 }, () => makeDrop(false))
  const glass = Array.from({ length: 31 }, () => makeDrop(true))

  const paint = (timestamp: number) => {
    frame = window.requestAnimationFrame(paint)
    const elapsed = previous === undefined ? 0 : timestamp - previous
    if (previous !== undefined && elapsed < 32) return
    previous = timestamp
    const step = Math.min(elapsed, 80) / 1000
    context.clearRect(0, 0, width, height)
    context.save()
    context.clip(pane)
    drawRain(context, rain, step)
    drawGlass(context, glass, step)
    context.restore()
  }

  syncVisibility = () => {
    if (document.hidden) stop()
    else if (!frame) frame = window.requestAnimationFrame(paint)
  }
  document.addEventListener('visibilitychange', syncVisibility)
  syncVisibility()
})

onUnmounted(() => {
  stop()
  if (syncVisibility) document.removeEventListener('visibilitychange', syncVisibility)
})
</script>

<template>
  <canvas ref="canvas" class="scene-rain" :width="width" :height="height" aria-hidden="true"></canvas>
</template>

<style scoped>
.scene-rain {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  object-fit: cover;
}

@media (prefers-reduced-motion: reduce) {
  .scene-rain {
    display: none;
  }
}
</style>
