// Каталог тел карты.

export const BODIES = [
  { key: 'sun', name: 'Солнце', short: 'Солнце', glyph: '☉', kind: 'luminary', stationary: 0 },
  { key: 'moon', name: 'Луна', short: 'Луна', glyph: '☽', kind: 'luminary', stationary: 0 },
  { key: 'mercury', name: 'Меркурий', short: 'Меркурий', glyph: '☿', kind: 'planet', stationary: 0.03 },
  { key: 'venus', name: 'Венера', short: 'Венера', glyph: '♀', kind: 'planet', stationary: 0.012 },
  { key: 'mars', name: 'Марс', short: 'Марс', glyph: '♂', kind: 'planet', stationary: 0.008 },
  { key: 'jupiter', name: 'Юпитер', short: 'Юпитер', glyph: '♃', kind: 'planet', stationary: 0.003 },
  { key: 'saturn', name: 'Сатурн', short: 'Сатурн', glyph: '♄', kind: 'planet', stationary: 0.0016 },
  { key: 'uranus', name: 'Уран', short: 'Уран', glyph: '♅', kind: 'planet', stationary: 0.0008 },
  { key: 'neptune', name: 'Нептун', short: 'Нептун', glyph: '♆', kind: 'planet', stationary: 0.0006 },
  { key: 'pluto', name: 'Плутон', short: 'Плутон', glyph: '♇', kind: 'planet', stationary: 0.0005 },
  { key: 'true_node', name: 'Восходящий Узел', short: 'Сев. Узел', glyph: '☊', kind: 'point', stationary: 0.001 },
  { key: 'south_node', name: 'Нисходящий Узел', short: 'Юж. Узел', glyph: '☋', kind: 'point', stationary: 0.001 },
  { key: 'mean_lilith', name: 'Лилит', short: 'Лилит', glyph: '⚸', kind: 'point', stationary: 0 },
  { key: 'part_of_fortune', name: 'Часть Фортуны', short: 'Фортуна', glyph: '⊗', kind: 'lot', stationary: 0 },
];

export const BY_KEY = new Map(BODIES.map((body) => [body.key, body]));

export function getBody(key) {
  const body = BY_KEY.get(key);
  if (!body) throw new Error(`неизвестное тело: ${key}`);
  return body;
}

// Тела, у которых бывают достоинства: у узлов и жребиев их не бывает.
export const DIGNIFIED_KINDS = new Set(['planet', 'luminary']);
