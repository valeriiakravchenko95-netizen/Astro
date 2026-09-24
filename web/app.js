// Страница расчета: форма, поиск места, вывод карты.

import { Ephemeris } from './astro/ephemeris.js';
import { computeChart } from './astro/chart.js';
import { MODERN } from './astro/rulers.js';
import { PLACIDUS, WHOLE_SIGN } from './astro/houses.js';
import { formatLongitude, SIGN_GLYPHS } from './astro/zodiac.js';
import { formatOffset } from './astro/timezone.js';
import { label, loadCities, search } from './places.js';
import {
  renderReadings, loadInterpretations, neededTexts, addTexts, setOpenCards,
} from './readings.js';
import {
  renderTransits, renderUpcoming, loadTransitTexts, neededSkyTexts, addSkyTexts,
} from './transit-view.js';
import { renderWheel } from './wheel.js';
import {
  loadSite, renderAuthor, renderOffer, siteSettings, instagramNick,
} from './site.js';
import { loadEvents } from './astro/transits.js';
import { setGender } from './text.js';
import {
  loadChecks, askedCheck, neededCheckTexts, addCheckTexts, renderCheck,
} from './checks.js';

const form = document.getElementById('form');
const dateInput = document.getElementById('date');
const timeInput = document.getElementById('time');
const unknownTime = document.getElementById('unknown-time');
const placeInput = document.getElementById('place');
const suggestBox = document.getElementById('suggest');
const submit = document.getElementById('submit');
const status = document.getElementById('status');
const result = document.getElementById('result');
const genderInputs = document.querySelectorAll('input[name="gender"]');

let ephemeris = null;
let chosenPlace = null;
// Опубликованная страница берет тексты у сервера по одному запросу на карту.
// При работе с исходниками тексты уже загружены целиком из content/.
let published = false;

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
      loadEvents(),
      loadTransitTexts(),
      loadSite().then(() => {
        renderAuthor(document.querySelector('header'));
        setOpenCards(siteSettings().showcase_open);
      }),
      fetch('content/public.json').then((response) => { published = response.ok; }, () => {}),
      loadChecks(),
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

// Тексты для этой карты: только те, что она покажет. Весь набор целиком
// на страницу не попадает.
async function fetchTexts(chart, exactTime) {
  if (!published) return;
  const response = await fetch('api/texts', {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({
      natal: neededTexts(chart, exactTime),
      sky: neededSkyTexts(chart, exactTime),
      checks: neededCheckTexts(askedCheck()),
    }),
  });
  if (!response.ok) throw new Error('Не удалось загрузить тексты, попробуй еще раз');
  const payload = await response.json();
  addTexts(payload.natal);
  addSkyTexts(payload.sky);
  addCheckTexts(payload.checks?.checks);
}

form.addEventListener('submit', async (event) => {
  event.preventDefault();
  if (!ephemeris) return;

  if (!dateInput.value) {
    setStatus('Укажи дату рождения', true);
    return;
  }
  if (!chosenPlace) {
    setStatus('Выбери место из списка', true);
    return;
  }

  const [year, month, day] = dateInput.value.split('-').map(Number);
  const exactTime = !unknownTime.checked && Boolean(timeInput.value);
  const [hour, minute] = exactTime ? timeInput.value.split(':').map(Number) : [12, 0];
  setGender([...genderInputs].find((input) => input.checked)?.value);

  try {
    const chart = computeChart(ephemeris, {
      year, month, day, hour, minute,
      latitude: chosenPlace.latitude,
      longitude: chosenPlace.longitude,
      timeZone: chosenPlace.zone,
      exactTime,
      houseSystem: PLACIDUS,
      // Управители домов и цепочки - по современной схеме, как в методе
      // автора трактовок: Скорпион - Плутон, Водолей - Уран, Рыбы - Нептун.
      rulerScheme: MODERN,
    });
    submit.disabled = true;
    setStatus('Считаю...');
    await fetchTexts(chart, exactTime);
    setStatus('');
    render(chart, exactTime);
    result.scrollIntoView({ behavior: 'smooth', block: 'start' });
  } catch (error) {
    setStatus(error.message, true);
  } finally {
    submit.disabled = false;
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

  // Короткий режим под рилс: ссылка ?check=... показывает только эту
  // проверку и приглашение, а полная карта раскрывается кнопкой.
  const check = askedCheck();
  let target = result;
  if (check) {
    result.append(renderCheck(chart, check, { dmUrl: siteSettings().dm_url, nick: instagramNick() }));
    const offer = check.code_word ? null : renderOffer('readings');
    if (offer) result.append(offer);
    const more = element('button', 'more', 'Показать всю мою карту');
    more.type = 'button';
    target = element('div');
    target.hidden = true;
    more.addEventListener('click', () => {
      target.hidden = false;
      more.remove();
      target.scrollIntoView({ behavior: 'smooth', block: 'start' });
    });
    result.append(more, target);
  }

  const { name } = label(chosenPlace);
  const local = chart.moment;
  const head = card();
  head.append(element('h2', null, 'Твоя карта'));
  head.append(element('p', 'note',
    `${name} · ${dateInput.value.split('-').reverse().join('.')}`
    + (exactTime ? ` ${timeInput.value}` : '')
    + ` · ${formatOffset(local.offsetMinutes)}`));

  if (!exactTime) {
    head.append(element('div', 'warn',
      'Время рождения неизвестно, карта посчитана на полдень. Положения по '
      + 'знакам верны, но Луна за сутки проходит до 15°, а дома и Асцендент '
      + 'зависят от минут - их здесь нет.'));
  } else if (local.imaginary) {
    head.append(element('div', 'warn',
      'В этот день стрелки переводили вперед, и указанного часа не '
      + 'существовало. Проверь время.'));
  } else if (local.ambiguous) {
    head.append(element('div', 'warn',
      'В этот день стрелки переводили назад, и такой час прошел дважды. '
      + 'Взят первый.'));
  }
  head.append(renderWheel(chart, { exactTime }));
  target.append(head);

  // Сначала то, ради чего человек пришел: разбор по теме. Небо и цифры ниже.
  const readings = renderReadings(chart, { exactTime });
  if (readings) target.append(readings);
  const readingsOffer = check ? null : renderOffer('readings');
  if (readingsOffer) target.append(readingsOffer);

  const transits = renderTransits(chart, { exactTime });
  if (transits) {
    target.append(renderUpcoming(chart, {
      exactTime,
      onPick: (event) => {
        transits.showEvent(event);
        transits.scrollIntoView({ behavior: 'smooth', block: 'start' });
      },
    }));
    target.append(transits);
  }
  const skyOffer = renderOffer('sky');
  if (skyOffer) target.append(skyOffer);

  // Градусы, дома и аспекты нужны тем, кто хочет проверить; остальным они
  // только мешают дойти до текста, поэтому свернуты.
  const tech = element('details', 'card tech');
  tech.append(element('summary', null, 'Технические данные: градусы, дома, аспекты'));
  tech.append(renderPositions(chart, exactTime));
  if (exactTime) tech.append(renderAngles(chart));
  tech.append(renderAspects(chart));
  if (chart.patterns.length || chart.stelliums.length) tech.append(renderPatterns(chart));
  target.append(tech);

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
  if (exactTime) node.append(element('p', 'note', 'Последний столбец - дом. R - попятное движение, S - стоянка.'));
  return node;
}

function renderAngles(chart) {
  const node = card(`Углы и дома - ${chart.houseSystemName}`);
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
  node.append(element('p', 'note', 'Орб - отклонение от точного угла. → аспект сходится, ← расходится.'));
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
