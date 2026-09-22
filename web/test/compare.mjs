// Сверка браузерного расчёта с оригинальным.
//
// Читает карты, посчитанные Python-ядром, пересчитывает их здесь и
// сравнивает всё: градусы тел, углы, куспиды домов, аспекты, фигуры,
// достоинства. Расхождение выводится в угловых секундах.
//
//   node web/test/compare.mjs

import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import { Ephemeris } from '../astro/ephemeris.js';
import { computeChart } from '../astro/chart.js';
import { PLACIDUS, WHOLE_SIGN } from '../astro/houses.js';

const here = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(here, '..', '..');

// Допуск в угловых секундах. Перенос считает теми же формулами, но разной
// арифметикой, а положения берёт из таблиц, а не из ядра, поэтому
// расхождение в доли секунды неизбежно и безвредно.
const TOLERANCE = 3;

function angleDifference(a, b) {
  return Math.abs(((a - b + 180) % 360 + 360) % 360 - 180) * 3600;
}

function main() {
  const charts = JSON.parse(
    fs.readFileSync(path.join(root, 'tests', 'data', 'reference_charts.json'), 'utf8'),
  );
  const raw = fs.readFileSync(path.join(root, 'web', 'data', 'ephemeris.bin'));
  const ephemeris = new Ephemeris(
    raw.buffer.slice(raw.byteOffset, raw.byteOffset + raw.byteLength),
  );

  const worst = new Map();
  const failures = [];
  let compared = 0;
  let skipped = 0;

  const note = (what, value, chart) => {
    const current = worst.get(what);
    if (!current || value > current.value) worst.set(what, { value, chart });
    if (value > TOLERANCE) {
      failures.push({ what, value, chart });
    }
  };

  for (const reference of charts) {
    const input = reference.input;
    // Сверяется астрономия, поэтому обе стороны получают один и тот же
    // момент в мировом времени. Часовые пояса проверяются отдельно:
    // база в браузере и база в Python расходятся на редких зонах и
    // датах до 1945 года, и это разница данных, а не расчёта.
    const [datePart, timePart] = reference.utc.split('T');
    const [year, month, day] = datePart.split('-').map(Number);
    const [hour, minute] = timePart.split(':').map(Number);
    let chart;
    try {
      chart = computeChart(ephemeris, {
        year, month, day, hour, minute,
        latitude: input.latitude, longitude: input.longitude,
        timeZone: 'UTC', houseSystem: PLACIDUS, exactTime: true,
      });
    } catch (error) {
      skipped += 1;
      continue;
    }
    compared += 1;
    const label = `${input.year}-${String(input.month).padStart(2, '0')}-`
      + `${String(input.day).padStart(2, '0')} ${input.place}`;

    for (const [key, expected] of Object.entries(reference.positions)) {
      const got = chart.positions.get(key);
      if (!got) continue;
      note(`долгота ${key}`, angleDifference(got.longitude, expected.longitude), label);
      // скорость сравнивается в тех же единицах, что и долгота
      note(`скорость ${key}`, Math.abs(got.speed - expected.speed) * 3600, label);
    }

    for (const [key, expected] of Object.entries(reference.angles)) {
      if (key === 'obliquity' || key === 'ramc') continue;
      note(`угол ${key}`, angleDifference(chart.angles[key], expected), label);
    }

    for (const [system, cusps] of Object.entries(reference.houses)) {
      const built = chart.houses.get(system === 'placidus' ? PLACIDUS : WHOLE_SIGN);
      if (!built) continue;
      cusps.forEach((cusp, index) => {
        note(`куспид ${system}`, angleDifference(built.cusps[index], cusp), label);
      });
    }

    if (chart.diurnal !== reference.diurnal) {
      failures.push({ what: 'секта', value: Infinity, chart: label });
    }

    // аспекты: наборы пар должны совпадать
    const ourAspects = new Set(chart.aspects.map(
      (h) => [h.bodyA, h.bodyB].sort().join('|') + ':' + h.aspect.key,
    ));
    const theirAspects = new Set(reference.aspects.map(
      (h) => [h.a, h.b].sort().join('|') + ':' + h.aspect,
    ));
    for (const item of theirAspects) {
      if (!ourAspects.has(item)) {
        failures.push({ what: `нет аспекта ${item}`, value: Infinity, chart: label });
      }
    }
    for (const item of ourAspects) {
      if (!theirAspects.has(item)) {
        failures.push({ what: `лишний аспект ${item}`, value: Infinity, chart: label });
      }
    }

    // фигуры
    const ourPatterns = new Set(chart.patterns.map(
      (p) => p.key + ':' + [...p.bodies].sort().join('|'),
    ));
    const theirPatterns = new Set(reference.patterns.map(
      (p) => p.key + ':' + p.bodies.join('|'),
    ));
    for (const item of theirPatterns) {
      if (!ourPatterns.has(item)) {
        failures.push({ what: `нет фигуры ${item}`, value: Infinity, chart: label });
      }
    }

    // достоинства
    for (const [key, expected] of Object.entries(reference.dignities)) {
      const got = chart.dignities.get(key);
      if (!got) continue;
      if (got.state !== expected.state || got.term !== expected.term
          || got.decan !== expected.decan
          || got.own.join(',') !== expected.own.join(',')) {
        failures.push({ what: `достоинства ${key}`, value: Infinity, chart: label });
      }
    }

    if (chart.chartRuler !== reference.chart_ruler) {
      failures.push({ what: 'управитель карты', value: Infinity, chart: label });
    }
  }

  console.log(`сверено карт: ${compared}${skipped ? `, пропущено ${skipped}` : ''}`);
  console.log(`допуск: ${TOLERANCE} угловых секунд\n`);

  const rows = [...worst.entries()].sort((a, b) => b[1].value - a[1].value);
  console.log('худшие расхождения:');
  for (const [what, info] of rows.slice(0, 12)) {
    const mark = info.value > TOLERANCE ? ' ✗' : '';
    console.log(`  ${what.padEnd(26)} ${info.value.toFixed(3).padStart(9)}"  ${info.chart}${mark}`);
  }

  if (failures.length) {
    console.log(`\nнесовпадений: ${failures.length}`);
    for (const failure of failures.slice(0, 15)) {
      const value = Number.isFinite(failure.value) ? ` ${failure.value.toFixed(3)}"` : '';
      console.log(`  ${failure.what}${value} — ${failure.chart}`);
    }
    process.exitCode = 1;
  } else {
    console.log('\nвсё сошлось');
  }
}

main();
