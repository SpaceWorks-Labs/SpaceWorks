import { handleRequest } from '../shared/edge.mjs';

export default {
  fetch(request, env) {
    return handleRequest(request, env, req => env.ASSETS.fetch(req), fetch,
      request.headers.get('CF-Connecting-IP') || '');
  },
};
