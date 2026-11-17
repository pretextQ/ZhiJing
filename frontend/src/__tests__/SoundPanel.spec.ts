import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, describe, expect, it, vi } from 'vitest'

vi.mock('../playlist', () => ({
  readTracks: () => Promise.resolve([]),
  saveTracks: () => Promise.resolve(),
}))

import SoundPanel from '../components/SoundPanel.vue'

class FakeGain {
  gain = { value: 0, setTargetAtTime: vi.fn() }
  connect = vi.fn()
  disconnect = vi.fn()
}

class FakeSource {
  buffer: unknown = null
  loop = false
  connect = vi.fn()
  disconnect = vi.fn()
  start = vi.fn()
  stop = vi.fn()
}

class FakeAudioContext {
  state = 'running'
  sampleRate = 48_000
  currentTime = 0
  destination = {}
  resume = vi.fn()
  close = vi.fn()
  createBuffer = () => ({ getChannelData: () => new Float32Array(16) })
  createGain = () => new FakeGain()
  createBufferSource = () => new FakeSource()
}

function mountPanel() {
  return mount(SoundPanel, { props: { theme: null } })
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('SoundPanel ambience memory', () => {
  it('defaults to silent when nothing was remembered', async () => {
    vi.stubGlobal('AudioContext', FakeAudioContext)
    const wrapper = mountPanel()
    await flushPromises()
    expect((wrapper.get('#noise-kind').element as HTMLSelectElement).value).toBe('off')
  })

  it('remembers the selected noise so a reload keeps it', async () => {
    vi.stubGlobal('AudioContext', FakeAudioContext)
    const wrapper = mountPanel()
    await flushPromises()
    await wrapper.get('#noise-kind').setValue('pink')
    await flushPromises()
    expect(JSON.parse(localStorage.getItem('zhijing:noise') ?? 'null')).toBe('pink')
    wrapper.unmount()

    const reloaded = mountPanel()
    await flushPromises()
    expect((reloaded.get('#noise-kind').element as HTMLSelectElement).value).toBe('pink')
  })

  it('forgets a noise that fails to start instead of retrying forever', async () => {
    vi.stubGlobal(
      'AudioContext',
      class {
        state = 'running'
        destination = {}
        createGain(): never {
          throw new Error('audio blocked')
        }
      },
    )
    const wrapper = mountPanel()
    await flushPromises()
    await wrapper.get('#noise-kind').setValue('brown')
    await flushPromises()
    expect((wrapper.get('#noise-kind').element as HTMLSelectElement).value).toBe('off')
    expect(localStorage.getItem('zhijing:noise')).toBe(JSON.stringify('off'))
    expect(wrapper.text()).toContain('环境音启动失败')
  })
})
