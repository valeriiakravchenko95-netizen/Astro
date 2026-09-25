// Раздел «Сейчас в небе»: событие и то, как оно задевает карту.

import { allEvents, examine, eventsAround, findEvent } from './astro/transits.js';
import { formatLongitude } from './astro/zodiac.js';
import { textNodes } from './text.js';
import { renderWheel } from './wheel.js';

let content = {
  events: {}, contacts: {}, points: {}, forms: {}, houses: {}, house_details: {}, featured: null,
  links: {},
};

export async function loadTransitTexts() {
  // Опубликованная страница получает отсюда только закрепленное событие;
  // тексты придут с сервера под конкретную карту (см. neededSkyTexts).
  try {
    const response = await fetch('content/public.json');
    if (response.ok) {
      const data = await response.json();
      content.featured = data.featured || null;
      content.links = data.event_links || {};
      return content;
    }
  } catch (error) {
    // работаем с исходниками
  }
  try {
    const response = await fetch('content/transits.json');
    if (response.ok) content = { ...content, ...(await response.json()) };
  } catch (error) {
    // Без текстов раздел все равно полезен: видно, задевает или нет.
  }
  return content;
}

export function addSkyTexts(texts) {
  for (const [section, items] of Object.entries(texts || {})) {
    if (items && typeof items === 'object') content[section] = { ...(content[section] || {}), ...items };
  }
}

// Событие, о котором пришли спросить: ?event=ключ@дата или короткая ссылка
// под рилс вроде /polnolunie (раздел links в transits.json).
function askedLink() {
  const path = decodeURIComponent(location.pathname).replace(/^\/+|\/+$/g, '').toLowerCase();
  return path ? content.links?.[path] || null : null;
}

export function askedEvent() {
  const byQuery = findEvent(new URLSearchParams(location.search).get('event'));
  if (byQuery) return byQuery;
  const link = askedLink();
  return link ? findEvent(link.event) : null;
}

// Заголовок страницы, когда пришли по ссылке на событие: вместо «Натальная
// карта» - само событие.
export function eventHeading() {
  const event = askedEvent();
  if (!event) return null;
  const link = new URLSearchParams(location.search).get('event') ? null : askedLink();
  const date = event.date.split('-').reverse().slice(0, 2).join('.');
  return {
    main: link?.heading || event.title,
    accent: link?.heading_em ?? date,
    lead: link?.lead || 'Проверь по своей натальной карте, заденет ли это тебя и в какой сфере жизни. '
      + 'Расчет идет в твоем браузере: дата и место рождения никуда не отправляются.',
    title: link?.title || `${event.title} ${date}`,
  };
}

// Текст события. Для конкретного дня может быть свой, под ключом с датой
// («lunation.full@2026-09-26»): так пишется разбор под рилс, а общий текст
// остается для остальных полнолуний.
function eventText(event) {
  return content.events?.[`${event.key}@${event.date}`] || content.events?.[event.key] || '';
}

// Какие тексты раздела неба понадобятся этой карте: события рядом с
// сегодняшним днем, личный список, событие из ссылки и все касания в них.
export function neededSkyTexts(chart, exactTime) {
  const events = new Map();
  for (const event of eventsAround()) events.set(event.key + event.date, event);
  for (const { event } of strongestEvents(chart, { exactTime })) events.set(event.key + event.date, event);
  const wanted = [];
  for (const event of [askedEvent(), findEvent(content.featured)]) {
    if (!event) continue;
    events.set(event.key + event.date, event);
    // свой текст на конкретный день бывает только у событий из ссылок
    wanted.push(['events', `${event.key}@${event.date}`]);
    for (const form of ['conjunction', 'opposition', 'square', 'trine', 'sextile']) {
      wanted.push(['forms', `${form}@${event.key}@${event.date}`]);
    }
  }
  for (const event of events.values()) {
    wanted.push(['events', event.key]);
    for (const hit of examine(chart, event.longitude, event.title).hits) {
      if (hit.natalKind === 'cusp') {
        wanted.push(['contacts', `cusp.${hit.house}`]);
      } else {
        wanted.push(['contacts', `${hit.aspect.key}.${hit.natal}`], ['points', hit.natal]);
      }
    }
  }
  for (const form of ['conjunction', 'opposition', 'square', 'trine', 'sextile']) wanted.push(['forms', form]);
  for (let house = 1; house <= 12; house += 1) {
    wanted.push(['houses', String(house)], ['house_details', String(house)]);
  }
  const unique = new Map(wanted.map((pair) => [pair.join('\u0000'), pair]));
  return [...unique.values()];
}

