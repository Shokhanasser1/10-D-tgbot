// Cloudflare Pages Function: forwards /api/* (and /media/*, see ../media) to the backend's public
// origin, so the Mini App on *.pages.dev stays same-origin and needs no CORS. BACKEND_URL is the
// FastAPI app itself (JustRunMy, or a tunnel to its port 8000), which serves its routes from the
// root, so the /api prefix is stripped here the way nginx.conf strips it in docker compose.
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
  // Only the path and query are replaced on a copy of BACKEND_URL. Resolving the path as a relative
  // URL instead would let /api//evil.example/x reach another host (an open proxy).
  const target = new URL(backend)
  target.pathname = incoming.pathname.replace(/^\/api(?=\/|$)/, '') || '/'
  target.search = incoming.search
  if (target.origin !== new URL(backend).origin) return problem(400, 'bad_path')

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
