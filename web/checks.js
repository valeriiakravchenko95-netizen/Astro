// Проверки под рилсы: «сколько из этих показателей есть в твоей карте».
//
// Ссылка вида ?check=big-money переводит страницу в короткий режим: после
// расчета показывается только эта проверка - сколько показателей совпало,
// текст по каждому совпавшему и приглашение. Полная карта раскрывается
// кнопкой. Сами проверки описаны в content/checks.json: показатели задаются
// условиями, код трогать не нужно.

import { SIGNS_IN, norm180, signIndex } from './astro/zodiac.js';
import { rulerOf, TRADITIONAL } from './astro/rulers.js';
import { textNodes } from './text.js';

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

export function stripCheckTexts(full) {
  return (full.checks || []).map((check) => ({
    key: check.key,
    title: check.title,
    indicators: (check.indicators || []).map(({ id, title, when }) => ({ id, title, when })),
  }));
}

export function addCheckTexts(more) {
  texts = { ...texts, ...(more || {}) };
}

export function askedCheck() {
  const key = new URLSearchParams(location.search).get('check');
  return definitions.find((check) => check.key === key) || null;
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

export function renderCheck(chart, check) {
  const { results, yes, no, unknown } = runCheck(chart, check);
  const node = element('section', 'card check');
  node.append(element('h2', null, check.title));

  const total = results.length - unknown.length;
  const score = element('p', 'score');
  score.append(element('strong', null, `${yes.length} из ${total}`));
  score.append(document.createTextNode(` ${plural(total, 'показателя', 'показателей', 'показателей')} в твоей карте`));
  node.append(score);

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
    const rest = element('div', 'reading rest');
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

  const outro = texts[`${check.key}.outro`];
  if (outro) node.append(...textNodes(outro));
  return node;
}
