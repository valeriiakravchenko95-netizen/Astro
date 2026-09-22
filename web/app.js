// Страница расчёта: форма, поиск места, вывод карты.

import { Ephemeris } from './astro/ephemeris.js';
import { computeChart } from './astro/chart.js';
import { DIGNITY_NAMES } from './astro/rulers.js';
import { PLACIDUS, WHOLE_SIGN } from './astro/houses.js';
import { formatLongitude, SIGN_GLYPHS } from './astro/zodiac.js';
import { formatOffset } from './astro/timezone.js';
import { label, loadCities, search } from './places.js';
import { renderReadings, loadInterpretations } from './readings.js';

const form = document.getElementById('form');
const dateInput = document.getElementById('date');
const timeInput = document.getElementById('time');
const unknownTime = document.getElementById('unknown-time');
const placeInput = document.getElementById('place');
const suggestBox = document.getElementById('suggest');
const submit = document.getElementById('submit');
const status = document.getElementById('status');
const result = document.getElementById('result');

let ephemeris = null;
let chosenPlace = null;

function setStatus(text, isError = false) {
  status.textContent = text;
  status.classList.toggle('error', isError);
}

async function boot() {
  try {
    const [loaded] = await Promise.all([
      Ephemeris.load('data/ephemeris.bin'),
      loadCities(),
      loadInterpretations(),
    ]);
    ephemeris = loaded;
    submit.disabled = false;
    submit.textContent = 'Построить карту';
    setStatus('');
  } catch (error) {
    submit.textContent = 'Не удалось загрузить данные';
    setStatus(error.message, true);
  }
}

// --- выбор места -----------------------------------------------------------

function showSuggestions(cities) {
  suggestBox.replaceChildren();
  if (!cities.length) {
    suggestBox.hidden = true;
    return;
  }
  for (const city of cities) {
    const { name, where } = label(city);
    const button = document.createElement('button');
    button.type = 'button';
    button.innerHTML = `${name} <span class="where">${where}</span>`;
    button.addEventListener('click', () => {
      chosenPlace = city;
      placeInput.value = name;
      suggestBox.hidden = true;
      setStatus('');
    });
    suggestBox.append(button);
  }
  suggestBox.hidden = false;
}

placeInput.addEventListener('input', () => {
  chosenPlace = null;
  showSuggestions(search(placeInput.value));
});

placeInput.addEventListener('blur', () => {
  // Задержка нужна, чтобы клик по подсказке успел сработать раньше.
  setTimeout(() => { suggestBox.hidden = true; }, 150);
});

unknownTime.addEventListener('change', () => {
  timeInput.disabled = unknownTime.checked;
  if (unknownTime.checked) timeInput.value = '';
});

// --- расчёт ----------------------------------------------------------------

form.addEventListener('submit', (event) => {
  event.preventDefault();
  if (!ephemeris) return;

  if (!dateInput.value) {
    setStatus('Укажите дату рождения', true);
    return;
  }
  if (!chosenPlace) {
    setStatus('Выберите место из списка', true);
    return;
  }

  const [year, month, day] = dateInput.value.split('-').map(Number);
  const exactTime = !unknownTime.checked && Boolean(timeInput.value);
  const [hour, minute] = exactTime ? timeInput.value.split(':').map(Number) : [12, 0];

  try {
    const chart = computeChart(ephemeris, {
      year, month, day, hour, minute,
      latitude: chosenPlace.latitude,
      longitude: chosenPlace.longitude,
      timeZone: chosenPlace.zone,
      exactTime,
      houseSystem: PLACIDUS,
    });
    setStatus('');
    render(chart, exactTime);
    result.scrollIntoView({ behavior: 'smooth', block: 'start' });
  } catch (error) {
    setStatus(error.message, true);
  }
});

// --- вывод -----------------------------------------------------------------

function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function card(title) {
  const node = element('section', 'card');
  if (title) node.append(element('h2', null, title));
  return node;
}

function render(chart, exactTime) {
  result.replaceChildren();

  const { name, where } = label(chosenPlace);
  const local = chart.moment;
  const head = card();
  head.append(element('h2', null, 'Карта'));
  head.append(element('p', 'note',
    `${name}, ${where.split(',')[0]} · ${dateInput.value.split('-').reverse().join('.')}`
    + (exactTime ? ` ${timeInput.value}` : '')
    + ` · ${formatOffset(local.offsetMinutes)}`));

  if (!exactTime) {
    head.append(element('div', 'warn',
      'Время рождения неизвестно, карта посчитана на полдень. Положения по '
      + 'знакам верны, но Луна за сутки проходит до 15°, а дома и Асцендент '
      + 'зависят от минут — их здесь нет.'));
  } else if (local.imaginary) {
    head.append(element('div', 'warn',
      'В этот день стрелки переводили вперёд, и указанного часа не '
      + 'существовало. Проверьте время.'));
  } else if (local.ambiguous) {
    head.append(element('div', 'warn',
      'В этот день стрелки переводили назад, и такой час прошёл дважды. '
      + 'Взят первый.'));
  }
  result.append(head);

  result.append(renderPositions(chart, exactTime));
  if (exactTime) result.append(renderAngles(chart));
  result.append(renderAspects(chart));
  if (chart.dignities.size) result.append(renderDignities(chart));
  if (chart.patterns.length || chart.stelliums.length) result.append(renderPatterns(chart));

  const readings = renderReadings(chart, { exactTime });
  if (readings) result.append(readings);

  result.hidden = false;
}

