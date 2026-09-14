"""Состояния диалога."""

from aiogram.fsm.state import State, StatesGroup


class ChartDialog(StatesGroup):
    """Сбор данных для карты.

    Введённые дата, время и место живут только в памяти процесса и только
    до конца расчёта: сразу после него состояние очищается, и остаются
    лишь готовые тексты разделов.
    """

    waiting_date = State()
    waiting_time = State()
    waiting_place = State()
    choosing_place = State()
    showing_chart = State()
