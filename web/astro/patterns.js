// Аспектные фигуры, стеллиумы и контакты по антисам.

import { antiscion, contraAntiscion, separation, signIndex } from './zodiac.js';

// Фигура — набор вершин с определёнными рёбрами между ними.
export const PATTERNS = [
  { key: 'grand_cross', name: 'Большой крест', size: 4, edges: [
    [0, 2, 'opposition'], [1, 3, 'opposition'],
    [0, 1, 'square'], [1, 2, 'square'], [2, 3, 'square'], [0, 3, 'square']] },
  { key: 'kite', name: 'Парус', size: 4, edges: [
    [0, 1, 'trine'], [1, 2, 'trine'], [0, 2, 'trine'],
    [0, 3, 'opposition'], [1, 3, 'sextile'], [2, 3, 'sextile']] },
  { key: 'mystic_rectangle', name: 'Мистический прямоугольник', size: 4, edges: [
    [0, 2, 'opposition'], [1, 3, 'opposition'],
    [0, 1, 'trine'], [2, 3, 'trine'], [1, 2, 'sextile'], [0, 3, 'sextile']] },
  { key: 't_square', name: 'Тау-квадрат', size: 3, edges: [
    [0, 1, 'opposition'], [0, 2, 'square'], [1, 2, 'square']] },
  { key: 'grand_trine', name: 'Большой трин', size: 3, edges: [
    [0, 1, 'trine'], [1, 2, 'trine'], [0, 2, 'trine']] },
  { key: 'yod', name: 'Йод', size: 3, edges: [
    [0, 1, 'sextile'], [0, 2, 'quincunx'], [1, 2, 'quincunx']] },
  { key: 'minor_trine', name: 'Малый трин', size: 3, edges: [
    [0, 1, 'sextile'], [1, 2, 'sextile'], [0, 2, 'trine']] },
];

// Южный узел из вершин исключён: он всегда напротив северного, и любая
// планета в квадрате к ним давала бы мнимый тау-квадрат. Часть Фортуны —
// не тело, а точка, считаемая от угла карты.
export const EXCLUDED = new Set(['south_node', 'part_of_fortune']);

function permutations(items) {
  if (items.length <= 1) return [items];
  const result = [];
  for (let i = 0; i < items.length; i += 1) {
    const rest = items.slice(0, i).concat(items.slice(i + 1));
    for (const tail of permutations(rest)) result.push([items[i], ...tail]);
  }
  return result;
}

function combinations(items, size) {
  if (size === 0) return [[]];
  const result = [];
  for (let i = 0; i <= items.length - size; i += 1) {
    for (const tail of combinations(items.slice(i + 1), size - 1)) {
      result.push([items[i], ...tail]);
    }
  }
  return result;
}

export function findPatterns(hits, { excluded = EXCLUDED, includeSub = false } = {}) {
  const usable = hits.filter((h) => !excluded.has(h.bodyA) && !excluded.has(h.bodyB));
  const table = new Map();
  for (const hit of usable) {
    table.set([hit.bodyA, hit.bodyB].sort().join('|'), hit);
  }
  const bodies = [...new Set(usable.flatMap((h) => [h.bodyA, h.bodyB]))].sort();

  const found = [];
  for (const spec of PATTERNS) {
    for (const group of combinations(bodies, spec.size)) {
      for (const order of permutations(group)) {
        const orbs = [];
        let matched = true;
        for (const [left, right, aspectKey] of spec.edges) {
          const hit = table.get([order[left], order[right]].sort().join('|'));
          if (!hit || hit.aspect.key !== aspectKey) { matched = false; break; }
          orbs.push(hit.orb);
        }
        if (!matched) continue;
        const members = new Set(order);
        const already = found.some(
          (f) => f.key === spec.key && f.bodies.length === order.length
            && f.bodies.every((b) => members.has(b)),
        );
        if (!already) {
          found.push({
            key: spec.key, name: spec.name, bodies: order, orbs,
            worstOrb: Math.max(...orbs),
          });
        }
        break;
      }
    }
  }

  // Фигура, целиком вложенная в большую, отдельно не показывается: в
  // парусе нет своего большого трина, в кресте — двух тау-квадратов.
  if (includeSub) return found;
  return found.filter((hit) => !found.some((other) => other !== hit
    && other.bodies.length > hit.bodies.length
    && hit.bodies.every((b) => other.bodies.includes(b))));
}

export function findStelliums(positions, hits, minimum = 3) {
  const parent = new Map([...positions.keys()].map((k) => [k, k]));
  const root = (key) => {
    let node = key;
    while (parent.get(node) !== node) {
      parent.set(node, parent.get(parent.get(node)));
      node = parent.get(node);
    }
    return node;
  };
  for (const hit of hits) {
    if (hit.aspect.key !== 'conjunction') continue;
    const a = root(hit.bodyA);
    const b = root(hit.bodyB);
    if (a !== b) parent.set(a, b);
  }

  const result = [];
  const groups = new Map();
  for (const key of positions.keys()) {
    const head = root(key);
    if (!groups.has(head)) groups.set(head, []);
    groups.get(head).push(key);
  }
  for (const members of groups.values()) {
    if (members.length >= minimum) {
      result.push({ bodies: members.sort(), sign: null, byConjunction: true });
    }
  }

  const bySign = new Map();
  for (const [key, position] of positions) {
    const sign = signIndex(position.longitude);
    if (!bySign.has(sign)) bySign.set(sign, []);
    bySign.get(sign).push(key);
  }
  for (const [sign, members] of [...bySign.entries()].sort((a, b) => a[0] - b[0])) {
    if (members.length >= minimum) {
      result.push({ bodies: members.sort(), sign, byConjunction: false });
    }
  }
  return result;
}

// Антисы традиционно берут с узким орбисом — по умолчанию градус.
export function findAntiscia(positions, orb = 1) {
  const entries = [...positions.entries()];
  const found = [];
  for (let i = 0; i < entries.length; i += 1) {
    for (let j = i + 1; j < entries.length; j += 1) {
      const [keyA, a] = entries[i];
      const [keyB, b] = entries[j];
      const direct = separation(antiscion(a.longitude), b.longitude);
      if (direct <= orb) {
        found.push({ bodyA: keyA, bodyB: keyB, kind: 'antiscion', name: 'Антис', orb: direct });
      }
      const contra = separation(contraAntiscion(a.longitude), b.longitude);
      if (contra <= orb) {
        found.push({ bodyA: keyA, bodyB: keyB, kind: 'contra_antiscion', name: 'Контр-антис', orb: contra });
      }
    }
  }
  found.sort((x, y) => x.orb - y.orb);
  return found;
}
