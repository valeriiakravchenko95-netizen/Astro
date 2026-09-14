"""Эфемериды малых тел: Хирон и прочее, чего нет в ядрах DE.

Ядра DE содержат только Солнце, Луну и планеты. Для астероидов JPL
Horizons отдаёт ядра SPK типа 21, а Skyfield читает лишь чебышёвские
сегменты типов 2 и 3 — то есть кернел Хирона напрямую не открывается ни
Skyfield, ни jplephem.

Поэтому малые тела хранятся в собственном компактном формате: таблица
состояний на равномерной сетке плюс кубическая интерполяция Эрмита. Она
использует и положение, и скорость в узлах, поэтому на шаге в несколько
суток погрешность для медленных тел вроде Хирона исчезающе мала — см.
проверку в tests/test_smallbody.py, где тот же конвейер прогоняется на
Юпитере и сверяется с ядром DE.

Файлы готовит scripts/fetch_chiron.py; в рабочее время сеть не нужна.
"""

from __future__ import annotations

import os
from typing import Optional

import numpy as np
from skyfield.constants import AU_KM
from skyfield.vectorlib import VectorFunction

#: Версия формата файла — на случай, если раскладка полей изменится.
FORMAT_VERSION = 1


class SmallBodyError(ValueError):
    """Файл эфемериды малого тела испорчен или не подходит."""


class SmallBody(VectorFunction):
    """Положение малого тела из таблицы состояний.

    Совместим со Skyfield: объект можно передавать в ``observe`` наравне с
    планетой из ядра DE, и световое время с аберрацией учтутся штатно.
    """

    def __init__(self, path: str):
        self.path = path
        with np.load(path, allow_pickle=False) as data:
            version = int(data["version"])
            if version != FORMAT_VERSION:
                raise SmallBodyError(
                    f"{path}: версия формата {version}, поддерживается {FORMAT_VERSION}"
                )
            self.target = int(data["target"])
            self.center = int(data["center"])
            self.jd_start = float(data["jd_start"])
            self.step_days = float(data["step_days"])
            self._states = np.ascontiguousarray(data["states"], dtype=float)
            self.name = str(data["name"]) if "name" in data else str(self.target)

        if self._states.ndim != 2 or self._states.shape[1] != 6:
            raise SmallBodyError(f"{path}: таблица состояний должна быть N×6")
        if len(self._states) < 2:
            raise SmallBodyError(f"{path}: нужно хотя бы два узла")
        if self.step_days <= 0:
            raise SmallBodyError(f"{path}: шаг сетки должен быть положительным")

        self._positions = self._states[:, :3]
        self._velocities = self._states[:, 3:]

    @property
    def jd_end(self) -> float:
        return self.jd_start + self.step_days * (len(self._states) - 1)

    @property
    def vector_name(self) -> str:
        return f"{os.path.basename(self.path)!r} таблица состояний"

    def time_range(self, ts):
        return ts.tdb_jd(self.jd_start), ts.tdb_jd(self.jd_end)

    def _at(self, t):
        jd = np.asarray(t.whole, dtype=float) + np.asarray(t.tdb_fraction, dtype=float)
        position, velocity = self._interpolate(jd)
        return position / AU_KM, velocity / AU_KM, None, None

    def _interpolate(self, jd):
        """Кубический Эрмит по положению и скорости в узлах сетки."""
        scalar = np.ndim(jd) == 0
        jd = np.atleast_1d(jd)

        offset = (jd - self.jd_start) / self.step_days
        if np.any(offset < 0) or np.any(offset > len(self._states) - 1):
            raise SmallBodyError(
                f"{os.path.basename(self.path)}: таблица покрывает JD "
                f"{self.jd_start:.1f}–{self.jd_end:.1f}, запрошено вне этого интервала"
            )

        index = np.clip(np.floor(offset).astype(int), 0, len(self._states) - 2)
        x = (offset - index)[:, None]
        step = self.step_days

        p0 = self._positions[index]
        p1 = self._positions[index + 1]
        m0 = self._velocities[index] * step
        m1 = self._velocities[index + 1] * step

        x2 = x * x
        x3 = x2 * x
        position = (
            (2 * x3 - 3 * x2 + 1) * p0
            + (x3 - 2 * x2 + x) * m0
            + (-2 * x3 + 3 * x2) * p1
            + (x3 - x2) * m1
        )
        velocity = (
            ((6 * x2 - 6 * x) * (p0 - p1)) / step
            + (3 * x2 - 4 * x + 1) * self._velocities[index]
            + (3 * x2 - 2 * x) * self._velocities[index + 1]
        )

        position = position.T
        velocity = velocity.T
        if scalar:
            return position[:, 0], velocity[:, 0]
        return position, velocity


def save(
    path: str,
    target: int,
    center: int,
    jd_start: float,
    step_days: float,
    states: np.ndarray,
    name: Optional[str] = None,
) -> None:
    """Записывает таблицу состояний.

    ``states`` — массив N×6: положение в км и скорость в км/сутки в системе
    ICRF, относительно ``center`` (обычно барицентра Солнечной системы),
    на моменты jd_start + k·step_days в шкале TDB.
    """
    states = np.asarray(states, dtype=float)
    if states.ndim != 2 or states.shape[1] != 6:
        raise SmallBodyError("таблица состояний должна быть N×6")
    np.savez_compressed(
        path,
        version=FORMAT_VERSION,
        target=int(target),
        center=int(center),
        jd_start=float(jd_start),
        step_days=float(step_days),
        states=states,
        name=name if name is not None else str(target),
    )


def load(path: str) -> SmallBody:
    """Открывает файл малого тела."""
    if not os.path.isfile(path):
        raise SmallBodyError(f"файл эфемериды не найден: {path}")
    return SmallBody(path)
