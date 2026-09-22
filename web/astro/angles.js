// Углы карты: Асцендент, середина неба, Вертекс.

import { ramc, trueObliquity } from './time.js';
import { norm360 } from './zodiac.js';

const RAD = Math.PI / 180;
const DEG = 180 / Math.PI;

// Середина неба — точка эклиптики на верхнем меридиане. Её прямое
// восхождение равно местному звёздному времени.
export function midheaven(ramcDegrees, obliquityDegrees) {
  const ra = ramcDegrees * RAD;
  const eps = obliquityDegrees * RAD;
  return norm360(Math.atan2(Math.sin(ra), Math.cos(ra) * Math.cos(eps)) * DEG);
}

// Асцендент — пересечение эклиптики с восточной половиной горизонта.
export function ascendant(ramcDegrees, obliquityDegrees, latitude) {
  const ra = ramcDegrees * RAD;
  const eps = obliquityDegrees * RAD;
  const phi = latitude * RAD;
  const y = Math.cos(ra);
  const x = -(Math.sin(ra) * Math.cos(eps) + Math.tan(phi) * Math.sin(eps));
  return norm360(Math.atan2(y, x) * DEG);
}

// Вертекс — западное пересечение эклиптики с главным вертикалом. Тот же
// расчёт, что у Асцендента, но для дополнения широты и противоположного
// меридиана; дополнение берётся со знаком, иначе в южном полушарии точка
// уходит с главного вертикала.
export function vertex(ramcDegrees, obliquityDegrees, latitude) {
  return ascendant(norm360(ramcDegrees + 180), obliquityDegrees, 90 - latitude);
}

export function eclipticDeclination(longitude, obliquityDegrees) {
  return Math.asin(Math.sin(obliquityDegrees * RAD) * Math.sin(longitude * RAD)) * DEG;
}

export function eclipticRightAscension(longitude, obliquityDegrees) {
  const lon = longitude * RAD;
  const eps = obliquityDegrees * RAD;
  return norm360(Math.atan2(Math.sin(lon) * Math.cos(eps), Math.cos(lon)) * DEG);
}

export function longitudeFromRightAscension(raDegrees, obliquityDegrees) {
  const ra = raDegrees * RAD;
  const eps = obliquityDegrees * RAD;
  return norm360(Math.atan2(Math.sin(ra), Math.cos(ra) * Math.cos(eps)) * DEG);
}

export function computeAngles(jdTt, latitude, longitudeEast) {
  const obliquity = trueObliquity(jdTt) * DEG;
  const localSiderealTime = ramc(jdTt, longitudeEast);
  const asc = ascendant(localSiderealTime, obliquity, latitude);
  const mc = midheaven(localSiderealTime, obliquity);
  return {
    obliquity,
    ramc: localSiderealTime,
    asc,
    mc,
    desc: norm360(asc + 180),
    ic: norm360(mc + 180),
    vertex: vertex(localSiderealTime, obliquity, latitude),
    eastPoint: ascendant(localSiderealTime, obliquity, 0),
  };
}
