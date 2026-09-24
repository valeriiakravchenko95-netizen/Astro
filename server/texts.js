// Ответ на запрос текстов трактовок для одной карты.
//
// Общая часть для обоих способов публикации на Cloudflare: Workers
// (worker/index.js) и Pages (functions/api/texts.js). Тексты лежат только
// на сервере; страница присылает ключи, нужные ее карте, и получает только их.

// Одной карте нужно несколько десятков текстов. Запрос на сотни - это
// попытка выкачать все, а не чья-то карта.
const LIMITS = { natal: 120, sky: 200, checks: 40 };

function pick(source, wanted, limit) {
  const found = {};
  if (!Array.isArray(wanted)) return found;
  for (const pair of wanted.slice(0, limit)) {
    if (!Array.isArray(pair)) continue;
    const [section, key] = pair.map(String);
    const value = source?.[section]?.[key];
    if (typeof value !== 'string' || !value) continue;
    (found[section] ||= {})[key] = value;
  }
  return found;
}

function reply(body, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: {
      'content-type': 'application/json; charset=utf-8',
      'cache-control': 'no-store',
      'x-robots-tag': 'noindex',
    },
  });
}

export async function handleTexts(request, natal, sky, checks = {}) {
  if (request.method !== 'POST') return reply({ error: 'method not allowed' }, 405);
  // Чужие сайты не могут подтягивать тексты к себе: браузер присылает
  // адрес страницы, с которой идет запрос, и он должен совпадать с нашим.
  const origin = request.headers.get('origin');
  if (origin && new URL(origin).host !== new URL(request.url).host) {
    return reply({ error: 'forbidden' }, 403);
  }
  let body;
  try {
    body = await request.json();
  } catch (error) {
    return reply({ error: 'bad request' }, 400);
  }
  return reply({
    natal: pick(natal.texts, body?.natal, LIMITS.natal),
    sky: pick(sky, body?.sky, LIMITS.sky),
    checks: pick(checks, body?.checks, LIMITS.checks),
  });
}
