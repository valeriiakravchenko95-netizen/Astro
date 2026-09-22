// Зодиак: знаки, приведение углов, запись градусов.

export const SIGNS = [
  'Овен', 'Телец', 'Близнецы', 'Рак', 'Лев', 'Дева',
  'Весы', 'Скорпион', 'Стрелец', 'Козерог', 'Водолей', 'Рыбы',
];

// Предложный падеж: «Солнце в Тельце», «Асцендент в Весах».
export const SIGNS_IN = [
  'Овне', 'Тельце', 'Близнецах', 'Раке', 'Льве', 'Деве',
  'Весах', 'Скорпионе', 'Стрельце', 'Козероге', 'Водолее', 'Рыбах',
];

export const SIGNS_GENITIVE = [
  'Овна', 'Тельца', 'Близнецов', 'Рака', 'Льва', 'Девы',
  'Весов', 'Скорпиона', 'Стрельца', 'Козерога', 'Водолея', 'Рыб',
];

export const SIGN_GLYPHS = ['♈', '♉', '♊', '♋', '♌', '♍', '♎', '♏', '♐', '♑', '♒', '♓'];

export const ELEMENTS = ['Огонь', 'Земля', 'Воздух', 'Вода'];
export const MODALITIES = ['Кардинальный', 'Фиксированный', 'Мутабельный'];

export const DEGREES = Math.PI / 180;

export function norm360(x) {
  const value = x % 360;
  return value < 0 ? value + 360 : value;
}

export function norm180(x) {
  const value = (x + 180) % 360;
  return value <= 0 ? value + 180 : value - 180;
}

export function separation(a, b) {
  return Math.abs(norm180(a - b));
}

export function signIndex(longitude) {
  return Math.floor(norm360(longitude) / 30);
}

// Разбор долготы на знак, градусы, минуты и секунды. Округление ведётся
// до целых секунд с переносом разрядов, чтобы 59'59.6" не превращалось в
// 59'60", а уезжало в следующий знак.
export function toSign(longitude) {
  const value = norm360(longitude);
  let index = Math.floor(value / 30);
  let total = Math.round((value - index * 30) * 3600);
  if (total >= 30 * 3600) {
    total = 0;
    index = (index + 1) % 12;
  }
  const degree = Math.floor(total / 3600);
  const minute = Math.floor((total % 3600) / 60);
  const second = total % 60;
  return {
    index, degree, minute, second,
    longitude: value,
    sign: SIGNS[index],
    signGenitive: SIGNS_GENITIVE[index],
    glyph: SIGN_GLYPHS[index],
    element: ELEMENTS[index % 4],
    modality: MODALITIES[index % 3],
    degreeInSign: value % 30,
  };
}

const pad = (n) => String(n).padStart(2, '0');

export function formatLongitude(longitude) {
  const p = toSign(longitude);
  return `${pad(p.degree)}°${pad(p.minute)}'${pad(p.second)}" ${p.sign}`;
}

export function formatShort(longitude) {
  const p = toSign(longitude);
  return `${pad(p.degree)}°${pad(p.minute)}' ${p.glyph}`;
}

export function formatSignedArc(value) {
  const sign = value < 0 ? '−' : '+';
  const total = Math.round(Math.abs(value) * 3600);
  return `${sign}${Math.floor(total / 3600)}°${pad(Math.floor((total % 3600) / 60))}'`;
}

// Антис — отражение относительно оси солнцестояний, через 0° Рака и
// 0° Козерога: градусы с одинаковой длиной дня.
export function antiscion(longitude) {
  return norm360(180 - longitude);
}

export function contraAntiscion(longitude) {
  return norm360(360 - longitude);
}
