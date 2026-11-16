import { createRequire } from 'node:module'
import { resolve } from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'

const project = fileURLToPath(new URL('../', import.meta.url))
const frontend = resolve(project, '.dev/learnhub/frontend')
const require = createRequire(resolve(frontend, 'package.json'))
const { loadConfigFromFile } = await import(pathToFileURL(require.resolve('vite')).href)

export default async (env) => {
  const { config } = await loadConfigFromFile(env, resolve(frontend, 'vite.config.js'), frontend)
  const spring = process.env.ZHIJING_SPRING_URL || 'http://127.0.0.1:18080'
  const polish = process.env.ZHIJING_POLISH_BACKEND || 'spring'
  if (!['spring', 'python'].includes(polish)) {
    throw new Error('ZHIJING_POLISH_BACKEND must be spring or python')
  }
  const proxy = {}
  if (polish === 'python') {
    proxy['^/api/ai/polish-stream(?:\\?|$)'] = {
      target: process.env.ZHIJING_PYTHON_URL || 'http://127.0.0.1:18081',
      changeOrigin: true,
      configure(server) {
        // When fetch is aborted after uploading its body, close the upstream response too.
        server.on('proxyRes', (upstream, _request, response) => {
          if (response.destroyed) upstream.destroy()
          else response.once('close', () => {
            if (!response.writableFinished) upstream.destroy()
          })
        })
      },
    }
  }
  proxy['/api'] = { target: spring, changeOrigin: true }
  // Build the proxy map in match order. Merging the baseline map would leave /api first.
  const { server, preview, ...base } = config
  return {
    ...base,
    server: { ...server, host: '127.0.0.1', port: Number(process.env.ZHIJING_VITE_PORT || 15174), proxy },
    preview: { ...preview, host: '127.0.0.1', proxy },
  }
}
