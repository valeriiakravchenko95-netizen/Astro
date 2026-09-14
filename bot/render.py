"""Оформление карты для Telegram.

Сообщения собираются узкими: телефон переносит длинные строки, и таблица
рассыпается. Поэтому колонки считаются по глифам, а не по названиям, и
каждая строка укладывается примерно в тридцать знаков.
"""

from __future__ import annotations

from typing import List, Optional

from astro import rulers as rulers_mod
from astro.chart import Chart
from astro.zodiac import SIGN_GLYPHS, to_sign

#: Предел одного сообщения в Telegram — 4096 знаков; берём с запасом.
MESSAGE_LIMIT = 3500


def _degrees(longitude: float) -> str:
    """Компактная запись: 00°01' ♊."""
    position = to_sign(longitude)
    return f"{position.degree:02d}°{position.minute:02d}' {position.glyph}"


def header(chart: Chart, place_label: Optional[str], exact_time: bool) -> str:
    lines = [f"<b>Натальная карта</b>"]
    if place_label:
        lines.append(f"{place_label}")
    lines.append(
        f"{chart.moment.local:%d.%m.%Y %H:%M} "
        f"(UTC{chart.moment.offset_hours:+g}), {chart.moment.utc:%H:%M} UTC"
    )
    if not exact_time:
        lines.append(
            "\n⚠️ <b>Время рождения неизвестно.</b> Карта посчитана "
            "на полдень. Положения планет по знакам верны, но Луна за сутки "
            "проходит до 15°, а дома и Асцендент зависят от минут — им "
            "верить нельзя."
        )
    if chart.moment.imaginary:
        lines.append(
            "\n⚠️ Указанного часа в этот день не существовало: "
            "стрелки переводили вперёд. Проверьте время."
        )
    elif chart.moment.ambiguous:
        lines.append(
            "\n⚠️ В этот день стрелки переводили назад, и такой час "
            "прошёл дважды. Взят первый."
        )
    return "\n".join(lines)


def positions(chart: Chart, with_houses: bool = True) -> str:
    rows = []
    for position in chart.positions.values():
        mark = "R" if position.retrograde else " "
        if position.stationary:
            mark = "S"
        house = f"{position.houses[chart.primary_system]:2d}" if with_houses else "  "
        rows.append(
            f"{position.body.glyph} {position.body.short_name:<11s}"
            f"{_degrees(position.longitude)} {mark} {house}"
        )
    title = "ПОЛОЖЕНИЯ" + ("        дом" if with_houses else "")
    return f"<b>{title}</b>\n<pre>" + "\n".join(rows) + "</pre>"


def angles_and_houses(chart: Chart) -> str:
    houses = chart.primary_houses
    rows = [
        f"ASC  {_degrees(chart.angles.asc)}",
        f"MC   {_degrees(chart.angles.mc)}",
        f"DSC  {_degrees(chart.angles.desc)}",
        f"IC   {_degrees(chart.angles.ic)}",
        f"Vtx  {_degrees(chart.angles.vertex)}",
    ]
    cusps = [f"{i + 1:2d}   {_degrees(houses.cusps[i])}" for i in range(12)]
    return (
        "<b>УГЛЫ</b>\n<pre>" + "\n".join(rows) + "</pre>"
        + f"\n<b>ДОМА — {houses.system_name}</b>\n<pre>" + "\n".join(cusps) + "</pre>"
    )


def aspects(chart: Chart) -> str:
    if not chart.aspects:
        return "<b>АСПЕКТЫ</b>\nВ заданных орбисах аспектов нет."
    rows = []
    for hit in chart.aspects:
        glyph_a = chart.positions[hit.body_a].body.glyph
        glyph_b = chart.positions[hit.body_b].body.glyph
        motion = "→" if hit.applying else "←"
        rows.append(
            f"{glyph_a} {hit.aspect.glyph} {glyph_b}  "
            f"{hit.aspect.name:<11s} {hit.orb:4.1f}° {motion}"
        )
    legend = "→ сходится, ← расходится"
    return "<b>АСПЕКТЫ</b>\n<pre>" + "\n".join(rows) + f"</pre>\n<i>{legend}</i>"


