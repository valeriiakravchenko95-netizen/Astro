// Транзиты: как градус в небе задевает натальную карту.
//
// Транзит — это встреча, а не свойство карты: планета в небе подходит к
// градусу, который в карте чем-то занят. Поэтому считается не «что
// происходит», а «за что именно в этой карте цепляется вот этот градус».

import { MAJOR, ASPECTS } from './aspects.js';
import { houseOf } from './houses.js';
import { rulerOf, TRADITIONAL } from './rulers.js';
import { norm180, signIndex } from './zodiac.js';

// Орбисы транзитов уже натальных: планета проходит градус за дни или
// недели, и широкий орбис размазал бы событие на месяцы.
export const TRANSIT_ORBS = {
  conjunction: 3, opposition: 3, square: 3, trine: 3, sextile: 2,
};

export const CUSP_ORB = 2;

// Точным считается контакт в пределах четверти градуса — это примерно
// сутки хода для Луны и недели для внешних планет.
const EXACT = 0.25;

export function ruledHouses(chart) {
  // Дом управляется телом, которому принадлежит знак на его куспиде.
  // Это и переводит «задета планета» в «задета тема»: транзит к
  // управителю второго дома говорит о деньгах, даже если сама планета
  // стоит в седьмом. Управители берутся из той же схемы, по которой
  // построена карта.
  const cusps = chart.houses.get(chart.houseSystem).cusps;
  const mapping = new Map();
  for (let house = 1; house <= 12; house += 1) {
    const ruler = rulerOf(signIndex(cusps[house - 1]), chart.rulerScheme || TRADITIONAL);
    if (!mapping.has(ruler)) mapping.set(ruler, []);
    mapping.get(ruler).push(house);
  }
  return mapping;
}

export function examine(chart, longitude, transitName = 'транзит', options = {}) {
  const {
    orbs = TRANSIT_ORBS,
    cuspOrb = CUSP_ORB,
    aspects = MAJOR,
  } = options;

  const hasHouses = chart.exactTime !== false;
  const hits = [];

  const check = (natal, natalLongitude, kind) => {
    for (const aspect of aspects) {
      const limit = orbs[aspect.key];
      if (!limit) continue;
      const delta = norm180(longitude - natalLongitude);
      const target = delta >= 0 ? aspect.angle : -aspect.angle;
      const orb = Math.abs(norm180(delta - target));
      if (orb <= limit) {
        hits.push({
          transit: transitName, natal, natalKind: kind, aspect, orb,
          exact: orb <= EXACT, natalLongitude,
          strength: Math.max(0, 1 - orb / limit),
        });
        return; // ближайший аспект для пары найден
      }
    }
  };

  for (const [key, position] of chart.positions) {
    check(key, position.longitude, 'body');
  }

  if (hasHouses) {
    check('asc', chart.angles.asc, 'angle');
    check('mc', chart.angles.mc, 'angle');

    const cusps = chart.houses.get(chart.houseSystem).cusps;
    for (let house = 1; house <= 12; house += 1) {
      const orb = Math.abs(norm180(longitude - cusps[house - 1]));
      if (orb <= cuspOrb) {
        hits.push({
          transit: transitName, natal: `куспид ${house}`, natalKind: 'cusp',
          house, aspect: ASPECTS[0], orb, exact: orb <= EXACT,
          natalLongitude: cusps[house - 1],
          strength: Math.max(0, 1 - orb / cuspOrb),
        });
      }
    }
  }

  hits.sort((a, b) => a.orb - b.orb);

  const cusps = hasHouses ? chart.houses.get(chart.houseSystem).cusps : null;
  const house = cusps ? houseOf(cusps, longitude) : null;

  const rulership = hasHouses ? ruledHouses(chart) : new Map();
  const touched = new Set();
  if (house) touched.add(house);
  for (const hit of hits) {
    if (hit.natalKind === 'body') {
      for (const ruled of rulership.get(hit.natal) || []) touched.add(ruled);
      const position = chart.positions.get(hit.natal);
      if (position && hasHouses) touched.add(position.house);
    } else if (hit.natalKind === 'cusp') {
      touched.add(hit.house);
    } else if (hit.natal === 'asc') {
      touched.add(1);
    } else if (hit.natal === 'mc') {
      touched.add(10);
    }
  }

  return {
    longitude,
    hits,
    house,
    housesTouched: [...touched].sort((a, b) => a - b),
    ruledHouses: rulership,
    get touches() { return hits.length > 0 || house !== null; },
  };
}

// Загрузка календаря событий.
let calendar = null;

export async function loadEvents(url = 'data/events.json') {
  if (calendar) return calendar;
  try {
    const response = await fetch(url);
    if (!response.ok) throw new Error(String(response.status));
    const payload = await response.json();
    calendar = payload.events || [];
  } catch (error) {
    calendar = [];
  }
  return calendar;
}

export function allEvents() {
  return calendar || [];
}

// Ближайшие события: недавно прошедшие и предстоящие.
export function eventsAround(date = new Date(), before = 21, after = 45) {
  const today = date.toISOString().slice(0, 10);
  const from = new Date(date.getTime() - before * 86400000).toISOString().slice(0, 10);
  const to = new Date(date.getTime() + after * 86400000).toISOString().slice(0, 10);
  return allEvents()
    .filter((event) => event.date >= from && event.date <= to)
    .map((event) => ({ ...event, past: event.date < today }));
}

export function findEvent(key) {
  if (!key) return null;
  // Ключ может быть с датой — так ссылка указывает на конкретное событие,
  // а не на любое такое же в календаре.
  const [base, date] = key.split('@');
  const matches = allEvents().filter((event) => event.key === base);
  if (!matches.length) return null;
  if (date) return matches.find((event) => event.date === date) || matches[0];
  // Без даты берётся ближайшее к сегодняшнему дню.
  const today = new Date().toISOString().slice(0, 10);
  return matches.reduce((best, event) => {
    const distance = Math.abs(Date.parse(event.date) - Date.parse(today));
    const bestDistance = Math.abs(Date.parse(best.date) - Date.parse(today));
    return distance < bestDistance ? event : best;
  });
}
