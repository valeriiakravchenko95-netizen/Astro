// Аспекты с настраиваемыми орбисами.

import { norm180 } from './zodiac.js';

export const ASPECTS = [
  { key: 'conjunction', name: 'Соединение', angle: 0, glyph: '☌', major: true },
  { key: 'opposition', name: 'Оппозиция', angle: 180, glyph: '☍', major: true },
  { key: 'trine', name: 'Трин', angle: 120, glyph: '△', major: true },
  { key: 'square', name: 'Квадрат', angle: 90, glyph: '□', major: true },
  { key: 'sextile', name: 'Секстиль', angle: 60, glyph: '⚹', major: true },
  { key: 'semisextile', name: 'Полусекстиль', angle: 30, glyph: '⚺', major: false },
  { key: 'semisquare', name: 'Полуквадрат', angle: 45, glyph: '∠', major: false },
  { key: 'sesquisquare', name: 'Полутораквадрат', angle: 135, glyph: '⚼', major: false },
  { key: 'quincunx', name: 'Квиконс', angle: 150, glyph: '⚻', major: false },
  { key: 'quintile', name: 'Квинтиль', angle: 72, glyph: 'Q', major: false },
  { key: 'biquintile', name: 'Биквинтиль', angle: 144, glyph: 'bQ', major: false },
];

export const MAJOR = ASPECTS.filter((a) => a.major);

export const DEFAULT_ORBS = {
  conjunction: 8, opposition: 8, trine: 7, square: 7, sextile: 5,
  semisextile: 2, semisquare: 2, sesquisquare: 2, quincunx: 3,
  quintile: 1.5, biquintile: 1.5,
};

// Светилам традиционно дают орбис шире.
export const DEFAULT_BONUS = { sun: 2, moon: 2 };

// Узлы стоят в точной оппозиции друг к другу по построению — это их
// устройство, а не расположение карты, и показывать её среди аспектов
// значит выдавать механику расчёта за свойство карты.
const DEGENERATE = [['true_node', 'south_node'], ['mean_node', 'south_node']];

function isDegenerate(a, b) {
  return DEGENERATE.some(([x, y]) => (a === x && b === y) || (a === y && b === x));
}

export function orbLimit(bodyA, bodyB, aspect, orbs = DEFAULT_ORBS, bonus = DEFAULT_BONUS) {
  const base = orbs[aspect.key] ?? 0;
  return base + Math.max(bonus[bodyA] ?? 0, bonus[bodyB] ?? 0);
}

export function findBetween(a, b, list = MAJOR, orbs = DEFAULT_ORBS, bonus = DEFAULT_BONUS) {
  let best = null;
  for (const aspect of list) {
    const limit = orbLimit(a.key, b.key, aspect, orbs, bonus);
    if (limit <= 0) continue;
    const delta = norm180(a.longitude - b.longitude);
    const target = delta >= 0 ? aspect.angle : -aspect.angle;
    const signed = norm180(delta - target);
    const orb = Math.abs(signed);
    if (orb > limit) continue;
    // Аспект сходится, когда отклонение и относительная скорость смотрят
    // в разные стороны: разность долгот идёт к точному углу.
    const applying = signed * (a.speed - b.speed) < 0;
    const hit = {
      bodyA: a.key, bodyB: b.key, aspect, orb, limit, applying,
      separation: Math.abs(delta),
      strength: Math.max(0, 1 - orb / limit),
    };
    if (!best || hit.orb < best.orb) best = hit;
  }
  return best;
}

export function findAll(positions, list = MAJOR, orbs = DEFAULT_ORBS, bonus = DEFAULT_BONUS) {
  const entries = [...positions.entries()].map(([key, value]) => ({ key, ...value }));
  const hits = [];
  for (let i = 0; i < entries.length; i += 1) {
    for (let j = i + 1; j < entries.length; j += 1) {
      if (isDegenerate(entries[i].key, entries[j].key)) continue;
      const hit = findBetween(entries[i], entries[j], list, orbs, bonus);
      if (hit) hits.push(hit);
    }
  }
  hits.sort((x, y) => x.orb - y.orb);
  return hits;
}

// Аспекты к углам карты. Углы бегут со скоростью вращения Земли, поэтому
// сходимость для них не считается.
export function findToAngles(positions, angles, list = MAJOR, orbs = DEFAULT_ORBS, bonus = DEFAULT_BONUS) {
  const targets = { asc: angles.asc, mc: angles.mc };
  const hits = [];
  for (const [key, position] of positions) {
    for (const [name, longitude] of Object.entries(targets)) {
      for (const aspect of list) {
        const limit = orbLimit(key, name, aspect, orbs, bonus);
        const delta = norm180(position.longitude - longitude);
        const target = delta >= 0 ? aspect.angle : -aspect.angle;
        const orb = Math.abs(norm180(delta - target));
        if (orb <= limit) {
          hits.push({ bodyA: key, bodyB: name, aspect, orb, limit, applying: false });
        }
      }
    }
  }
  hits.sort((x, y) => x.orb - y.orb);
  return hits;
}
