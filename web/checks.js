// Проверки под рилсы: «сколько из этих показателей есть в твоей карте».
//
// Ссылка вида ?check=big-money переводит страницу в короткий режим: после
// расчета показывается только эта проверка - сколько показателей совпало,
// текст по каждому совпавшему и приглашение. Полная карта раскрывается
// кнопкой. Сами проверки описаны в content/checks.json: показатели задаются
// условиями, код трогать не нужно.

import { SIGNS_IN, norm180, signIndex } from './astro/zodiac.js';
import { rulerOf, TRADITIONAL } from './astro/rulers.js';
import { textNodes, inGender } from './text.js';
import { allEvents, examineEvent } from './astro/transits.js';

let definitions = [];
let texts = {};

export async function loadChecks() {
  // Опубликованная страница получает условия без текстов (content/public.json),
  // тексты придут с сервера. При работе с исходниками читается полный файл.
  try {
    const response = await fetch('content/public.json');
    if (response.ok) {
      definitions = (await response.json()).checks || [];
      return definitions;
    }
  } catch (error) {
    // работаем с исходниками
  }
  try {
    const response = await fetch('content/checks.json');
    if (response.ok) {
      const full = await response.json();
      definitions = full.checks || [];
      texts = flattenCheckTexts(full);
    }
  } catch (error) {
    definitions = [];
  }
  return definitions;
}

// Все тексты проверок одной плоской таблицей: «big-money.intro»,
// «big-money.i.pluto-money». Так их удобно отдавать с сервера по ключам.
export function flattenCheckTexts(full) {
  const flat = {};
  for (const check of full.checks || []) {
    for (const field of ['intro', 'outro', 'none', 'few', 'many']) {
      if (check[field]) flat[`${check.key}.${field}`] = check[field];
    }
    for (const item of check.indicators || []) {
      if (item.text) flat[`${check.key}.i.${item.id}`] = item.text;
    }
  }
  return flat;
}

// Что из проверки можно отдать странице заранее: условия, заголовки,
// кодовое слово. Тексты - только с сервера.
const PUBLIC_FIELDS = ['key', 'slug', 'title', 'houses', 'more', 'code_word', 'cta', 'share',
  'heading', 'heading_em', 'lead'];

export function stripCheckTexts(full) {
  return (full.checks || []).map((check) => ({
    ...Object.fromEntries(PUBLIC_FIELDS.filter((field) => field in check).map((field) => [field, check[field]])),
    indicators: (check.indicators || []).map(({ id, title, when }) => ({ id, title, when })),
  }));
}

export function addCheckTexts(more) {
  texts = { ...texts, ...(more || {}) };
}

// Проверку можно открыть ссылкой ?check=big-money или короткой ссылкой
// /dengi - по полю slug. Короткие ссылки удобнее в сторис и видны в
// статистике по отдельности.
export function askedCheck() {
  const key = new URLSearchParams(location.search).get('check');
  const path = decodeURIComponent(location.pathname).replace(/^\/+|\/+$/g, '').toLowerCase();
  return definitions.find((check) => check.key === key)
    || definitions.find((check) => path && (check.slug === path || check.key === path))
    || null;
}

export function neededCheckTexts(check) {
  if (!check) return [];
  const keys = ['intro', 'outro', 'none', 'few', 'many'].map((field) => `${check.key}.${field}`);
  for (const item of check.indicators) keys.push(`${check.key}.i.${item.id}`);
  return keys.map((key) => ['checks', key]);
}

// --- условия -----------------------------------------------------------------
//
// Каждое условие возвращает null, если в карте его нет, или строку-основание
// («Юпитер во 2 доме»), если есть. Если для условия нужно время рождения, а
// его нет, возвращается NEED_TIME.

const NEED_TIME = Symbol('нужно время');
const PLANETS = ['sun', 'moon', 'mercury', 'venus', 'mars', 'jupiter', 'saturn',
  'uranus', 'neptune', 'pluto'];
const list = (value) => (Array.isArray(value) ? value : [value]);
const name = (chart, key) => chart.positions.get(key)?.body.name || key;

function houseRuler(chart, house) {
  const cusps = chart.houses.get(chart.houseSystem).cusps;
  return rulerOf(signIndex(cusps[house - 1]), chart.rulerScheme || TRADITIONAL);
}

