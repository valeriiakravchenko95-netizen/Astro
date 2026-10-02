// Оформление по брендовой ссылке: та же страница, но в стиле lumeself.com
// (белый фон, темно-синий текст, антиква в заголовках, кнопки-таблетки).
// Ссылка с брендом - в brand_slugs проверки в checks.json, тексты кнопок и
// инстаграм бренда - в brands в site.json.

export const BRANDS = {
  lume: {
    title: 'lume',
    // Как на lumeself.com: заголовки антиквой с контрастом (Playfair
    // Display), текст системным шрифтом, знак lume - картинкой.
    head: '<link rel="preconnect" href="https://fonts.googleapis.com">'
      + '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
      + '<link href="https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,400;0,500;1,400&display=swap" rel="stylesheet">',
    header: '<div class="brand brand-lume"><img src="/brand/lume-logo.png" alt="lume" width="146" height="46"></div>',
  },
};
