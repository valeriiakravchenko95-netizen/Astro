// Темы и трактовки.
//
// Карта считается целиком, но показывать целиком её незачем: под каждую
// тему из карты выбирается несколько значимых мест, и к ним подбирается
// текст. И темы, и тексты лежат в content/interpretations.json — код
// знает только, как достать из карты фактор каждого вида, а какие именно
// факторы входят в тему, решает файл. Новая тема не требует правки кода.

import { SIGNS_IN, signIndex, toSign } from './astro/zodiac.js';
import { DIGNITY_NAMES, rulerOf } from './astro/rulers.js';

let content = { topics: [], texts: {} };

export async function loadInterpretations(url = 'content/interpretations.json') {
  try {
    const response = await fetch(url);
    if (response.ok) content = await response.json();
  } catch (error) {
    // Без трактовок страница остаётся полезной: цифры никуда не делись.
    content = { topics: [], texts: {} };
  }
  return content;
}

function text(section, key) {
  return content.texts?.[section]?.[key] || '';
}

const bodyName = (chart, key) => chart.positions.get(key)?.body.name || key;
const shortName = (chart, key) => chart.positions.get(key)?.body.short || key;

// --- как достать из карты фактор каждого вида -------------------------------
//
// Каждый вид получает карту, признак известного времени и описание из файла,
// а возвращает либо готовый фактор, либо ничего — если в этой карте такого
// нет или для него не хватает времени рождения.

const FACTOR_KINDS = {
  planet_sign(chart, exactTime, spec) {
    const position = chart.positions.get(spec.body);
    if (!position) return null;
    return {
      id: `${spec.body}.${position.sign.index}`,
      section: 'planet_in_sign',
      title: `${position.body.name} в ${SIGNS_IN[position.sign.index]}`,
      where: position.sign.sign,
    };
  },

  planet_house(chart, exactTime, spec) {
    if (!exactTime) return null;
    const position = chart.positions.get(spec.body);
    if (!position) return null;
    return {
      id: `${spec.body}.${position.house}`,
      section: 'planet_in_house',
      title: `${position.body.name} в ${position.house} доме`,
      where: `${position.house} дом`,
    };
  },

  // Дом говорит о чём, управитель — через что. Это основной способ читать
  // тему дома, и он работает даже когда в самом доме пусто.
  house_ruler(chart, exactTime, spec) {
    if (!exactTime) return null;
    const cusps = chart.houses.get(chart.houseSystem).cusps;
    const sign = signIndex(cusps[spec.house - 1]);
    const ruler = rulerOf(sign);
    const position = chart.positions.get(ruler);
    if (!position) return null;
    return {
      id: `${spec.house}.${ruler}.${position.house}`,
      section: 'house_ruler',
      title: `${spec.house} дом в ${SIGNS_IN[sign]}, управитель ${position.body.name} в ${position.house} доме`,
      where: `${spec.house} дом`,
      fallback: `Тема ${spec.house} дома идёт через ${position.body.name} — он стоит `
        + `в ${position.house} доме, в ${SIGNS_IN[position.sign.index]}.`,
    };
  },

  planets_in_house(chart, exactTime, spec) {
    if (!exactTime) return null;
    const inside = [...chart.positions.entries()]
      .filter(([, position]) => position.house === spec.house)
      .map(([key]) => key);
    if (!inside.length) return null;
    return {
      id: `${spec.house}.${inside.join('-')}`,
      section: 'planets_in_house',
      title: `В ${spec.house} доме: ${inside.map((key) => bodyName(chart, key)).join(', ')}`,
      where: `${spec.house} дом`,
      fallback: `В ${spec.house} доме стоят: ${inside.map((key) => bodyName(chart, key)).join(', ')}.`,
    };
  },

  aspect(chart, exactTime, spec) {
    const hit = chart.aspects.find(
      (h) => (h.bodyA === spec.a && h.bodyB === spec.b)
        || (h.bodyA === spec.b && h.bodyB === spec.a),
    );
    if (!hit) return null;
    return {
      id: `${[spec.a, spec.b].sort().join('.')}.${hit.aspect.key}`,
      section: 'aspect',
      title: `${shortName(chart, hit.bodyA)} ${hit.aspect.name.toLowerCase()} ${shortName(chart, hit.bodyB)}`,
      where: `орб ${hit.orb.toFixed(1)}°`,
    };
  },

  dignity(chart, exactTime, spec) {
    const item = chart.dignities.get(spec.body);
    if (!item) return null;
    const strong = item.own.filter((code) => code === 'domicile' || code === 'exaltation');
    if (!strong.length) return null;
    return {
      id: `${spec.body}.${strong[0]}`,
      section: 'dignity',
      title: `${bodyName(chart, spec.body)}: ${DIGNITY_NAMES[strong[0]]}`,
      where: 'достоинство',
      fallback: `${bodyName(chart, spec.body)} стоит сильно — это ${DIGNITY_NAMES[strong[0]]}.`,
    };
  },

  ascendant(chart, exactTime) {
    if (!exactTime) return null;
    const sign = toSign(chart.angles.asc);
    return {
      id: `asc.${sign.index}`,
      section: 'ascendant',
      title: `Асцендент в ${SIGNS_IN[sign.index]}`,
      where: 'угол карты',
    };
  },

  midheaven(chart, exactTime) {
    if (!exactTime) return null;
    const sign = toSign(chart.angles.mc);
    return {
      id: `mc.${sign.index}`,
      section: 'midheaven',
      title: `МС в ${SIGNS_IN[sign.index]}`,
      where: 'угол карты',
    };
  },

  // Финальный диспозитор — планета, к которой сходятся все цепочки
  // управления. Если он есть, им обычно и объясняется склад карты.
  final_dispositor(chart) {
    const finals = chart.dispositors.finalDispositors;
    if (!finals.length) return null;
    return {
      id: finals.join('-'),
      section: 'final_dispositor',
      title: finals.length === 1
        ? `Финальный диспозитор: ${bodyName(chart, finals[0])}`
        : `Финальные диспозиторы: ${finals.map((key) => bodyName(chart, key)).join(', ')}`,
      where: 'цепочки управления',
      fallback: `Все цепочки управления в карте сходятся к ${finals.map((key) => bodyName(chart, key)).join(' и ')}.`,
    };
  },

  elements(chart) {
    const counts = { Огонь: 0, Земля: 0, Воздух: 0, Вода: 0 };
    for (const [key, position] of chart.positions) {
      if (!['sun', 'moon', 'mercury', 'venus', 'mars', 'jupiter', 'saturn'].includes(key)) continue;
      counts[position.sign.element] += 1;
    }
    const order = Object.entries(counts).sort((a, b) => b[1] - a[1]);
    const missing = order.filter(([, count]) => count === 0).map(([name]) => name);
    return {
      id: order.map(([name, count]) => `${name}${count}`).join('-'),
      section: 'elements',
      title: `Стихии: ${order.map(([name, count]) => `${name} ${count}`).join(', ')}`,
      where: 'по семи планетам',
      fallback: missing.length
        ? `Больше всего ${order[0][0].toLowerCase()}а. Не набрано ни одной планеты в стихии: ${missing.join(', ').toLowerCase()}.`
        : `Больше всего ${order[0][0].toLowerCase()}а, меньше всего ${order[order.length - 1][0].toLowerCase()}ы.`,
    };
  },
};

