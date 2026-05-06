import requests
import random
import json
import os
from datetime import datetime, timezone, timedelta

# Московское время (UTC+3)
MOSCOW_TZ = timezone(timedelta(hours=3))

# Файл для хранения вчерашней погоды
HISTORY_FILE = "weather_history.json"

# Вебхук URL из секретов GitHub
WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")

# -------------------------------------------------------------------
# 1. Функция для загрузки/сохранения истории погоды
# -------------------------------------------------------------------
def load_history():
    """Загружает историю погоды из файла"""
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"last_weather": None, "last_date": None}

def save_history(weather, date):
    """Сохраняет погоду за сегодня"""
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump({"last_weather": weather, "last_date": date}, f)

# -------------------------------------------------------------------
# 2. Выбор погоды с учётом вероятностей и вчерашнего тумана
# -------------------------------------------------------------------
def choose_weather(last_weather):
    """Выбирает погоду на сегодня с учётом вчерашнего тумана"""
    # Базовые шансы
    chances = {
        "Солнечная": 50,
        "Дождь": 20,
        "Туман": 10,
        "Гроза": 10,
        "Аномальная жара": 5,
        "Аномальный холод": 5
    }
    
    # Если вчера был туман: -5% к солнцу, +5% к дождю
    if last_weather == "Туман":
        chances["Солнечная"] -= 5
        chances["Дождь"] += 5
        # Не даём шансам уйти в минус или за 100
        if chances["Солнечная"] < 0:
            chances["Солнечная"] = 0
    
    # Превращаем шансы в накопительный список
    weathers = []
    weights = []
    for weather, weight in chances.items():
        weathers.append(weather)
        weights.append(weight)
    
    return random.choices(weathers, weights=weights)[0]

# -------------------------------------------------------------------
# 3. Расчёт температуры с учётом сезона (6 мая — весна)
# -------------------------------------------------------------------
def calculate_temperature(weather):
    """Возвращает температуру, влажность, ветер, 'ощущается как'"""
    now = datetime.now(MOSCOW_TZ)
    month = now.month
    day = now.day
    
    # Весна (март, апрель, май) — ядро
    if 3 <= month <= 5:
        if weather == "Солнечная":
            temp = random.randint(15, 25)
        elif weather == "Дождь":
            temp = random.randint(8, 15)
        elif weather == "Туман":
            temp = random.randint(5, 12)
        elif weather == "Гроза":
            temp = random.randint(12, 20)
        elif weather == "Аномальная жара":
            temp = random.randint(25, 35)
        else:  # Аномальный холод
            temp = random.randint(-5, 8)
    else:
        # Лето/осень/зима — запасная логика, если вдруг дата съедет
        temp = random.randint(0, 20)
    
    # Влажность и ветер
    humidity = random.randint(30, 90)
    wind_speed = random.randint(0, 10)
    
    # "Ощущается как" (грубая формула)
    feels_like = temp - int(wind_speed / 2) + int((humidity - 50) / 10)
    
    return temp, humidity, wind_speed, feels_like

# -------------------------------------------------------------------
# 4. Активность зомби в зависимости от погоды
# -------------------------------------------------------------------
def zombie_activity(weather):
    """Возвращает строку с активностью зомби"""
    if weather == "Солнечная":
        return "низкая ☀️"
    elif weather == "Дождь":
        return "средняя 🌧️"
    elif weather == "Туман":
        return "высокая 🌫️"
    elif weather == "Гроза":
        return "критическая ⚡"
    elif weather == "Аномальная жара":
        return "низкая 🔥"
    elif weather == "Аномальный холод":
        return "низкая ❄️"
    return "средняя"

# -------------------------------------------------------------------
# 5. Совет выжившему
# -------------------------------------------------------------------
def survival_tip(weather):
    """Короткий совет в духе зомби-апокалипсиса"""
    tips = {
        "Солнечная": "Пей больше воды и не снимай головной убор.",
        "Дождь": "Дождь маскирует запах — отличное время для разведки.",
        "Туман": "Слух важнее зрения. Двигайся медленно.",
        "Гроза": "Молнии привлекают орды. Спрячься в подвале.",
        "Аномальная жара": "Зомби сохнут, но ты тоже не перегревайся.",
        "Аномальный холод": "Зомби медленнее, но риск обморожения высок."
    }
    return tips.get(weather, "Будь осторожен.")

