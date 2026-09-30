// Cloudflare Pages Function: forwards /api/* (and /media/*, see ../media) to the backend's public
// origin, so the Mini App on *.pages.dev stays same-origin and needs no CORS. BACKEND_URL is the
// Cloudflare Tunnel in front of the docker compose `web` nginx, which strips /api and serves photos.
// Headers and the raw body pass through untouched: Telegram and Stripe webhooks check signatures.

interface Env {
  BACKEND_URL?: string
}

interface PagesContext {
  request: Request
  env: Env
}

function problem(status: number, detail: string): Response {
  return new Response(JSON.stringify({ detail }), {
    status,
    headers: { 'Content-Type': 'application/json', 'Cache-Control': 'no-store' },
  })
}

export async function onRequest({ request, env }: PagesContext): Promise<Response> {
  const backend = env.BACKEND_URL?.trim()
  if (!backend) return problem(503, 'backend_not_configured')

  const incoming = new URL(request.url)
  const target = new URL(incoming.pathname + incoming.search, backend)

  const headers = new Headers(request.headers)
  headers.set('X-Forwarded-Host', incoming.host)
  headers.set('X-Forwarded-Proto', 'https')
  const clientIp = request.headers.get('CF-Connecting-IP')
  if (clientIp) headers.set('X-Forwarded-For', clientIp)

  const hasBody = request.method !== 'GET' && request.method !== 'HEAD'
  try {
    return await fetch(target, {
      method: request.method,
      headers,
      body: hasBody ? request.body : undefined,
      redirect: 'manual',
    })
  } catch {
    return problem(502, 'backend_unreachable')
  }
}
