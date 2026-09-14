"""Часовые пояса, включая советские декретное и летнее время."""

from datetime import datetime

import pytest

from astro import timeutil


@pytest.mark.parametrize("local,lat,lon,offset,note", [
    (datetime(1925, 7, 15, 12, 0), 55.7558, 37.6173, 2.0, "до декретного времени"),
    (datetime(1931, 7, 15, 12, 0), 55.7558, 37.6173, 3.0, "декретное время"),
    (datetime(1980, 7, 15, 12, 0), 55.7558, 37.6173, 3.0, "декретное, летнего ещё нет"),
    (datetime(1981, 7, 15, 12, 0), 55.7558, 37.6173, 4.0, "декретное плюс летнее"),
    (datetime(1985, 1, 15, 12, 0), 55.7558, 37.6173, 3.0, "зима при летнем режиме"),
    (datetime(1987, 7, 14, 11, 25), 50.4501, 30.5234, 4.0, "Киев, лето 1987"),
    (datetime(1975, 5, 5, 3, 30), 41.2995, 69.2401, 6.0, "Ташкент, декретное"),
    (datetime(2012, 1, 15, 12, 0), 55.7558, 37.6173, 4.0, "постоянное время 2011-2014"),
    (datetime(2024, 7, 15, 12, 0), 55.7558, 37.6173, 3.0, "нынешнее московское"),
])
def test_soviet_and_modern_offsets(local, lat, lon, offset, note):
    moment = timeutil.resolve(local, lat, lon)
    assert moment.offset_hours == pytest.approx(offset), note


def test_zone_lookup_by_coordinates():
    assert timeutil.find_zone(55.7558, 37.6173) == "Europe/Moscow"
    assert timeutil.find_zone(43.1198, 131.8869) == "Asia/Vladivostok"


def test_ambiguous_hour_is_flagged_and_resolvable():
    """Осенний перевод стрелок: один и тот же час проходит дважды."""
    first = timeutil.resolve(datetime(2014, 10, 26, 1, 30), 55.7558, 37.6173, fold=0)
    second = timeutil.resolve(datetime(2014, 10, 26, 1, 30), 55.7558, 37.6173, fold=1)
    assert first.ambiguous and second.ambiguous
    assert first.offset_hours == pytest.approx(4.0)
    assert second.offset_hours == pytest.approx(3.0)
    assert (second.utc - first.utc).total_seconds() == pytest.approx(3600.0)


def test_imaginary_hour_is_flagged():
    """Весенний перевод стрелок: этого часа в сутках не было."""
    moment = timeutil.resolve(datetime(1981, 4, 1, 0, 30), 55.7558, 37.6173)
    assert moment.imaginary


def test_manual_offset_overrides_zone():
    moment = timeutil.resolve(
        datetime(1987, 7, 14, 11, 25), 50.45, 30.52, utc_offset_hours=4.0
    )
    assert moment.zone is None
    assert moment.utc.hour == 7 and moment.utc.minute == 25


def test_aware_datetime_rejected():
    from datetime import timezone
    with pytest.raises(ValueError):
        timeutil.resolve(
            datetime(2000, 1, 1, tzinfo=timezone.utc), 55.0, 37.0
        )
