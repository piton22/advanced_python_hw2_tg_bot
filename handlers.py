import os
import json
import tempfile
import matplotlib.pyplot as plt
import aiohttp
from aiogram import Router, types
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, FSInputFile
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiohttp import ClientConnectorError

from config import WEATHER_API_KEY
from states import ProfileData, LogFoodState, LogWorkoutState
from functions import fetch_weather, fetch_food_info

JSON_FILENAME = 'users.json'
ACTIVITIES_CALORIES_FILENAME = 'activities_calories.json'

if os.path.exists(JSON_FILENAME):
    with open(JSON_FILENAME, 'r') as file:
        users = json.load(file)
else:
    users = {}

with open(ACTIVITIES_CALORIES_FILENAME, 'r') as file:
    activities_calories = json.load(file)

# Создаем список кнопок
buttons = []
for activity in activities_calories.keys():
    buttons.append(KeyboardButton(text=activity)) 

grouped_buttons = [buttons[i:i + 3] for i in range(0, len(buttons), 3)]

# Создаем клавиатуру
keyboard = ReplyKeyboardMarkup(
    keyboard=grouped_buttons, 
    resize_keyboard=True, 
    one_time_keyboard=True
)

router = Router()

# Обработчик команды /start
@router.message(Command("start"))
async def cmd_start(message: Message):
    user_id = message.from_user.id
    if user_id not in users:
        users[user_id] = {
            "weight": None,
            "height": None,
            "age": None,
            "activity_type": None,
            "activity_minutes": None,
            "city": None,
            "water_goal": 0,
            "calorie_goal": 0,
            "logged_water": 0,
            "logged_calories": 0,
            "burned_calories": 0
        }
    await message.answer("Добро пожаловать! Я помогу вам выполнять ежедневную норму по калориям и воде.\nВведите /help для списка команд.")

# Обработчик команды /help
@router.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer(
        "Доступные команды:\n"
        "/start - Начало работы\n"
        "/set_profile - Настройка профиля\n"
        "/log_water <количество> - Логирование воды\n"
        "/log_food <название продукта> - Логирование еды\n"
        "/log_workout <тип тренировки> <время (мин)> - Логирование тренировок\n"
        "/check_progress - Прогресс по воде и калориям"
    )