// Склонение существительного при числе: одна точка, две точки, пять точек.
function plural(count, one, few, many) {
  const tens = count % 100;
  const units = count % 10;
  let word = many;
  if (tens < 11 || tens > 14) {
    if (units === 1) word = one;
    else if (units >= 2 && units <= 4) word = few;
  }
  return `${count} ${word}`;
}

function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

// Какое событие показывать. Ссылка вида ?event=station.uranus.retrograde
// или с датой через собаку - так пост в ленте ведет ровно на то событие,
// о котором рассказывали.
function chooseEvent(events) {
  const byLink = askedEvent();
  if (byLink) return byLink;
  const featured = findEvent(content.featured);
  if (featured) return featured;
  // Иначе ближайшее к сегодняшнему дню, предпочитая уже наступившее.
  if (!events.length) return null;
  const today = new Date().toISOString().slice(0, 10);
  const past = events.filter((event) => event.date <= today);
  return past.length ? past[past.length - 1] : events[0];
}

// Текст касания. Если под точным ключом («square.venus», «cusp.10») текста
// нет, он собирается из двух кусков: что в карте задето (points) и как
// идет касание (forms). Для куспида - из названия темы дома.
// У события из ссылки могут быть свои формы касаний под ключом
// «sextile@lunation.full@2026-09-26»: полнолуние с Нептуном просит
// другого шага, чем обычное.
function contactText(hit, event) {
  if (hit.natalKind === 'cusp') {
    const exact = content.contacts?.[`cusp.${hit.house}`];
    if (exact) return exact;
    const theme = content.houses?.[String(hit.house)];
    return theme ? `Градус приходится на самое начало темы: ${theme}.` : '';
  }
  const exact = content.contacts?.[`${hit.aspect.key}.${hit.natal}`];
  if (exact) return exact;
  const point = content.points?.[hit.natal];
  const form = (event && content.forms?.[`${hit.aspect.key}@${event.key}@${event.date}`])
    || content.forms?.[hit.aspect.key];
  return point && form ? `${point}\n\n${form}` : '';
}

function nameOf(chart, hit) {
  if (hit.natalKind === 'cusp') return `начало ${hit.house} дома`;
  if (hit.natal === 'asc') return 'Асцендент';
  if (hit.natal === 'mc') return 'МС';
  return chart.positions.get(hit.natal)?.body.name || hit.natal;
}

// focus - страница открыта по ссылке на событие: сначала колесо с этим
// событием поверх карты и его разбор, календарь остальных событий в конце.
// skyAt(event) дает планеты неба на момент события для внешнего кольца.
// Подпись под колесом: что нарисовано коралловым.
function skyLegend(bodies, report) {
  const legend = element('p', 'sky-legend');
  const names = bodies.map((body) => body.name);
  const list = names.length > 1 ? `${names.slice(0, -1).join(', ')} и ${names[names.length - 1]}` : names[0];
  if (list) {
    legend.append(element('b', null, 'За кругом'), ` - где в день события стоят ${list}. `);
  }
  if (report.hits.length) {
    legend.append(element('b', null, 'Линии и коралловое внутри'),
      ' - планеты, углы и начала домов твоей карты, которые это задевает.');
  } else {
    legend.append('Линий нет: точки твоей карты это не задевает.');
  }
  return legend;
}

