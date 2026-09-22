// Управители знаков, достоинства и цепочки диспозиторов.

import { signIndex } from './zodiac.js';

export const TRADITIONAL = 'traditional';
export const MODERN = 'modern';

const TRADITIONAL_RULERS = [
  'mars', 'venus', 'mercury', 'moon', 'sun', 'mercury',
  'venus', 'mars', 'jupiter', 'saturn', 'saturn', 'jupiter',
];

const MODERN_RULERS = [
  'mars', 'venus', 'mercury', 'moon', 'sun', 'mercury',
  'venus', 'pluto', 'jupiter', 'saturn', 'uranus', 'neptune',
];

const SCHEMES = { [TRADITIONAL]: TRADITIONAL_RULERS, [MODERN]: MODERN_RULERS };

// Экзальтации: тело — знак и градус наибольшей силы.
export const EXALTATIONS = {
  sun: [0, 19], moon: [1, 3], mercury: [5, 15], venus: [11, 27],
  mars: [9, 28], jupiter: [3, 15], saturn: [6, 21],
};

export const DIGNITY_NAMES = {
  domicile: 'обитель', exaltation: 'экзальтация', detriment: 'изгнание',
  fall: 'падение', peregrine: 'перегрин', triplicity: 'триплицитет',
  term: 'терм', decan: 'декан',
};

// Триплицитеты по Дорофею: стихия — дневной, ночной и участвующий управитель.
const TRIPLICITY = [
  ['sun', 'jupiter', 'saturn'],
  ['venus', 'moon', 'mars'],
  ['saturn', 'mercury', 'jupiter'],
  ['venus', 'mars', 'moon'],
];

// Египетские термы: знак — управитель и верхняя граница в градусах знака.
const TERMS = [
  [['jupiter', 6], ['venus', 12], ['mercury', 20], ['mars', 25], ['saturn', 30]],
  [['venus', 8], ['mercury', 14], ['jupiter', 22], ['saturn', 27], ['mars', 30]],
  [['mercury', 6], ['jupiter', 12], ['venus', 17], ['mars', 24], ['saturn', 30]],
  [['mars', 7], ['venus', 13], ['mercury', 19], ['jupiter', 26], ['saturn', 30]],
  [['jupiter', 6], ['venus', 11], ['saturn', 18], ['mercury', 24], ['mars', 30]],
  [['mercury', 7], ['venus', 17], ['jupiter', 21], ['mars', 28], ['saturn', 30]],
  [['saturn', 6], ['mercury', 14], ['jupiter', 21], ['venus', 28], ['mars', 30]],
  [['mars', 7], ['venus', 11], ['mercury', 19], ['jupiter', 24], ['saturn', 30]],
  [['jupiter', 12], ['venus', 17], ['mercury', 21], ['saturn', 26], ['mars', 30]],
  [['mercury', 7], ['jupiter', 14], ['venus', 22], ['saturn', 26], ['mars', 30]],
  [['mercury', 7], ['venus', 13], ['jupiter', 20], ['mars', 25], ['saturn', 30]],
  [['venus', 12], ['jupiter', 16], ['mercury', 19], ['mars', 28], ['saturn', 30]],
];

// Халдейский ряд планет по убыванию видимой скорости.
const CHALDEAN = ['saturn', 'jupiter', 'mars', 'sun', 'venus', 'mercury', 'moon'];

export function rulerOf(sign, scheme = TRADITIONAL) {
  return SCHEMES[scheme][((sign % 12) + 12) % 12];
}

export function triplicityRuler(sign, diurnal) {
  const [day, night] = TRIPLICITY[(((sign % 12) + 12) % 12) % 4];
  return diurnal ? day : night;
}

export function termRuler(longitude) {
  const sign = signIndex(longitude);
  const degree = ((longitude % 30) + 30) % 30;
  for (const [ruler, bound] of TERMS[sign]) {
    if (degree < bound) return ruler;
  }
  return TERMS[sign][TERMS[sign].length - 1][0];
}

