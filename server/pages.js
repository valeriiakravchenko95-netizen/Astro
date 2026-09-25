// Короткие ссылки под рилсы: /dengi вместо /?check=big-money, /polnolunie
// вместо /?event=lunation.full@2026-09-26. У такой ссылки свое превью в
// мессенджерах - ее название и описание.

const slugOf = (pathname) => {
  const slug = decodeURIComponent(pathname).replace(/^\/+|\/+$/g, '').toLowerCase();
  return !slug || slug.includes('/') || slug.includes('.') ? null : slug;
};

export function checkForPath(checkFile, pathname) {
  const slug = slugOf(pathname);
  if (!slug) return null;
  return (checkFile.checks || []).find((check) => check.slug === slug || check.key === slug) || null;
}

// Ссылка на событие неба из раздела links в transits.json.
export function eventLinkForPath(sky, pathname) {
  const slug = slugOf(pathname);
  return slug ? sky.links?.[slug] || null : null;
}

const CHECK_DESCRIPTION = 'Проверь по своей натальной карте: сколько показателей у тебя и что с ними делать.';
const EVENT_DESCRIPTION = 'Проверь по своей натальной карте, заденет ли это тебя и в какой сфере.';

// heading, heading_em и lead - заголовок самой страницы: сервер ставит его
// сразу, чтобы до загрузки скриптов не мелькала «Натальная карта».
export function metaForCheck(check) {
  return {
    title: check.share || check.title,
    description: CHECK_DESCRIPTION,
    heading: check.heading || check.title,
    heading_em: check.heading_em ?? 'в твоей карте',
    lead: check.lead,
  };
}

export function metaForEvent(link) {
  return {
    title: link.title,
    description: link.description || EVENT_DESCRIPTION,
    heading: link.heading,
    heading_em: link.heading_em,
    lead: link.lead,
  };
}

const escape = (text) => String(text).replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;');
// Короткие слова («с», «в», «на») не остаются в конце строки заголовка.
const glue = (text) => String(text).replace(/(^|\s)([а-яa-z]{1,2})\s/giu, '$1$2&nbsp;');

export async function rewriteMeta(page, {
  title, description, heading, heading_em: accent, lead,
}) {
  let html = await page.text();
  html = html
    .replace(/<title>[^<]*<\/title>/, `<title>${escape(title)} · Lume</title>`)
    .replace(/(<meta property="og:title" content=")[^"]*"/, `$1${escape(title)}"`)
    .replace(/(<meta property="og:description" content=")[^"]*"/, `$1${escape(description)}"`);
  if (heading) {
    const em = accent ? ` <em>${glue(escape(accent))}</em>` : '';
    html = html.replace(/<h1>[\s\S]*?<\/h1>/, `<h1>${glue(escape(heading))}${em}</h1>`);
    if (lead) html = html.replace(/(<\/h1>\s*<p>)[\s\S]*?(<\/p>)/, `$1${escape(lead)}$2`);
    html = html.replace('<header>', '<header class="landing">');
  }
  const headers = new Headers(page.headers);
  headers.set('content-type', 'text/html; charset=utf-8');
  headers.delete('content-length');
  return new Response(html, { status: 200, headers });
}