const CONDITIONS = {
  planet_in_house(chart, spec) {
    if (!chart.exactTime) return NEED_TIME;
    for (const body of list(spec.bodies)) {
      const position = chart.positions.get(body);
      if (position && list(spec.houses).includes(position.house)) {
        return `${position.body.name} в ${position.house} доме`;
      }
    }
    return null;
  },

  planet_in_sign(chart, spec) {
    for (const body of list(spec.bodies)) {
      const position = chart.positions.get(body);
      if (position && list(spec.signs).includes(position.sign.index)) {
        return `${position.body.name} в ${SIGNS_IN[position.sign.index]}`;
      }
    }
    return null;
  },

  ruler_in_house(chart, spec) {
    if (!chart.exactTime) return NEED_TIME;
    const ruler = houseRuler(chart, spec.house);
    const position = chart.positions.get(ruler);
    if (position && list(spec.houses).includes(position.house)) {
      return `управитель ${spec.house} дома ${position.body.name} в ${position.house} доме`;
    }
    return null;
  },

  ruler_dignity(chart, spec) {
    if (!chart.exactTime) return NEED_TIME;
    const ruler = houseRuler(chart, spec.house);
    const own = chart.dignities.get(ruler)?.own || [];
    if (own.includes('domicile') || own.includes('exaltation')) {
      const position = chart.positions.get(ruler);
      return `управитель ${spec.house} дома ${position.body.name} в ${SIGNS_IN[position.sign.index]}`;
    }
    return null;
  },

  aspect(chart, spec) {
    const kinds = spec.aspects ? list(spec.aspects) : null;
    for (const hit of chart.aspects) {
      const pairs = [[hit.bodyA, hit.bodyB], [hit.bodyB, hit.bodyA]];
      const matches = pairs.some(([x, y]) => list(spec.a).includes(x) && list(spec.b).includes(y));
      if (matches && (!kinds || kinds.includes(hit.aspect.key))) {
        return `${name(chart, hit.bodyA)} ${hit.aspect.name.toLowerCase()} ${name(chart, hit.bodyB)}`;
      }
    }
    return null;
  },

  // Две сферы связаны, если управитель одной стоит в другой, у них один
  // управитель или управители в мажорном аспекте друг к другу.
  rulers_linked(chart, spec) {
    if (!chart.exactTime) return NEED_TIME;
    const [first, second] = spec.houses;
    const a = houseRuler(chart, first);
    const b = houseRuler(chart, second);
    if (a === b) return `у ${first} и ${second} дома один управитель - ${name(chart, a)}`;
    if (chart.positions.get(a)?.house === second) return `управитель ${first} дома в ${second} доме`;
    if (chart.positions.get(b)?.house === first) return `управитель ${second} дома в ${first} доме`;
    const hit = chart.aspects.find((h) => (h.bodyA === a && h.bodyB === b) || (h.bodyA === b && h.bodyB === a));
    if (hit) {
      return `управители ${first} и ${second} дома: ${name(chart, a)} ${hit.aspect.name.toLowerCase()} ${name(chart, b)}`;
    }
    return null;
  },

  planets_in_houses(chart, spec) {
    if (!chart.exactTime) return NEED_TIME;
    const bodies = spec.bodies ? list(spec.bodies) : PLANETS;
    const inside = bodies.filter((body) => list(spec.houses).includes(chart.positions.get(body)?.house));
    if (inside.length >= (spec.min || 1)) {
      return `${inside.map((body) => name(chart, body)).join(', ')} в ${list(spec.houses).join(', ')} домах`;
    }
    return null;
  },

  planet_on_angle(chart, spec) {
    if (!chart.exactTime) return NEED_TIME;
    const orb = spec.orb ?? 6;
    for (const body of list(spec.bodies)) {
      const position = chart.positions.get(body);
      if (!position) continue;
      for (const angle of list(spec.angles)) {
        if (Math.abs(norm180(position.longitude - chart.angles[angle])) <= orb) {
          return `${position.body.name} на ${angle === 'mc' ? 'МС' : 'Асценденте'}`;
        }
      }
    }
    return null;
  },

  any(chart, specs) {
    let needTime = false;
    for (const spec of specs) {
      const found = evaluate(chart, spec);
      if (found === NEED_TIME) needTime = true;
      else if (found) return found;
    }
    return needTime ? NEED_TIME : null;
  },

  all(chart, specs) {
    const found = [];
    for (const spec of specs) {
      const one = evaluate(chart, spec);
      if (!one || one === NEED_TIME) return one;
      found.push(one);
    }
    return found.join('; ');
  },
};

