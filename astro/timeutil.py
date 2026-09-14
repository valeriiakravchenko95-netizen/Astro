"""Перевод гражданского времени рождения в шкалу эфемерид.

Часовой пояс определяется по координатам через timezonefinder, а сам
сдвиг берётся из базы IANA. Это важно для советских дат: декретное время
1930 года, летнее время 1981–1991, отмена декретного в 1991-м и возврат в
1992-м, постоянное «летнее» время 2011–2014 — всё это в базе есть, и
пересчёт получается правильным без отдельных таблиц.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .ephemeris import _timescale


class TimeZoneError(ValueError):
    """Часовой пояс не определён или время в нём невозможно."""


@dataclass(frozen=True)
class Moment:
    """Момент рождения во всех нужных представлениях."""

    t: object                 # skyfield.timelib.Time
    utc: datetime
    local: datetime
    zone: Optional[str]
    offset_hours: float
    ambiguous: bool = False   # час повторяется при переходе на зимнее время
    imaginary: bool = False   # часа не существует: перевод стрелок вперёд

    @property
    def julian_day(self) -> float:
        return self.t.tt

    def describe(self) -> str:
        offset = f"UTC{self.offset_hours:+.2f}".rstrip("0").rstrip(".")
        zone = self.zone or "смещение задано вручную"
        note = ""
        if self.imaginary:
            note = "  [время попало в переведённый вперёд час]"
        elif self.ambiguous:
            note = "  [час повторяется при переводе стрелок]"
        return (
            f"{self.local:%Y-%m-%d %H:%M:%S} {offset} ({zone})  =  "
            f"{self.utc:%Y-%m-%d %H:%M:%S} UTC{note}"
        )


def find_zone(latitude: float, longitude: float) -> str:
    """Определяет имя зоны IANA по координатам."""
    try:
        from timezonefinder import TimezoneFinder
    except ImportError as exc:  # pragma: no cover
        raise TimeZoneError(
            "не установлен timezonefinder; задайте зону или смещение вручную"
        ) from exc

    zone = _finder(TimezoneFinder).timezone_at(lat=latitude, lng=longitude)
    if zone is None:
        raise TimeZoneError(
            f"не удалось определить часовой пояс для {latitude:.4f}, {longitude:.4f}"
        )
    return zone


_finder_cache = {}


def _finder(cls):
    if "instance" not in _finder_cache:
        _finder_cache["instance"] = cls()
    return _finder_cache["instance"]


def resolve(
    local_time: datetime,
    latitude: float,
    longitude: float,
    zone: Optional[str] = None,
    utc_offset_hours: Optional[float] = None,
    fold: int = 0,
) -> Moment:
    """Переводит местное гражданское время в UTC и в шкалу Skyfield.

    ``utc_offset_hours`` задаёт смещение напрямую и отменяет поиск зоны —
    это нужно, когда в документах записано время с известным сдвигом или
    когда место рождения приходится на спорную границу зон.

    ``fold`` разрешает неоднозначность осеннего перевода стрелок, когда
    один и тот же час проходит дважды: 0 — первый проход, ещё по летнему
    времени (так по умолчанию), 1 — второй, уже по зимнему.
    """
    if local_time.tzinfo is not None:
        raise ValueError("местное время должно быть без часового пояса")

    if utc_offset_hours is not None:
        utc = local_time - timedelta(hours=utc_offset_hours)
        utc = utc.replace(tzinfo=timezone.utc)
        return Moment(
            t=_to_skyfield(utc),
            utc=utc,
            local=local_time,
            zone=None,
            offset_hours=utc_offset_hours,
        )

    zone_name = zone if zone is not None else find_zone(latitude, longitude)
    try:
        tz = ZoneInfo(zone_name)
    except ZoneInfoNotFoundError as exc:
        raise TimeZoneError(f"неизвестная зона IANA: {zone_name!r}") from exc

    if fold not in (0, 1):
        raise ValueError("fold должен быть 0 или 1")

    aware = local_time.replace(tzinfo=tz, fold=fold)
    other = local_time.replace(tzinfo=tz, fold=1 - fold)
    offset = aware.utcoffset()
    ambiguous = offset != other.utcoffset()

    utc = aware.astimezone(timezone.utc)
    # Несуществующее время: обратный перевод не совпадает с исходным.
    imaginary = utc.astimezone(tz).replace(tzinfo=None) != local_time

    return Moment(
        t=_to_skyfield(utc),
        utc=utc,
        local=local_time,
        zone=zone_name,
        offset_hours=offset.total_seconds() / 3600.0,
        ambiguous=ambiguous and not imaginary,
        imaginary=imaginary,
    )


def from_utc(utc_time: datetime) -> Moment:
    """Момент, заданный сразу в UTC."""
    if utc_time.tzinfo is None:
        utc_time = utc_time.replace(tzinfo=timezone.utc)
    else:
        utc_time = utc_time.astimezone(timezone.utc)
    return Moment(
        t=_to_skyfield(utc_time),
        utc=utc_time,
        local=utc_time.replace(tzinfo=None),
        zone="UTC",
        offset_hours=0.0,
    )


def _to_skyfield(utc: datetime):
    """datetime в UTC → объект времени Skyfield."""
    ts = _timescale()
    seconds = utc.second + utc.microsecond / 1e6
    return ts.utc(utc.year, utc.month, utc.day, utc.hour, utc.minute, seconds)
