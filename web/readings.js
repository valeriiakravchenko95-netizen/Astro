// Темы и трактовки.
//
// Карта считается целиком, но показывать целиком ее незачем: под каждую
// тему из карты выбирается несколько значимых мест, и к ним подбирается
// текст. И темы, и тексты лежат в content/interpretations.json - код
// знает только, как достать из карты фактор каждого вида, а какие именно
// факторы входят в тему, решает файл. Новая тема не требует правки кода.

import { SIGNS_IN, signIndex, toSign } from './astro/zodiac.js';
import { rulerOf, TRADITIONAL } from './astro/rulers.js';
import { textNodes } from './text.js';

let content = { topics: [], texts: {} };

// На опубликованной странице тексты не лежат одним файлом: страница знает
// только список тем (content/public.json), а сами тексты спрашивает у
// сервера - ровно те, что нужны для этой карты. При работе с исходниками
// (локально, в тестах) public.json нет, и читается полный файл.
export async function loadInterpretations() {
  try {
    const response = await fetch('content/public.json');
    if (response.ok) {
      const published = await response.json();
      content = { topics: published.topics || [], texts: {} };
      return content;
    }
  } catch (error) {
    // нет - значит, работаем с исходниками
  }
  try {
    const response = await fetch('content/interpretations.json');
    if (response.ok) content = await response.json();
  } catch (error) {
    // Без трактовок страница остается полезной: цифры никуда не делись.
    content = { topics: [], texts: {} };
  }
  return content;
}

// Какие тексты понадобятся этой карте во всех темах: точные ключи и куски.
export function neededTexts(chart, exactTime) {
  const wanted = [];
  for (const topic of content.topics || []) {
    for (const factor of collectFactors(chart, topic.key, exactTime)) {
      wanted.push([factor.section, factor.id]);
      for (const piece of factor.parts || []) wanted.push([piece.section, piece.key]);
    }
  }
  return wanted;
}

export function addTexts(texts) {
  for (const [section, items] of Object.entries(texts || {})) {
    content.texts[section] = { ...(content.texts[section] || {}), ...items };
  }
}

function text(section, key) {
  return content.texts?.[section]?.[key] || '';
}

const bodyName = (chart, key) => chart.positions.get(key)?.body.name || key;
const shortName = (chart, key) => chart.positions.get(key)?.body.short || key;

// Десять планет. Узлы, Лилит, Хирон и жребии в составных текстах не
// участвуют: по методу они окрашивают вывод, а не делают его.
const PLANETS = ['sun', 'moon', 'mercury', 'venus', 'mars', 'jupiter',
  'saturn', 'uranus', 'neptune', 'pluto'];

const ELEMENTS = ['Огонь', 'Земля', 'Воздух', 'Вода'];

const where = (chart, key) => {
  const position = chart.positions.get(key);
  return `${position.body.name} в ${SIGNS_IN[position.sign.index]}`
    + (chart.exactTime === false ? '' : ` в ${position.house} доме`);
};

// Кусок текста фактора: ключ, по которому он лежит в файле, и подпись,
// если кусков в одном факторе несколько.
const part = (section, key, label = null) => ({ section, key, label });

// --- как достать из карты фактор каждого вида -------------------------------
//
// Каждый вид получает карту, признак известного времени и описание из файла,
// а возвращает либо готовый фактор, либо ничего - если в этой карте такого
// нет или для него не хватает времени рождения.
//
// У фактора есть точный ключ (section + id): если под ним в файле лежит
// текст, берется он. Если нет, фактор может собрать текст из кусков
// (parts) - так не нужно писать отдельный текст на каждое сочетание.

