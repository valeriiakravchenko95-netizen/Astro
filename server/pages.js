// Короткие ссылки проверок под рилсы: /dengi вместо /?check=big-money.
// У такой ссылки свое превью в мессенджерах - название проверки.

export function checkForPath(checkFile, pathname) {
  const slug = decodeURIComponent(pathname).replace(/^\/+|\/+$/g, '').toLowerCase();
  if (!slug || slug.includes('/') || slug.includes('.')) return null;
  return (checkFile.checks || []).find((check) => check.slug === slug || check.key === slug) || null;
}

const escape = (text) => String(text).replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;');

export async function rewriteMeta(page, check) {
  const title = check.share || check.title;
  const description = 'Проверь по своей натальной карте: сколько показателей у тебя и что с ними делать.';
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
