"""Зодиак: знаки, стихии, кресты, форматирование градусов."""

from __future__ import annotations

from dataclasses import dataclass

SIGNS = (
    "Овен", "Телец", "Близнецы", "Рак", "Лев", "Дева",
    "Весы", "Скорпион", "Стрелец", "Козерог", "Водолей", "Рыбы",
)

SIGNS_EN = (
    "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
    "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces",
)

SIGN_GLYPHS = "♈♉♊♋♌♍♎♏♐♑♒♓"

ELEMENTS = ("Огонь", "Земля", "Воздух", "Вода")
MODALITIES = ("Кардинальный", "Фиксированный", "Мутабельный")


def norm360(x: float) -> float:
    """Приводит угол к диапазону [0, 360)."""
    return x % 360.0


def norm180(x: float) -> float:
    """Приводит угол к диапазону (-180, 180]."""
    x = (x + 180.0) % 360.0 - 180.0
    return x + 360.0 if x <= -180.0 else x


def separation(a: float, b: float) -> float:
    """Кратчайшее расстояние между двумя долготами, 0..180."""
    return abs(norm180(a - b))


@dataclass(frozen=True)
class SignPosition:
    """Положение точки внутри знака."""

    sign_index: int
    degree: int
    minute: int
    second: int
    longitude: float

    @property
    def sign(self) -> str:
        return SIGNS[self.sign_index]

    @property
    def sign_en(self) -> str:
        return SIGNS_EN[self.sign_index]

    @property
    def glyph(self) -> str:
        return SIGN_GLYPHS[self.sign_index]

    @property
    def element(self) -> str:
        return ELEMENTS[self.sign_index % 4]

    @property
    def modality(self) -> str:
        return MODALITIES[self.sign_index % 3]

    @property
    def degree_in_sign(self) -> float:
        return self.longitude % 30.0

    def __str__(self) -> str:
        return f"{self.degree:02d}°{self.minute:02d}'{self.second:02d}\" {self.sign}"

    def short(self) -> str:
        return f"{self.degree}°{self.minute:02d}' {self.glyph}"


def to_sign(longitude: float) -> SignPosition:
    """Разбирает эклиптическую долготу на знак и градус/минуту/секунду.

    Округление ведётся до целых секунд дуги с переносом разрядов, чтобы
    59'59.6" не превращалось в 59'60".
    """
    lon = norm360(longitude)
    sign_index = int(lon // 30)
    rest = lon - sign_index * 30.0

    total_seconds = int(round(rest * 3600.0))
    if total_seconds >= 30 * 3600:  # округление перебросило в следующий знак
        total_seconds = 0
        sign_index = (sign_index + 1) % 12

    degree, rem = divmod(total_seconds, 3600)
    minute, second = divmod(rem, 60)
    return SignPosition(sign_index, degree, minute, second, lon)


def format_longitude(longitude: float) -> str:
    """Человекочитаемая запись долготы: 12°34'56" Овен."""
    return str(to_sign(longitude))


def format_signed_arc(value: float) -> str:
    """Запись угла со знаком: -2°14'03" (для широт и орбисов)."""
    sign = "-" if value < 0 else "+"
    total_seconds = int(round(abs(value) * 3600.0))
    degree, rem = divmod(total_seconds, 3600)
    minute, second = divmod(rem, 60)
    return f"{sign}{degree}°{minute:02d}'{second:02d}\""