# Обработчик команды /set_profile
@router.message(Command("set_profile"))
async def set_profile(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    if user_id not in users:
        await message.answer("Сначала введите команду /start")
        return
    
    await state.set_state(ProfileData.waiting_for_weight)
    await message.answer("Введите ваш вес (в кг):")


# Обработчики состояний
@router.message(ProfileData.waiting_for_weight)
async def process_weight(message: types.Message, state: FSMContext):
    try:
        weight = int(message.text.strip())
    except ValueError:
        await message.answer("Неверный формат веса. Попробуйте снова:")
        return
    if weight < 20 or weight > 500:
        await message.answer("Введенный вес некорректен. Попробуйте снова:")
        return
    
    await state.update_data(weight=weight)
    
    await state.set_state(ProfileData.waiting_for_height)
    await message.answer("Введите ваш рост (в см):")

@router.message(ProfileData.waiting_for_height)
async def process_height(message: types.Message, state: FSMContext):
    try:
        height = int(message.text.strip())
    except ValueError:
        await message.answer("Неверный формат роста. Попробуйте снова:")
        return
    if height < 50 or height > 250:
        await message.answer("Введенный рост некорректен. Попробуйте снова:")
        return
    
    await state.update_data(height=height)

    await state.set_state(ProfileData.waiting_for_age)
    await message.answer("Введите ваш возраст:")

@router.message(ProfileData.waiting_for_age)
async def process_age(message: types.Message, state: FSMContext):
    try:
        age = int(message.text.strip())
    except ValueError:
        await message.answer("Неверный формат возраста. Попробуйте снова:")
        return
    if age < 5 or age > 100:
        await message.answer("Введенный возраст некорректен. Попробуйте снова:")
        return
    
    await state.update_data(age=age)
    
    await state.set_state(ProfileData.waiting_for_activity_minutes)
    await message.answer("Сколько минут активности у вас в день? (Если активности нет, то укажите 0)")

@router.message(ProfileData.waiting_for_activity_minutes)
async def process_activity_minutes(message: types.Message, state: FSMContext):
    try:
        activity_minutes = int(message.text.strip())
    except ValueError:
        await message.answer("Неверный формат времени активности. Попробуйте снова:")
        return
    if activity_minutes < 0 or activity_minutes > 1440:
        await message.answer("Введенное время некорректено. Попробуйте снова:")
        return
    
    await state.update_data(activity_minutes=activity_minutes)
    
    if activity_minutes > 0:
        await state.set_state(ProfileData.waiting_for_activity_type)
        await message.answer("Укажите тип активности:", reply_markup=keyboard)
    else:
        await state.set_state(ProfileData.waiting_for_city)
        await message.answer("В каком городе вы находитесь? (на английском)")


@router.message(ProfileData.waiting_for_activity_type)
async def process_activity_type(message: types.Message, state: FSMContext):
    activity_type = message.text.strip()
    await state.update_data(activity_type=activity_type)    
    await state.set_state(ProfileData.waiting_for_city)
    await message.answer("В каком городе вы находитесь? (введите название на английском)")


@router.message(ProfileData.waiting_for_city)
async def process_city(message: types.Message, state: FSMContext):
    city = message.text.strip()    
    await state.update_data(city=city)

    data = await state.get_data()

    user_id = message.from_user.id
    for key, value in data.items():
        users[user_id][key] = value
 
    try:
        async with aiohttp.ClientSession() as session:
            temperature = await fetch_weather(session, city, WEATHER_API_KEY)
    except ClientConnectorError as e:
        print(f'Ошибка соединения: {e}')
    except Exception as e:
        print(f'При получении погоды возникла ошибка: {e}')

    water_goal = int(users[user_id]['weight'] * 30 + 500 * (users[user_id]['activity_minutes']//30) + 1000 * (temperature > 25))
    users[user_id]["water_goal"] = round(water_goal)

    calorie_goal = 10 * users[user_id]['weight'] + 6.25 * users[user_id]['height'] - 5 * users[user_id]['age'] 

    # Добавим дополнительные калории, если у пользователя есть физическая активность
    if users[user_id]['activity_minutes'] > 0:
        calorie_goal += (activities_calories[users[user_id]['activity_type']] * (users[user_id]['activity_minutes']/60) * users[user_id]['weight'])

    users[user_id]["calorie_goal"] = round(calorie_goal)

    await state.clear()
    await message.answer("Профиль успешно создан!")

    with open('users.json', 'w', encoding='utf-8') as file:
        json.dump(users, file, ensure_ascii=False, indent=4)


# Обработчик команды /log_water <количество>
@router.message(Command("log_water"))
async def cmd_log_water(message: Message):
    user_id = message.from_user.id
    if user_id not in users:
        await message.answer("Сначала введите команду /start")
        return
    if (users[user_id]['weight'] is None 
        or users[user_id]['height'] is None
        or users[user_id]['age'] is None 
        or users[user_id]['activity_minutes'] is None
        or users[user_id]['city'] is None):
        await message.answer("Данные профиля не заполнены. Используйте команду /set_profile.")
        return

    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("Пожалуйста, укажите количество выпитой воды в мл после команды /log_water.")
        return
    
    try:
        water_drunk = int(parts[1].strip())
    except ValueError:
        await message.answer("Количество должно быть числом. Попробуйте еще раз.")
        return
    if water_drunk < 0:
        await message.answer("Введенный объем воды некорректен. Попробуйте снова:")
        return

    users[user_id]["logged_water"] += water_drunk
    water_left = users[user_id]["water_goal"] - users[user_id]["logged_water"]

    with open('users.json', 'w', encoding='utf-8') as file:
        json.dump(users, file, ensure_ascii=False, indent=4)

    if water_left > 0:
        await message.answer(f"Осталось выпить {water_left} мл воды.")  
    else:
        await message.answer("Поздравляем! Норма воды выполнена!")  


# Обработчик команды /log_food <название продукта>
@router.message(Command("log_food"))
async def start_logging_food(message: Message, state: FSMContext):
    user_id = message.from_user.id
    if user_id not in users:
        await message.answer("Сначала введите команду /start")
        return
    if (users[user_id]['weight'] is None 
        or users[user_id]['height'] is None
        or users[user_id]['age'] is None 
        or users[user_id]['activity_minutes'] is None
        or users[user_id]['city'] is None):
        await message.answer("Данные профиля не заполнены. Используйте команду /set_profile.")
        return
    

    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("Пожалуйста, укажите название продукта после команды /log_food.")
        return
    
    product_name = parts[1].strip()
    await state.update_data(product_name=product_name)
    await state.set_state(LogFoodState.waiting_for_weight)
    await message.answer("Сколько грамм вы съели?")

@router.message(LogFoodState.waiting_for_weight)
async def handle_product_weight(message: Message, state: FSMContext):
    user_id = message.from_user.id
    try:
        weight = float(message.text.strip())
    except ValueError:
        await message.answer("Пожалуйста, введите вес в граммах.")
        return
    if weight < 0:
        await message.answer("Введенная масса некорректна. Попробуйте снова:")
        return

    product_data = await state.get_data()

    try:
        async with aiohttp.ClientSession() as session:
            food_info = await fetch_food_info(session, product_data['product_name'])
            if food_info is None:
                raise Exception("Продукт не найден")
            calories_per_100g = food_info['calories']
            total_calories = round((calories_per_100g * weight) / 100)

    except Exception as e:
        print(f'Ошибка при получении калорийности: {e}')
        await message.answer("Возникла ошибка при получении калорийности. Попробуйте еще раз.")
        return  
    
    users[user_id]["logged_calories"] += total_calories
    with open('users.json', 'w', encoding='utf-8') as file:
        json.dump(users, file, ensure_ascii=False, indent=4)

    await message.answer(f"Записано {total_calories} ккал.")
    await state.clear()

# Обработчик команды /log_workout
@router.message(Command("log_workout"))
async def start_logging_workout(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    if user_id not in users:
        await message.answer("Сначала введите команду /start")
        return
    if (users[user_id]['weight'] is None 
        or users[user_id]['height'] is None
        or users[user_id]['age'] is None 
        or users[user_id]['activity_minutes'] is None
        or users[user_id]['city'] is None):
        await message.answer("Данные профиля не заполнены. Используйте команду /set_profile.")
        return
    await message.answer("Укажите тип активности:", reply_markup=keyboard)
    await state.set_state(LogWorkoutState.waiting_for_activity_type)

@router.message(LogWorkoutState.waiting_for_activity_type)
async def process_activity_type(message: types.Message, state: FSMContext):
    activity_type = message.text.strip()
    if activity_type not in activities_calories:
        await message.answer("Неизвестная активность. Выберите из предложенных вариантов.")
        return

    await state.update_data(activity_type=activity_type)
    await state.set_state(LogWorkoutState.waiting_for_minutes)
    await message.answer("Сколько минут вы занимались?")


@router.message(LogWorkoutState.waiting_for_minutes)
async def process_workout_minutes(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    try:
        activity_minutes = int(message.text.strip())
    except ValueError:
        await message.answer("Неверный формат времени активности. Попробуйте снова:")
        return
    if activity_minutes < 0 or activity_minutes > 1440:
        await message.answer("Введенное время некорректно. Попробуйте снова:")
        return
    
    await state.update_data(activity_minutes=activity_minutes)
    workout_data = await state.get_data()
    activity_coefficient = activities_calories[workout_data['activity_type']]
    workout_calories = round((activity_coefficient * (workout_data['activity_minutes']/60) * users[user_id]['weight']))
    workout_water = round(200 * workout_data['activity_minutes'] / 30)
    users[user_id]["water_goal"] += workout_water
    users[user_id]["burned_calories"] += workout_calories

    with open('users.json', 'w', encoding='utf-8') as file:
        json.dump(users, file, ensure_ascii=False, indent=4)

    await message.answer(f'На тренировке "{workout_data['activity_type']}" вы сожгли {workout_calories} ккал. Дополнительно выпейте {workout_water} мл воды.')  
    await state.clear()


# Обработчик команды /check_progress
@router.message(Command("check_progress"))
async def check_progress(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    if user_id not in users:
        await message.answer("Сначала введите команду /start")
        return
    if (users[user_id]['weight'] is None 
        or users[user_id]['height'] is None
        or users[user_id]['age'] is None 
        or users[user_id]['activity_minutes'] is None
        or users[user_id]['city'] is None):
        await message.answer("Данные профиля не заполнены. Используйте команду /set_profile.")
        return
    user_id = message.from_user.id
    water_left = round(users[user_id]["water_goal"] - users[user_id]["logged_water"])
    calories_balance = users[user_id]["logged_calories"] - users[user_id]["burned_calories"]
    
    text_message = (f'''
Вода:
  - Выпито: {users[user_id]["logged_water"]} мл из {users[user_id]["water_goal"]} мл.
  - Осталось: {max(water_left, 0)} мл.

Калории:
  - Потреблено: {users[user_id]["logged_calories"]} ккал из {users[user_id]["calorie_goal"]} ккал.
  - Сожжено: {users[user_id]["burned_calories"]} ккал.
  - Баланс: {calories_balance} ккал.''')
    
    # Построение графика для воды
    plt.figure(figsize=(10,4))
    plt.subplot(1, 2, 1)
    plt.bar(['Цель', 'Выпито'], [users[user_id]['water_goal'], users[user_id]['logged_water']], color=['skyblue', 'lightgreen'])
    plt.title('Цель по воде')
    plt.ylabel('Количество воды (мл)')
    plt.grid(True)

    # Построение графика для калорий
    plt.subplot(1, 2, 2)
    plt.bar(['Цель', 'Потреблено', 'Сожжено'], [users[user_id]['calorie_goal'], users[user_id]['logged_calories'], users[user_id]['burned_calories']], color=['orange', 'green', 'red'])
    plt.title('Цель по калориям')
    plt.ylabel('Калории (ккал)')
    plt.grid(True)

    # Создание временного файла для изображения с графиками
    with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as temp_file:
        plt.savefig(temp_file.name, format='png')
    photo = FSInputFile(temp_file.name)

    # Отправка текста и изображения по прогрессу
    await message.answer(text_message)  
    await message.answer_photo(photo)
    os.unlink(temp_file.name)

# Функция для подключения обработчиков
def setup_handlers(dp):
    dp.include_router(router)
