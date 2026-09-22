// Жребии: секта карты и Часть Фортуны.

import { norm360 } from './zodiac.js';

// Дневная ли карта — стоит ли Солнце над горизонтом. Горизонт делит
// зодиак линией ASC–DSC: дуга от Десцендента до Асцендента — верхняя.
export function isDiurnal(sunLongitude, ascendant) {
  return norm360(sunLongitude - norm360(ascendant + 180)) < 180;
}

// Днём дуга отмеряется от Солнца к Луне, ночью наоборот; в обоих случаях
// та же дуга откладывается от Асцендента. Без этой перемены у ночных карт
// жребий выходит зеркальным.
export function partOfFortune(ascendant, sunLongitude, moonLongitude, diurnal) {
  return diurnal
    ? norm360(ascendant + moonLongitude - sunLongitude)
    : norm360(ascendant + sunLongitude - moonLongitude);
}
