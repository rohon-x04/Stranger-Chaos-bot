"""Finite State Machine states."""

from aiogram.fsm.state import State, StatesGroup


class Register(StatesGroup):
    age     = State()
    gender  = State()
    country = State()


class EditProfile(StatesGroup):
    age     = State()
    country = State()


class ReportFlow(StatesGroup):
    reason = State()
