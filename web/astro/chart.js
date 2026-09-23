// Сборка натальной карты.

import { computeAngles } from './angles.js';
import { DIGNIFIED_KINDS, getBody, BODIES } from './bodies.js';
import { findAll, findToAngles, MAJOR, ASPECTS, DEFAULT_ORBS, DEFAULT_BONUS } from './aspects.js';
import { build as buildHouses, houseOf, PLACIDUS, WHOLE_SIGN, SYSTEM_NAMES, widths } from './houses.js';
import { isDiurnal, partOfFortune } from './lots.js';
import { findAntiscia, findPatterns, findStelliums } from './patterns.js';
import { buildDispositors, essentialDignities, rulerOf, TRADITIONAL } from './rulers.js';
import { julianDay, ttFromUtc } from './time.js';
import { zonedTimeToUtc } from './timezone.js';
import { signIndex, toSign } from './zodiac.js';

// Тела, которые берутся из таблиц. Южный узел и Часть Фортуны считаются
// от них, поэтому в таблицах их нет.
const TABLE_KEYS = [
  'sun', 'moon', 'mercury', 'venus', 'mars', 'jupiter',
  'saturn', 'uranus', 'neptune', 'pluto', 'true_node', 'mean_lilith',
];

export function computeChart(ephemeris, input) {
  const {
    year, month, day, hour = 12, minute = 0,
    latitude, longitude, timeZone,
    exactTime = true,
    houseSystem = PLACIDUS,
    rulerScheme = TRADITIONAL,
    minorAspects = false,
    antisciaOrb = 1,
  } = input;

  const moment = zonedTimeToUtc({ year, month, day, hour, minute, second: 0 }, timeZone);
  const utc = new Date(moment.timestamp);
  const jdUtc = julianDay(
    utc.getUTCFullYear(), utc.getUTCMonth() + 1, utc.getUTCDate(),
    utc.getUTCHours(), utc.getUTCMinutes(), utc.getUTCSeconds(),
  );
  const jdTt = ttFromUtc(jdUtc);

  const positions = new Map();
  for (const key of TABLE_KEYS) {
    if (ephemeris.has(key)) positions.set(key, ephemeris.position(key, jdTt));
  }

  const northNode = positions.get('true_node');
  if (northNode) {
    positions.set('south_node', {
      longitude: (northNode.longitude + 180) % 360,
      speed: northNode.speed,
      retrograde: northNode.retrograde,
    });
  }

  const angles = computeAngles(jdTt, latitude, longitude);

  const sun = positions.get('sun');
  const moon = positions.get('moon');
  const diurnal = sun ? isDiurnal(sun.longitude, angles.asc) : null;
  if (sun && moon) {
    positions.set('part_of_fortune', {
      // Жребий движется вместе с Асцендентом — около градуса за четыре
      // минуты. Такая скорость не описывает движение среди знаков, и
      // сходимость аспектов по ней считать бессмысленно.
      longitude: partOfFortune(angles.asc, sun.longitude, moon.longitude, diurnal),
      speed: 0,
      retrograde: false,
    });
  }

  const houses = new Map();
  for (const system of [houseSystem, WHOLE_SIGN]) {
    if (!houses.has(system)) {
      houses.set(system, buildHouses(system, angles, latitude, WHOLE_SIGN));
    }
  }

  const ordered = new Map();
  for (const body of BODIES) {
    if (positions.has(body.key)) ordered.set(body.key, positions.get(body.key));
  }

  const list = minorAspects ? ASPECTS : MAJOR;
  const aspects = findAll(ordered, list, DEFAULT_ORBS, DEFAULT_BONUS);
  const angleAspects = findToAngles(ordered, angles, list);

  const dignities = new Map();
  if (diurnal !== null) {
    for (const [key, position] of ordered) {
      if (DIGNIFIED_KINDS.has(getBody(key).kind)) {
        dignities.set(key, essentialDignities(key, position.longitude, diurnal, rulerScheme));
      }
    }
  }

  const signByBody = {};
  for (const [key, position] of ordered) signByBody[key] = signIndex(position.longitude);

  const details = new Map();
  for (const [key, position] of ordered) {
    const body = getBody(key);
    const houseNumbers = {};
    for (const [system, built] of houses) {
      houseNumbers[system] = houseOf(built.cusps, position.longitude);
    }
    details.set(key, {
      body,
      longitude: position.longitude,
      speed: position.speed,
      retrograde: position.retrograde,
      stationary: body.stationary > 0 && Math.abs(position.speed) < body.stationary,
      sign: toSign(position.longitude),
      houses: houseNumbers,
      house: houseNumbers[houseSystem],
    });
  }

  return {
    jdTt,
    utc,
    moment,
    exactTime,
    angles,
    houses,
    houseSystem,
    houseSystemName: SYSTEM_NAMES[houses.get(houseSystem).system],
    positions: details,
    raw: ordered,
    aspects,
    angleAspects,
    dignities,
    diurnal,
    patterns: findPatterns(aspects),
    stelliums: findStelliums(ordered, aspects),
    antiscia: findAntiscia(ordered, antisciaOrb),
    rulerScheme,
    dispositors: buildDispositors(signByBody, rulerScheme),
    chartRuler: rulerOf(signIndex(angles.asc), rulerScheme),
    widths: (system) => widths(houses.get(system).cusps),
  };
}
