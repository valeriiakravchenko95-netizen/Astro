// Какие трактовки писать первыми.
//
// Полный набор — это сотни текстов, и писать их подряд бессмысленно:
// «Солнце в Раке» встретится у каждого двенадцатого посетителя, а
// «Меркурий в 12 доме, управитель 9-го» — у одного из двухсот. Скрипт
// прогоняет много правдоподобных карт через ту же отборку факторов, что
// работает на странице, и показывает ключи по убыванию частоты вместе с
// долей карточек, у которых уже есть текст. Написанные ключи в списке
// пропускаются: он показывает, что писать дальше.
//
//   node scripts/priority.mjs                 # все темы
//   node scripts/priority.mjs money 40        # одна тема, сорок строк

import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(here, '..');
const web = path.join(root, 'web');

// Модули страницы рассчитаны на браузер: подменяем загрузку файлов чтением
// с диска, чтобы считать теми же формулами, а не их копией.
globalThis.fetch = async (url) => {
  const file = path.join(web, url);
  return {
    ok: fs.existsSync(file),
    json: async () => JSON.parse(fs.readFileSync(file, 'utf8')),
    arrayBuffer: async () => {
      const buffer = fs.readFileSync(file);
      return buffer.buffer.slice(buffer.byteOffset, buffer.byteOffset + buffer.byteLength);
    },
  };
};

const { Ephemeris } = await import(path.join(web, 'astro/ephemeris.js'));
const { computeChart } = await import(path.join(web, 'astro/chart.js'));
const { MODERN } = await import(path.join(web, 'astro/rulers.js'));
const { collectFactors, loadInterpretations } = await import(path.join(web, 'readings.js'));

// Правдоподобная аудитория: взрослые люди, большие города, известное время.
const PLACES = [
  { latitude: 55.7558, longitude: 37.6173, timeZone: 'Europe/Moscow' },
  { latitude: 50.4501, longitude: 30.5234, timeZone: 'Europe/Kyiv' },
  { latitude: 48.0230, longitude: 37.8022, timeZone: 'Europe/Kyiv' },
  { latitude: 59.9343, longitude: 30.3351, timeZone: 'Europe/Moscow' },
  { latitude: 53.9006, longitude: 27.5590, timeZone: 'Europe/Minsk' },
  { latitude: 43.2220, longitude: 76.8512, timeZone: 'Asia/Almaty' },
  { latitude: 41.2995, longitude: 69.2401, timeZone: 'Asia/Tashkent' },
  { latitude: 56.8389, longitude: 60.6057, timeZone: 'Asia/Yekaterinburg' },
];

const FIRST_YEAR = 1965;
const LAST_YEAR = 2008;

function makeRandom(seed) {
  // Простой генератор с зерном: результат должен повторяться от запуска к
  // запуску, иначе список приоритетов будет скакать.
  let state = seed;
  return () => {
    state = (state * 1103515245 + 12345) & 0x7fffffff;
    return state / 0x7fffffff;
  };
}

const [topicArgument, limitArgument] = process.argv.slice(2);
const LIMIT = Number(limitArgument) || 25;
const COUNT = 2000;

const ephemeris = await Ephemeris.load('data/ephemeris.bin');
const content = await loadInterpretations();
const topics = content.topics.filter(
  (topic) => !topicArgument || topic.key === topicArgument,
);
if (!topics.length) {
  console.error(`тема не найдена: ${topicArgument}`);
  process.exit(1);
}

const random = makeRandom(20260923);
const charts = [];
while (charts.length < COUNT) {
  const place = PLACES[Math.floor(random() * PLACES.length)];
  const year = FIRST_YEAR + Math.floor(random() * (LAST_YEAR - FIRST_YEAR + 1));
  const month = 1 + Math.floor(random() * 12);
  const day = 1 + Math.floor(random() * 28);
  const hour = Math.floor(random() * 24);
  const minute = Math.floor(random() * 60);
  try {
    charts.push(computeChart(ephemeris, {
      year, month, day, hour, minute, ...place, rulerScheme: MODERN,
    }));
  } catch (error) {
    // Карта вне интервала таблиц — просто берём следующую.
  }
}

const written = (section, id) => Boolean(content.texts?.[section]?.[id]);

// Что писать под фактор. Если у него есть точный текст - он и есть ключ.
// Иначе фактор собирается из кусков, и писать нужно куски: так один текст
// «управитель 2 дома в 10» закрывает все планеты, которые могут управлять.
function unitsOf(factor) {
  if (written(factor.section, factor.id) || !factor.parts?.length) {
    return [{ section: factor.section, id: factor.id, title: factor.title }];
  }
  return factor.parts.map((piece) => ({
    section: piece.section, id: piece.key, title: `${factor.title} (${piece.section})`,
  }));
}

const shows = (factor) => unitsOf(factor).some((unit) => written(unit.section, unit.id));

for (const topic of topics) {
  const counts = new Map();
  const titles = new Map();
  let factorsTotal = 0;
  let factorsShown = 0;

  for (const chart of charts) {
    const factors = collectFactors(chart, topic.key, true);
    for (const factor of factors) {
      factorsTotal += 1;
      if (shows(factor)) factorsShown += 1;
      for (const unit of unitsOf(factor)) {
        const key = `${unit.section}\u0000${unit.id}`;
        counts.set(key, (counts.get(key) || 0) + 1);
        if (!titles.has(key)) titles.set(key, unit.title);
      }
    }
  }

  const rows = [...counts.entries()]
    .map(([key, count]) => {
      const [section, id] = key.split('\u0000');
      return { section, id, count, title: titles.get(key), done: written(section, id) };
    })
    .sort((a, b) => b.count - a.count);

  const done = rows.filter((row) => row.done).length;
  console.log(`\n=== ${topic.name} ===`);
  console.log(`всего разных ключей: ${rows.length}, написано: ${done}`);
  console.log(`карточек с текстом: ${((factorsShown / Math.max(1, factorsTotal)) * 100).toFixed(0)} % `
    + `(на ${charts.length} картах)`);
  console.log(`${'ключ'.padEnd(34)} ${'встретится'.padStart(11)}  пример`);

  // Накопленный охват: доля карт, где встретится хоть один из ключей
  // сверху списка. Считается честно — по картам, а не сложением частот.
  let shown = 0;
  for (const row of rows.filter((item) => !item.done || LIMIT > rows.length)) {
    if (shown >= LIMIT) break;
    shown += 1;
    const share = (row.count / charts.length) * 100;
    const mark = row.done ? '✓' : ' ';
    console.log(
      `${mark} ${(row.section + '/' + row.id).padEnd(32)} ${share.toFixed(1).padStart(9)} %  ${row.title}`,
    );
  }

}
