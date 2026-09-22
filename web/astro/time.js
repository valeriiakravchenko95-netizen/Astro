// Шкалы времени, нутация и звёздное время.
//
// Повторяет то, что делает Skyfield, на тех же константах: они выгружены
// в constants.js прямо из Python, поэтому расхождения из-за опечатки в
// длинной таблице чисел здесь быть не может.

import {
  DELTA_T, DELTA_T_FIRST_YEAR, DELTA_T_PER_YEAR,
  FUNDAMENTAL_CONSTANT, FUNDAMENTAL_RATE,
  LEAP_DATES, LEAP_OFFSETS, NUTATION_ARGUMENTS, NUTATION_LONGITUDE,
  PRE_LEAP_OFFSET,
  NUTATION_LONGITUDE_OFFSET, NUTATION_OBLIQUITY, NUTATION_OBLIQUITY_OFFSET,
} from './constants.js';
import { DEGREES } from './zodiac.js';

export const J2000 = 2451545.0;
const ARCSECONDS_TO_RADIANS = Math.PI / (180 * 3600);
const TAU = 2 * Math.PI;

// Юлианская дата по григорианскому календарю.
export function julianDay(year, month, day, hour = 0, minute = 0, second = 0) {
  let y = year;
  let m = month;
  if (m <= 2) {
    y -= 1;
    m += 12;
  }
  const a = Math.floor(y / 100);
  const b = 2 - a + Math.floor(a / 4);
  const jd = Math.floor(365.25 * (y + 4716))
    + Math.floor(30.6001 * (m + 1))
    + day + b - 1524.5;
  return jd + (hour + minute / 60 + second / 3600) / 24;
}

// Разница TAI − UTC на момент: накопленные скачки секунды.
export function taiMinusUtc(jdUtc) {
  // До первого скачка секунды разница своя, а не значение первой записи.
  let offset = PRE_LEAP_OFFSET;
  for (let i = 0; i < LEAP_DATES.length; i += 1) {
    if (jdUtc >= LEAP_DATES[i]) offset = LEAP_OFFSETS[i];
  }
  return offset;
}

// Разница TT − UT1 линейной интерполяцией по годам.
export function deltaT(jd) {
  const year = 2000 + (jd - J2000) / 365.25;
  const position = (year - DELTA_T_FIRST_YEAR) * DELTA_T_PER_YEAR;
  if (position <= 0) return DELTA_T[0];
  if (position >= DELTA_T.length - 1) return DELTA_T[DELTA_T.length - 1];
  const index = Math.floor(position);
  const fraction = position - index;
  return DELTA_T[index] * (1 - fraction) + DELTA_T[index + 1] * fraction;
}

// Из UTC в земное время: TT = UTC + (TAI − UTC) + 32.184 секунды.
export function ttFromUtc(jdUtc) {
  return jdUtc + (taiMinusUtc(jdUtc) + 32.184) / 86400;
}

export function ut1FromTt(jdTt) {
  return jdTt - deltaT(jdTt) / 86400;
}

// Аргументы Делоне в радианах: средняя аномалия Луны и Солнца, аргумент
// широты Луны, элонгация и долгота узла.
function fundamentalArguments(t) {
  const result = new Array(5);
  for (let i = 0; i < 5; i += 1) {
    const arcseconds = FUNDAMENTAL_CONSTANT[i] + FUNDAMENTAL_RATE[i] * t;
    result[i] = (arcseconds % 1296000) * ARCSECONDS_TO_RADIANS;
  }
  return result;
}

// Нутация по модели IAU 2000B. Возвращает поправки к долготе и наклону в
// радианах.
export function nutation(jdTt) {
  const t = (jdTt - J2000) / 36525;
  const a = fundamentalArguments(t);

  let dpsi = 0;
  let deps = 0;
  for (let i = 0; i < NUTATION_ARGUMENTS.length; i += 1) {
    const row = NUTATION_ARGUMENTS[i];
    const argument = row[0] * a[0] + row[1] * a[1] + row[2] * a[2]
      + row[3] * a[3] + row[4] * a[4];
    const sin = Math.sin(argument);
    const cos = Math.cos(argument);
    const lon = NUTATION_LONGITUDE[i];
    const obl = NUTATION_OBLIQUITY[i];
    dpsi += (lon[0] + lon[1] * t) * sin + lon[2] * cos;
    deps += (obl[0] + obl[1] * t) * cos + obl[2] * sin;
  }
  dpsi += NUTATION_LONGITUDE_OFFSET;
  deps += NUTATION_OBLIQUITY_OFFSET;

  // Ряд считан в десятых долях микросекунды дуги.
  const scale = 1e-7 * ARCSECONDS_TO_RADIANS;
  return { dpsi: dpsi * scale, deps: deps * scale };
}

// Средний наклон эклиптики в радианах (Capitaine et al. 2003).
export function meanObliquity(jdTt) {
  const t = (jdTt - J2000) / 36525;
  const arcseconds = ((((-0.0000000434 * t
    - 0.000000576) * t
    + 0.00200340) * t
    - 0.0001831) * t
    - 46.836769) * t + 84381.406;
  return arcseconds * ARCSECONDS_TO_RADIANS;
}

export function trueObliquity(jdTt) {
  return meanObliquity(jdTt) + nutation(jdTt).deps;
}

// Угол поворота Земли — доля оборота (резолюция IAU B1.8 2000 года).
function earthRotationAngle(jdUt1) {
  const whole = Math.floor(jdUt1);
  const fraction = jdUt1 - whole;
  const th = 0.7790572732640 + 0.00273781191135448 * (jdUt1 - J2000);
  return (((th % 1) + (whole % 1) + fraction) % 1 + 1) % 1;
}

// Среднее гринвичское звёздное время в часах.
export function gmst(jdTt) {
  const theta = earthRotationAngle(ut1FromTt(jdTt));
  const t = (jdTt - J2000) / 36525;
  const st = 0.014506
    + ((((-0.0000000368 * t
      - 0.000029956) * t
      - 0.00000044) * t
      + 1.3915817) * t
      + 4612.156534) * t;
  return ((st / 54000 + theta * 24) % 24 + 24) % 24;
}

// Видимое гринвичское звёздное время: среднее плюс уравнение равноденствий.
// Дополнительные члены уравнения не превышают трёх тысячных угловой
// секунды и опущены — это меньше десятитысячной доли градуса в RAMC.
export function gast(jdTt) {
  const { dpsi } = nutation(jdTt);
  const equation = dpsi * Math.cos(meanObliquity(jdTt));
  return ((gmst(jdTt) + (equation / TAU) * 24) % 24 + 24) % 24;
}

// Местное звёздное время в градусах — прямое восхождение середины неба.
export function ramc(jdTt, longitudeEast) {
  const value = gast(jdTt) * 15 + longitudeEast;
  return ((value % 360) + 360) % 360;
}

export { DEGREES };