def angle_aspects(chart: Chart) -> str:
    if not chart.angle_aspects:
        return ""
    rows = [
        f"{chart.positions[hit.body_a].body.glyph} {hit.aspect.glyph} "
        f"{hit.body_b.upper():<4s} {hit.aspect.name:<11s} {hit.orb:4.1f}°"
        for hit in chart.angle_aspects
    ]
    return "<b>АСПЕКТЫ К УГЛАМ</b>\n<pre>" + "\n".join(rows) + "</pre>"


def dignities(chart: Chart) -> str:
    if not chart.dignities:
        return ""
    sect = "дневная" if chart.diurnal else "ночная"
    rows = []
    for key, item in chart.dignities.items():
        body = chart.positions[key].body
        if item.peregrine:
            note = "перегрин"
        else:
            note = ", ".join(rulers_mod.dignity_name(code) for code in item.own)
        state = "" if item.state == "peregrine" else rulers_mod.dignity_name(item.state)
        rows.append(f"{body.glyph} {body.short_name:<11s}{state or note}")
    return (
        f"<b>ДОСТОИНСТВА</b>  <i>карта {sect}</i>\n<pre>"
        + "\n".join(rows) + "</pre>"
    )


def patterns(chart: Chart) -> str:
    blocks: List[str] = []
    if chart.patterns or chart.stelliums:
        rows = []
        for hit in chart.patterns:
            glyphs = " ".join(chart.positions[key].body.glyph for key in hit.bodies)
            rows.append(f"{hit.name}\n   {glyphs}   орб до {hit.worst_orb:.1f}°")
        for item in chart.stelliums:
            glyphs = " ".join(chart.positions[key].body.glyph for key in item.bodies)
            how = "в соединении" if item.by_conjunction else "в одном знаке"
            if item.sign_index is not None:
                how += f" {SIGN_GLYPHS[item.sign_index]}"
            rows.append(f"Стеллиум {how}\n   {glyphs}")
        blocks.append("<b>ФИГУРЫ</b>\n" + "\n".join(rows))
    if chart.antiscia:
        rows = [
            f"{hit.name}: {chart.positions[hit.body_a].body.glyph} "
            f"{chart.positions[hit.body_b].body.glyph}  {hit.orb:.2f}°"
            for hit in chart.antiscia
        ]
        blocks.append("<b>АНТИСЫ</b>\n<pre>" + "\n".join(rows) + "</pre>")
    return "\n\n".join(blocks)


def dispositors(chart: Chart) -> str:
    names = {key: position.body.name for key, position in chart.positions.items()}
    rows = [
        rulers_mod.describe_chain(key, chart.dispositors, names)
        for key in chart.positions
        if key in chart.dispositors.dispositor
    ]
    tail = []
    if chart.dispositors.final_dispositors:
        final = ", ".join(names[key] for key in chart.dispositors.final_dispositors)
        tail.append(f"Финальные: {final}")
    for pair in chart.dispositors.mutual_receptions:
        tail.append(f"Взаимная рецепция: {names[pair[0]]} и {names[pair[1]]}")
    tail.append(f"Управитель карты: {names.get(chart.chart_ruler, chart.chart_ruler)}")
    return "<b>ДИСПОЗИТОРЫ</b>\n<pre>" + "\n".join(rows) + "</pre>\n" + "\n".join(tail)


def split(text: str, limit: int = MESSAGE_LIMIT) -> List[str]:
    """Режет длинный текст на сообщения по границам строк.

    Блоки <pre> закрываются и открываются заново, иначе разметка на стыке
    сообщений разъедется.
    """
    if len(text) <= limit:
        return [text]

    parts: List[str] = []
    current: List[str] = []
    length = 0
    inside_pre = False
    for line in text.split("\n"):
        if length + len(line) + 1 > limit and current:
            if inside_pre:
                current.append("</pre>")
            parts.append("\n".join(current))
            current = ["<pre>"] if inside_pre else []
            length = len(current[0]) if current else 0
        current.append(line)
        length += len(line) + 1
        inside_pre = (inside_pre or "<pre>" in line) and "</pre>" not in line
    if current:
        parts.append("\n".join(current))
    return parts
