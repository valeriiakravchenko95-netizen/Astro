// Колесо карты: знаки по кругу, дома, планеты и аспекты между ними.
//
// Рисуется в SVG прямо на странице, без картинок и библиотек. Асцендент
// слева, как принято: круг поворачивается так, чтобы восходящий градус
// оказался на девяти часах, а зодиак шел против часовой стрелки. Если
// время рождения неизвестно, домов и углов нет, и слева ставится 0° Овна.
//
// Для события неба поверх натала рисуется внешнее кольцо: планеты в день
// события, линии от градуса события к задетым точкам карты.

import { SIGN_GLYPHS } from './astro/zodiac.js';

const NS = 'http://www.w3.org/2000/svg';
const TEXT = '︎'; // просит шрифт рисовать символ знаком, а не цветной картинкой

// Что наносить на колесо. Жребии и южный узел только загромождают круг:
// южный узел всегда напротив северного.
const SHOWN = ['sun', 'moon', 'mercury', 'venus', 'mars', 'jupiter', 'saturn',
  'uranus', 'neptune', 'pluto', 'true_node', 'mean_lilith'];

const HARMONIC = new Set(['trine', 'sextile']);
const TENSE = new Set(['square', 'opposition']);

const SIZE = 400;
const C = SIZE / 2;
const R_OUT = 196;
const R_SIGN = 166;
const R_PLANET = 146;
const R_HOUSE_NUM = 116;
const R_INNER = 100;

function node(tag, attrs = {}, text) {
  const item = document.createElementNS(NS, tag);
  for (const [key, value] of Object.entries(attrs)) item.setAttribute(key, value);
  if (text !== undefined) item.textContent = text;
  return item;
}

// Разводит близко стоящие планеты, чтобы значки не налезали друг на друга.
// Настоящий градус при этом отмечается черточкой на кольце знаков.
function spread(longitudes, gap = 8) {
  const items = longitudes.map((value, index) => ({ index, value, shown: value }))
    .sort((a, b) => a.value - b.value);
  for (let pass = 0; pass < 40; pass += 1) {
    let moved = false;
    for (let i = 0; i < items.length; i += 1) {
      const a = items[i];
      const b = items[(i + 1) % items.length];
      const distance = ((b.shown - a.shown) % 360 + 360) % 360;
      if (items.length > 1 && distance < gap) {
        const push = (gap - distance) / 2;
        a.shown -= push;
        b.shown += push;
        moved = true;
      }
    }
    if (!moved) break;
  }
  const result = [];
  for (const item of items) result[item.index] = item.shown;
  return result;
}

