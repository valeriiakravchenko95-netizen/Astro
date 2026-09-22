// Часовые пояса.
//
// База часовых поясов уже есть в браузере, вместе со всей историей: и
// декретное время 1930 года, и советское летнее 1981-1991, и постоянное
// время 2011-2014. Отдельных таблиц не нужно, нужен лишь обратный
// переход — от местного времени к мировому, которого в Intl нет напрямую.

// Смещение зоны в минутах на заданный момент.
export function offsetAt(timestamp, timeZone) {
  const formatter = new Intl.DateTimeFormat('en-US', {
    timeZone,
    hour12: false,
    year: 'numeric', month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit', second: '2-digit',
  });
  const parts = {};
  for (const part of formatter.formatToParts(new Date(timestamp))) {
    if (part.type !== 'literal') parts[part.type] = Number(part.value);
  }
  const asUtc = Date.UTC(
    parts.year, parts.month - 1, parts.day,
    parts.hour % 24, parts.minute, parts.second,
  );
  return (asUtc - timestamp) / 60000;
}

// Местное гражданское время в зоне → момент в мировом времени.
//
// Смещение зависит от самого момента, поэтому решается итерацией: сперва
// местное время принимается за мировое, затем дважды уточняется. Двух
// проходов хватает всегда, включая переводы стрелок.
export function zonedTimeToUtc(fields, timeZone) {
  const naive = Date.UTC(
    fields.year, fields.month - 1, fields.day,
    fields.hour, fields.minute, fields.second || 0,
  );
  let timestamp = naive;
  for (let i = 0; i < 3; i += 1) {
    timestamp = naive - offsetAt(timestamp, timeZone) * 60000;
  }

  const offset = offsetAt(timestamp, timeZone);
  // Осенью один и тот же час проходит дважды: берём первый, ещё летний.
  const earlier = naive - offsetAt(naive - 12 * 3600000, timeZone) * 60000;
  const ambiguous = earlier !== timestamp
    && offsetAt(earlier, timeZone) * 60000 === naive - earlier;

  // Весной часа не существует вовсе: обратный перевод не совпадает.
  const back = new Date(timestamp);
  const roundTrip = offsetAt(timestamp, timeZone);
  const imaginary = Math.abs((naive - timestamp) / 60000 - roundTrip) > 1e-6;

  return {
    timestamp: ambiguous ? earlier : timestamp,
    offsetMinutes: ambiguous ? offsetAt(earlier, timeZone) : offset,
    ambiguous,
    imaginary,
    date: back,
  };
}

export function formatOffset(minutes) {
  const sign = minutes < 0 ? '−' : '+';
  const absolute = Math.abs(minutes);
  const hours = Math.floor(absolute / 60);
  const rest = absolute % 60;
  return rest ? `UTC${sign}${hours}:${String(rest).padStart(2, '0')}` : `UTC${sign}${hours}`;
}
