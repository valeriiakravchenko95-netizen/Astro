"""Командная строка: расчёт карты в человекочитаемом виде или в JSON."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from typing import Optional, Sequence

from . import aspects as aspects_mod
from . import houses as houses_mod
from . import rulers as rulers_mod
from .chart import Chart, Place, compute
from .ephemeris import EphemerisNotFound, load_ephemeris
from .zodiac import format_longitude, format_signed_arc


def _parse_moment(value: str) -> datetime:
    for pattern in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M"):
        try:
            return datetime.strptime(value, pattern)
        except ValueError:
            continue
    raise argparse.ArgumentTypeError(
        f"не разобрать дату и время: {value!r} (ожидается 'ГГГГ-ММ-ДД ЧЧ:ММ')"
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="astro",
        description="Расчёт натальной карты: позиции, дома, аспекты, диспозиторы.",
    )
    parser.add_argument("moment", type=_parse_moment, help="местное время рождения, 'ГГГГ-ММ-ДД ЧЧ:ММ'")
    parser.add_argument("latitude", type=float, help="широта, градусы (север положительный)")
    parser.add_argument("longitude", type=float, help="долгота, градусы (восток положительный)")
    parser.add_argument("--place", help="название места, только для подписи")
    parser.add_argument("--zone", help="зона IANA вместо определения по координатам")
    parser.add_argument("--utc-offset", type=float, help="смещение от UTC в часах вместо зоны")
    parser.add_argument("--fold", type=int, choices=(0, 1), default=0,
                        help="какой из двух одинаковых часов брать при осеннем переводе стрелок")
    parser.add_argument("--houses", default="placidus",
                        choices=(houses_mod.PLACIDUS, houses_mod.WHOLE_SIGN, houses_mod.PORPHYRY),
                        help="основная система домов (по умолчанию Плацидус)")
    parser.add_argument("--house-fallback",
                        choices=(houses_mod.WHOLE_SIGN, houses_mod.PORPHYRY),
                        help="система на замену там, где основная не определена")
    parser.add_argument("--rulers", default=rulers_mod.TRADITIONAL,
                        choices=(rulers_mod.TRADITIONAL, rulers_mod.MODERN),
                        help="схема управителей")
    parser.add_argument("--minor", action="store_true", help="считать и минорные аспекты")
    parser.add_argument("--orb", action="append", metavar="АСПЕКТ=ГРАДУСЫ", default=[],
                        help="переопределить орбис, например --orb square=6")
    parser.add_argument("--ephemeris", help="путь к ядру .bsp")
    parser.add_argument("--json", action="store_true", help="выдать JSON вместо таблицы")
    parser.add_argument("--with-birth-data", action="store_true",
                        help="включить в JSON дату и место рождения (по умолчанию их там нет)")
    return parser


def _orb_policy(overrides: Sequence[str]) -> aspects_mod.OrbPolicy:
    policy = aspects_mod.DEFAULT_ORBS
    values = {}
    for item in overrides:
        if "=" not in item:
            raise SystemExit(f"неверный формат орбиса: {item!r}, нужно аспект=градусы")
        key, _, raw = item.partition("=")
        try:
            values[key.strip()] = float(raw)
        except ValueError:
            raise SystemExit(f"не число в орбисе: {item!r}") from None
    return policy.with_orbs(**values) if values else policy


#: Подписи углов в выдаче аспектов.
ANGLE_LABELS = {"asc": "ASC", "mc": "MC"}


def render(chart: Chart) -> str:
    """Текстовая таблица карты."""
    names = {key: p.body.name for key, p in chart.positions.items()}
    names.update(ANGLE_LABELS)

    def label(key: str) -> str:
        return names.get(key, key)

    lines = []
    lines.append(chart.moment.describe())
    place = chart.place.name or f"{chart.place.latitude:.4f}, {chart.place.longitude:.4f}"
    lines.append(f"Место: {place}   φ={chart.place.latitude:.4f}°  λ={chart.place.longitude:.4f}°")
    lines.append(f"Эфемериды: {chart.ephemeris}   наклон эклиптики {chart.angles.obliquity:.6f}°")
    lines.append("")

    lines.append("ПОЛОЖЕНИЯ")
    header = f"  {'тело':16s} {'долгота':<21s}   {'широта':>10s} {'дом':>4s} {'скорость':>11s}  достоинство"
    lines.append(header)
    for position in chart.positions.values():
        mark = "R" if position.retrograde else " "
        if position.stationary:
            mark = "S"
        dignity = rulers_mod.dignity_name(position.dignity)
        dignity = "" if dignity == "перегрин" else dignity
        lines.append(
            f"  {position.body.name:16s} {format_longitude(position.longitude):<21s}{mark}"
            f"  {format_signed_arc(position.latitude):>10s} {position.house:4d}"
            f" {position.speed:+10.4f}°  {dignity}"
        )
    lines.append("")

    lines.append("УГЛЫ")
    for title, value in (
        ("ASC", chart.angles.asc), ("MC", chart.angles.mc),
        ("DSC", chart.angles.desc), ("IC", chart.angles.ic),
        ("Вертекс", chart.angles.vertex),
    ):
        lines.append(f"  {title:8s} {format_longitude(value)}")
    lines.append(f"  Управитель карты: {label(chart.chart_ruler)}")
    lines.append("")

    for name, houses in chart.houses.items():
        mark = " (основная)" if name == chart.primary_system else ""
        lines.append(f"ДОМА — {houses.system_name}{mark}")
        widths = houses.widths()
        for i in range(12):
            lines.append(
                f"  {i + 1:2d}  {format_longitude(houses.cusps[i]):<21s} {widths[i]:6.2f}°"
            )
        lines.append("")

    lines.append("АСПЕКТЫ")
    if not chart.aspects:
        lines.append("  нет аспектов в заданных орбисах")
    for hit in chart.aspects:
        motion = "схождение" if hit.applying else "расхождение"
        lines.append(
            f"  {label(hit.body_a):16s} {hit.aspect.name:16s} {label(hit.body_b):16s}"
            f"  орб {hit.orb:5.2f}° из {hit.limit:4.1f}°  {motion}"
        )
    lines.append("")

    if chart.angle_aspects:
        lines.append("АСПЕКТЫ К УГЛАМ")
        for hit in chart.angle_aspects:
            lines.append(
                f"  {label(hit.body_a):16s} {hit.aspect.name:16s} {label(hit.body_b):5s}"
                f"  орб {hit.orb:5.2f}°"
            )
        lines.append("")

    lines.append("ДИСПОЗИТОРЫ")
    for key in chart.positions:
        if chart.dispositors.dispositor.get(key) is None and not chart.dispositors.chain_of(key):
            continue
        lines.append("  " + rulers_mod.describe_chain(key, chart.dispositors, names))
    if chart.dispositors.final_dispositors:
        final = ", ".join(label(k) for k in chart.dispositors.final_dispositors)
        lines.append(f"  финальные: {final}")
    for pair in chart.dispositors.mutual_receptions:
        lines.append(f"  взаимная рецепция: {label(pair[0])} и {label(pair[1])}")
    return "\n".join(lines)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)

    try:
        ephemeris = load_ephemeris(args.ephemeris)
    except EphemerisNotFound as exc:
        print(str(exc), file=sys.stderr)
        return 2

    systems = [args.houses]
    for extra in (houses_mod.WHOLE_SIGN, houses_mod.PLACIDUS):
        if extra not in systems:
            systems.append(extra)

    aspect_set = aspects_mod.ALL_ASPECTS if args.minor else aspects_mod.MAJOR

    try:
        chart = compute(
            args.moment,
            Place(args.latitude, args.longitude, args.place),
            zone=args.zone,
            utc_offset_hours=args.utc_offset,
            fold=args.fold,
            house_systems=systems,
            primary_system=args.houses,
            house_fallback=args.house_fallback,
            aspect_set=aspect_set,
            orb_policy=_orb_policy(args.orb),
            ruler_scheme=args.rulers,
            ephemeris=ephemeris,
        )
    except houses_mod.HouseError as exc:
        print(f"Дома не построены: {exc}", file=sys.stderr)
        print("Подсказка: добавьте --house-fallback whole_sign или porphyry.", file=sys.stderr)
        return 3

    if args.json:
        print(json.dumps(chart.to_dict(include_birth_data=args.with_birth_data),
                         ensure_ascii=False, indent=2))
    else:
        print(render(chart))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