export function renderTransits(chart, { exactTime, focus = false, skyAt = null }) {
  const events = eventsAround();
  const chosen = chooseEvent(events);
  if (!chosen) return null;

  const node = element('section', 'card');
  node.append(element('h2', null, focus ? 'Как это ложится на твою карту' : 'Сейчас в небе'));

  const chooser = element('div', 'topics');
  const body = element('div');

  const show = (event) => {
    for (const button of chooser.children) {
      button.setAttribute('aria-pressed', String(button.dataset.key === event.key + event.date));
    }
    body.replaceChildren();

    const report = examine(chart, event.longitude, event.title);

    if (focus && skyAt) {
      body.append(renderWheel(chart, {
        exactTime,
        overlay: { point: event.longitude, hits: report.hits, bodies: skyAt(event) },
      }));
      body.append(skyLegend(skyAt(event), report));
    }

    const heading = element('h3', null, event.title);
    const when = element('p', 'where',
      `${event.date.split('-').reverse().join('.')} · ${formatLongitude(event.longitude)}`
      + (event.past ? ' · уже прошло' : ''));
    body.append(heading, when);

    const about = eventText(event);
    if (about) body.append(...textNodes(about));

    if (!report.touches) {
      body.append(element('p', 'note',
        'Твоей карты это событие не задевает: ни одна планета и ни один '
        + 'угол не попадают в орбис.'));
      return;
    }

    const verdict = element('div', 'warn');
    if (report.hits.length) {
      const parts = [`Задевает ${plural(report.hits.length, 'точку', 'точки', 'точек')} карты`];
      if (report.house) parts.push(`градус приходится на ${report.house} дом`);
      verdict.textContent = parts.join(', ') + '.';
    } else {
      verdict.textContent = `Лично тебя не задевает: ни одна точка карты не попадает в орбис. `
        + `Градус приходится на ${report.house} дом - в этой сфере событие пройдет фоном.`;
    }
    body.append(verdict);

    const table = element('table');
    for (const hit of report.hits) {
      const row = element('tr');
      row.append(element('td', 'name', nameOf(chart, hit)));
      row.append(element('td', 'note', hit.aspect.name.toLowerCase()));
      row.append(element('td', 'deg', `${hit.orb.toFixed(1)}°`));
      row.append(element('td', 'mark', hit.exact ? '!' : ''));
      table.append(row);
    }
    if (report.hits.length) {
      body.append(table);
      if (report.hits.some((hit) => hit.exact)) {
        body.append(element('p', 'note', 'Восклицательный знак - касание точное.'));
      }
    }

    for (const hit of report.hits) {
      const written = contactText(hit, event);
      if (!written) continue;
      const item = element('div', 'reading');
      item.append(element('h3', null, hit.natalKind === 'cusp'
        ? `Касается: ${nameOf(chart, hit)}`
        : `Касается: ${nameOf(chart, hit)}, ${hit.aspect.name.toLowerCase()}`));
      item.append(...textNodes(written));
      body.append(item);
    }

    if (exactTime && report.housesTouched.length) {
      const themes = element('div', 'reading');
      themes.append(element('h3', null, 'Каких сфер жизни это касается'));
      const list = element('ul', 'themes');
      for (const house of report.housesTouched) {
        const name = content.houses?.[String(house)] || `${house} дом`;
        const details = content.house_details?.[String(house)];
        const item = element('li');
        item.append(element('strong', null, name));
        if (details) item.append(document.createTextNode(`: ${details}`));
        list.append(item);
      }
      themes.append(list);
      body.append(themes);
    } else if (!exactTime) {
      body.append(element('p', 'note',
        'Без точного времени рождения видно только касания планет: '
        + 'дома и углы зависят от минут.'));
    }
  };

  const addButton = (event) => {
    const button = document.createElement('button');
    button.type = 'button';
    button.dataset.key = event.key + event.date;
    button.textContent = `${event.date.slice(8)}.${event.date.slice(5, 7)} ${event.title}`;
    button.setAttribute('aria-pressed', 'false');
    button.addEventListener('click', () => show(event));
    chooser.append(button);
  };
  for (const event of events) addButton(event);

  if (focus) {
    const more = element('h3', 'more-events', 'Другие события неба');
    node.append(body, more, chooser);
  } else {
    node.append(chooser, body);
  }
  show(chosen);

  // Открыть любое событие календаря, даже если его нет среди кнопок рядом с
  // сегодняшним днем: так работает список «что заденет тебя».
  node.showEvent = (event) => {
    const id = event.key + event.date;
    if (![...chooser.children].some((button) => button.dataset.key === id)) addButton(event);
    show(event);
  };
  return node;
}

