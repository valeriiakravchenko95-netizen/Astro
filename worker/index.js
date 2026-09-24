// Сайт на Cloudflare Workers: страница из dist/ и тексты трактовок по
// адресу /api/texts. Файлы страницы Cloudflare отдает сам, сюда приходят
// только запросы, для которых файла нет: тексты и короткие ссылки проверок
// вроде /dengi.

import natal from '../web/content/interpretations.json' with { type: 'json' };
import sky from '../web/content/transits.json' with { type: 'json' };
import checkFile from '../web/content/checks.json' with { type: 'json' };
import { flattenCheckTexts } from '../web/checks.js';
import { handleTexts } from '../server/texts.js';
import { checkForPath, rewriteMeta } from '../server/pages.js';

const checks = { checks: flattenCheckTexts(checkFile) };

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (url.pathname === '/api/texts') return handleTexts(request, natal, sky, checks);

    // Короткая ссылка проверки: отдаем страницу, но с ее заголовком в превью.
    const check = checkForPath(checkFile, url.pathname);
    if (check) {
      if (url.pathname.endsWith('/')) {
        return Response.redirect(`${url.origin}${url.pathname.replace(/\/+$/, '')}${url.search}`, 301);
      }
      const page = await env.ASSETS.fetch(new Request(new URL('/', url), request));
      return rewriteMeta(page, check);
    }
    return env.ASSETS.fetch(request);
  },
};
