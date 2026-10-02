// Оформление по брендовой ссылке: та же страница, но в стиле lumeself.com.
// Ссылка с брендом - в brand_slugs проверки в checks.json, тексты кнопок и
// инстаграм бренда - в brands в site.json.

const LUME_MARK = '<svg class="lmark" viewBox="0 0 64 64" aria-hidden="true">'
  + '<circle cx="32" cy="32" r="21.5"/><circle cx="32" cy="32" r="15.5"/>'
  + '<line x1="47.5" y1="32" x2="53.5" y2="32"/><line x1="42.96" y1="42.96" x2="47.2" y2="47.2"/>'
  + '<line x1="32" y1="47.5" x2="32" y2="53.5"/><line x1="21.04" y1="42.96" x2="16.8" y2="47.2"/>'
  + '<line x1="16.5" y1="32" x2="10.5" y2="32"/><line x1="21.04" y1="21.04" x2="16.8" y2="16.8"/>'
  + '<line x1="32" y1="16.5" x2="32" y2="10.5"/><line x1="42.96" y1="21.04" x2="47.2" y2="16.8"/>'
  + '<path d="M20.5 33.5 L40 21.5 L34.5 43.5 Z"/><line x1="17" y1="24" x2="45.5" y2="44"/></svg>';

export const BRANDS = {
  lume: {
    title: 'Lumè',
    // Шрифты лендинга: Inter Tight для текста, Cormorant Unicase для знака.
    head: '<link rel="preconnect" href="https://fonts.googleapis.com">'
      + '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
      + '<link href="https://fonts.googleapis.com/css2?family=Inter+Tight:wght@400;500;600&family=Cormorant+Unicase:wght@500&display=swap" rel="stylesheet">',
    header: `<div class="brand brand-lume">${LUME_MARK}<span class="brand-name">Lumè</span></div>`,
  },
};
