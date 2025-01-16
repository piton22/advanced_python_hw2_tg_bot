from aiogram.filters.state import State, StatesGroup

class ProfileData(StatesGroup):
    waiting_for_weight = State()
    waiting_for_height = State()
    waiting_for_age = State()
    waiting_for_activity_minutes = State()
    waiting_for_activity_type = State()
    waiting_for_city = State()

class LogFoodState(StatesGroup):
    waiting_for_weight = State()

class LogWorkoutState(StatesGroup):
    waiting_for_activity_type = State()
    waiting_for_minutes = State()