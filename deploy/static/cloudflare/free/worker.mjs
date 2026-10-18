import web from '../worker.mjs';
import { runScheduledTick } from './tick.mjs';

export default {
  fetch: web.fetch,
  async scheduled(_controller, env, _context) {
    await runScheduledTick(env);
  },
};
