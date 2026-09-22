// Чтение таблиц эфемерид и восстановление положений.
//
// Таблица — выжимка из ядра JPL: видимая эклиптическая долгота и её
// скорость на равномерной сетке. Между узлами работает кубическая
// интерполяция Эрмита: она опирается и на значение, и на производную,
// поэтому даёт точность в доли угловой секунды при разумном шаге.

const MAGIC = 'ASTREPH1';

export class Ephemeris {
  constructor(buffer) {
    const bytes = new Uint8Array(buffer);
    const signature = String.fromCharCode(...bytes.subarray(0, 8));
    if (signature !== MAGIC) {
      throw new Error('файл эфемерид не распознан');
    }
    const headerLength = new DataView(buffer).getUint32(8, true);
    const header = JSON.parse(new TextDecoder().decode(bytes.subarray(12, 12 + headerLength)));
    const base = 12 + headerLength;

    this.jdStart = header.jd_start;
    this.jdEnd = header.jd_end;
    this.micro = header.micro;
    this.tables = new Map();

    for (const entry of header.bodies) {
      const start = base + entry.offset;
      this.tables.set(entry.key, {
        step: entry.step,
        count: entry.count,
        // Долгота лежит целыми в микроградусах, скорость — плавающей.
        longitude: new Int32Array(buffer.slice(start, start + 4 * entry.count)),
        rate: new Float32Array(buffer.slice(start + 4 * entry.count, start + 8 * entry.count)),
      });
    }
  }

  static async load(url) {
    const response = await fetch(url);
    if (!response.ok) {
      throw new Error(`не удалось загрузить эфемериды: ${response.status}`);
    }
    return new Ephemeris(await response.arrayBuffer());
  }

  has(key) {
    return this.tables.has(key);
  }

  get keys() {
    return [...this.tables.keys()];
  }

  covers(jdTt) {
    return jdTt >= this.jdStart && jdTt <= this.jdEnd;
  }

  // Долгота и суточная скорость тела на момент jdTt.
  position(key, jdTt) {
    const table = this.tables.get(key);
    if (!table) throw new Error(`нет данных для тела: ${key}`);
    if (!this.covers(jdTt)) {
      throw new RangeError('дата вне интервала, покрытого таблицами');
    }

    const position = (jdTt - this.jdStart) / table.step;
    let index = Math.floor(position);
    if (index < 0) index = 0;
    if (index > table.count - 2) index = table.count - 2;
    const u = position - index;

    const left = table.longitude[index] / this.micro;
    const right = table.longitude[index + 1] / this.micro;
    // Приращение берётся кратчайшим путём: в таблице долгота лежит
    // приведённой к кругу, и на переходе через ноль разность без этого
    // подскочила бы на триста шестьдесят градусов.
    let delta = (right - left + 180) % 360;
    if (delta < 0) delta += 360;
    delta -= 180;

    const slopeLeft = table.rate[index] * table.step;
    const slopeRight = table.rate[index + 1] * table.step;

    const u2 = u * u;
    const u3 = u2 * u;
    const longitude = left
      + (-2 * u3 + 3 * u2) * delta
      + (u3 - 2 * u2 + u) * slopeLeft
      + (u3 - u2) * slopeRight;

    // Производная того же многочлена — суточная скорость. Слагаемое при
    // приращении входит со знаком плюс: производные базисных множителей
    // при концах отрезка противоположны, и p0 с p1 дают (6u − 6u²)·Δ.
    const speed = ((6 * u - 6 * u2) * delta
      + (3 * u2 - 4 * u + 1) * slopeLeft
      + (3 * u2 - 2 * u) * slopeRight) / table.step;

    return {
      longitude: ((longitude % 360) + 360) % 360,
      speed,
      retrograde: speed < 0,
    };
  }

  positions(keys, jdTt) {
    const result = new Map();
    for (const key of keys) {
      if (this.has(key)) result.set(key, this.position(key, jdTt));
    }
    return result;
  }
}
