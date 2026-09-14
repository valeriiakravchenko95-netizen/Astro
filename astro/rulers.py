"""Управители знаков, достоинства и цепочки диспозиторов."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Mapping, Optional, Sequence, Tuple

from .zodiac import SIGNS

TRADITIONAL = "traditional"
MODERN = "modern"

#: Управители знаков по порядку от Овна до Рыб.
TRADITIONAL_RULERS: Tuple[str, ...] = (
    "mars", "venus", "mercury", "moon", "sun", "mercury",
    "venus", "mars", "jupiter", "saturn", "saturn", "jupiter",
)

#: Современная схема: высшие планеты управляют Скорпионом, Водолеем и Рыбами.
MODERN_RULERS: Tuple[str, ...] = (
    "mars", "venus", "mercury", "moon", "sun", "mercury",
    "venus", "pluto", "jupiter", "saturn", "uranus", "neptune",
)

#: Классический управитель остаётся вторым для знаков с высшим управителем.
CO_RULERS: Dict[int, str] = {7: "mars", 10: "saturn", 11: "jupiter"}

SCHEMES = {TRADITIONAL: TRADITIONAL_RULERS, MODERN: MODERN_RULERS}

#: Экзальтации: тело → (индекс знака, градус наибольшей силы).
EXALTATIONS: Dict[str, Tuple[int, float]] = {
    "sun": (0, 19.0),       # Овен
    "moon": (1, 3.0),       # Телец
    "mercury": (5, 15.0),   # Дева
    "venus": (11, 27.0),    # Рыбы
    "mars": (9, 28.0),      # Козерог
    "jupiter": (3, 15.0),   # Рак
    "saturn": (6, 21.0),    # Весы
}

DIGNITY_NAMES = {
    "domicile": "обитель",
    "exaltation": "экзальтация",
    "detriment": "изгнание",
    "fall": "падение",
    "peregrine": "перегрин",
}


def rulers(scheme: str = TRADITIONAL) -> Tuple[str, ...]:
    """Таблица управителей выбранной схемы."""
    try:
        return SCHEMES[scheme]
    except KeyError:
        raise ValueError(f"неизвестная схема управителей: {scheme!r}") from None


def ruler_of(sign_index: int, scheme: str = TRADITIONAL) -> str:
    """Управитель знака."""
    return rulers(scheme)[sign_index % 12]


def co_ruler_of(sign_index: int, scheme: str = TRADITIONAL) -> Optional[str]:
    """Второй управитель знака — классический, если основной высший."""
    if scheme != MODERN:
        return None
    return CO_RULERS.get(sign_index % 12)


def signs_ruled_by(body: str, scheme: str = TRADITIONAL) -> Tuple[int, ...]:
    """Индексы знаков, которыми управляет тело."""
    return tuple(i for i, r in enumerate(rulers(scheme)) if r == body)


def dignity(body: str, sign_index: int, scheme: str = TRADITIONAL) -> str:
    """Эссенциальное достоинство тела в знаке.

    Проверяются четыре классических состояния; если ни одно не подходит,
    тело перегрин — без достоинства и без ущерба.
    """
    sign_index %= 12
    table = rulers(scheme)
    if table[sign_index] == body:
        return "domicile"
    if table[(sign_index + 6) % 12] == body:
        return "detriment"
    exaltation = EXALTATIONS.get(body)
    if exaltation is not None:
        if exaltation[0] == sign_index:
            return "exaltation"
        if (exaltation[0] + 6) % 12 == sign_index:
            return "fall"
    return "peregrine"


def dignity_name(code: str) -> str:
    return DIGNITY_NAMES.get(code, code)


@dataclass(frozen=True)
class DispositorTree:
    """Результат разбора цепочек диспозиторов.

    ``dispositor`` — непосредственный диспозитор каждого тела: управитель
    знака, в котором тело стоит. ``chains`` — путь от тела до входа в
    замкнутый круг. ``cycles`` — сами круги: цикл длиной один означает
    планету в своей обители, то есть финального диспозитора карты; цикл
    длиннее одного — взаимная рецепция или более длинное кольцо, у карты
    тогда единого финального диспозитора нет.
    """

    dispositor: Mapping[str, Optional[str]]
    chains: Mapping[str, Tuple[str, ...]]
    cycles: Tuple[Tuple[str, ...], ...]
    terminal: Mapping[str, Optional[Tuple[str, ...]]]

    @property
    def final_dispositors(self) -> Tuple[str, ...]:
        """Планеты в своей обители — конечные точки всех цепочек."""
        return tuple(cycle[0] for cycle in self.cycles if len(cycle) == 1)

    @property
    def mutual_receptions(self) -> Tuple[Tuple[str, str], ...]:
        """Пары планет, взаимно управляющих знаками друг друга."""
        return tuple(
            (cycle[0], cycle[1]) for cycle in self.cycles if len(cycle) == 2
        )

    def chain_of(self, body: str) -> Tuple[str, ...]:
        return self.chains.get(body, ())


def build_dispositors(
    sign_by_body: Mapping[str, int],
    scheme: str = TRADITIONAL,
    bodies: Optional[Sequence[str]] = None,
) -> DispositorTree:
    """Строит диспозиторы для тел карты.

    ``sign_by_body`` — ключ тела → индекс знака, в котором оно стоит.
    Учитываются только те управители, которые сами есть в карте: если
    схема традиционная, а Плутон в карте есть, диспозитором он не станет,
    потому что знаками не управляет.
    """
    present = set(bodies) if bodies is not None else set(sign_by_body)

    dispositor: Dict[str, Optional[str]] = {}
    for body in sign_by_body:
        if body not in present:
            continue
        ruler = ruler_of(sign_by_body[body], scheme)
        dispositor[body] = ruler if ruler in present and ruler in sign_by_body else None

    chains: Dict[str, Tuple[str, ...]] = {}
    terminal: Dict[str, Optional[Tuple[str, ...]]] = {}
    cycles: List[Tuple[str, ...]] = []
    cycle_by_member: Dict[str, Tuple[str, ...]] = {}

    for start in dispositor:
        path: List[str] = []
        index_of: Dict[str, int] = {}
        node: Optional[str] = start
        while node is not None and node not in index_of:
            index_of[node] = len(path)
            path.append(node)
            node = dispositor.get(node)

        if node is None:  # цепочка оборвалась: управителя нет в карте
            chains[start] = tuple(path[1:])
            terminal[start] = None
            continue

        if node in cycle_by_member:  # пришли в уже известный круг
            cycle = cycle_by_member[node]
        else:
            cycle = tuple(path[index_of[node]:])
            # круг записывается всегда с одного и того же тела, чтобы
            # один и тот же цикл не появлялся в разных поворотах
            pivot = cycle.index(min(cycle))
            cycle = cycle[pivot:] + cycle[:pivot]
            cycles.append(cycle)
            for member in cycle:
                cycle_by_member[member] = cycle

        chains[start] = tuple(path[: index_of[node]][1:])
        terminal[start] = cycle

    cycles.sort(key=lambda c: (len(c), c))
    return DispositorTree(dispositor, chains, tuple(cycles), terminal)


def describe_chain(
    body: str,
    tree: DispositorTree,
    names: Optional[Mapping[str, str]] = None,
) -> str:
    """Человекочитаемая цепочка диспозиторов: от тела до кольца.

    ``names`` подменяет ключи тел на любые подписи, например русские.
    """
    def label(key: str) -> str:
        return names.get(key, key) if names else key

    steps: List[str] = [label(body)]
    steps.extend(label(k) for k in tree.chain_of(body))
    cycle = tree.terminal.get(body)
    if cycle is None:
        return " \u2192 ".join(steps) + " \u2192 ?"
    if len(cycle) == 1:
        if len(steps) == 1 and cycle[0] == body:
            return f"{label(body)} в своей обители"
        steps.append(label(cycle[0]))
        return " \u2192 ".join(steps) + " (финальный диспозитор)"
    ring_parts = [label(k) for k in cycle]
    ring = (" \u21c4 ".join(ring_parts) if len(cycle) == 2
            else " \u2192 ".join(ring_parts + ring_parts[:1]))
    if body in cycle:
        return f"{label(body)} в кольце: {ring}"
    return " \u2192 ".join(steps) + f" \u2192 кольцо: {ring}"
