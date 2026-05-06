import requests
import random
import json
import os
from datetime import datetime, timezone, timedelta
import google.generativeai as genai

# Московское время (UTC+3)
MOSCOW_TZ = timezone(timedelta(hours=3))

# Файлы для хранения данных
HISTORY_FILE = "weather_history.json"
TIPS_HISTORY_FILE = "tips_history.json"

# Вебхук URL и API ключ из секретов GitHub
WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

# Настройка Gemini
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel('gemini-1.5-flash')  # Быстрая и бесплатная модель
else:
    print("Предупреждение: GEMINI_API_KEY не найден, ИИ-генерация работать не будет")
    model = None

# -------------------------------------------------------------------
# 1. Советы для каждого типа погоды (по 3 штуки) - резервные на случай ошибки ИИ
# -------------------------------------------------------------------
TIPS = {
    "Солнечная": [
        "Пей больше воды и не снимай головной убор.",
        "Солнце — враг зомби, но и твоя кожа не железная. Пользуйся кремом.",
        "Сегодня отличный день, чтобы просушить припасы и проветрить убежище."
    ],
    "Дождь": [
        "Дождь маскирует запах и звуки — отличное время для разведки.",
        "Влага мешает зомби, но может испортить оружие. Протри стволы насухо.",
        "Собирай дождевую воду — она пригодится, если река заражена."
    ],
    "Туман": [
        "Слух важнее зрения. Двигайся медленно и прислушивайся.",
        "Туман — лучший друг сталкера и худший враг новичка. Не теряй ориентиры.",
        "В тумане зомби почти не видят, но отлично слышат. Затаись или стреляй глушителем."
    ],
    "Гроза": [
        "Молнии привлекают орды шумом. Спрячься в подвале до затишья.",
        "Гроза — не время для вылазок. Одно попадание — и ты нежить.",
        "После грозы часто идут кислотные дожди. Проверь воду перед употреблением."
    ],
    "Аномальная жара": [
        "Зомби высыхают и становятся хрупкими, но ты рискуешь получить тепловой удар.",
        "Носи светлую одежду и пей солёную воду — электролиты спасают жизнь.",
        "В такую жару патроны могут самовоспламениться. Не носи их в кармане."
    ],
    "Аномальный холод": [
        "Зомби медленнее, но риск обморожения высок. Утеплись и не стой на месте.",
        "Дыши через шарф — пар выдаст твоё положение. Двигайся короткими перебежками.",
        "Металлическое оружие примерзает к рукам. Обмотай рукоятки тканью."
    ]
}

# Эмодзи для каждого типа погоды
EMOJI_MAP = {
    "Солнечная": "☀️",
    "Дождь": "🌧️",
    "Туман": "🌫️",
    "Гроза": "⛈️",
    "Аномальная жара": "🔥",
    "Аномальный холод": "❄️"
}

# -------------------------------------------------------------------
# 2. Работа с историей
# -------------------------------------------------------------------
def load_history():
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"last_weather": None, "last_date": None}

def save_history(weather, date):
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump({"last_weather": weather, "last_date": date}, f)

