// Системы домов: целые знаки, Плацидус, Порфирий.

import { eclipticDeclination, longitudeFromRightAscension } from './angles.js';
import { norm180, norm360 } from './zodiac.js';

const RAD = Math.PI / 180;
const DEG = 180 / Math.PI;

export const WHOLE_SIGN = 'whole_sign';
export const PLACIDUS = 'placidus';
export const PORPHYRY = 'porphyry';

export const SYSTEM_NAMES = {
  [WHOLE_SIGN]: 'Целые знаки',
  [PLACIDUS]: 'Плацидус',
  [PORPHYRY]: 'Порфирий',
};

export class CircumpolarError extends Error {}

// Промежуточные куспиды Плацидуса: доля суточной дуги, лежит ли дуга над
// горизонтом, и начальное приближение в прямом восхождении.
const PLACIDUS_SPEC = {
  11: [1 / 3, true, 30],
  12: [2 / 3, true, 60],
  2: [2 / 3, false, 120],
  3: [1 / 3, false, 150],
};

const MAX_ITERATIONS = 60;
const TOLERANCE = 1e-10;

function semiarc(declination, latitude) {
  const cosine = -Math.tan(latitude * RAD) * Math.tan(declination * RAD);
  if (cosine > 1 || cosine < -1) {
    throw new CircumpolarError(
      `точка эклиптики не пересекает горизонт на широте ${latitude.toFixed(4)}°`,
    );
  }
  return Math.acos(cosine) * DEG;
}

// Куспид ищется итерациями: по оценке долготы считается склонение, по нему
// суточная дуга, по дуге — часовой угол и новая долгота.
function placidusCusp(house, ramc, obliquity, latitude) {
  const [fraction, diurnal, offset] = PLACIDUS_SPEC[house];
  let candidate = longitudeFromRightAscension(ramc + offset, obliquity);

  for (let attempt = 0, damping = 1; attempt < 3; attempt += 1, damping *= 0.5) {
    let value = candidate;
    for (let i = 0; i < MAX_ITERATIONS; i += 1) {
      const declination = eclipticDeclination(value, obliquity);
      const diurnalArc = semiarc(declination, latitude);
      const hourAngle = diurnal
        ? -fraction * diurnalArc
        : -(180 - fraction * (180 - diurnalArc));
      const updated = longitudeFromRightAscension(ramc - hourAngle, obliquity);
      const step = norm180(updated - value);
      value = norm360(value + damping * step);
      if (Math.abs(step) < TOLERANCE) return value;
    }
  }
  throw new Error(`куспид ${house} дома не сошёлся`);
}

export function wholeSign(asc) {
  const start = Math.floor(norm360(asc) / 30) * 30;
  return { system: WHOLE_SIGN, cusps: Array.from({ length: 12 }, (_, i) => norm360(start + 30 * i)) };
}

// Порфирий: каждый из четырёх квадрантов делится на три равные дуги.
export function porphyry(asc, mc) {
  const desc = norm360(asc + 180);
  const ic = norm360(mc + 180);
  const first = norm360(ic - asc) / 3;
  const second = norm360(desc - ic) / 3;
  return {
    system: PORPHYRY,
    cusps: [
      asc, norm360(asc + first), norm360(asc + 2 * first),
      ic, norm360(ic + second), norm360(ic + 2 * second),
      desc, norm360(desc + first), norm360(desc + 2 * first),
      mc, norm360(mc + second), norm360(mc + 2 * second),
    ],
  };
}

export function placidus(angles, latitude) {
  if (Math.abs(latitude) >= 90 - angles.obliquity) {
    throw new CircumpolarError(
      `широта ${latitude.toFixed(4)}° за полярным кругом: Плацидус там не определён`,
    );
  }
  const cusp11 = placidusCusp(11, angles.ramc, angles.obliquity, latitude);
  const cusp12 = placidusCusp(12, angles.ramc, angles.obliquity, latitude);
  const cusp2 = placidusCusp(2, angles.ramc, angles.obliquity, latitude);
  const cusp3 = placidusCusp(3, angles.ramc, angles.obliquity, latitude);
  return {
    system: PLACIDUS,
    cusps: [
      angles.asc, cusp2, cusp3,
      angles.ic, norm360(cusp11 + 180), norm360(cusp12 + 180),
      angles.desc, norm360(cusp2 + 180), norm360(cusp3 + 180),
      angles.mc, cusp11, cusp12,
    ],
  };
}

export function build(system, angles, latitude, fallback = null) {
  const builders = {
    [WHOLE_SIGN]: () => wholeSign(angles.asc),
    [PLACIDUS]: () => placidus(angles, latitude),
    [PORPHYRY]: () => porphyry(angles.asc, angles.mc),
  };
  if (!builders[system]) throw new Error(`неизвестная система домов: ${system}`);
  try {
    return builders[system]();
  } catch (error) {
    // Молча подменять систему домов хуже, чем сказать о невозможности,
    // поэтому запасной вариант применяется только когда он задан явно.
    if (error instanceof CircumpolarError && fallback && fallback !== system) {
      return builders[fallback]();
    }
    throw error;
  }
}

export function houseOf(cusps, longitude) {
  const value = norm360(longitude);
  for (let i = 0; i < 12; i += 1) {
    const start = cusps[i];
    let width = norm360(cusps[(i + 1) % 12] - start);
    if (width === 0) width = 360;
    if (norm360(value - start) < width) return i + 1;
  }
  return 12;
}

export function widths(cusps) {
  return cusps.map((cusp, i) => norm360(cusps[(i + 1) % 12] - cusp));
}
