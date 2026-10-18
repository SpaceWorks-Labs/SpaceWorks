import { handleRequest } from '../shared/edge.mjs';

export default (request, context) => handleRequest(request, {
  PUBLIC_ORIGIN: Netlify.env.get('PUBLIC_ORIGIN'),
  BACKEND_ORIGIN: Netlify.env.get('BACKEND_ORIGIN'),
  LIVE_ORIGIN: Netlify.env.get('LIVE_ORIGIN'),
  PUBLIC_API_URL: Netlify.env.get('PUBLIC_API_URL'),
  PUBLIC_TENANT_TOKEN: Netlify.env.get('PUBLIC_TENANT_TOKEN'),
  ORIGIN_BOOTSTRAP: Netlify.env.get('ORIGIN_BOOTSTRAP'),
  CONNECT_ORIGINS: Netlify.env.get('CONNECT_ORIGINS'),
  IMAGE_ORIGINS: Netlify.env.get('IMAGE_ORIGINS'),
  MEDIA_ORIGINS: Netlify.env.get('MEDIA_ORIGINS'),
  ANALYTICS_SCRIPT_ORIGINS: Netlify.env.get('ANALYTICS_SCRIPT_ORIGINS'),
}, () => context.next(), fetch, context.ip);

export const config = { path: '/*', onError: 'fail' };
