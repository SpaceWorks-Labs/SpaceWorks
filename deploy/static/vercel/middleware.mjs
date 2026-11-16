import { handleRequest } from '../shared/edge.mjs';

export default function middleware(request) {
  return handleRequest(request, process.env, async () =>
    new Response(null, { headers: { 'x-middleware-next': '1' } }), fetch,
  request.headers.get('x-vercel-forwarded-for') || '');
}

export const config = { matcher: '/:path*' };
