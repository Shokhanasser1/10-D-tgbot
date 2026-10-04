// Opens a free Cloudflare quick tunnel to the local backend (the FastAPI app on port 8000 by
// default: docker compose `api` or uvicorn; the Pages Function strips /api itself), points the
// Pages project at it (BACKEND_URL) and redeploys so the change takes effect.
// A quick tunnel gets a new *.trycloudflare.com address on every start, which is why this runs
// both steps together; the Mini App keeps its stable *.pages.dev address.
//
// Usage (from frontend/, after `npx wrangler login`):  npm run tunnel
// Keep it running: stopping it (Ctrl+C) closes the tunnel and the shop loses its backend.

import { spawn, spawnSync } from 'node:child_process'

const LOCAL_URL = process.env.BACKEND_LOCAL_URL ?? 'http://localhost:8000'
const TUNNEL_URL = /https:\/\/[a-z0-9-]+\.trycloudflare\.com/

function wrangler(args, input) {
  const result = spawnSync('npx', ['wrangler', ...args], {
    input,
    stdio: [input === undefined ? 'inherit' : 'pipe', 'inherit', 'inherit'],
    shell: process.platform === 'win32',
  })
  if (result.status !== 0) throw new Error(`wrangler ${args.join(' ')} failed`)
}

function publish(backendUrl) {
  console.log(`\nTunnel is up: ${backendUrl}\nPointing Pages at it and redeploying...`)
  try {
    wrangler(['pages', 'secret', 'put', 'BACKEND_URL'], backendUrl)
    wrangler(['pages', 'deploy'])
    console.log('\nDone. Leave this window open while the shop should work.')
  } catch (error) {
    console.error(`\n${error.message}. The tunnel stays up; fix the error and rerun.`)
  }
}

const tunnel = spawn('cloudflared', ['tunnel', '--no-autoupdate', '--url', LOCAL_URL])
let published = false
const watch = (chunk) => {
  const match = !published && chunk.toString().match(TUNNEL_URL)
  if (match) {
    published = true
    publish(match[0])
  }
}
tunnel.stdout.on('data', watch)
tunnel.stderr.on('data', watch)
tunnel.on('error', () => {
  console.error('cloudflared not found: install it from https://github.com/cloudflare/cloudflared')
  process.exit(1)
})
tunnel.on('exit', (code) => process.exit(code ?? 0))
process.on('SIGINT', () => tunnel.kill('SIGINT'))
