"""Аспектные фигуры и контакты по антисам.

Фигуры ищутся поверх уже найденных аспектов: строится таблица «пара тел →
аспект», и в ней отыскиваются наборы вершин, связанные нужными рёбрами.
Поэтому фигура настолько же строга, насколько строги заданные орбисы: сузьте
орбисы — и рассыплется половина конфигураций, это нормально.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations, permutations
from typing import Dict, FrozenSet, List, Mapping, Optional, Sequence, Tuple

from . import aspects as aspects_mod
from .zodiac import antiscion, contra_antiscion, norm360, separation


@dataclass(frozen=True)
class PatternSpec:
    """Описание фигуры: сколько вершин и какие рёбра между ними."""

    key: str
    name: str
    size: int
    edges: Tuple[Tuple[int, int, str], ...]


GRAND_TRINE = PatternSpec("grand_trine", "Большой трин", 3, (
    (0, 1, "trine"), (1, 2, "trine"), (0, 2, "trine"),
))
T_SQUARE = PatternSpec("t_square", "Тау-квадрат", 3, (
    (0, 1, "opposition"), (0, 2, "square"), (1, 2, "square"),
))
YOD = PatternSpec("yod", "Йод", 3, (
    (0, 1, "sextile"), (0, 2, "quincunx"), (1, 2, "quincunx"),
))
MINOR_TRINE = PatternSpec("minor_trine", "Малый трин", 3, (
    (0, 1, "sextile"), (1, 2, "sextile"), (0, 2, "trine"),
))
GRAND_CROSS = PatternSpec("grand_cross", "Большой крест", 4, (
    (0, 2, "opposition"), (1, 3, "opposition"),
    (0, 1, "square"), (1, 2, "square"), (2, 3, "square"), (0, 3, "square"),
))
KITE = PatternSpec("kite", "Парус", 4, (
    (0, 1, "trine"), (1, 2, "trine"), (0, 2, "trine"),
    (0, 3, "opposition"), (1, 3, "sextile"), (2, 3, "sextile"),
))
MYSTIC_RECTANGLE = PatternSpec("mystic_rectangle", "Мистический прямоугольник", 4, (
    (0, 2, "opposition"), (1, 3, "opposition"),
    (0, 1, "trine"), (2, 3, "trine"),
    (1, 2, "sextile"), (0, 3, "sextile"),
))

#: Фигуры из четырёх вершин ищутся раньше, чтобы их части не перекрывались
#: более мелкими: парус включает в себя большой трин, а большой крест —
#: два тау-квадрата.
ALL_PATTERNS = (GRAND_CROSS, KITE, MYSTIC_RECTANGLE, T_SQUARE, GRAND_TRINE, YOD, MINOR_TRINE)

PATTERNS_BY_KEY = {p.key: p for p in ALL_PATTERNS}


@dataclass(frozen=True)
class PatternHit:
    """Найденная фигура."""

    spec: PatternSpec
    bodies: Tuple[str, ...]
    orbs: Tuple[float, ...]

    @property
    def key(self) -> str:
        return self.spec.key

    @property
    def name(self) -> str:
        return self.spec.name

    @property
    def worst_orb(self) -> float:
        return max(self.orbs)

    @property
    def mean_orb(self) -> float:
        return sum(self.orbs) / len(self.orbs)

    @property
    def members(self) -> FrozenSet[str]:
        return frozenset(self.bodies)

    def describe(self) -> str:
        return f"{self.name}: {', '.join(self.bodies)} (худший орб {self.worst_orb:.2f}°)"


@dataclass(frozen=True)
class Stellium:
    """Скопление тел — в соединении или просто в одном знаке."""

    bodies: Tuple[str, ...]
    sign_index: Optional[int]
    by_conjunction: bool

    @property
    def size(self) -> int:
        return len(self.bodies)

    def describe(self) -> str:
        how = "в соединении" if self.by_conjunction else "в одном знаке"
        return f"Стеллиум {how}: {', '.join(self.bodies)}"


def _aspect_table(hits: Sequence[aspects_mod.AspectHit]) -> Dict[FrozenSet[str], object]:
    table = {}
    for hit in hits:
        table[frozenset((hit.body_a, hit.body_b))] = hit
    return table


#: Точки, которые по умолчанию не участвуют в фигурах.
#:
#: Узлы всегда стоят в точной оппозиции друг к другу — это их устройство, а
#: не конфигурация карты, и любая планета в квадрате к ним порождала бы
#: мнимый тау-квадрат. Поэтому из пары остаётся только северный узел.
#: Часть Фортуны исключена как вычисляемая от угла точка, а не тело.
DEFAULT_PATTERN_EXCLUDED = frozenset({"south_node", "part_of_fortune"})


def find_patterns(
    hits: Sequence[aspects_mod.AspectHit],
    patterns: Sequence[PatternSpec] = ALL_PATTERNS,
    include_subpatterns: bool = False,
    excluded: FrozenSet[str] = DEFAULT_PATTERN_EXCLUDED,
) -> Tuple[PatternHit, ...]:
    """Ищет фигуры среди найденных аспектов.

    По умолчанию фигура, целиком вложенная в большую, не выдаётся отдельно:
    в парусе не показывается образующий его большой трин. ``include_subpatterns``
    отключает это подавление. ``excluded`` убирает точки из рассмотрения.
    """
    if excluded:
        hits = [
            hit for hit in hits
            if hit.body_a not in excluded and hit.body_b not in excluded
        ]
    table = _aspect_table(hits)
    bodies = sorted({body for pair in table for body in pair})

    found: List[PatternHit] = []
    for spec in patterns:
        for group in combinations(bodies, spec.size):
            for order in permutations(group):
                orbs = _match(spec, order, table)
                if orbs is None:
                    continue
                candidate = PatternHit(spec, tuple(order), orbs)
                if not _already_found(candidate, found):
                    found.append(candidate)
                break  # перестановки одной группы дают ту же фигуру

    if not include_subpatterns:
        found = [
            hit for hit in found
            if not any(
                other is not hit
                and len(other.bodies) > len(hit.bodies)
                and hit.members < other.members
                for other in found
            )
        ]
    found.sort(key=lambda hit: (-len(hit.bodies), hit.worst_orb))
    return tuple(found)


def _match(spec: PatternSpec, order: Sequence[str], table) -> Optional[Tuple[float, ...]]:
    """Проверяет, связаны ли вершины именно теми аспектами, что нужны фигуре."""
    orbs = []
    for left, right, aspect_key in spec.edges:
        hit = table.get(frozenset((order[left], order[right])))
        if hit is None or hit.aspect.key != aspect_key:
            return None
        orbs.append(hit.orb)
    return tuple(orbs)


def _already_found(candidate: PatternHit, found: Sequence[PatternHit]) -> bool:
    return any(
        hit.spec.key == candidate.spec.key and hit.members == candidate.members
        for hit in found
    )


def find_stelliums(
    positions: Mapping[str, object],
    hits: Sequence[aspects_mod.AspectHit] = (),
    minimum: int = 3,
    by_sign: bool = True,
) -> Tuple[Stellium, ...]:
    """Ищет скопления тел.

    Два разных чтения стеллиума: цепочка соединений и просто несколько тел
    в одном знаке. Первое строже и не зависит от границ знаков, второе
    привычнее; возвращаются оба, помеченные признаком ``by_conjunction``.
    """
    result: List[Stellium] = []

    # Цепочки соединений: тела объединяются, если связаны соединением хотя
    # бы через соседа, поэтому длинная растянутая цепочка тоже считается.
    parent: Dict[str, str] = {key: key for key in positions}

    def root(key: str) -> str:
        while parent[key] != key:
            parent[key] = parent[parent[key]]
            key = parent[key]
        return key

    for hit in hits:
        if hit.aspect.key == "conjunction":
            a, b = root(hit.body_a), root(hit.body_b)
            if a != b:
                parent[a] = b

    groups: Dict[str, List[str]] = {}
    for key in positions:
        groups.setdefault(root(key), []).append(key)
    for members in groups.values():
        if len(members) >= minimum:
            result.append(Stellium(tuple(sorted(members)), None, True))

    if by_sign:
        in_sign: Dict[int, List[str]] = {}
        for key, position in positions.items():
            in_sign.setdefault(int(norm360(position.longitude) // 30), []).append(key)
        for sign_index, members in sorted(in_sign.items()):
            if len(members) >= minimum:
                result.append(Stellium(tuple(sorted(members)), sign_index, False))

    return tuple(result)


@dataclass(frozen=True)
class AntisciaHit:
    """Контакт по антисам."""

    body_a: str
    body_b: str
    kind: str   # antiscion | contra_antiscion
    orb: float

    @property
    def name(self) -> str:
        return "Антис" if self.kind == "antiscion" else "Контр-антис"

    def describe(self) -> str:
        return f"{self.name}: {self.body_a} и {self.body_b} (орб {self.orb:.2f}°)"


def find_antiscia(
    positions: Mapping[str, object],
    orb: float = 1.0,
    order: Optional[Sequence[str]] = None,
) -> Tuple[AntisciaHit, ...]:
    """Ищет контакты по антисам и контр-антисам.

    Орбис у антисов традиционно узкий — по умолчанию градус.
    """
    keys = list(order) if order is not None else list(positions)
    found: List[AntisciaHit] = []
    for i, key_a in enumerate(keys):
        for key_b in keys[i + 1:]:
            longitude_a = positions[key_a].longitude
            longitude_b = positions[key_b].longitude
            for kind, reflected in (
                ("antiscion", antiscion(longitude_a)),
                ("contra_antiscion", contra_antiscion(longitude_a)),
            ):
                distance = separation(reflected, longitude_b)
                if distance <= orb:
                    found.append(AntisciaHit(key_a, key_b, kind, distance))
    found.sort(key=lambda hit: hit.orb)
    return tuple(found)