function evaluate(chart, when) {
  const [type, spec] = Object.entries(when || {})[0] || [];
  const condition = CONDITIONS[type];
  return condition ? condition(chart, spec) : null;
}

export function runCheck(chart, check) {
  const results = check.indicators.map((item) => {
    const found = evaluate(chart, item.when);
    return {
      item,
      state: found === NEED_TIME ? 'unknown' : (found ? 'yes' : 'no'),
      because: found && found !== NEED_TIME ? found : '',
    };
  });
  return {
    results,
    yes: results.filter((r) => r.state === 'yes'),
    no: results.filter((r) => r.state === 'no'),
    unknown: results.filter((r) => r.state === 'unknown'),
  };
}

// --- вывод -------------------------------------------------------------------

function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function plural(count, one, few, many) {
  const tens = count % 100;
  const units = count % 10;
  if (tens >= 11 && tens <= 14) return many;
  if (units === 1) return one;
  if (units >= 2 && units <= 4) return few;
  return many;
}

// --- «еще N мест в твоей карте» ---------------------------------------------
//
// Места карты, которые тоже влияют на тему, - только названиями. Что они
// значат и как связаны между собой, остается для консультации.

function morePlaces(chart, check, already) {
  if (!chart.exactTime || !check.more) return [];
  const found = [];
  // Место, уже названное среди найденных показателей, второй раз не идет:
  // сверяем по «планета в доме», в каком бы обороте оно ни стояло.
  const seen = (planetInHouse) => already.some((line) => line.includes(planetInHouse))
    || found.some((line) => line.includes(planetInHouse));
  const add = (label, planetInHouse = label) => {
    if (!seen(planetInHouse)) found.push(label);
  };
  for (const spec of check.more) {
    if (spec.ruler) {
      const ruler = houseRuler(chart, spec.ruler);
      const position = chart.positions.get(ruler);
      if (position) {
        const place = `${position.body.name} в ${position.house} доме`;
        add(`управитель ${spec.ruler} дома ${place}`, place);
      }
    }
    if (spec.planets_in) {
      for (const body of [...PLANETS, 'true_node']) {
        const position = chart.positions.get(body);
        if (position && list(spec.planets_in).includes(position.house)) {
          add(`${position.body.name} в ${position.house} доме`);
        }
      }
    }
    if (spec.ruler_aspects) {
      const ruler = houseRuler(chart, spec.ruler_aspects);
      for (const hit of chart.aspects) {
        if (hit.bodyA !== ruler && hit.bodyB !== ruler) continue;
        if (!PLANETS.includes(hit.bodyA) || !PLANETS.includes(hit.bodyB)) continue;
        add(`${name(chart, hit.bodyA)} ${hit.aspect.name.toLowerCase()} ${name(chart, hit.bodyB)}`);
      }
    }
  }
  return found.slice(0, 5);
}

// --- периоды на год вперед ----------------------------------------------------
//
// Месяцы, когда события неба точно ложатся на личные точки карты и задевают
// дома этой темы. Только месяцы: что в них делать - консультация.

const PERSONAL = ['sun', 'moon', 'mercury', 'venus', 'mars', 'jupiter', 'saturn', 'asc', 'mc'];
const MONTHS = ['январь', 'февраль', 'март', 'апрель', 'май', 'июнь', 'июль', 'август',
  'сентябрь', 'октябрь', 'ноябрь', 'декабрь'];

export function topicPeriods(chart, houses, { days = 365, today = new Date(), max = 4 } = {}) {
  if (!chart.exactTime || !houses?.length) return [];
  const from = today.toISOString().slice(0, 10);
  const to = new Date(today.getTime() + days * 86400000).toISOString().slice(0, 10);
  const months = [];
  for (const event of allEvents()) {
    if (event.date < from || event.date > to) continue;
    const limit = event.kind === 'lunation' ? 1 : 1.5;
    const report = examineEvent(chart, event);
    const personal = report.hits.some((hit) => PERSONAL.includes(hit.natal) && hit.orb <= limit);
    if (!personal || !report.housesTouched.some((house) => houses.includes(house))) continue;
    const [year, month] = event.date.split('-').map(Number);
    const label = `${MONTHS[month - 1]} ${year}`;
    if (!months.includes(label)) months.push(label);
  }
  return months.slice(0, max);
}

