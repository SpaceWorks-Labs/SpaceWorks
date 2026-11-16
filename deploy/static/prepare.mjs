/** Stage a self-contained static deployment. Run after the existing frontend build. */
import { cp, mkdir, readFile, readdir, writeFile, lstat } from 'node:fs/promises';
import { createRequire } from 'node:module';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const root = resolve(here, '../..');
const require = createRequire(join(root, 'frontend/package.json'));

async function ensureRegularTree(path) {
  const stat = await lstat(path);
  if (stat.isSymbolicLink()) throw new Error('symlink_in_publish_tree');
  if (stat.isDirectory()) {
    for (const item of await readdir(path)) await ensureRegularTree(join(path, item));
  } else if (!stat.isFile()) throw new Error('non_regular_publish_file');
}

export async function prepare(provider, output) {
  if (!['pages', 'vercel'].includes(provider)) throw new Error('select_pages_or_vercel');
  const dist = join(root, 'frontend/dist');
  await ensureRegularTree(dist);
  await readFile(join(dist, 'index.html'));
  // Refuse stale or arbitrary output. Never remove a directory to make deployment succeed.
  await mkdir(output, { recursive: false });
  const { rolldown } = await import(pathToFileURL(require.resolve('rolldown')).href);
  const publicDir = provider === 'pages' ? output : join(output, 'public');
  if (provider === 'vercel') await mkdir(publicDir);
  for (const name of await readdir(dist)) {
    await cp(join(dist, name), join(publicDir, name), { recursive: true, force: false, errorOnExist: true });
  }
  const input = join(here, provider === 'pages' ? 'cloudflare/pages/_worker.js' : 'vercel/middleware.mjs');
  const bundle = await rolldown({ input, platform: 'neutral' });
  try { await bundle.write({ file: join(output, provider === 'pages' ? '_worker.js' : 'middleware.js'), format: 'esm' }); }
  finally { await bundle.close(); }
  if (provider === 'pages') {
    await cp(join(here, 'cloudflare/pages/_routes.json'), join(output, '_routes.json'));
  } else {
    const config = JSON.parse(await readFile(join(here, 'vercel/vercel.json'), 'utf8'));
    Object.assign(config, { framework: null, buildCommand: '', installCommand: '', outputDirectory: 'public' });
    delete config.env;
    await writeFile(join(output, 'vercel.json'), JSON.stringify(config, null, 2) + '\n');
    await writeFile(join(output, 'package.json'), '{"private":true,"type":"module"}\n');
  }
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const [provider, output] = process.argv.slice(2);
  if (!output) throw new Error('output_must_be_a_new_directory');
  try { await prepare(provider, resolve(output)); }
  catch { process.stderr.write('Static staging failed; verify the build and use a new output directory.\n'); process.exitCode = 1; }
}