function renderPositions(chart, exactTime) {
  const node = card('Положения');
  const table = element('table');
  for (const [, position] of chart.positions) {
    const row = element('tr');
    row.append(element('td', 'glyph', position.body.glyph));
    row.append(element('td', 'name', position.body.short));
    row.append(element('td', 'deg', formatLongitude(position.longitude)));
    row.append(element('td', 'mark',
      position.stationary ? 'S' : (position.retrograde ? 'R' : '')));
    row.append(element('td', 'house', exactTime ? String(position.house) : ''));
    table.append(row);
  }
  node.append(table);
  if (exactTime) node.append(element('p', 'note', 'Последний столбец — дом. R — попятное движение, S — стоянка.'));
  return node;
}

function renderAngles(chart) {
  const node = card(`Углы и дома — ${chart.houseSystemName}`);
  const table = element('table');
  const angles = [['ASC', chart.angles.asc], ['MC', chart.angles.mc],
    ['DSC', chart.angles.desc], ['IC', chart.angles.ic]];
  for (const [title, value] of angles) {
    const row = element('tr');
    row.append(element('td', 'name', title));
    row.append(element('td', 'deg', formatLongitude(value)));
    table.append(row);
  }
  node.append(table);

  const cusps = element('table');
  chart.houses.get(chart.houseSystem).cusps.forEach((cusp, index) => {
    const row = element('tr');
    row.append(element('td', 'name', `${index + 1} дом`));
    row.append(element('td', 'deg', formatLongitude(cusp)));
    cusps.append(row);
  });
  node.append(cusps);
  return node;
}

function renderAspects(chart) {
  const node = card('Аспекты');
  if (!chart.aspects.length) {
    node.append(element('p', 'note', 'В заданных орбисах аспектов нет.'));
    return node;
  }
  const table = element('table');
  for (const hit of chart.aspects) {
    const a = chart.positions.get(hit.bodyA).body;
    const b = chart.positions.get(hit.bodyB).body;
    const row = element('tr');
    row.append(element('td', 'glyph', a.glyph));
    row.append(element('td', 'name', `${a.short} ${hit.aspect.glyph} ${b.short}`));
    row.append(element('td', 'deg', `${hit.orb.toFixed(1)}°`));
    row.append(element('td', 'mark', hit.applying ? '→' : '←'));
    table.append(row);
  }
  node.append(table);
  node.append(element('p', 'note', 'Орб — отклонение от точного угла. → аспект сходится, ← расходится.'));
  return node;
}

function renderDignities(chart) {
  const node = card(`Достоинства — карта ${chart.diurnal ? 'дневная' : 'ночная'}`);
  const table = element('table');
  for (const [key, item] of chart.dignities) {
    const body = chart.positions.get(key).body;
    const own = item.peregrine
      ? 'перегрин'
      : item.own.map((code) => DIGNITY_NAMES[code]).join(', ');
    const row = element('tr');
    row.append(element('td', 'glyph', body.glyph));
    row.append(element('td', 'name', body.short));
    row.append(element('td', 'note', own));
    table.append(row);
  }
  node.append(table);
  return node;
}

function renderPatterns(chart) {
  const node = card('Фигуры');
  const list = element('table');
  for (const pattern of chart.patterns) {
    const glyphs = pattern.bodies.map((key) => chart.positions.get(key).body.glyph).join(' ');
    const row = element('tr');
    row.append(element('td', 'name', pattern.name));
    row.append(element('td', 'deg', glyphs));
    list.append(row);
  }
  for (const stellium of chart.stelliums) {
    const glyphs = stellium.bodies.map((key) => chart.positions.get(key).body.glyph).join(' ');
    const row = element('tr');
    row.append(element('td', 'name', stellium.byConjunction
      ? 'Стеллиум в соединении'
      : `Стеллиум в знаке ${SIGN_GLYPHS[stellium.sign]}`));
    row.append(element('td', 'deg', glyphs));
    list.append(row);
  }
  node.append(list);
  return node;
}

boot();