def load_tips_history():
    if os.path.exists(TIPS_HISTORY_FILE):
        with open(TIPS_HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_tips_history(history):
    with open(TIPS_HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f)

# -------------------------------------------------------------------
# 3. Выбор погоды
# -------------------------------------------------------------------
def choose_weather(last_weather):
    chances = {
        "Солнечная": 50,
        "Дождь": 20,
        "Туман": 10,
        "Гроза": 10,
        "Аномальная жара": 5,
        "Аномальный холод": 5
    }
    
    if last_weather == "Туман":
        chances["Солнечная"] -= 5
        chances["Дождь"] += 5
        if chances["Солнечная"] < 0:
            chances["Солнечная"] = 0
    
    weathers = list(chances.keys())
    weights = list(chances.values())
    return random.choices(weathers, weights=weights)[0]

# -------------------------------------------------------------------
# 4. Выбор совета (без повторов 2 дня подряд)
# -------------------------------------------------------------------
def get_unique_tip(weather, tips_history):
    """Возвращает совет, который не повторялся вчера для этой погоды"""
    available_tips = TIPS[weather].copy()
    
    # Узнаём, какой совет использовался вчера для этой погоды
    last_tip = tips_history.get(weather)
    
    if last_tip and last_tip in available_tips:
        available_tips.remove(last_tip)
    
    # Если все советы уже использовались (очищаем историю)
    if not available_tips:
        available_tips = TIPS[weather].copy()
        if last_tip and last_tip in available_tips:
            available_tips.remove(last_tip)
    
    return random.choice(available_tips)

# -------------------------------------------------------------------
# 5. Температура с учётом сезона
# -------------------------------------------------------------------
def calculate_temperature(weather):
    now = datetime.now(MOSCOW_TZ)
    month = now.month
    
    if 3 <= month <= 5:  # Весна
        ranges = {
            "Солнечная": (15, 25),
            "Дождь": (8, 15),
            "Туман": (5, 12),
            "Гроза": (12, 20),
            "Аномальная жара": (25, 35),
            "Аномальный холод": (-5, 8)
        }
    elif 6 <= month <= 8:  # Лето
        ranges = {
            "Солнечная": (22, 32),
            "Дождь": (15, 22),
            "Туман": (12, 20),
            "Гроза": (18, 28),
            "Аномальная жара": (32, 42),
            "Аномальный холод": (5, 15)
        }
    else:  # Осень/Зима
        ranges = {
            "Солнечная": (0, 10),
            "Дождь": (-3, 5),
            "Туман": (-5, 3),
            "Гроза": (-2, 6),
            "Аномальная жара": (10, 18),
            "Аномальный холод": (-20, -5)
        }
    
    temp_range = ranges.get(weather, (5, 15))
    temp = random.randint(temp_range[0], temp_range[1])
    
    humidity = random.randint(30, 90)
    wind_speed = random.randint(0, 10)
    feels_like = temp - int(wind_speed / 2) + int((humidity - 50) / 20)
    
    return temp, humidity, wind_speed, feels_like

# -------------------------------------------------------------------
# 6. Активность зомби
# -------------------------------------------------------------------
def zombie_activity(weather):
    activities = {
        "Солнечная": "низкая ☀️",
        "Дождь": "средняя 🌧️",
        "Туман": "высокая 🌫️",
        "Гроза": "критическая ⚡",
        "Аномальная жара": "низкая 🔥",
        "Аномальный холод": "низкая ❄️"
    }
    return activities.get(weather, "средняя")

# -------------------------------------------------------------------
# 7. ГЕНЕРАЦИЯ ОПИСАНИЯ ЧЕРЕЗ ИИ (НОВОЕ!)
# -------------------------------------------------------------------
def generate_ai_description(weather, temp, humidity, wind, feels_like, activity):
    """Генерирует уникальное описание погоды через Google Gemini"""
    
    if not model:
        # Если ИИ не настроен, возвращаем стандартное описание
        return generate_fallback_description(weather)
    
    today = datetime.now(MOSCOW_TZ)
    date_str = today.strftime("%d.%m.%Y")
    
    # Форматируем температуру
    temp_str = f"+{temp}" if temp > 0 else str(temp)
    feels_str = f"+{feels_like}" if feels_like > 0 else str(feels_like)
    
    # Промпт для ИИ
    prompt = f"""
Ты — Зомби-Синоптик, выживший в мире зомби-апокалипсиса. Твоя задача — написать атмосферную, мрачную, но с долей чёрного юмора сводку погоды.

Сегодня {date_str}.
Погода: {weather}
Температура: {temp_str}°C (ощущается как {feels_str}°C)
Влажность: {humidity}%
Ветер: {wind} м/с
Активность зомби: {activity}

Напиши короткое описание (2-3 предложения) в стиле постапокалипсиса. Используй образные выражения, упоминай зомби, выживание, опасности. Пиши на русском языке. Не используй markdown и форматирование. Будь краток, но атмосферно!
"""
    
    try:
        response = model.generate_content(prompt)
        description = response.text.strip()
        # Ограничиваем длину до 500 символов
        if len(description) > 500:
            description = description[:497] + "..."
        return description
    except Exception as e:
        print(f"Ошибка при генерации через ИИ: {e}")
        return generate_fallback_description(weather)

def generate_fallback_description(weather):
    """Резервное описание на случай ошибки ИИ"""
    fallbacks = {
        "Солнечная": "Ясное небо, лёгкий ветер с юго-запада. Зомби сегодня пассивны — солнечный свет замедляет их реакции.",
        "Дождь": "Моросящий дождь. Земля становится скользкой. Зомби хуже слышат из-за шума капель.",
        "Туман": "Нулевая видимость. Ты слышишь шаги, но не видишь врага. Осторожно, выживший.",
        "Гроза": "Небо разрывают молнии. Каждый удар грома может привлечь орду. Ищи укрытие немедленно.",
        "Аномальная жара": "Зной выше +30. Асфальт плавится, зомби становятся вялыми, но риск теплового удара высок.",
        "Аномальный холод": "Внезапные заморозки. Дыши через шарф — пар выдаст твоё положение."
    }
    return fallbacks.get(weather, "Будь готов к любым неожиданностям.")

# -------------------------------------------------------------------
# 8. Формирование сообщения в рамке (Discord Embed) с ИИ-описанием
# -------------------------------------------------------------------
def build_discord_embed():
    """Создаёт embed (рамку) с описанием от ИИ"""
    
    # Загружаем историю
    history = load_history()
    last_weather = history.get("last_weather")
    tips_history = load_tips_history()
    
    # Выбираем погоду и совет
    today_weather = choose_weather(last_weather)
    tip = get_unique_tip(today_weather, tips_history)
    
    # Обновляем историю советов
    tips_history[today_weather] = tip
    save_tips_history(tips_history)
    
    # Сохраняем погоду
    today_str = datetime.now(MOSCOW_TZ).strftime("%Y-%m-%d")
    save_history(today_weather, today_str)
    
    # Получаем параметры
    temp, humidity, wind, feels = calculate_temperature(today_weather)
    activity = zombie_activity(today_weather)
    
    # ГЕНЕРИРУЕМ ОПИСАНИЕ ЧЕРЕЗ ИИ
    ai_description = generate_ai_description(today_weather, temp, humidity, wind, feels, activity)
    
    emoji = EMOJI_MAP.get(today_weather, "🌡️")
    
    # Форматируем температуру с плюсом/минусом
    temp_str = f"+{temp}" if temp > 0 else str(temp)
    feels_str = f"+{feels}" if feels > 0 else str(feels)
    
    # Создаём Embed (рамку)
    embed = {
        "title": f"{emoji} Погода на сегодня",
        "description": ai_description,  # <--- ЗДЕСЬ ТЕПЕРЬ ИИ-ОПИСАНИЕ
        "color": get_color_for_weather(today_weather),
        "fields": [
            {
                "name": "🌡️ Температура",
                "value": f"{temp_str}°C (ощущается как {feels_str}°C)",
                "inline": True
            },
            {
                "name": "💧 Влажность",
                "value": f"{humidity}%",
                "inline": True
            },
            {
                "name": "💨 Ветер",
                "value": f"{wind} м/с",
                "inline": True
            },
            {
                "name": "🧟 Активность зомби",
                "value": activity,
                "inline": True
            },
            {
                "name": "💡 Совет выжившему",
                "value": f"*{tip}*",
                "inline": False
            }
        ],
        "footer": {
            "text": f"📅 {datetime.now(MOSCOW_TZ).strftime('%d.%m.%Y')} | Данные от Зомби-Синоптика | 🤖 Описание сгенерировано ИИ"
        }
    }
    
    return embed

def get_color_for_weather(weather):
    """Цвет рамки в зависимости от погоды"""
    colors = {
        "Солнечная": 0xFFD700,  # Золотой
        "Дождь": 0x4A90E2,      # Синий
        "Туман": 0x808080,       # Серый
        "Гроза": 0x8B0000,       # Тёмно-красный
        "Аномальная жара": 0xFF4500,  # Оранжево-красный
        "Аномальный холод": 0x1E90FF   # Голубой
    }
    return colors.get(weather, 0x5865F2)  # Цвет Discord по умолчанию

# -------------------------------------------------------------------
# 9. Отправка в Discord через вебхук
# -------------------------------------------------------------------
def send_to_discord(embed):
    if not WEBHOOK_URL:
        print("Ошибка: DISCORD_WEBHOOK_URL не найден!")
        return False
    
    data = {
        "embeds": [embed]
    }
    
    response = requests.post(WEBHOOK_URL, json=data)
    if response.status_code == 204:
        print("Сообщение успешно отправлено в Discord!")
        return True
    else:
        print(f"Ошибка: {response.status_code} - {response.text}")
        return False

# -------------------------------------------------------------------
# 10. Главная функция
# -------------------------------------------------------------------
def main():
    print("Запуск бота погоды с ИИ-генерацией...")
    
    if not GEMINI_API_KEY:
        print("ВНИМАНИЕ: GEMINI_API_KEY не найден. Будет использовано стандартное описание.")
    
    embed = build_discord_embed()
    success = send_to_discord(embed)
    
    if success:
        print("Готово! Завтра в 00:00 МСК снова пришлю погоду.")
    else:
        print("Что-то пошло не так. Проверь WEBHOOK_URL и GEMINI_API_KEY.")

if __name__ == "__main__":
    main()