// --- что из ближайшего заденет именно тебя -------------------------------

// Точки, касание которых человек почувствует лично. Высшие планеты и
// расчетные точки задеваются годами у целых поколений - их здесь нет.
const PERSONAL = ['sun', 'moon', 'mercury', 'venus', 'mars', 'jupiter', 'saturn', 'asc', 'mc'];

// Новолуния и полнолуния бывают каждые две недели и задевают что-нибудь
// почти всегда, поэтому для них допуск уже.
const LIMIT = { lunation: 1, default: 1.5 };

export function personalEvents(chart, { exactTime, days = 183, today = new Date() } = {}) {
  const from = today.toISOString().slice(0, 10);
  const to = new Date(today.getTime() + days * 86400000).toISOString().slice(0, 10);
  const found = [];
  for (const event of allEvents()) {
    if (event.date < from || event.date > to) continue;
    const report = examine(chart, event.longitude, event.title);
    const limit = LIMIT[event.kind] ?? LIMIT.default;
    const hits = report.hits.filter((hit) => PERSONAL.includes(hit.natal)
      && hit.orb <= limit && (exactTime || hit.natalKind === 'body'));
    if (hits.length) found.push({ event, hits, weight: weigh(event, hits, limit) });
  }
  return found;
}

// За полгода таких касаний набирается полтора-два десятка. Показываются
// самые заметные: точнее, по светилам и углам, через напряженные аспекты,
// затмения и развороты планет.
const LOUD = new Set(['sun', 'moon', 'asc', 'mc']);
const HARD = new Set(['conjunction', 'opposition', 'square']);

function weigh(event, hits, limit) {
  let weight = 0;
  for (const hit of hits) {
    weight += (1 - hit.orb / (limit + 0.5))
      * (LOUD.has(hit.natal) ? 1.3 : 1)
      * (HARD.has(hit.aspect.key) ? 1.3 : 1);
  }
  if (event.kind === 'station') weight += 0.3;
  if (event.key.endsWith('.solar') || event.key.endsWith('.lunar')) weight += 0.5;
  return weight;
}

export function strongestEvents(chart, options = {}, count = 8) {
  return personalEvents(chart, options)
    .sort((a, b) => b.weight - a.weight)
    .slice(0, count)
    .sort((a, b) => a.event.date.localeCompare(b.event.date));
}

export function renderUpcoming(chart, { exactTime, onPick }) {
  const found = strongestEvents(chart, { exactTime });
  const node = element('section', 'card');
  node.append(element('h2', null, 'Что из ближайшего заденет тебя'));
  if (!found.length) {
    node.append(element('p', 'note',
      'В ближайшие полгода крупных касаний к твоим личным точкам нет.'));
    return node;
  }
  node.append(element('p', 'note',
    'События неба на полгода вперед, которые ложатся точно на твои личные точки. '
    + 'Нажми, чтобы прочитать, о чем это.'));
  const list = element('ul', 'upcoming');
  for (const { event, hits } of found) {
    const item = element('li');
    const button = element('button', null);
    button.type = 'button';
    button.append(element('span', 'date', event.date.split('-').reverse().join('.')));
    button.append(element('span', 'what', event.title));
    button.append(element('span', 'touch', 'касается: '
      + hits.map((hit) => `${nameOf(chart, hit)} (${hit.aspect.name.toLowerCase()})`).join(', ')));
    button.addEventListener('click', () => onPick?.(event));
    item.append(button);
    list.append(item);
  }
  node.append(list);
  return node;
}
