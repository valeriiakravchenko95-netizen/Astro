// Раздел «Сейчас в небе»: событие и то, как оно задевает карту.

import { examine, eventsAround, findEvent } from './astro/transits.js';
import { formatLongitude } from './astro/zodiac.js';
import { textNodes } from './text.js';

let content = {
  events: {}, contacts: {}, points: {}, forms: {}, houses: {}, house_details: {}, featured: null,
};

export async function loadTransitTexts(url = 'content/transits.json') {
  try {
    const response = await fetch(url);
    if (response.ok) content = { ...content, ...(await response.json()) };
  } catch (error) {
    // Без текстов раздел все равно полезен: видно, задевает или нет.
  }
  return content;
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
  const asked = new URLSearchParams(location.search).get('event');
  const byLink = findEvent(asked);
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
function contactText(hit) {
  if (hit.natalKind === 'cusp') {
    const exact = content.contacts?.[`cusp.${hit.house}`];
    if (exact) return exact;
    const theme = content.houses?.[String(hit.house)];
    return theme ? `Градус приходится на самое начало темы: ${theme}.` : '';
  }
  const exact = content.contacts?.[`${hit.aspect.key}.${hit.natal}`];
  if (exact) return exact;
  const point = content.points?.[hit.natal];
  const form = content.forms?.[hit.aspect.key];
  return point && form ? `${point}\n\n${form}` : '';
}

function nameOf(chart, hit) {
  if (hit.natalKind === 'cusp') return `начало ${hit.house} дома`;
  if (hit.natal === 'asc') return 'Асцендент';
  if (hit.natal === 'mc') return 'МС';
  return chart.positions.get(hit.natal)?.body.name || hit.natal;
}

export function renderTransits(chart, { exactTime }) {
  const events = eventsAround();
  const chosen = chooseEvent(events);
  if (!chosen) return null;

  const node = element('section', 'card');
  node.append(element('h2', null, 'Сейчас в небе'));

  const chooser = element('div', 'topics');
  const body = element('div');

  const show = (event) => {
    for (const button of chooser.children) {
      button.setAttribute('aria-pressed', String(button.dataset.key === event.key + event.date));
    }
    body.replaceChildren();

    const heading = element('h3', null, event.title);
    const when = element('p', 'where',
      `${event.date.split('-').reverse().join('.')} · ${formatLongitude(event.longitude)}`
      + (event.past ? ' · уже прошло' : ''));
    body.append(heading, when);

    const about = content.events?.[event.key];
    if (about) body.append(...textNodes(about));

    const report = examine(chart, event.longitude, event.title);

    if (!report.touches) {
      body.append(element('p', 'note',
        'Твоей карты это событие не задевает: ни одна планета и ни один '
        + 'угол не попадают в орбис.'));
      return;
    }

    const verdict = element('div', 'warn');
    const parts = [];
    if (report.hits.length) {
      parts.push(`Задевает ${plural(report.hits.length, 'точку', 'точки', 'точек')} карты`);
    }
    if (report.house) parts.push(`градус приходится на ${report.house} дом`);
    verdict.textContent = parts.join(', ') + '.';
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
      body.append(element('p', 'note', 'Восклицательный знак - касание точное.'));
    }

    for (const hit of report.hits) {
      const written = contactText(hit);
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

  for (const event of events) {
    const button = document.createElement('button');
    button.type = 'button';
    button.dataset.key = event.key + event.date;
    button.textContent = `${event.date.slice(8)}.${event.date.slice(5, 7)} ${event.title}`;
    button.setAttribute('aria-pressed', 'false');
    button.addEventListener('click', () => show(event));
    chooser.append(button);
  }

  node.append(chooser, body);
  show(chosen);
  return node;
}
