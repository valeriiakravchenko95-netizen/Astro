// Темы и трактовки.
//
// Карта считается целиком, но показывать целиком её незачем: под каждую
// тему из карты выбирается несколько значимых мест, и к ним подбирается
// текст. Сами тексты лежат в content/interpretations.json и правятся без
// участия кода — здесь только выбор того, о чём говорить.

import { SIGNS, SIGNS_IN, signIndex, toSign } from './astro/zodiac.js';
import { DIGNITY_NAMES } from './astro/rulers.js';

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

const bodyName = (chart, key) => chart.positions.get(key)?.body.short || key;

// --- отбор значимых мест карты ---------------------------------------------

function planetInSign(chart, key) {
  const position = chart.positions.get(key);
  if (!position) return null;
  const sign = SIGNS[position.sign.index];
  return {
    id: `${key}.${position.sign.index}`,
    section: 'planet_in_sign',
    title: `${position.body.name} в ${SIGNS_IN[position.sign.index]}`,
    where: sign,
  };
}

function planetInHouse(chart, key, exactTime) {
  if (!exactTime) return null;
  const position = chart.positions.get(key);
  if (!position) return null;
  return {
    id: `${key}.${position.house}`,
    section: 'planet_in_house',
    title: `${position.body.name} в ${position.house} доме`,
    where: `${position.house} дом`,
  };
}

// Управитель дома и место, куда он поставлен, — основной способ читать
// тему дома: дом говорит о чём, управитель — через что.
function houseRuler(chart, house, exactTime) {
  if (!exactTime) return null;
  const cusps = chart.houses.get(chart.houseSystem).cusps;
  const sign = signIndex(cusps[house - 1]);
  const ruler = content.rulers?.[sign] ?? null;
  const rulerKey = ruler || rulerOfSign(chart, sign);
  const position = chart.positions.get(rulerKey);
  if (!position) return null;
  return {
    id: `${house}.${rulerKey}.${position.house}`,
    section: 'house_ruler',
    title: `${house} дом в ${SIGNS_IN[sign]}, управитель ${position.body.name} в ${position.house} доме`,
    where: `${house} дом`,
    fallback: `Тема ${house} дома идёт через ${position.body.name} — он стоит `
      + `в ${position.house} доме, в ${SIGNS_IN[position.sign.index]}.`,
  };
}

function rulerOfSign(chart, sign) {
  // Управитель берётся из уже посчитанных диспозиторов карты.
  for (const [key, position] of chart.positions) {
    if (chart.dispositors.dispositor.has(key) && position.sign.index === sign) break;
  }
  const table = ['mars', 'venus', 'mercury', 'moon', 'sun', 'mercury',
    'venus', 'mars', 'jupiter', 'saturn', 'saturn', 'jupiter'];
  return table[sign % 12];
}

function aspectBetween(chart, a, b) {
  const hit = chart.aspects.find(
    (h) => (h.bodyA === a && h.bodyB === b) || (h.bodyA === b && h.bodyB === a),
  );
  if (!hit) return null;
  return {
    id: `${[a, b].sort().join('.')}.${hit.aspect.key}`,
    section: 'aspect',
    title: `${bodyName(chart, hit.bodyA)} ${hit.aspect.name.toLowerCase()} ${bodyName(chart, hit.bodyB)}`,
    where: `орб ${hit.orb.toFixed(1)}°`,
  };
}

function dignityNote(chart, key) {
  const item = chart.dignities.get(key);
  if (!item || item.peregrine) return null;
  const strong = item.own.filter((code) => code === 'domicile' || code === 'exaltation');
  if (!strong.length) return null;
  return {
    id: `${key}.${strong[0]}`,
    section: 'dignity',
    title: `${bodyName(chart, key)}: ${DIGNITY_NAMES[strong[0]]}`,
    where: 'достоинство',
    fallback: `${bodyName(chart, key)} стоит сильно — это ${DIGNITY_NAMES[strong[0]]}.`,
  };
}

// Что показывать под каждой темой.
const TOPIC_FACTORS = {
  money: (chart, exactTime) => [
    houseRuler(chart, 2, exactTime),
    houseRuler(chart, 10, exactTime),
    houseRuler(chart, 6, exactTime),
    planetInSign(chart, 'venus'),
    planetInHouse(chart, 'venus', exactTime),
    planetInSign(chart, 'jupiter'),
    planetInHouse(chart, 'jupiter', exactTime),
    planetInSign(chart, 'saturn'),
    planetInHouse(chart, 'saturn', exactTime),
    dignityNote(chart, 'venus'),
    dignityNote(chart, 'jupiter'),
  ],
  relations: (chart, exactTime) => [
    houseRuler(chart, 7, exactTime),
    houseRuler(chart, 5, exactTime),
    planetInSign(chart, 'venus'),
    planetInHouse(chart, 'venus', exactTime),
    planetInSign(chart, 'mars'),
    planetInHouse(chart, 'mars', exactTime),
    planetInSign(chart, 'moon'),
    planetInHouse(chart, 'moon', exactTime),
    aspectBetween(chart, 'venus', 'mars'),
    aspectBetween(chart, 'moon', 'venus'),
    aspectBetween(chart, 'venus', 'saturn'),
  ],
  character: (chart, exactTime) => [
    planetInSign(chart, 'sun'),
    planetInHouse(chart, 'sun', exactTime),
    planetInSign(chart, 'moon'),
    planetInHouse(chart, 'moon', exactTime),
    planetInSign(chart, 'mercury'),
    aspectBetween(chart, 'sun', 'moon'),
    dignityNote(chart, 'sun'),
    dignityNote(chart, 'moon'),
  ],
  purpose: (chart, exactTime) => [
    planetInSign(chart, 'true_node'),
    planetInHouse(chart, 'true_node', exactTime),
    planetInSign(chart, 'south_node'),
    planetInHouse(chart, 'south_node', exactTime),
    houseRuler(chart, 10, exactTime),
    houseRuler(chart, 9, exactTime),
  ],
};

function ascendantFactor(chart, exactTime) {
  if (!exactTime) return null;
  const sign = toSign(chart.angles.asc);
  return {
    id: `asc.${sign.index}`,
    section: 'ascendant',
    title: `Асцендент в ${SIGNS_IN[sign.index]}`,
    where: 'угол карты',
  };
}

export function collectFactors(chart, topicKey, exactTime) {
  const build = TOPIC_FACTORS[topicKey];
  if (!build) return [];
  const factors = build(chart, exactTime).filter(Boolean);
  if (topicKey === 'character') {
    const ascendant = ascendantFactor(chart, exactTime);
    if (ascendant) factors.unshift(ascendant);
  }
  return factors;
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
