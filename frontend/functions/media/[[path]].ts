// Product photos. With an R2 bucket bound as MEDIA (backend MEDIA_STORAGE=r2) they are read
// straight from the bucket; without one they come from the backend like /api (local disk + nginx).
import { onRequest as proxyToBackend } from '../api/[[path]]'

interface R2ObjectBody {
  body: ReadableStream
  httpEtag: string
}

interface Env {
  BACKEND_URL?: string
  MEDIA?: { get(key: string): Promise<R2ObjectBody | null> }
}

interface PagesContext {
  request: Request
  env: Env
}

// Only what the API ever writes: random hex names, webp.
const PHOTO_KEY = /^\/media\/(products\/[0-9a-f]+\.webp)$/

export async function onRequest(context: PagesContext): Promise<Response> {
  const { request, env } = context
  if (!env.MEDIA) return proxyToBackend(context)

  const key = new URL(request.url).pathname.match(PHOTO_KEY)?.[1]
  if (!key || (request.method !== 'GET' && request.method !== 'HEAD')) {
    return new Response('Not found', { status: 404 })
  }
  const object = await env.MEDIA.get(key)
  if (!object) return new Response('Not found', { status: 404 })

  // Names are random and never reused, so they cache forever (same as nginx.conf).
  return new Response(request.method === 'HEAD' ? null : object.body, {
    headers: {
      'Content-Type': 'image/webp',
      'Cache-Control': 'public, max-age=31536000, immutable',
      ETag: object.httpEtag,
      'X-Content-Type-Options': 'nosniff',
    },
  })
}