export function renderWheel(chart, { exactTime, overlay = null }) {
  const start = exactTime ? chart.angles.asc : 0;
  // Экранный угол градуса эклиптики: слева старт, дальше против часовой.
  const point = (longitude, radius) => {
    const angle = Math.PI + ((longitude - start) * Math.PI) / 180;
    return [C + radius * Math.cos(angle), C - radius * Math.sin(angle)];
  };
  const line = (lonA, rA, lonB, rB, cls) => {
    const [x1, y1] = point(lonA, rA);
    const [x2, y2] = point(lonB, rB);
    return node('line', {
      x1: x1.toFixed(1), y1: y1.toFixed(1), x2: x2.toFixed(1), y2: y2.toFixed(1), class: cls,
    });
  };

  // Внешнему кольцу события нужно место за кругом знаков.
  const pad = overlay ? 34 : 0;
  const svg = node('svg', {
    viewBox: `${-pad} ${-pad} ${SIZE + 2 * pad} ${SIZE + 2 * pad}`,
    class: overlay ? 'wheel with-sky' : 'wheel', role: 'img',
    'aria-label': overlay ? 'Событие неба поверх натальной карты' : 'Колесо натальной карты',
  });

  svg.append(node('circle', { cx: C, cy: C, r: R_OUT, class: 'ring' }));
  svg.append(node('circle', { cx: C, cy: C, r: R_SIGN, class: 'ring' }));
  svg.append(node('circle', { cx: C, cy: C, r: R_INNER, class: 'ring thin' }));

  // Знаки: границы через 30° и значок посередине.
  for (let sign = 0; sign < 12; sign += 1) {
    svg.append(line(sign * 30, R_SIGN, sign * 30, R_OUT, 'tick'));
    const [x, y] = point(sign * 30 + 15, (R_OUT + R_SIGN) / 2);
    svg.append(node('text', {
      x: x.toFixed(1), y: y.toFixed(1), class: `sign el${sign % 4}`,
    }, SIGN_GLYPHS[sign] + TEXT));
  }

  // Какие углы задевает событие - их подписи тоже подсвечиваются.
  const touchedAngles = new Set((overlay?.hits || [])
    .filter((hit) => hit.natalKind === 'angle').map((hit) => hit.natal));
  const touchedCusps = new Set((overlay?.hits || [])
    .filter((hit) => hit.natalKind === 'cusp').map((hit) => hit.house));

  // Дома: куспиды от кольца знаков к внутреннему кругу, номер посередине.
  if (exactTime) {
    const cusps = chart.houses.get(chart.houseSystem).cusps;
    cusps.forEach((cusp, index) => {
      const angle = index === 0 || index === 9;
      const hit = touchedCusps.has(index + 1) ? ' hit' : '';
      svg.append(line(cusp, R_SIGN, cusp, R_INNER, `${angle ? 'axis' : 'cusp'}${hit}`));
      const next = cusps[(index + 1) % 12];
      const middle = cusp + ((((next - cusp) % 360) + 360) % 360) / 2;
      const [x, y] = point(middle, R_HOUSE_NUM);
      svg.append(node('text', { x: x.toFixed(1), y: y.toFixed(1), class: `house${hit}` }, String(index + 1)));
    });
    // Подписи углов снаружи круга.
    for (const [label, longitude] of [['ASC', chart.angles.asc], ['MC', chart.angles.mc]]) {
      const [x, y] = point(longitude, R_INNER - 12);
      const hit = touchedAngles.has(label.toLowerCase()) ? ' hit' : '';
      svg.append(node('text', { x: x.toFixed(1), y: y.toFixed(1), class: `angle${hit}` }, label));
    }
  }

  // Аспекты: линии внутри малого круга.
  const shown = SHOWN.filter((key) => chart.positions.has(key));
  const inner = node('g');
  for (const hit of chart.aspects) {
    if (!shown.includes(hit.bodyA) || !shown.includes(hit.bodyB)) continue;
    const kind = HARMONIC.has(hit.aspect.key) ? 'soft' : TENSE.has(hit.aspect.key) ? 'hard' : null;
    if (!kind) continue;
    const a = chart.positions.get(hit.bodyA).longitude;
    const b = chart.positions.get(hit.bodyB).longitude;
    inner.append(line(a, R_INNER, b, R_INNER, `aspect ${kind}`));
  }
  svg.append(inner);

  // Касания события: линии от его градуса к задетым точкам карты.
  const touched = new Set();
  if (overlay) {
    const contacts = node('g');
    for (const hit of overlay.hits) {
      let target = null;
      if (hit.natalKind === 'body' && shown.includes(hit.natal)) target = chart.positions.get(hit.natal).longitude;
      else if (hit.natalKind === 'angle' && exactTime) target = chart.angles[hit.natal];
      if (target === null) continue;
      touched.add(hit.natal);
      contacts.append(line(overlay.point, R_INNER, target, R_INNER, 'contact'));
    }
    svg.append(contacts);
  }

  // Планеты: черточка на настоящем градусе и значок на разведенном месте.
  const longitudes = shown.map((key) => chart.positions.get(key).longitude);
  const places = spread(longitudes);
  shown.forEach((key, index) => {
    const position = chart.positions.get(key);
    svg.append(line(position.longitude, R_SIGN, position.longitude, R_SIGN - 7, 'mark'));
    svg.append(line(position.longitude, R_INNER, position.longitude, R_INNER + 4, 'mark'));
    const [x, y] = point(places[index], R_PLANET);
    const glyph = node('text', {
      x: x.toFixed(1), y: y.toFixed(1),
      class: `planet${position.retrograde ? ' retro' : ''}${touched.has(key) ? ' hit' : ''}`,
    }, position.body.glyph + TEXT);
    glyph.append(node('title', {}, position.body.name));
    svg.append(glyph);
  });

  if (overlay) {
    // Градус события - сквозная черта через все кольца.
    svg.append(line(overlay.point, R_INNER, overlay.point, R_OUT + 4, 'event-axis'));
    const R_SKY = R_OUT + 18;
    const places = spread(overlay.bodies.map((body) => body.longitude), 10);
    overlay.bodies.forEach((body, index) => {
      svg.append(line(body.longitude, R_OUT, body.longitude, R_OUT + 6, 'sky-mark'));
      const [x, y] = point(places[index], R_SKY);
      const glyph = node('text', {
        x: x.toFixed(1), y: y.toFixed(1), class: 'sky-planet',
      }, body.glyph + TEXT);
      glyph.append(node('title', {}, `${body.name} в небе`));
      svg.append(glyph);
    });
  }

  return svg;
}