// --- картинка для сторис -------------------------------------------------------

async function storyImage({ title, big, small, lines, link, nick }) {
  const width = 1080;
  const height = 1920;
  const canvas = document.createElement('canvas');
  canvas.width = width;
  canvas.height = height;
  const ctx = canvas.getContext('2d');
  try {
    await Promise.all([
      document.fonts.load('400 80px Cormorant'), document.fonts.load('italic 400 80px Cormorant'),
    ]);
  } catch (error) {
    // без шрифта нарисуется запасным
  }
  const serif = "Cormorant, 'Cormorant Garamond', Georgia, serif";
  ctx.fillStyle = '#f5f1e8';
  ctx.fillRect(0, 0, width, height);
  ctx.strokeStyle = '#a8875a';
  ctx.lineWidth = 2;
  ctx.strokeRect(60, 60, width - 120, height - 120);

  // подпись автора
  ctx.textAlign = 'center';
  ctx.fillStyle = '#8a6c43';
  ctx.font = '600 26px -apple-system, Helvetica, sans-serif';
  ctx.fillText('А С Т Р О Л О Г', width / 2, 230);
  ctx.fillStyle = '#1f1a15';
  ctx.font = `400 58px ${serif}`;
  ctx.fillText('Валерия Кравченко', width / 2, 300);

  const wrap = (text, font, maxWidth) => {
    ctx.font = font;
    const words = text.split(' ');
    const rows = [];
    let row = '';
    for (const word of words) {
      const test = row ? `${row} ${word}` : word;
      if (ctx.measureText(test).width > maxWidth && row) {
        rows.push(row);
        row = word;
      } else row = test;
    }
    if (row) rows.push(row);
    return rows;
  };

  let y = 520;
  for (const row of wrap(title, `400 78px ${serif}`, 860)) {
    ctx.fillText(row, width / 2, y);
    y += 88;
  }
  y += 70;
  ctx.fillStyle = '#8a6c43';
  ctx.font = `400 260px ${serif}`;
  ctx.fillText(big, width / 2, y + 170);
  y += 320;
  ctx.fillStyle = '#7a6f63';
  ctx.font = `italic 400 54px ${serif}`;
  ctx.fillText(small, width / 2, y);
  y += 110;

  ctx.fillStyle = '#1f1a15';
  for (const line of lines.slice(0, 6)) {
    for (const row of wrap(line, `400 46px ${serif}`, 800)) {
      ctx.fillText(row, width / 2, y);
      y += 58;
    }
    y += 18;
  }

  ctx.fillStyle = '#a8875a';
  ctx.fillRect(width / 2 - 30, height - 330, 60, 2);
  ctx.fillStyle = '#1f1a15';
  ctx.font = `italic 400 48px ${serif}`;
  ctx.fillText('Проверь свою карту', width / 2, height - 250);
  ctx.font = '500 34px -apple-system, Helvetica, sans-serif';
  ctx.fillStyle = '#7a6f63';
  ctx.fillText(link, width / 2, height - 190);
  if (nick) ctx.fillText(nick, width / 2, height - 140);

  return new Promise((resolve) => canvas.toBlob(resolve, 'image/png'));
}

async function shareStory(options, holder) {
  const blob = await storyImage(options);
  if (!blob) return;
  const file = new File([blob], 'valeri.png', { type: 'image/png' });
  if (navigator.canShare?.({ files: [file] })) {
    try {
      await navigator.share({ files: [file] });
      return;
    } catch (error) {
      if (error?.name === 'AbortError') return;
    }
  }
  // Встроенный браузер инстаграма делиться файлами не умеет: показываем
  // картинку, ее можно сохранить долгим нажатием.
  holder.replaceChildren();
  const image = element('img');
  image.src = URL.createObjectURL(blob);
  image.alt = 'Картинка для сторис';
  image.className = 'story';
  holder.append(element('p', 'note', 'Нажми на картинку и удерживай, чтобы сохранить.'), image);
}

