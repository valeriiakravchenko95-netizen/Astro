// Сайт на Cloudflare Workers: страница из dist/ и тексты трактовок по
// адресу /api/texts. Файлы страницы Cloudflare отдает сам, сюда приходят
// только запросы, для которых файла нет.

import natal from '../web/content/interpretations.json' with { type: 'json' };
import sky from '../web/content/transits.json' with { type: 'json' };
import { handleTexts } from '../server/texts.js';

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (url.pathname === '/api/texts') return handleTexts(request, natal, sky);
    return env.ASSETS.fetch(request);
  },
};