# -------------------------------------------------------------------
# 6. Формирование Discord-сообщения
# -------------------------------------------------------------------
def build_discord_message():
    """Собирает всё в красивое сообщение для Discord"""
    
    # 1. Загружаем вчерашнюю погоду
    history = load_history()
    last_weather = history.get("last_weather")
    
    # 2. Выбираем сегодняшнюю погоду
    today_weather = choose_weather(last_weather)
    
    # 3. Сохраняем сегодняшнюю погоду для завтра
    today_str = datetime.now(MOSCOW_TZ).strftime("%Y-%m-%d")
    save_history(today_weather, today_str)
    
    # 4. Получаем параметры
    temp, humidity, wind, feels = calculate_temperature(today_weather)
    activity = zombie_activity(today_weather)
    tip = survival_tip(today_weather)
    
    # Эмодзи для каждого типа погоды
    emoji_map = {
        "Солнечная": "☀️",
        "Дождь": "🌧️",
        "Туман": "🌫️",
        "Гроза": "⛈️",
        "Аномальная жара": "🔥",
        "Аномальный холод": "❄️"
    }
    emoji = emoji_map.get(today_weather, "🌡️")
    
    # 5. Собираем сообщение
    message = f"""# {emoji} Погода на сегодня

**{today_weather}** | {temp:+d}° | Влажность {humidity}%

{get_weather_description(today_weather)}

🌀 Влажность: {humidity}%  
💨 Ветер: {wind} м/с  
🌡️ Ощущается как: {feels:+d}°  
💀 Активность зомби: {activity}

💡 *{tip}*
"""
    return message

def get_weather_description(weather):
    """Краткое описание погоды для Discord"""
    desc = {
        "Солнечная": "Ясное небо, лёгкий ветер с юго-запада. Зомби сегодня пассивны — солнечный свет замедляет их реакции.",
        "Дождь": "Моросящий дождь. Земля становится скользкой. Зомби хуже слышат из-за шума капель.",
        "Туман": "Нулевая видимость. Ты слышишь шаги, но не видишь врага. Осторожно, выживший.",
        "Гроза": "Небо разрывают молнии. Каждый удар грома может привлечь орду. Ищи укрытие немедленно.",
        "Аномальная жара": "Зной выше +30. Асфальт плавится, зомби становятся вялыми, но риск теплового удара высок.",
        "Аномальный холод": "Внезапные заморозки. Дыши через шарф — пар выдаст твоё положение."
    }
    return desc.get(weather, "Будь готов к любым неожиданностям.")

# -------------------------------------------------------------------
# 7. Отправка в Discord
# -------------------------------------------------------------------
def send_to_discord(message):
    """Отправляет сообщение через вебхук"""
    if not WEBHOOK_URL:
        print("Ошибка: DISCORD_WEBHOOK_URL не найден в секретах!")
        return False
    
    data = {
        "content": message,
        "username": "Зомби-Синоптик",
        "avatar_url": "https://cdn-icons-png.flaticon.com/512/4351/4351479.png"  # иконка-облачко
    }
    
    response = requests.post(WEBHOOK_URL, json=data)
    if response.status_code == 204:
        print("Сообщение успешно отправлено в Discord!")
        return True
    else:
        print(f"Ошибка: {response.status_code} - {response.text}")
        return False

# -------------------------------------------------------------------
# 8. Главная функция
# -------------------------------------------------------------------
def main():
    print("Запуск бота погоды...")
    message = build_discord_message()
    print(message)
    success = send_to_discord(message)
    if success:
        print("Готово! Завтра в 00:00 МСК снова пришлю погоду.")
    else:
        print("Что-то пошло не так. Проверь WEBHOOK_URL и интернет.")

if __name__ == "__main__":
    main()