// --- вывод проверки --------------------------------------------------------------

export function renderCheck(chart, check, { dmUrl = '', nick = '' } = {}) {
  const { results, yes, no, unknown } = runCheck(chart, check);
  const node = element('section', 'card check-card');
  node.append(element('h2', null, check.title));

  // Счет мягкий: «из восьми» показываем, только когда совпало много, -
  // «1 из 8» читается как приговор, а это противоречит методу.
  const total = results.length - unknown.length;
  let big = '';
  let small = '';
  if (yes.length >= 3) {
    big = `${yes.length} из ${total}`;
    small = `${plural(total, 'показателя', 'показателей', 'показателей')} в твоей карте`;
  } else if (yes.length > 0) {
    big = String(yes.length);
    small = `${plural(yes.length, 'показатель', 'показателя', 'показателей')} в твоей карте`;
  }
  if (big) {
    const score = element('p', 'score');
    score.append(element('strong', null, big), document.createTextNode(small));
    node.append(score);
  }

  const summary = texts[`${check.key}.${yes.length === 0 ? 'none' : (yes.length <= 2 ? 'few' : 'many')}`];
  if (summary) node.append(...textNodes(summary));
  const intro = texts[`${check.key}.intro`];
  if (intro) node.append(...textNodes(intro));

  for (const { item, because } of yes) {
    const block = element('div', 'reading hit');
    block.append(element('h3', null, item.title));
    block.append(element('p', 'where', because));
    const text = texts[`${check.key}.i.${item.id}`];
    if (text) block.append(...textNodes(text));
    node.append(block);
  }

  if (no.length) {
    const rest = element('div', 'rest');
    rest.append(element('h3', null, 'Остальные показатели из списка'));
    const items = element('ul');
    for (const { item } of no) items.append(element('li', null, item.title));
    rest.append(items);
    node.append(rest);
  }

  if (unknown.length) {
    node.append(element('p', 'note',
      `Еще ${unknown.length} ${plural(unknown.length, 'показатель', 'показателя', 'показателей')} `
      + 'зависят от времени рождения - без него их не проверить.'));
  }

  const places = morePlaces(chart, check, yes.map((r) => r.because));
  if (places.length) {
    const box = element('div', 'more-places');
    box.append(element('h3', null,
      `Еще ${places.length} ${plural(places.length, 'место', 'места', 'мест')} в твоей карте влияют на эту тему`));
    const items = element('ul');
    for (const label of places) items.append(element('li', null, label));
    box.append(items);
    box.append(element('p', 'note', 'Как они связаны с тем, что выше, и что с ними делать, разбираю на консультации.'));
    node.append(box);
  }

  const months = topicPeriods(chart, check.houses);
  if (months.length) {
    const box = element('div', 'periods');
    box.append(element('h3', null, 'Периоды в ближайший год, которые задевают эту тему'));
    box.append(element('p', 'months', months.join(' · ')));
    box.append(element('p', 'note', 'Что в каждом из них делать - тоже тема консультации.'));
    node.append(box);
  }

  const outro = texts[`${check.key}.outro`];
  if (outro) node.append(...textNodes(outro));

  if (check.code_word) {
    const cta = element('div', 'cta');
    cta.append(...textNodes(inGender(check.cta || 'Хочешь разобрать, как это работает именно у тебя? Напиши мне в директ слово')));
    cta.append(element('span', 'word', check.code_word));
    if (dmUrl) {
      const link = element('a', 'button', 'Написать в директ');
      link.href = dmUrl;
      link.rel = 'noopener';
      cta.append(link);
    }
    node.append(cta);
  }

  const share = element('button', 'share', 'Сохранить результат для сторис');
  share.type = 'button';
  const holder = element('div', 'story-holder');
  share.addEventListener('click', () => shareStory({
    title: check.share || check.title,
    big: big || '·',
    small: big ? small : 'моя карта',
    lines: yes.map((r) => r.item.title),
    link: `${location.host}${check.slug ? `/${check.slug}` : `/?check=${check.key}`}`,
    nick,
  }, holder));
  node.append(share, holder);
  return node;
}
