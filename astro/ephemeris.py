"""Загрузка ядра эфемерид JPL и видимые геоцентрические позиции.

Всё считается офлайн: ядро .bsp читается с диска, шкала времени и модель
нутации встроены в Skyfield. Обращений в сеть модуль не делает.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from typing import Optional, Sequence

from skyfield.api import load_file
from skyfield.framelib import ecliptic_frame
from skyfield.timelib import Timescale

from .bodies import Body
from .zodiac import norm360

#: Имена ядер в порядке предпочтения. DE440 — актуальная эфемерида JPL;
#: de440s покрывает 1849–2150 при 32 МБ, полный de440 — 1550–2650 при 114 МБ.
#: DE421 оставлен фолбэком для разработки: на интервале 1900–2100 он
#: расходится с DE440 на единицы миллисекунд дуги, что для астрологии
#: неразличимо.
KERNEL_NAMES = ("de440s.bsp", "de440.bsp", "de441.bsp", "de430.bsp", "de421.bsp")

#: Переменная окружения с явным путём к ядру.
ENV_VAR = "ASTRO_EPHEMERIS"


class EphemerisNotFound(FileNotFoundError):
    """Ядро эфемерид не найдено."""


def _candidate_dirs() -> list[str]:
    here = os.path.dirname(os.path.abspath(__file__))
    root = os.path.dirname(here)
    return [
        os.path.join(root, "ephemeris"),
        os.path.join(root, "data"),
        root,
        os.getcwd(),
    ]


def find_kernel(path: Optional[str] = None) -> str:
    """Ищет файл ядра: явный путь → $ASTRO_EPHEMERIS → ./ephemeris → пакет skyfield_data."""
    for explicit in (path, os.environ.get(ENV_VAR)):
        if explicit:
            if os.path.isfile(explicit):
                return explicit
            raise EphemerisNotFound(f"ядро эфемерид не найдено: {explicit}")

    for directory in _candidate_dirs():
        for name in KERNEL_NAMES:
            candidate = os.path.join(directory, name)
            if os.path.isfile(candidate):
                return candidate

    try:  # последний фолбэк — de421.bsp из пакета skyfield-data
        import skyfield_data

        candidate = os.path.join(
            os.path.dirname(skyfield_data.__file__), "data", "de421.bsp"
        )
        if os.path.isfile(candidate):
            return candidate
    except ImportError:
        pass

    raise EphemerisNotFound(
        "Не найдено ядро эфемерид JPL. Положите de440s.bsp в каталог "
        "ephemeris/ (см. scripts/fetch_ephemeris.sh) или задайте "
        f"{ENV_VAR}=/путь/к/de440s.bsp"
    )


@dataclass(frozen=True)
class RawPosition:
    """Сырые координаты тела до разбора на знаки.

    longitude / latitude — видимые геоцентрические эклиптические координаты
    в истинной эклиптике и равноденствии даты (тропический зодиак), градусы.
    distance — в астрономических единицах.
    speed — скорость по долготе, градусов в сутки; отрицательная означает
    попятное движение.
    """

    longitude: float
    latitude: float
    distance: float
    speed: float

    @property
    def retrograde(self) -> bool:
        return self.speed < 0.0


class Ephemeris:
    """Обёртка над ядром JPL: видимые геоцентрические положения тел."""

    #: Шаг численного дифференцирования долготы, суток (1 час).
    SPEED_STEP = 1.0 / 24.0

    def __init__(self, path: Optional[str] = None, timescale: Optional[Timescale] = None):
        self.path = find_kernel(path)
        self.kernel = load_file(self.path)
        self.ts = timescale if timescale is not None else _timescale()
        self._earth = self.kernel[399]
        self._cache: dict[str, object] = {}
        self._small_bodies = _find_small_bodies()

    @property
    def name(self) -> str:
        return os.path.basename(self.path)

    def close(self) -> None:
        self.kernel.close()

    def has(self, body: Body) -> bool:
        """Есть ли данные для тела — в ядре DE или в файле малого тела.

        ValueError ловится ради SmallBodyError: испорченный или неподходящий
        файл малого тела должен означать «тела нет», а не падение карты.
        """
        try:
            self.target(body)
        except (KeyError, OSError, ValueError):
            return False
        return True

    def target(self, body: Body):
        """Возвращает объект Skyfield для тела, выбирая доступный код NAIF.

        Малые тела в ядрах DE отсутствуют и читаются из отдельных файлов
        таблиц состояний, лежащих рядом с ядром.
        """
        cached = self._cache.get(body.key)
        if cached is not None:
            return cached

        if body.kind == "asteroid":
            path = self._small_bodies.get(body.key)
            if path is None:
                raise KeyError(
                    f"нет файла эфемериды для тела {body.name}: положите "
                    f"{body.key}.npz в каталог ephemeris/ "
                    f"(см. scripts/fetch_chiron.py)"
                )
            from .smallbody import load as load_small_body

            target = load_small_body(path)
            self._cache[body.key] = target
            return target

        for code in body.targets:
            if code in self.kernel.codes:
                target = self.kernel[code]
                self._cache[body.key] = target
                return target
        raise KeyError(
            f"в ядре {self.name} нет тела {body.name} "
            f"(искали коды NAIF {list(body.targets)})"
        )

    def ecliptic(self, body: Body, t) -> tuple:
        """Видимые эклиптические долгота, широта и расстояние на момент t.

        Наблюдатель — центр Земли. ``apparent()`` учитывает время движения
        света и годичную аберрацию; ``ecliptic_frame`` — истинная эклиптика
        и равноденствие даты, то есть нутация уже включена. Это ровно та
        система, в которой работают астрологические эфемериды.
        """
        astrometric = self._earth.at(t).observe(self.target(body))
        lat, lon, distance = astrometric.apparent().frame_latlon(ecliptic_frame)
        # Skyfield считает в numpy; наружу отдаём обычные float, иначе
        # numpy-типы просачиваются до JSON и ломают сериализацию.
        return float(norm360(lon.degrees)), float(lat.degrees), float(distance.au)

    def position(self, body: Body, t) -> RawPosition:
        """Полное положение тела вместе со скоростью по долготе."""
        lon, lat, dist = self.ecliptic(body, t)
        speed = self.longitude_speed(body, t)
        return RawPosition(lon, lat, dist, speed)

    def longitude_speed(self, body: Body, t) -> float:
        """Скорость по долготе, градусов в сутки (центральная разность).

        Скорость считается численно, а не из вектора состояния: нужна
        производная именно видимой долготы в эклиптике даты, в которую
        входят аберрация, световое время и вращение самой системы
        координат. Центральная разность с шагом в час даёт для всех тел
        точность лучше 1e-6 град/сут.
        """
        h = self.SPEED_STEP
        tt = t.tt
        t_minus = self.ts.tt_jd(tt - h)
        t_plus = self.ts.tt_jd(tt + h)
        lon_minus, _, _ = self.ecliptic(body, t_minus)
        lon_plus, _, _ = self.ecliptic(body, t_plus)
        delta = (lon_plus - lon_minus + 180.0) % 360.0 - 180.0
        return float(delta / (2.0 * h))

    def moon_state(self, t):
        """Геоцентрический вектор состояния Луны в эклиптике даты.

        Возвращает (положение в км, скорость в км/с). Нужен для истинного
        (оскулирующего) лунного узла: он определяется мгновенной плоскостью
        орбиты Луны, а не видимым направлением на неё, поэтому здесь берётся
        геометрическое положение без аберрации и светового времени.
        """
        from .bodies import MOON

        relative = (self.target(MOON) - self._earth).at(t)
        position, velocity = relative.frame_xyz_and_velocity(ecliptic_frame)
        return position.km, velocity.km_per_s

    def positions(self, bodies: Sequence[Body], t) -> dict:
        """Положения нескольких тел одним вызовом."""
        return {b.key: self.position(b, t) for b in bodies}


def _find_small_bodies() -> dict:
    """Ищет файлы малых тел рядом с ядром: ephemeris/<ключ>.npz."""
    found = {}
    for directory in _candidate_dirs():
        if not os.path.isdir(directory):
            continue
        for name in os.listdir(directory):
            if name.endswith(".npz"):
                found.setdefault(name[:-4], os.path.join(directory, name))
    return found


@lru_cache(maxsize=1)
def _timescale() -> Timescale:
    """Шкала времени Skyfield со встроенными данными (без сети)."""
    from skyfield.api import load

    return load.timescale()


@lru_cache(maxsize=4)
def load_ephemeris(path: Optional[str] = None) -> Ephemeris:
    """Кэширующая загрузка ядра — файл читается один раз на процесс."""
    return Ephemeris(path)
