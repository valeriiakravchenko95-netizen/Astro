// То, что страница говорит от имени автора: подпись в шапке и предложения
// под разделами. Все лежит в content/site.json, пустые поля не выводятся.

import { textNodes } from './text.js';

let site = { author: {}, offers: {} };

export async function loadSite(url = 'content/site.json') {
  try {
    const response = await fetch(url);
    if (response.ok) site = { ...site, ...(await response.json()) };
  } catch (error) {
    // Без подписи страница работает как раньше.
  }
  return site;
}

function instagramUrl(handle) {
  const clean = String(handle).trim().replace(/^@/, '');
  if (!clean) return '';
  return /^https?:\/\//.test(clean) ? clean : `https://instagram.com/${clean}`;
}

export function siteSettings() {
  return site;
}

export function instagramNick() {
  const handle = String(site.author?.instagram || '').trim()
    .replace(/^https?:\/\/(www\.)?instagram\.com\//, '').replace(/\/$/, '').replace(/^@/, '');
  return handle ? `@${handle}` : '';
}

export function renderAuthor(container) {
  const { name, instagram, about } = site.author || {};
  if (!name && !instagram && !about) return;
  const box = document.createElement('p');
  box.className = 'author';
  if (name) {
    const strong = document.createElement('strong');
    strong.textContent = name;
    box.append(strong);
  }
  if (instagram) {
    const link = document.createElement('a');
    link.href = instagramUrl(instagram);
    link.rel = 'noopener';
    link.textContent = `@${String(instagram).replace(/^@/, '').replace(/^https?:\/\/(www\.)?instagram\.com\//, '').replace(/\/$/, '')}`;
    if (name) box.append(document.createTextNode(' · '));
    box.append(link);
  }
  if (about) {
    if (name || instagram) box.append(document.createElement('br'));
    box.append(document.createTextNode(about));
  }
  container.append(box);
}

// Предложение под разделом: текст и кнопка. Показывается, только если
// заполнен хотя бы текст.
export function renderOffer(key) {
  const offer = site.offers?.[key];
  if (!offer?.text) return null;
  const node = document.createElement('section');
  node.className = 'card offer';
  node.append(...textNodes(offer.text));
  if (offer.url) {
    const link = document.createElement('a');
    link.className = 'button';
    link.href = offer.url;
    link.rel = 'noopener';
    link.textContent = offer.button || 'Подробнее';
    node.append(link);
  }
  return node;
}