const FACTOR_KINDS = {
  planet_sign(chart, exactTime, spec) {
    const position = chart.positions.get(spec.body);
    if (!position) return null;
    return {
      id: `${spec.body}.${position.sign.index}`,
      section: 'planet_in_sign',
      title: `${position.body.name} в ${SIGNS_IN[position.sign.index]}`,
      where: 'знак',
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
      where: 'дом',
    };
  },

  // Дом говорит о чем, управитель - через что. Это основной способ читать
  // тему дома, и он работает даже когда в самом доме пусто. Управитель
  // берется по той схеме, по которой построена карта.
  house_ruler(chart, exactTime, spec) {
    if (!exactTime) return null;
    const cusps = chart.houses.get(chart.houseSystem).cusps;
    const sign = signIndex(cusps[spec.house - 1]);
    const ruler = rulerOf(sign, chart.rulerScheme || TRADITIONAL);
    const position = chart.positions.get(ruler);
    if (!position) return null;
    return {
      id: `${spec.house}.${ruler}.${position.house}`,
      section: 'house_ruler',
      title: `${spec.house} дом в ${SIGNS_IN[sign]}, его управитель ${position.body.name} `
        + `в ${SIGNS_IN[position.sign.index]} в ${position.house} доме`,
      where: 'управитель дома',
      parts: [part('ruler_in_house', `${spec.house}.${position.house}`)],
    };
  },

  planets_in_house(chart, exactTime, spec) {
    if (!exactTime) return null;
    const inside = [...chart.positions.entries()]
      .filter(([, position]) => position.house === spec.house)
      .map(([key]) => key);
    // Лилит, Хирон и жребии в доме без планет отдельной карточки не дают.
    const own = inside.filter((key) => PLANETS.includes(key) || key.endsWith('_node'));
    if (!own.length) return null;
    return {
      id: `${spec.house}.${inside.join('-')}`,
      section: 'planets_in_house',
      title: `В ${spec.house} доме: ${inside.map((key) => bodyName(chart, key)).join(', ')}`,
      where: 'дом',
      parts: own.map((key) => part('planet_in_house', `${key}.${spec.house}`,
        own.length > 1 ? bodyName(chart, key) : null)),
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
      where: 'связь двух планет',
    };
  },

  // Свой знак или знак экзальтации. Названия достоинств на страницу не
  // выводятся: текст описывает, как это работает, а не ставит оценку.
  dignity(chart, exactTime, spec) {
    const item = chart.dignities.get(spec.body);
    if (!item) return null;
    const strong = item.own.filter((code) => code === 'domicile' || code === 'exaltation');
    if (!strong.length) return null;
    const position = chart.positions.get(spec.body);
    return {
      id: `${spec.body}.${strong[0]}`,
      section: 'dignity',
      title: `${position.body.name} в ${SIGNS_IN[position.sign.index]}`,
      where: 'знак',
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

  // Центр карты - планета в своем знаке, к которой сходятся цепочки
  // управления других планет. Планета в своем знаке, к которой не
  // сходится ничего, самодостаточна, но центром не считается.
  final_dispositor(chart) {
    const { finalDispositors, terminal } = chart.dispositors;
    const centres = finalDispositors.filter((body) => PLANETS.some(
      (other) => other !== body && terminal.get(other)?.length === 1
        && terminal.get(other)[0] === body,
    ));
    if (!centres.length) return null;
    const all = centres.length === 1 && PLANETS.every(
      (other) => terminal.get(other)?.[0] === centres[0],
    );
    return {
      id: centres.join('-'),
      section: 'final_dispositor',
      title: `${centres.length === 1 ? 'Центр карты' : 'Центры карты'}: `
        + centres.map((key) => where(chart, key)).join('; '),
      where: centres.length > 1 ? 'к ним сходятся цепочки управления'
        : `к нему сходятся ${all ? 'все ' : ''}цепочки управления`,
      parts: centres.map((key) => part('final_dispositor', key,
        centres.length > 1 ? bodyName(chart, key) : null)),
    };
  },

  elements(chart) {
    const counts = Object.fromEntries(ELEMENTS.map((name) => [name, 0]));
    for (const [key, position] of chart.positions) {
      if (!PLANETS.slice(0, 7).includes(key)) continue;
      counts[position.sign.element] += 1;
    }
    const order = ELEMENTS.map((name) => [name, counts[name]]).sort((a, b) => b[1] - a[1]);
    // Преобладание есть, когда первое место делят не больше двух. Ровный
    // счет без пустых мест ничего особенного не говорит - карточки нет.
    const leaders = order.filter(([, count]) => count === order[0][1]);
    const top = leaders.length <= 2 ? leaders : [];
    const missing = order.filter(([, count]) => count === 0);
    if (!top.length && !missing.length) return null;
    return {
      id: order.map(([name, count]) => `${name}${count}`).join('-'),
      section: 'elements',
      title: order.map(([name, count]) => `${name} ${count}`).join(' · '),
      where: 'по семи личным планетам',
      parts: [
        ...top.map(([name]) => part('elements', `dominant.${name}`,
          top.length > 1 || missing.length ? `Больше всего: ${name.toLowerCase()}` : null)),
        ...missing.map(([name]) => part('elements', `missing.${name}`,
          `Ни одной: ${name.toLowerCase()}`)),
      ],
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
    // Один и тот же текст внутри темы показывается один раз: Венера во
    // втором доме может прийти и как «планета в доме», и как «кто стоит
    // во втором доме».
    const shown = new Set();
    for (const factor of factors) {
      const own = text(factor.section, factor.id);
      const candidates = own
        ? [{ section: factor.section, key: factor.id, raw: own }]
        : (factor.parts || []).map((piece) => ({ ...piece, raw: text(piece.section, piece.key) }));
      const pieces = [];
      let repeated = false;
      for (const piece of candidates) {
        const mark = `${piece.section}:${piece.key}`;
        if (!piece.raw) continue;
        if (shown.has(mark)) {
          repeated = true;
          continue;
        }
        shown.add(mark);
        pieces.push(piece);
      }
      // Все, что было сказать, уже сказано выше - карточку не повторяем.
      if (!pieces.length && repeated) continue;

      const item = document.createElement('div');
      item.className = 'reading';
      const title = document.createElement('h3');
      title.textContent = factor.title;
      const note = document.createElement('p');
      note.className = 'where';
      note.textContent = factor.where;
      item.append(title, note);
      for (const piece of pieces) {
        if (piece.label) {
          const label = document.createElement('h4');
          label.textContent = piece.label;
          item.append(label);
        }
        item.append(...textNodes(piece.raw));
      }
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
  // Ссылка вида ?topic=money открывает сразу нужную тему: так пост про
  // деньги ведет прямо в «Деньги и работа».
  const asked = new URLSearchParams(location.search).get('topic');
  show(topics.find((topic) => topic.key === asked) || topics[0]);
  return node;
}