// Деканы по халдейскому ряду: первый декан Овна достаётся Марсу.
export function decanRuler(longitude) {
  const sign = signIndex(longitude);
  const decan = Math.floor((((longitude % 30) + 30) % 30) / 10);
  return CHALDEAN[(CHALDEAN.indexOf('mars') + sign * 3 + decan) % 7];
}

export function exaltationRulerOf(sign) {
  const index = ((sign % 12) + 12) % 12;
  for (const [body, [exaltSign]] of Object.entries(EXALTATIONS)) {
    if (exaltSign === index) return body;
  }
  return null;
}

export function majorState(body, sign, scheme = TRADITIONAL) {
  const index = ((sign % 12) + 12) % 12;
  const table = SCHEMES[scheme];
  if (table[index] === body) return 'domicile';
  if (table[(index + 6) % 12] === body) return 'detriment';
  const exaltation = EXALTATIONS[body];
  if (exaltation) {
    if (exaltation[0] === index) return 'exaltation';
    if ((exaltation[0] + 6) % 12 === index) return 'fall';
  }
  return 'peregrine';
}

// Все пять достоинств сразу. Важное различие: тело без обители и
// экзальтации ещё не перегрин — у него могут быть терм или декан.
// Перегрин — тот, у кого нет ни одного из пяти.
export function essentialDignities(body, longitude, diurnal, scheme = TRADITIONAL) {
  const sign = signIndex(longitude);
  const ruler = rulerOf(sign, scheme);
  const exaltation = exaltationRulerOf(sign);
  const triplicity = triplicityRuler(sign, diurnal);
  const term = termRuler(longitude);
  const decan = decanRuler(longitude);
  const own = [];
  if (ruler === body) own.push('domicile');
  if (exaltation === body) own.push('exaltation');
  if (triplicity === body) own.push('triplicity');
  if (term === body) own.push('term');
  if (decan === body) own.push('decan');
  return {
    body, sign, ruler, exaltation, triplicity, term, decan, own,
    state: majorState(body, sign, scheme),
    peregrine: own.length === 0,
  };
}

// Диспозиторы: у каждого тела — управитель его знака. Цепочки сходятся в
// кольца; кольцо из одного тела означает планету в своей обители, то есть
// финального диспозитора, из двух — взаимную рецепцию.
export function buildDispositors(signByBody, scheme = TRADITIONAL) {
  const present = new Set(Object.keys(signByBody));
  const dispositor = new Map();
  for (const [body, sign] of Object.entries(signByBody)) {
    const ruler = rulerOf(sign, scheme);
    dispositor.set(body, present.has(ruler) ? ruler : null);
  }

  const chains = new Map();
  const terminal = new Map();
  const cycles = [];
  const cycleByMember = new Map();

  for (const start of dispositor.keys()) {
    const path = [];
    const seen = new Map();
    let node = start;
    while (node !== null && node !== undefined && !seen.has(node)) {
      seen.set(node, path.length);
      path.push(node);
      node = dispositor.get(node);
    }
    if (node === null || node === undefined) {
      chains.set(start, path.slice(1));
      terminal.set(start, null);
      continue;
    }
    let cycle = cycleByMember.get(node);
    if (!cycle) {
      cycle = path.slice(seen.get(node));
      const pivot = cycle.indexOf([...cycle].sort()[0]);
      cycle = cycle.slice(pivot).concat(cycle.slice(0, pivot));
      cycles.push(cycle);
      cycle.forEach((member) => cycleByMember.set(member, cycle));
    }
    chains.set(start, path.slice(1, seen.get(node)));
    terminal.set(start, cycle);
  }

  cycles.sort((a, b) => a.length - b.length);
  return {
    dispositor,
    chains,
    terminal,
    cycles,
    finalDispositors: cycles.filter((c) => c.length === 1).map((c) => c[0]),
    mutualReceptions: cycles.filter((c) => c.length === 2),
  };
}