export function collectFactors(chart, topicKey, exactTime) {
  const topic = (content.topics || []).find((item) => item.key === topicKey);
  if (!topic) return [];
  const factors = [];
  for (const spec of topic.factors || []) {
    const build = FACTOR_KINDS[spec.type];
    if (!build) continue;
    const factor = build(chart, exactTime, spec);
    if (factor) factors.push(factor);
  }
  return factors;
}

export function availableFactorKinds() {
  return Object.keys(FACTOR_KINDS);
}

// --- вывод -----------------------------------------------------------------

export function renderReadings(chart, { exactTime }) {
  const topics = content.topics || [];
  if (!topics.length) return null;

  const node = document.createElement('section');
  node.className = 'card';
  const heading = document.createElement('h2');
  heading.textContent = 'Разбор по теме';
  node.append(heading);

  const buttons = document.createElement('div');
  buttons.className = 'topics';
  const body = document.createElement('div');

  const show = (topic) => {
    for (const button of buttons.children) {
      button.setAttribute('aria-pressed', String(button.dataset.key === topic.key));
    }
    body.replaceChildren();
    const factors = collectFactors(chart, topic.key, exactTime);
    if (!factors.length) {
      const empty = document.createElement('p');
      empty.className = 'note';
      empty.textContent = exactTime
        ? 'По этой теме в карте нечего отметить.'
        : 'Для этой темы нужно точное время рождения.';
      body.append(empty);
      return;
    }
    for (const factor of factors) {
      const item = document.createElement('div');
      item.className = 'reading';
      const title = document.createElement('h3');
      title.textContent = factor.title;
      const where = document.createElement('p');
      where.className = 'where';
      where.textContent = factor.where;
      const paragraph = document.createElement('p');
      const written = text(factor.section, factor.id);
      paragraph.textContent = written || factor.fallback || '';
      if (!paragraph.textContent) paragraph.className = 'note';
      item.append(title, where);
      if (paragraph.textContent) item.append(paragraph);
      body.append(item);
    }
  };

  for (const topic of topics) {
    const button = document.createElement('button');
    button.type = 'button';
    button.dataset.key = topic.key;
    button.textContent = topic.name;
    button.setAttribute('aria-pressed', 'false');
    button.addEventListener('click', () => show(topic));
    buttons.append(button);
  }

  node.append(buttons, body);
  show(topics[0]);
  return node;
}
