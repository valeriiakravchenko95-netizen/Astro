// Поиск места рождения по списку городов.

let data = null;

export async function loadCities(url = 'data/cities.json') {
  if (data) return data;
  const response = await fetch(url);
  if (!response.ok) throw new Error(`не удалось загрузить список городов: ${response.status}`);
  const payload = await response.json();

  const index = payload.cities.map((row) => {
    const names = [row[0], ...(row[1] || [])];
    return {
      name: row[0],
      names,
      country: row[2],
      latitude: row[3],
      longitude: row[4],
      population: row[5] * 1000,
      zone: payload.zones[row[6]],
      // Ключи готовятся заранее: приводить тридцать тысяч названий при
      // каждом нажатии клавиши заметно медленнее.
      keys: names.map(normalize),
    };
  });

  data = { index, countries: payload.countries };
  return data;
}

// Регистр, дефисы и диакритика в написании гуляют, поэтому снимаются:
// «Санкт-Петербург», «санкт петербург» и «Sankt-Peterburg» должны
// находить одно и то же.
export function normalize(text) {
  let value = text.trim().toLowerCase().normalize('NFKD');
  value = value.replace(/[̀-ͯ]/g, '');
  value = value.replace(/[-'’`.,]/g, ' ');
  return value.split(/\s+/).filter(Boolean).join(' ');
}

export function search(query, limit = 7) {
  if (!data) return [];
  const key = normalize(query);
  if (key.length < 2) return [];

  const exact = [];
  const prefix = [];
  for (const city of data.index) {
    const hit = city.keys.findIndex((k) => k === key);
    if (hit >= 0) {
      // Показывается то написание, по которому нашлось: человек ввёл
      // «Донецк» — он и увидит «Донецк», а не сербский вариант.
      exact.push({ ...city, matched: city.names[hit] });
      continue;
    }
    const partial = city.keys.findIndex((k) => k.startsWith(key));
    if (partial >= 0) prefix.push({ ...city, matched: city.names[partial] });
    if (exact.length >= limit && prefix.length >= limit) break;
  }
  // Список отсортирован по убыванию населения, поэтому первым идёт тот
  // город, который скорее всего и имели в виду.
  return [...exact, ...prefix].slice(0, limit);
}

export function countryName(code) {
  return data?.countries?.[code] || code;
}

export function label(city) {
  const name = city.matched || city.name;
  const where = countryName(city.country);
  return { name, where: city.population ? `${where}, ${Math.round(city.population / 1000)} тыс.` : where };
}
