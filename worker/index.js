// Сайт на Cloudflare Workers: страница из dist/ и тексты трактовок по
// адресу /api/texts. Файлы страницы Cloudflare отдает сам, сюда приходят
// только запросы, для которых файла нет: тексты и короткие ссылки проверок
// и событий вроде /dengi и /polnolunie.

import natal from '../web/content/interpretations.json' with { type: 'json' };
import sky from '../web/content/transits.json' with { type: 'json' };
import checkFile from '../web/content/checks.json' with { type: 'json' };
import { flattenCheckTexts } from '../web/checks.js';
import { handleTexts } from '../server/texts.js';
import {
  checkForPath, eventLinkForPath, metaForCheck, metaForEvent, rewriteMeta,
} from '../server/pages.js';

const checks = { checks: flattenCheckTexts(checkFile) };

// Сайт закрыт от поисковиков: страницы открываются только по личной ссылке.
const hidden = (response) => {
  const out = new Response(response.body, response);
  out.headers.set('X-Robots-Tag', 'noindex, nofollow, noarchive');
  return out;
};

export default {
  async fetch(request, env) {
    return hidden(await route(request, env));
  },
};

async function route(request, env) {
  const url = new URL(request.url);
  if (url.pathname === '/api/texts') return handleTexts(request, natal, sky, checks);

  // Короткая ссылка проверки или события: отдаем страницу, но с ее
  // заголовком в превью.
  const check = checkForPath(checkFile, url.pathname);
  const link = check ? null : eventLinkForPath(sky, url.pathname);
  if (check || link) {
    if (url.pathname.endsWith('/')) {
      return Response.redirect(`${url.origin}${url.pathname.replace(/\/+$/, '')}${url.search}`, 301);
    }
    const page = await env.ASSETS.fetch(new Request(new URL('/', url), request));
    return rewriteMeta(page, check ? metaForCheck(check) : metaForEvent(link));
  }
  // Любой другой адрес без расширения - закрытая главная: по чужой или
  // угаданной ссылке тема не открывается.
  if (url.pathname !== '/' && !/\.[a-z0-9]+$/i.test(url.pathname)) {
    return env.ASSETS.fetch(new Request(new URL('/', url), request));
  }
  return env.ASSETS.fetch(request);
}
