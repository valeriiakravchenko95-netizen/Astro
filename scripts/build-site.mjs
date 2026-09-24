// Сборка страницы для публикации: папка dist/.
//
//   npm run build
//
// Что делает:
// - код страницы собирается в один файл и сжимается - читать его глазами
//   становится трудно;
// - тексты трактовок в dist/ не попадают вовсе: их отдает серверная функция
//   functions/api/texts.js, по несколько десятков под конкретную карту;
// - на страницу идет только список тем и закрепленное событие
//   (content/public.json) и подпись автора (content/site.json);
// - в превью ссылки подставляется адрес сайта: SITE_URL из настроек
//   Cloudflare, а если его нет - адрес по умолчанию ниже.

import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import * as esbuild from 'esbuild';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const web = path.join(root, 'web');
const dist = path.join(root, 'dist');
const SITE_URL = (process.env.SITE_URL || 'https://valeri-lume.lumeself.workers.dev').replace(/\/$/, '');

fs.rmSync(dist, { recursive: true, force: true });
fs.mkdirSync(path.join(dist, 'content'), { recursive: true });

for (const file of ['favicon.svg', 'preview.png']) {
  fs.copyFileSync(path.join(web, file), path.join(dist, file));
}
fs.cpSync(path.join(web, 'data'), path.join(dist, 'data'), { recursive: true });
fs.copyFileSync(path.join(web, 'content', 'site.json'), path.join(dist, 'content', 'site.json'));

const read = (name) => JSON.parse(fs.readFileSync(path.join(web, 'content', name), 'utf8'));
fs.writeFileSync(path.join(dist, 'content', 'public.json'), JSON.stringify({
  topics: read('interpretations.json').topics,
  featured: read('transits.json').featured || null,
}));

await esbuild.build({
  entryPoints: [path.join(web, 'app.js')],
  outfile: path.join(dist, 'app.js'),
  bundle: true,
  minify: true,
  format: 'esm',
  target: 'es2020',
  legalComments: 'none',
  charset: 'utf8',
});
await esbuild.build({
  entryPoints: [path.join(web, 'style.css')],
  outfile: path.join(dist, 'style.css'),
  minify: true,
  charset: 'utf8',
});

const html = fs.readFileSync(path.join(web, 'index.html'), 'utf8')
  .replace(/<!--[\s\S]*?-->\n?/g, '')
  .replaceAll('__SITE_URL__', SITE_URL);
fs.writeFileSync(path.join(dist, 'index.html'), html);

// Поисковикам незачем индексировать служебные адреса.
fs.writeFileSync(path.join(dist, 'robots.txt'), 'User-agent: *\nDisallow: /api/\nDisallow: /data/\n');

console.log(`собрано в dist/, адрес сайта ${SITE_URL}`);
