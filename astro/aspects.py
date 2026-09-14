"""Аспекты с настраиваемыми орбисами.

Орбис складывается из двух частей: базового орбиса самого аспекта и
надбавки за участвующие тела (светилам традиционно дают шире). Способ
сложения надбавок настраивается, а при необходимости всю политику можно
заменить своей функцией.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import (
    Callable, Dict, FrozenSet, Iterable, Mapping, Optional, Sequence, Tuple,
)

from .zodiac import norm180, separation


@dataclass(frozen=True)
class Aspect:
    """Тип аспекта."""

    key: str
    name: str
    angle: float
    glyph: str
    harmonic: str  # major | minor


CONJUNCTION = Aspect("conjunction", "Соединение", 0.0, "☌", "major")
OPPOSITION = Aspect("opposition", "Оппозиция", 180.0, "☍", "major")
TRINE = Aspect("trine", "Трин", 120.0, "△", "major")
SQUARE = Aspect("square", "Квадрат", 90.0, "□", "major")
SEXTILE = Aspect("sextile", "Секстиль", 60.0, "⚹", "major")

SEMISEXTILE = Aspect("semisextile", "Полусекстиль", 30.0, "⚺", "minor")
SEMISQUARE = Aspect("semisquare", "Полуквадрат", 45.0, "∠", "minor")
SESQUISQUARE = Aspect("sesquisquare", "Полутораквадрат", 135.0, "⚼", "minor")
QUINCUNX = Aspect("quincunx", "Квиконс", 150.0, "⚻", "minor")
QUINTILE = Aspect("quintile", "Квинтиль", 72.0, "Q", "minor")
BIQUINTILE = Aspect("biquintile", "Биквинтиль", 144.0, "bQ", "minor")

MAJOR = (CONJUNCTION, OPPOSITION, TRINE, SQUARE, SEXTILE)
MINOR = (SEMISEXTILE, SEMISQUARE, SESQUISQUARE, QUINCUNX, QUINTILE, BIQUINTILE)
ALL_ASPECTS = MAJOR + MINOR

BY_KEY = {a.key: a for a in ALL_ASPECTS}

#: Базовые орбисы аспектов в градусах.
DEFAULT_ASPECT_ORBS: Dict[str, float] = {
    CONJUNCTION.key: 8.0,
    OPPOSITION.key: 8.0,
    TRINE.key: 7.0,
    SQUARE.key: 7.0,
    SEXTILE.key: 5.0,
    SEMISEXTILE.key: 2.0,
    SEMISQUARE.key: 2.0,
    SESQUISQUARE.key: 2.0,
    QUINCUNX.key: 3.0,
    QUINTILE.key: 1.5,
    BIQUINTILE.key: 1.5,
}

#: Надбавка к орбису за участие тела.
DEFAULT_BODY_BONUS: Dict[str, float] = {
    "sun": 2.0,
    "moon": 2.0,
}


@dataclass(frozen=True)
class OrbPolicy:
    """Политика орбисов.

    ``combine`` задаёт, как сводятся надбавки двух тел:
    ``max`` — берётся большая (по умолчанию), ``sum`` — складываются,
    ``mean`` — усредняются. ``override`` полностью заменяет расчёт:
    функция получает ключи тел и аспект, возвращает предельный орбис.
    """

    aspect_orbs: Mapping[str, float] = field(
        default_factory=lambda: dict(DEFAULT_ASPECT_ORBS)
    )
    body_bonus: Mapping[str, float] = field(
        default_factory=lambda: dict(DEFAULT_BODY_BONUS)
    )
    combine: str = "max"
    override: Optional[Callable[[str, str, Aspect], float]] = None

    def limit(self, body_a: str, body_b: str, aspect: Aspect) -> float:
        """Предельный орбис для пары тел и аспекта, градусы."""
        if self.override is not None:
            return self.override(body_a, body_b, aspect)
        base = self.aspect_orbs.get(aspect.key, 0.0)
        bonus_a = self.body_bonus.get(body_a, 0.0)
        bonus_b = self.body_bonus.get(body_b, 0.0)
        if self.combine == "sum":
            bonus = bonus_a + bonus_b
        elif self.combine == "mean":
            bonus = 0.5 * (bonus_a + bonus_b)
        elif self.combine == "max":
            bonus = max(bonus_a, bonus_b)
        else:
            raise ValueError(f"неизвестный способ сложения надбавок: {self.combine!r}")
        return base + bonus

    def with_orbs(self, **orbs: float) -> "OrbPolicy":
        """Копия политики с изменёнными орбисами отдельных аспектов."""
        updated = dict(self.aspect_orbs)
        for key, value in orbs.items():
            if key not in BY_KEY:
                raise KeyError(f"неизвестный аспект: {key!r}")
            updated[key] = value
        return replace(self, aspect_orbs=updated)


#: Политика по умолчанию: мажорные орбисы 5–8°, светилам плюс 2°.
DEFAULT_ORBS = OrbPolicy()

#: Узкая политика — только плотные аспекты.
TIGHT_ORBS = OrbPolicy(
    aspect_orbs={k: v * 0.5 for k, v in DEFAULT_ASPECT_ORBS.items()},
    body_bonus={"sun": 1.0, "moon": 1.0},
)


@dataclass(frozen=True)
class AspectHit:
    """Найденный аспект между двумя телами."""

    body_a: str
    body_b: str
    aspect: Aspect
    orb: float           # отклонение от точного угла, всегда >= 0
    orb_signed: float    # со знаком: куда смещён аспект
    limit: float         # предельный орбис, при котором аспект засчитан
    applying: bool       # сходящийся (True) или расходящийся (False)
    exact_separation: float  # фактическое угловое расстояние тел

    @property
    def strength(self) -> float:
        """Сила аспекта от 0 до 1: 1 — точный, 0 — на границе орбиса."""
        if self.limit <= 0:
            return 0.0
        return max(0.0, 1.0 - self.orb / self.limit)

    @property
    def is_exact(self) -> bool:
        """Точный в пределах одной угловой минуты."""
        return self.orb <= 1.0 / 60.0

    def describe(self) -> str:
        arrow = "→" if self.applying else "←"
        return (
            f"{self.body_a} {self.aspect.name.lower()} {self.body_b} "
            f"орб {self.orb:.2f}° {arrow}"
        )


def _signed_orb(lon_a: float, lon_b: float, angle: float) -> Tuple[float, float]:
    """Отклонение от точного аспекта со знаком и фактическое расстояние."""
    delta = norm180(lon_a - lon_b)
    target = angle if delta >= 0 else -angle
    return norm180(delta - target), abs(delta)


def find_between(
    body_a: str,
    lon_a: float,
    speed_a: float,
    body_b: str,
    lon_b: float,
    speed_b: float,
    aspects: Sequence[Aspect] = MAJOR,
    policy: OrbPolicy = DEFAULT_ORBS,
) -> Optional[AspectHit]:
    """Ищет аспект между двумя телами, возвращает самый точный из подходящих."""
    best: Optional[AspectHit] = None
    for aspect in aspects:
        limit = policy.limit(body_a, body_b, aspect)
        if limit <= 0:
            continue
        orb_signed, exact = _signed_orb(lon_a, lon_b, aspect.angle)
        orb = abs(orb_signed)
        if orb > limit:
            continue
        relative_speed = speed_a - speed_b
        applying = orb_signed * relative_speed < 0
        hit = AspectHit(
            body_a=body_a,
            body_b=body_b,
            aspect=aspect,
            orb=orb,
            orb_signed=orb_signed,
            limit=limit,
            applying=applying,
            exact_separation=exact,
        )
        if best is None or hit.orb < best.orb:
            best = hit
    return best


#: Пары, аспект между которыми ничего не значит.
#:
#: Узлы стоят в точной оппозиции друг к другу по построению, а не по
#: расположению карты, и показывать эту оппозицию среди аспектов —
#: значит выдавать устройство расчёта за свойство карты.
DEGENERATE_PAIRS = frozenset({
    frozenset({"true_node", "south_node"}),
    frozenset({"mean_node", "south_node"}),
})


def find_all(
    positions: Mapping[str, object],
    aspects: Sequence[Aspect] = MAJOR,
    policy: OrbPolicy = DEFAULT_ORBS,
    order: Optional[Sequence[str]] = None,
    skip_pairs: FrozenSet[FrozenSet[str]] = DEGENERATE_PAIRS,
) -> Tuple[AspectHit, ...]:
    """Все аспекты между телами карты.

    ``positions`` — отображение ключа тела на объект с полями ``longitude``
    и ``speed``. Каждая пара рассматривается один раз; результат
    отсортирован по возрастанию орбиса, то есть от самых точных.
    ``skip_pairs`` убирает пары, связанные по построению.
    """
    keys = list(order) if order is not None else list(positions)
    hits = []
    for i, key_a in enumerate(keys):
        for key_b in keys[i + 1:]:
            if frozenset((key_a, key_b)) in skip_pairs:
                continue
            pos_a = positions[key_a]
            pos_b = positions[key_b]
            hit = find_between(
                key_a, pos_a.longitude, pos_a.speed,
                key_b, pos_b.longitude, pos_b.speed,
                aspects=aspects, policy=policy,
            )
            if hit is not None:
                hits.append(hit)
    hits.sort(key=lambda h: (h.orb, h.body_a, h.body_b))
    return tuple(hits)


def to_angles(
    longitude: float,
    speed: float,
    body_key: str,
    angle_longitudes: Mapping[str, float],
    aspects: Sequence[Aspect] = MAJOR,
    policy: OrbPolicy = DEFAULT_ORBS,
) -> Tuple[AspectHit, ...]:
    """Аспекты тела к углам карты (ASC, MC и прочим).

    Углы неподвижны относительно зодиака только условно: они бегут со
    скоростью вращения Земли, поэтому сходимость здесь не считается —
    ``applying`` у таких аспектов всегда False.
    """
    hits = []
    for name, angle_lon in angle_longitudes.items():
        for aspect in aspects:
            limit = policy.limit(body_key, name, aspect)
            if limit <= 0:
                continue
            orb_signed, exact = _signed_orb(longitude, angle_lon, aspect.angle)
            if abs(orb_signed) > limit:
                continue
            hits.append(
                AspectHit(
                    body_a=body_key, body_b=name, aspect=aspect,
                    orb=abs(orb_signed), orb_signed=orb_signed, limit=limit,
                    applying=False, exact_separation=exact,
                )
            )
    hits.sort(key=lambda h: h.orb)
    return tuple(hits)


def resolve_aspects(names: Optional[Iterable[str]]) -> Tuple[Aspect, ...]:
    """Список аспектов по ключам; None — только мажорные."""
    if names is None:
        return MAJOR
    return tuple(BY_KEY[n] for n in names)
