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

export function metaForCheck(check) {
  return { title: check.share || check.title, description: CHECK_DESCRIPTION };
}

export function metaForEvent(link) {
  return { title: link.title, description: link.description || EVENT_DESCRIPTION };
}

const escape = (text) => String(text).replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;');

export async function rewriteMeta(page, { title, description }) {
  let html = await page.text();
  html = html
    .replace(/<title>[^<]*<\/title>/, `<title>${escape(title)} · Lume</title>`)
    .replace(/(<meta property="og:title" content=")[^"]*"/, `$1${escape(title)}"`)
    .replace(/(<meta property="og:description" content=")[^"]*"/, `$1${escape(description)}"`);
  const headers = new Headers(page.headers);
  headers.set('content-type', 'text/html; charset=utf-8');
  headers.delete('content-length');
  return new Response(html, { status: 200, headers });
}
