import asyncio
import base64
import binascii
import hashlib
import hmac
import json
import os
import random
import re
import time
import unicodedata
import uuid
from datetime import datetime, timedelta
from urllib.parse import parse_qsl
from zoneinfo import ZoneInfo

from adventure import (
    ADVENTURE_TASKS,
    EXPERT_MAX_LIVES,
    EXPERT_REWARD_PER_CORRECT,
    FORMULA_MAX_MISTAKES,
    FORMULA_REWARD_PER_CORRECT,
    ensure_formula_round,
    grade_solution,
    new_session,
    public_formula_state,
    public_task,
)


MOSCOW = ZoneInfo("Europe/Moscow")
DAILY_AWARDS = {
    1: ("Победитель дня", "🥇"),
    2: ("Второе место дня", "🥈"),
    3: ("Третье место дня", "🥉"),
}
MONTHLY_AWARDS = {
    1: ("Чемпион месяца", "🏆"),
    2: ("Серебряный призёр месяца", "🥈"),
    3: ("Бронзовый призёр месяца", "🥉"),
}
LOGIN_REWARDS = {1: 10, 2: 15, 3: 20, 4: 25, 5: 30}
WHEEL_DAYS = {6, 7}
WHEEL_PRIZES = (
    {"kind": "coins", "value": 5, "label": "5 монет", "weight": 16},
    {"kind": "coins", "value": 10, "label": "10 монет", "weight": 16},
    {"kind": "coins", "value": 15, "label": "15 монет", "weight": 15},
    {"kind": "coins", "value": 20, "label": "20 монет", "weight": 14},
    {"kind": "coins", "value": 50, "label": "50 монет", "weight": 7},
    {"kind": "discount", "value": 10, "label": "Скидка 10%", "weight": 14},
    {"kind": "discount", "value": 15, "label": "Скидка 15%", "weight": 10},
    {"kind": "discount", "value": 20, "label": "Скидка 20%", "weight": 8},
)
COUPON_VALID_DAYS = 30
SHOP_OWNERSHIP_DAYS = 30
SHOP_ALLOW_PERMANENT = False
BATTLE_WIN_REWARD = 10
BATTLE_DAILY_REWARD_DAYS = 7
BATTLE_MONTHLY_ITEM_DAYS = 20
BATTLE_MONTHLY_COUPON_DAYS = 30
BATTLE_DAILY_DISCOUNTS = (5, 10, 15)
BATTLE_MONTHLY_DISCOUNTS = (30, 40, 50)
BATTLE_QUESTION_SECONDS = 30
BATTLE_COUNTDOWN_SECONDS = 3
BATTLE_MISSED_ANSWER = -1
SHOP_CATALOG = (
    {"id": "guide-algebra", "name": "Карта алгебры", "description": "Короткие опорные схемы по алгебре.", "price": 1500, "department": "book", "slot": "guide", "icon": "📘"},
    {"id": "guide-geometry", "name": "Атлас геометрии", "description": "Формулы и чертежи в одной коллекции.", "price": 1500, "department": "book", "slot": "guide", "icon": "📐"},
    {"id": "guide-exam", "name": "Экзаменационный блокнот", "description": "Памятка по типичным ошибкам на экзамене.", "price": 2500, "department": "book", "slot": "guide", "icon": "📝"},
    {"id": "guide-functions", "name": "Навигатор по функциям", "description": "Графики, свойства и быстрые способы проверки.", "price": 2500, "department": "book", "slot": "guide", "icon": "📈"},
    {"id": "guide-trigonometry", "name": "Компас тригонометрии", "description": "Формулы, окружность и типовые преобразования.", "price": 2500, "department": "book", "slot": "guide", "icon": "🧭"},
    {"id": "guide-probability", "name": "Лаборатория вероятностей", "description": "Схемы событий, комбинаторика и статистика.", "price": 5000, "department": "book", "slot": "guide", "icon": "🎲"},
    {"id": "guide-stereometry", "name": "3D-атлас стереометрии", "description": "Объёмные чертежи и ключевые сечения.", "price": 5000, "department": "book", "slot": "guide", "icon": "🔷"},
    {"id": "guide-ege-pro", "name": "Архив эксперта ЕГЭ", "description": "Редкие ловушки, стратегии и разбор потери баллов.", "price": 10000, "department": "book", "slot": "guide", "icon": "🏛️"},
    {"id": "guide-master-system", "name": "Кодекс математического мастера", "description": "Премиальная система повторения всей школьной математики.", "price": 10000, "department": "book", "slot": "guide", "icon": "📜"},
    {"id": "outfit-viking", "name": "Плащ викинга", "description": "Тёплый плащ с северной застёжкой.", "price": 5000, "department": "magazine", "slot": "outfit", "icon": "🛡️"},
    {"id": "outfit-renaissance", "name": "Дублет Возрождения", "description": "Парадный костюм мастера наук.", "price": 5000, "department": "magazine", "slot": "outfit", "icon": "🧥"},
    {"id": "outfit-victorian", "name": "Викторианское пальто", "description": "Строгий образ исследователя.", "price": 10000, "department": "magazine", "slot": "outfit", "icon": "🎩"},
    {"id": "outfit-neon", "name": "Неоновый бомбер", "description": "Современная куртка с яркими вставками.", "price": 2500, "department": "magazine", "slot": "outfit", "icon": "🌈"},
    {"id": "outfit-academy", "name": "Академический жилет", "description": "Лаконичный жилет с вышитой формулой.", "price": 1500, "department": "magazine", "slot": "outfit", "icon": "🎓"},
    {"id": "outfit-denim", "name": "Джинсовая мастерская", "description": "Свободная куртка с математическими нашивками.", "price": 1500, "department": "magazine", "slot": "outfit", "icon": "🧢"},
    {"id": "outfit-varsity", "name": "Клубная куртка", "description": "Спортивный силуэт и объёмная эмблема клуба.", "price": 2500, "department": "magazine", "slot": "outfit", "icon": "🏅"},
    {"id": "outfit-cyber", "name": "Кибер-жакет", "description": "Контрастная куртка со светящимися линиями.", "price": 2500, "department": "magazine", "slot": "outfit", "icon": "⚡"},
    {"id": "outfit-samurai", "name": "Доспех учёного-самурая", "description": "Многослойная броня с геометрическим гербом.", "price": 5000, "department": "magazine", "slot": "outfit", "icon": "🥋"},
    {"id": "outfit-astronomer", "name": "Мантия астронома", "description": "Глубокий синий бархат и созвездия на ткани.", "price": 5000, "department": "magazine", "slot": "outfit", "icon": "🔭"},
    {"id": "outfit-baroque", "name": "Камзол эпохи барокко", "description": "Сложный крой, жемчужные пуговицы и золотой кант.", "price": 5000, "department": "magazine", "slot": "outfit", "icon": "👑"},
    {"id": "outfit-celestial", "name": "Мантия звёздного архитектора", "description": "Премиальный плащ с серебряными созвездиями и сапфирами.", "price": 10000, "department": "magazine", "slot": "outfit", "icon": "🌌"},
    {"id": "outfit-imperial", "name": "Императорский мундир", "description": "Бархат, золотая вышивка и парадные эполеты.", "price": 10000, "department": "magazine", "slot": "outfit", "icon": "🦅"},
    {"id": "outfit-dragon", "name": "Облачение алого дракона", "description": "Чешуйчатая броня, рубины и рельефный драконий герб.", "price": 10000, "department": "magazine", "slot": "outfit", "icon": "🐉"},
    {"id": "interior-lamp", "name": "Янтарная лампа", "description": "Уютный свет для кабинета.", "price": 1500, "department": "magazine", "slot": "interior", "icon": "🏮"},
    {"id": "interior-tea", "name": "Фарфоровый сервиз", "description": "Набор для спокойных перерывов.", "price": 2500, "department": "magazine", "slot": "interior", "icon": "🫖"},
    {"id": "interior-desk", "name": "Дубовая подставка", "description": "Настольная подставка для книг и конспектов.", "price": 1500, "department": "magazine", "slot": "interior", "icon": "🗂️"},
    {"id": "interior-globe", "name": "Глобус исследователя", "description": "Небольшой глобус в латунной оправе.", "price": 1500, "department": "magazine", "slot": "interior", "icon": "🌍"},
    {"id": "interior-telescope", "name": "Латунный телескоп", "description": "Кабинетный телескоп на резной треноге.", "price": 2500, "department": "magazine", "slot": "interior", "icon": "🔭"},
    {"id": "interior-gramophone", "name": "Винтажный граммофон", "description": "Музыкальный акцент для уютной комнаты.", "price": 2500, "department": "magazine", "slot": "interior", "icon": "📯"},
    {"id": "interior-arcade", "name": "Математический аркадный автомат", "description": "Игровой автомат с задачами на скорость.", "price": 5000, "department": "magazine", "slot": "interior", "icon": "🕹️"},
    {"id": "interior-throne", "name": "Кресло великого математика", "description": "Премиальное кресло с резьбой и формулами на спинке.", "price": 10000, "department": "magazine", "slot": "interior", "icon": "🪑"},
    {"id": "daily-victor-armor", "name": "Доспех победителя", "description": "Та самая награда за четыре победы — на 30 дней.", "price": 10000, "department": "magazine", "slot": "outfit", "icon": "⚔️"},
    {"id": "daily-victor-cape", "name": "Плащ чемпиона", "description": "Редкий плащ за пять побед — на 30 дней.", "price": 10000, "department": "magazine", "slot": "outfit", "icon": "🦸"},
    {"id": "gadget-phone", "name": "Смартфон", "description": "Персонаж держит его как настоящий гаджет.", "price": 5000, "department": "laptop", "slot": "accessory", "icon": "📱"},
    {"id": "gadget-watch", "name": "Умные часы", "description": "Яркие часы на запястье.", "price": 2500, "department": "laptop", "slot": "accessory", "icon": "⌚"},
    {"id": "gadget-tablet", "name": "Планшет", "description": "Цифровая доска для новых идей.", "price": 5000, "department": "laptop", "slot": "accessory", "icon": "💻"},
    {"id": "gadget-camera", "name": "Карманная камера", "description": "Компактная камера для лучших моментов.", "price": 1500, "department": "laptop", "slot": "accessory", "icon": "📷"},
    {"id": "gadget-stylus", "name": "Умный стилус", "description": "Световое перо для быстрых заметок.", "price": 1500, "department": "laptop", "slot": "accessory", "icon": "🖊️"},
    {"id": "gadget-projector", "name": "Карманный проектор", "description": "Проецирует формулы прямо перед персонажем.", "price": 2500, "department": "laptop", "slot": "accessory", "icon": "📽️"},
    {"id": "gadget-console", "name": "Портативная консоль", "description": "Игровая консоль в обеих руках персонажа.", "price": 5000, "department": "laptop", "slot": "accessory", "icon": "🎮"},
    {"id": "gadget-vr", "name": "AR-визор", "description": "Полупрозрачный визор дополненной реальности.", "price": 5000, "department": "laptop", "slot": "accessory", "icon": "🥽"},
    {"id": "gadget-camera-pro", "name": "Голографическая кинокамера", "description": "Премиальная камера с парящим объективом.", "price": 5000, "department": "laptop", "slot": "accessory", "icon": "🎥"},
    {"id": "gadget-fold-phone", "name": "Складной смартфон Aurora", "description": "Редкий смартфон с двумя сияющими экранами.", "price": 10000, "department": "laptop", "slot": "accessory", "icon": "📲"},
    {"id": "gadget-laptop", "name": "Голографический ноутбук", "description": "Открыт перед персонажем и удерживается одной рукой.", "price": 10000, "department": "laptop", "slot": "accessory", "icon": "🧑‍💻"},
    {"id": "gadget-glasses-classic", "name": "Очки профессора", "description": "Тонкая оправа для вдумчивого образа.", "price": 1500, "department": "laptop", "slot": "accessory", "icon": "👓"},
    {"id": "gadget-glasses-fashion", "name": "Имиджевые очки Prism", "description": "Выразительная прозрачная оправа с цветным кантом.", "price": 2500, "department": "laptop", "slot": "accessory", "icon": "👓"},
    {"id": "gadget-sunglasses", "name": "Солнцезащитные очки Eclipse", "description": "Тёмные линзы и премиальная золотая оправа.", "price": 5000, "department": "laptop", "slot": "accessory", "icon": "🕶️"},
    {"id": "headwear-cap", "name": "Кепка Math Club", "description": "Кепка с объёмной математической эмблемой.", "price": 1500, "department": "laptop", "slot": "accessory", "icon": "🧢"},
    {"id": "headwear-scarf", "name": "Шёлковый платок Aurora", "description": "Аккуратно облегает голову и завязывается сзади.", "price": 2500, "department": "laptop", "slot": "accessory", "icon": "🧣"},
    {"id": "headwear-fedora", "name": "Шляпа исследователя", "description": "Фетровая шляпа с лентой и миниатюрным гербом.", "price": 5000, "department": "laptop", "slot": "accessory", "icon": "🎩"},
    {"id": "headwear-beret", "name": "Берет художника формул", "description": "Асимметричный берет с серебряной булавкой.", "price": 5000, "department": "laptop", "slot": "accessory", "icon": "👒"},
)
DAILY_BATTLE_ITEMS = {
    4: {"id": "daily-victor-armor", "name": "Доспех победителя", "slot": "outfit", "icon": "⚔️"},
    5: {"id": "daily-victor-cape", "name": "Плащ чемпиона", "slot": "outfit", "icon": "🦸"},
}
GLOBAL_CHARACTER_KEY = "global"
CHARACTER_CATALOG = (
    {"id": "g8-neon-runner", "name": "Неоновый спринтер", "base_price": 0, "style": "neon"},
    {"id": "g8-basket-star", "name": "Баскет-звезда", "base_price": 0, "style": "basket"},
    {"id": "g8-pixel-gamer", "name": "Пиксельная геймерша", "base_price": 0, "style": "pixel"},
    {"id": "free-cozy-plaid", "name": "Тихий уют", "base_price": 0, "style": "cozy-plaid"},
    {"id": "free-pinterest", "name": "Небесный Pinterest", "base_price": 0, "style": "soft-blue"},
    {"id": "free-bronze-gent", "name": "Бронзовый джентльмен", "base_price": 0, "style": "bronze-gent"},
    {"id": "free-gym-hero", "name": "Герой зала", "base_price": 0, "style": "gym-hero"},
    {"id": "free-capy-cozy", "name": "Капибара-уют", "base_price": 2500, "style": "capy-cozy"},
    {"id": "g8-pink-wave", "name": "Розовая волна", "base_price": 2500, "style": "pink-wave"},
    {"id": "g8-white-street", "name": "Белый стрит", "base_price": 5000, "style": "white-street"},
    {"id": "g8-aqua-pop", "name": "Аква-поп", "base_price": 5000, "style": "aqua-pop"},
    {"id": "g8-turbo-bomber", "name": "Турбо-бомбер", "base_price": 10000, "style": "turbo"},
    {"id": "premium-city-white", "name": "Белый мегаполис", "base_price": 5000, "style": "city-white"},
    {"id": "premium-dog-varsity", "name": "Городская прогулка", "base_price": 5000, "style": "dog-varsity"},
    {"id": "premium-snow-dream", "name": "Снежная мечта", "base_price": 10000, "style": "snow-dream"},
    {"id": "premium-festive-forge", "name": "Праздничный кузнец", "base_price": 10000, "style": "festive-forge"},
    {"id": "premium-cardboard-bot", "name": "Картонный робот", "base_price": 10000, "style": "cardboard-bot"},
)
ADMIN_USERNAMES = {
    value.strip().lstrip("@").casefold()
    for value in os.getenv("ADMIN_USERNAMES", "supertutor15,Dany_german").split(",")
    if value.strip()
}
ADMIN_USER_IDS = {
    value.strip()
    for value in os.getenv("MINIAPP_ADMIN_IDS", "").split(",")
    if value.strip()
}
MAX_AVATAR_BYTES = 600 * 1024
BOT_WAIT_SECONDS = int(os.getenv("BATTLE_BOT_WAIT_SECONDS", "20"))
BOT_PLAYER_ID = "__math_bot__"
BOT_ANSWER_SECONDS = 5
AVATAR_TYPES = {
    "image/jpeg": ("jpg", (b"\xff\xd8\xff",)),
    "image/png": ("png", (b"\x89PNG\r\n\x1a\n",)),
    "image/webp": ("webp", (b"RIFF",)),
}


class CommunityError(ValueError):
    pass


def validate_telegram_init_data(init_data, bot_token, max_age_seconds=86400):
    if not init_data or not bot_token:
        raise CommunityError("Откройте приложение из Telegram")

    if not isinstance(init_data, str) or len(init_data) > 16384:
        raise CommunityError("Некорректная авторизация Telegram")
    pairs = parse_qsl(init_data, keep_blank_values=True)
    values = dict(pairs)
    if len(values) != len(pairs):
        raise CommunityError("Некорректная авторизация Telegram")
    received_hash = values.pop("hash", "")
    if not received_hash:
        raise CommunityError("Не удалось подтвердить Telegram-профиль")

    data_check_string = "\n".join(f"{key}={values[key]}" for key in sorted(values))
    secret = hmac.new(b"WebAppData", bot_token.encode("utf-8"), hashlib.sha256).digest()
    calculated_hash = hmac.new(secret, data_check_string.encode("utf-8"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(received_hash, calculated_hash):
        raise CommunityError("Не удалось подтвердить Telegram-профиль")

    try:
        auth_date = int(values.get("auth_date", "0"))
    except ValueError as error:
        raise CommunityError("Некорректная дата авторизации Telegram") from error
    age = time.time() - auth_date
    if auth_date <= 0 or age < -60 or age > max_age_seconds:
        raise CommunityError("Сессия Telegram устарела. Откройте приложение заново")

    try:
        user = json.loads(values.get("user", "{}"))
    except json.JSONDecodeError as error:
        raise CommunityError("Некорректный Telegram-профиль") from error
    if (not isinstance(user, dict) or type(user.get("id")) is not int
            or not 0 < user["id"] < 2**52
            or user.get("is_bot", False) is not False
            or "type" in user):
        raise CommunityError("Войдите с личного аккаунта Telegram, не от имени канала или бота")
    return user


_CONFUSABLES = str.maketrans({
    "0": "o", "1": "i", "3": "e", "4": "a", "5": "s", "6": "b", "@": "a",
    "а": "a", "е": "e", "ё": "e", "о": "o", "р": "p", "с": "c", "у": "y", "х": "x",
})
_FORBIDDEN = {
    "admin", "administrator", "support", "moderator", "teacher", "supertutor",
    "fuck", "fucker", "fucking", "shit", "bitch", "cunt", "dick", "nigger", "nigga",
    "хуй", "хуе", "пизд", "еба", "ебл", "бляд", "блят", "сука", "мудак", "гандон",
}


def validate_nickname(value):
    nickname = unicodedata.normalize("NFKC", str(value or "")).strip()
    if not 3 <= len(nickname) <= 24:
        raise CommunityError("Никнейм должен содержать от 3 до 24 символов")
    if not re.fullmatch(r"[A-Za-zА-Яа-яЁё0-9 _-]+", nickname):
        raise CommunityError("Используйте только буквы, цифры, пробел, _ или -")

    folded = nickname.casefold().replace("ё", "е")
    compact = re.sub(r"[\W_]+", "", folded, flags=re.UNICODE)
    squeezed = re.sub(r"(.)\1{2,}", r"\1\1", compact)
    latinised = squeezed.translate(_CONFUSABLES)
    candidates = {folded, compact, squeezed, latinised}
    if any(word in candidate for word in _FORBIDDEN for candidate in candidates):
        raise CommunityError("Этот никнейм нельзя использовать. Попробуйте другой")
    return nickname


def validate_message_text(value):
    message = unicodedata.normalize("NFKC", str(value or "")).strip()
    message = "\n".join(line.strip() for line in message.splitlines())
    message = re.sub(r"\n{3,}", "\n\n", message)
    if not message:
        raise CommunityError("Введите сообщение")
    if len(message) > 500:
        raise CommunityError("Сообщение должно быть не длиннее 500 символов")
    if any(unicodedata.category(char) == "Cc" and char not in "\n\t" for char in message):
        raise CommunityError("Сообщение содержит недопустимые символы")

    folded = message.casefold().replace("ё", "е")
    compact = re.sub(r"[\W_]+", "", folded, flags=re.UNICODE)
    latinised = compact.translate(_CONFUSABLES)
    if any(word in candidate for word in _FORBIDDEN for candidate in (folded, compact, latinised)):
        raise CommunityError("Сообщение не прошло проверку. Уберите оскорбительные слова")
    return message


def decode_avatar_data_url(value):
    match = re.fullmatch(
        r"data:(image/(?:jpeg|png|webp));base64,([A-Za-z0-9+/=\r\n]+)",
        str(value or ""),
    )
    if not match:
        raise CommunityError("Аватарка должна быть изображением JPG, PNG или WebP")
    mime_type, encoded = match.groups()
    try:
        payload = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError) as error:
        raise CommunityError("Не удалось прочитать изображение") from error
    if not payload or len(payload) > MAX_AVATAR_BYTES:
        raise CommunityError("Размер готовой аватарки должен быть не больше 600 КБ")
    extension, signatures = AVATAR_TYPES[mime_type]
    valid_signature = any(payload.startswith(signature) for signature in signatures)
    if mime_type == "image/webp":
        valid_signature = valid_signature and len(payload) >= 12 and payload[8:12] == b"WEBP"
    if not valid_signature:
        raise CommunityError("Содержимое файла не соответствует формату изображения")
    return extension, payload


def _now_iso():
    return datetime.now(MOSCOW).isoformat()


def _default_data():
    return {
        "version": 4,
        "profiles": {},
        "attempts": [],
        "awards": [],
        "battles": {},
        "friendships": [],
        "blocks": [],
        "messages": [],
        "battle_invites": [],
        "coin_transactions": [],
        "enrollments": [],
        "adventures": {},
    }


class CommunityStore:
    def __init__(self, path):
        self.path = path
        self.avatar_directory = os.path.join(os.path.dirname(path) or ".", "avatars")
        self.solution_directory = os.path.join(os.path.dirname(path) or ".", "solutions")
        self.material_directory = os.path.join(os.path.dirname(path) or ".", "materials")
        self.lock = asyncio.Lock()

    def _load(self):
        if not os.path.exists(self.path):
            return _default_data()
        with open(self.path, "r", encoding="utf-8") as source:
            data = json.load(source)
        default = _default_data()
        for key, value in default.items():
            data.setdefault(key, value)
        data["version"] = default["version"]
        seen_public_ids = set()
        for profile in data["profiles"].values():
            public_id = str(profile.get("public_id") or "")
            if not re.fullmatch(r"[a-f0-9]{12}", public_id) or public_id in seen_public_ids:
                public_id = uuid.uuid4().hex[:12]
                while public_id in seen_public_ids:
                    public_id = uuid.uuid4().hex[:12]
                profile["public_id"] = public_id
            seen_public_ids.add(public_id)
        return data

    def _save(self, data):
        directory = os.path.dirname(self.path) or "."
        os.makedirs(directory, exist_ok=True)
        temporary_path = f"{self.path}.tmp"
        descriptor = os.open(temporary_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as target:
            json.dump(data, target, ensure_ascii=False, indent=2)
        os.replace(temporary_path, self.path)

    @staticmethod
    def _user_id(user):
        return str(user["id"])

    @staticmethod
    def _is_admin(user):
        username = str(user.get("username") or "").lstrip("@").casefold()
        return str(user.get("id")) in ADMIN_USER_IDS or username in ADMIN_USERNAMES

    @staticmethod
    def _default_nickname(user):
        if user.get("username"):
            return str(user["username"])[:24]
        return str(user.get("first_name") or "Участник")[:24]

    def _ensure_profile(self, data, user):
        user_id = self._user_id(user)
        profile = data["profiles"].setdefault(user_id, {
            "nickname": self._default_nickname(user),
            "avatar_url": user.get("photo_url", ""),
            "avatar_source": "telegram",
            "telegram_avatar_url": user.get("photo_url", ""),
            "telegram_username": user.get("username", ""),
            "leaderboard_consent": False,
            "grade": None,
            "public_id": uuid.uuid4().hex[:12],
            "coins": 0,
            "login_streak": 0,
            "last_login_date": None,
            "selected_characters": {},
            "unlocked_characters": {},
            "character_prices": {},
            "shop_purchases": {},
            "material_orders": {},
            "equipped_items": {},
            "temporary_items": {},
            "discount_coupons": [],
            "wheel_claims": {},
            "battle_daily_claims": {},
            "battle_monthly_claims": {},
            "updated_at": _now_iso(),
        })
        profile.setdefault("public_id", uuid.uuid4().hex[:12])
        profile.setdefault("avatar_source", "telegram")
        profile.setdefault("allow_friend_requests", True)
        profile.setdefault("coins", 0)
        profile.setdefault("login_streak", 0)
        profile.setdefault("last_login_date", None)
        profile.setdefault("selected_characters", {})
        profile.setdefault("unlocked_characters", {})
        profile.setdefault("character_prices", {})
        profile.setdefault("shop_purchases", {})
        profile.setdefault("material_orders", {})
        profile.setdefault("equipped_items", {})
        profile.setdefault("temporary_items", {})
        profile.setdefault("discount_coupons", [])
        profile.setdefault("wheel_claims", {})
        profile.setdefault("battle_daily_claims", {})
        profile.setdefault("battle_monthly_claims", {})
        self._cleanup_inventory(profile)
        self._migrate_global_characters(profile)
        profile["telegram_avatar_url"] = user.get("photo_url", profile.get("telegram_avatar_url", ""))
        profile["telegram_username"] = user.get("username", profile.get("telegram_username", ""))
        if user.get("photo_url") and profile.get("avatar_source") != "custom":
            profile["avatar_url"] = user["photo_url"]
        return profile

    def _balance_payload(self, profile, user):
        return {
            "coins": int(profile.get("coins") or 0),
            "admin": self._is_admin(user),
        }

    def _material_path(self, item_id):
        if not re.fullmatch(r"guide-[a-z0-9-]+", str(item_id or "")):
            return None
        path = os.path.join(self.material_directory, f"{item_id}.pdf")
        return path if os.path.isfile(path) else None

    def _profile_materials(self, data, user_id, profile):
        purchases = profile.get("shop_purchases", {})
        orders = profile.setdefault("material_orders", {})
        result = []
        for item in SHOP_CATALOG:
            if item.get("slot") != "guide" or item["id"] not in purchases:
                continue
            order = orders.get(item["id"], {})
            purchased_at = order.get("purchased_at")
            if not purchased_at:
                transaction = next((
                    transaction for transaction in reversed(data.get("coin_transactions", []))
                    if transaction.get("user_id") == user_id
                    and transaction.get("item_id") == item["id"]
                    and transaction.get("kind") == "shop_purchase"
                ), None)
                purchased_at = (transaction or {}).get("created_at")
            if not purchased_at:
                try:
                    purchased_at = (
                        datetime.fromisoformat(purchases[item["id"]]).astimezone(MOSCOW)
                        - timedelta(days=SHOP_OWNERSHIP_DAYS)
                    ).isoformat()
                except (TypeError, ValueError):
                    purchased_at = profile.get("updated_at") or _now_iso()
            orders[item["id"]] = {"purchased_at": purchased_at}
            try:
                contact_after = datetime.fromisoformat(purchased_at).astimezone(MOSCOW) + timedelta(days=2)
            except (TypeError, ValueError):
                contact_after = datetime.now(MOSCOW) + timedelta(days=2)
            available = bool(self._material_path(item["id"]))
            result.append({
                "id": item["id"],
                "name": item["name"],
                "description": item["description"],
                "icon": item["icon"],
                "ownedUntil": purchases[item["id"]],
                "purchasedAt": purchased_at,
                "available": available,
                "contactAfter": contact_after.isoformat(),
                "contactAvailable": not available and datetime.now(MOSCOW) >= contact_after,
            })
        return result

    async def material_access(self, user, item_id):
        async with self.lock:
            data = self._load()
            profile = self._ensure_profile(data, user)
            item = next((item for item in SHOP_CATALOG if item["id"] == item_id and item.get("slot") == "guide"), None)
            if not item or item_id not in profile.get("shop_purchases", {}):
                raise CommunityError("Материал не приобретён или срок доступа завершён")
            path = self._material_path(item_id)
            if not path:
                raise CommunityError("Файл пока готовится")
            self._save(data)
            return {"path": path, "name": item["name"]}

    @staticmethod
    def _next_midnight_iso():
        now = datetime.now(MOSCOW)
        return datetime.combine(now.date() + timedelta(days=1), datetime.min.time(), tzinfo=MOSCOW).isoformat()

    @staticmethod
    def _is_active_until(value):
        try:
            return datetime.fromisoformat(str(value)).astimezone(MOSCOW) > datetime.now(MOSCOW)
        except (TypeError, ValueError):
            return False

    def _cleanup_inventory(self, profile):
        purchases = profile.setdefault("shop_purchases", {})
        temporary = profile.setdefault("temporary_items", {})
        equipped = profile.setdefault("equipped_items", {})
        active_purchases = {item_id: value for item_id, value in purchases.items() if self._is_active_until(value)}
        active_temporary = {item_id: value for item_id, value in temporary.items() if self._is_active_until(value)}
        profile["shop_purchases"] = active_purchases
        profile["temporary_items"] = active_temporary
        active_ids = set(active_purchases) | set(active_temporary)
        profile["equipped_items"] = {
            slot: item_id for slot, item_id in equipped.items() if item_id in active_ids
        }
        now = datetime.now(MOSCOW)
        profile["discount_coupons"] = [
            coupon for coupon in profile.setdefault("discount_coupons", [])
            if not coupon.get("used")
            and self._is_active_until(coupon.get("expires_at"))
        ]

    @staticmethod
    def _shop_expiry(ownership="monthly"):
        if ownership == "permanent":
            if not SHOP_ALLOW_PERMANENT:
                raise CommunityError("Постоянные покупки пока недоступны")
            return datetime(9999, 12, 31, tzinfo=MOSCOW).isoformat()
        return (datetime.now(MOSCOW) + timedelta(days=SHOP_OWNERSHIP_DAYS)).isoformat()

    def _delete_custom_avatar(self, profile):
        if profile.get("avatar_source") != "custom":
            return
        filename = os.path.basename(str(profile.get("avatar_url") or ""))
        if re.fullmatch(r"[a-f0-9]{32}\.(?:jpg|png|webp)", filename):
            try:
                os.remove(os.path.join(self.avatar_directory, filename))
            except FileNotFoundError:
                pass

    def _store_custom_avatar(self, profile, data_url):
        extension, payload = decode_avatar_data_url(data_url)
        os.makedirs(self.avatar_directory, exist_ok=True)
        filename = f"{uuid.uuid4().hex}.{extension}"
        final_path = os.path.join(self.avatar_directory, filename)
        temporary_path = f"{final_path}.tmp"
        with open(temporary_path, "wb") as target:
            target.write(payload)
        os.replace(temporary_path, final_path)
        self._delete_custom_avatar(profile)
        profile["avatar_url"] = f"/avatars/{filename}"
        profile["avatar_source"] = "custom"

    async def get_profile(self, user):
        async with self.lock:
            data = self._load()
            profile = self._ensure_profile(data, user)
            self._finalise_awards(data)
            materials = self._profile_materials(data, self._user_id(user), profile)
            result = {
                **profile,
                "awards": [award for award in data["awards"] if award["user_id"] == self._user_id(user)],
                "materials": materials,
            }
            self._save(data)
            result.update(self._balance_payload(profile, user))
            return result

    async def update_profile(self, user, payload):
        async with self.lock:
            data = self._load()
            profile = self._ensure_profile(data, user)
            if "nickname" in payload:
                profile["nickname"] = validate_nickname(payload["nickname"])
            if "leaderboardConsent" in payload:
                profile["leaderboard_consent"] = bool(payload["leaderboardConsent"])
            if "allowFriendRequests" in payload:
                if type(payload["allowFriendRequests"]) is not bool:
                    raise CommunityError("Некорректная настройка заявок")
                profile["allow_friend_requests"] = payload["allowFriendRequests"]
            if payload.get("grade") is not None:
                grade = int(payload["grade"])
                if grade not in {8, 9, 10, 11}:
                    raise CommunityError("Выберите класс от 8 до 11")
                profile["grade"] = grade
            if payload.get("avatarDataUrl"):
                self._store_custom_avatar(profile, payload["avatarDataUrl"])
            elif payload.get("useTelegramAvatar"):
                self._delete_custom_avatar(profile)
                profile["avatar_source"] = "telegram"
                profile["avatar_url"] = user.get("photo_url", "")
            profile["updated_at"] = _now_iso()
            materials = self._profile_materials(data, self._user_id(user), profile)
            result = {
                **profile,
                "awards": [a for a in data["awards"] if a["user_id"] == self._user_id(user)],
                "materials": materials,
            }
            self._save(data)
            result.update(self._balance_payload(profile, user))
            return result

    @staticmethod
    def _migrate_global_characters(profile):
        available_ids = {item["id"] for item in CHARACTER_CATALOG}
        selected_map = profile["selected_characters"]
        unlocked_map = profile["unlocked_characters"]
        selected = selected_map.get(GLOBAL_CHARACTER_KEY)
        if selected not in available_ids:
            legacy_candidates = [selected_map.get("8"), selected_map.get(str(profile.get("grade")))]
            selected = next((item for item in legacy_candidates if item in available_ids), None)
            if selected:
                selected_map[GLOBAL_CHARACTER_KEY] = selected
        migrated_unlocks = set(unlocked_map.get(GLOBAL_CHARACTER_KEY, []))
        for legacy_unlocks in unlocked_map.values():
            if isinstance(legacy_unlocks, list):
                migrated_unlocks.update(item for item in legacy_unlocks if item in available_ids)
        unlocked_map[GLOBAL_CHARACTER_KEY] = sorted(migrated_unlocks)

    def _ensure_character_selection(self, profile, catalog):
        grade_key = GLOBAL_CHARACTER_KEY
        available_ids = {item["id"] for item in catalog}
        free_ids = {item["id"] for item in catalog if int(item.get("base_price") or 0) == 0}
        unlocked = profile["unlocked_characters"].setdefault(grade_key, [])
        if not free_ids.issubset(unlocked):
            unlocked[:] = sorted(set(unlocked) | free_ids)
        selected = profile["selected_characters"].get(grade_key)
        if selected not in available_ids:
            selected = catalog[0]["id"] if catalog else None
            if selected:
                profile["selected_characters"][grade_key] = selected
                if selected not in unlocked:
                    unlocked.append(selected)
        elif selected not in unlocked:
            # Сохраняем уже выбранного персонажа у существующих пользователей после смены цен.
            unlocked.append(selected)
        return selected

    def _daily_login_payload(self, profile, user):
        today_key = datetime.now(MOSCOW).date().isoformat()
        claimed_today = profile.get("last_login_date") == today_key
        current_streak = int(profile.get("login_streak") or 0)
        next_day = current_streak if claimed_today else 1
        if not claimed_today and profile.get("last_login_date"):
            try:
                last_date = datetime.fromisoformat(profile["last_login_date"]).date()
                if last_date == datetime.now(MOSCOW).date() - timedelta(days=1):
                    next_day = (current_streak % 7) + 1
            except ValueError:
                pass
        active_day = max(1, min(7, current_streak if claimed_today else next_day))
        wheel_claim = profile.get("wheel_claims", {}).get(today_key)
        result = {
            "claimedToday": claimed_today,
            "streak": current_streak,
            "activeDay": active_day,
            "activeReward": LOGIN_REWARDS.get(active_day, 0),
            "activeKind": "wheel" if active_day in WHEEL_DAYS else "coins",
            "schedule": [
                {"day": day, "reward": LOGIN_REWARDS.get(day, 0), "kind": "wheel" if day in WHEEL_DAYS else "coins"}
                for day in range(1, 8)
            ],
            "wheelAvailable": claimed_today and active_day in WHEEL_DAYS and not wheel_claim,
            "wheelClaimed": bool(wheel_claim),
            "wheelPrize": wheel_claim,
        }
        result.update(self._balance_payload(profile, user))
        return result

    async def daily_login_status(self, user):
        async with self.lock:
            data = self._load()
            profile = self._ensure_profile(data, user)
            self._save(data)
            return self._daily_login_payload(profile, user)

    async def claim_daily_login(self, user):
        async with self.lock:
            data = self._load()
            user_id = self._user_id(user)
            profile = self._ensure_profile(data, user)
            today = datetime.now(MOSCOW).date()
            today_key = today.isoformat()
            if profile.get("last_login_date") == today_key:
                self._save(data)
                result = {
                    "claimed": False,
                    "reward": 0,
                    "streak": int(profile.get("login_streak") or 0),
                    "coins": int(profile.get("coins") or 0),
                }
                result.update(self._daily_login_payload(profile, user))
                return result

            is_consecutive = False
            if profile.get("last_login_date"):
                try:
                    last_date = datetime.fromisoformat(profile["last_login_date"]).date()
                    is_consecutive = last_date == today - timedelta(days=1)
                except ValueError:
                    pass
            previous = int(profile.get("login_streak") or 0)
            streak = (previous % 7) + 1 if is_consecutive else 1
            reward = LOGIN_REWARDS.get(streak, 0)
            profile["login_streak"] = streak
            profile["last_login_date"] = today_key
            if reward:
                profile["coins"] = int(profile.get("coins") or 0) + reward
            profile["updated_at"] = _now_iso()
            if reward:
                data["coin_transactions"].append({
                    "id": f"login:{user_id}:{today_key}",
                    "user_id": user_id,
                    "amount": reward,
                    "kind": "daily_login",
                    "created_at": _now_iso(),
                })
            self._save(data)
            result = {"claimed": True, "reward": reward, "streak": streak, "coins": profile["coins"]}
            result.update(self._daily_login_payload(profile, user))
            return result

    async def spin_daily_wheel(self, user):
        async with self.lock:
            data = self._load()
            user_id = self._user_id(user)
            profile = self._ensure_profile(data, user)
            today_key = datetime.now(MOSCOW).date().isoformat()
            if profile.get("last_login_date") != today_key or int(profile.get("login_streak") or 0) not in WHEEL_DAYS:
                raise CommunityError("Барабан открывается после получения награды 6-го или 7-го дня")
            if profile["wheel_claims"].get(today_key):
                raise CommunityError("Сегодня барабан уже был прокручен")
            prize = random.SystemRandom().choices(
                WHEEL_PRIZES,
                weights=[item["weight"] for item in WHEEL_PRIZES],
                k=1,
            )[0]
            stored_prize = {key: prize[key] for key in ("kind", "value", "label")}
            if prize["kind"] == "coins":
                profile["coins"] = int(profile.get("coins") or 0) + int(prize["value"])
                data["coin_transactions"].append({
                    "id": f"wheel:{user_id}:{today_key}",
                    "user_id": user_id,
                    "amount": int(prize["value"]),
                    "kind": "daily_wheel",
                    "created_at": _now_iso(),
                })
            else:
                coupon = {
                    "id": uuid.uuid4().hex[:12],
                    "percent": int(prize["value"]),
                    "created_at": _now_iso(),
                    "expires_at": (datetime.now(MOSCOW) + timedelta(days=COUPON_VALID_DAYS)).isoformat(),
                    "used": False,
                }
                profile["discount_coupons"].append(coupon)
                stored_prize["couponId"] = coupon["id"]
                stored_prize["expiresAt"] = coupon["expires_at"]
            profile["wheel_claims"][today_key] = stored_prize
            profile["updated_at"] = _now_iso()
            payload = self._daily_login_payload(profile, user)
            payload.update({"spun": True, "prize": stored_prize})
            self._save(data)
            return payload

    def _shop_payload(self, profile, user):
        self._cleanup_inventory(profile)
        purchases = profile.get("shop_purchases", {})
        temporary = profile.get("temporary_items", {})
        equipped = profile.get("equipped_items", {})
        coupons = sorted(
            profile.get("discount_coupons", []),
            key=lambda coupon: int(coupon.get("percent") or 0),
            reverse=True,
        )
        best_discount = int(coupons[0]["percent"]) if coupons else 0
        catalog = []
        for item in SHOP_CATALOG:
            owned_until = purchases.get(item["id"])
            catalog.append({
                **item,
                "discountedPrice": max(1, round(int(item["price"]) * (100 - best_discount) / 100)) if best_discount else int(item["price"]),
                "owned": bool(owned_until),
                "ownedUntil": owned_until,
                "equipped": equipped.get(item["slot"]) == item["id"],
            })
        temporary_by_id = {item["id"]: item for item in DAILY_BATTLE_ITEMS.values()}
        temporary_items = [{
            **temporary_by_id[item_id],
            "owned": True,
            "ownedUntil": expires_at,
            "equipped": equipped.get(temporary_by_id[item_id]["slot"]) == item_id,
            "temporary": True,
        } for item_id, expires_at in temporary.items() if item_id in temporary_by_id]
        result = {
            "ownershipDays": SHOP_OWNERSHIP_DAYS,
            "items": catalog,
            "temporaryItems": temporary_items,
            "equippedItems": dict(equipped),
            "coupons": coupons,
            "bestDiscount": best_discount,
        }
        result.update(self._balance_payload(profile, user))
        return result

    async def shop_catalog(self, user):
        async with self.lock:
            data = self._load()
            profile = self._ensure_profile(data, user)
            payload = self._shop_payload(profile, user)
            self._save(data)
            return payload

    async def purchase_shop_item(self, user, item_id):
        item = next((item for item in SHOP_CATALOG if item["id"] == item_id), None)
        if not item:
            raise CommunityError("Товар не найден")
        async with self.lock:
            data = self._load()
            user_id = self._user_id(user)
            profile = self._ensure_profile(data, user)
            if item_id in profile["shop_purchases"]:
                raise CommunityError("Этот предмет уже приобретён на 30 дней")
            balance = int(profile.get("coins") or 0)
            coupons = sorted(
                profile.get("discount_coupons", []),
                key=lambda coupon: int(coupon.get("percent") or 0),
                reverse=True,
            )
            coupon = coupons[0] if coupons else None
            discount = int(coupon.get("percent") or 0) if coupon else 0
            price = max(1, round(int(item["price"]) * (100 - discount) / 100))
            is_admin = self._is_admin(user)
            if not is_admin and balance < price:
                raise CommunityError(f"Не хватает {price - balance} монет")
            if not is_admin:
                profile["coins"] = balance - price
            if coupon:
                coupon["used"] = True
            expires_at = self._shop_expiry("monthly")
            profile["shop_purchases"][item_id] = expires_at
            if item.get("slot") == "guide":
                profile.setdefault("material_orders", {})[item_id] = {"purchased_at": _now_iso()}
            profile["updated_at"] = _now_iso()
            data["coin_transactions"].append({
                "id": f"shop:{user_id}:{item_id}:{uuid.uuid4().hex[:8]}",
                "user_id": user_id,
                "amount": 0 if is_admin else -price,
                "kind": "shop_purchase",
                "item_id": item_id,
                "discount": discount,
                "admin_purchase": is_admin,
                "created_at": _now_iso(),
            })
            payload = self._shop_payload(profile, user)
            payload.update({
                "purchased": True,
                "itemId": item_id,
                "paid": 0 if is_admin else price,
                "discountApplied": discount,
                "purchasedItem": {
                    "id": item["id"],
                    "name": item["name"],
                    "slot": item["slot"],
                    "icon": item["icon"],
                    "ownedUntil": expires_at,
                },
            })
            self._save(data)
            return payload

    async def equip_shop_item(self, user, item_id, remove=False):
        async with self.lock:
            data = self._load()
            profile = self._ensure_profile(data, user)
            all_items = {item["id"]: item for item in SHOP_CATALOG}
            all_items.update({item["id"]: item for item in DAILY_BATTLE_ITEMS.values()})
            item = all_items.get(item_id)
            if not item:
                raise CommunityError("Предмет не найден")
            owned = item_id in profile["shop_purchases"] or item_id in profile["temporary_items"]
            if not owned:
                raise CommunityError("Сначала приобретите этот предмет")
            if remove:
                if profile["equipped_items"].get(item["slot"]) == item_id:
                    profile["equipped_items"].pop(item["slot"], None)
            else:
                profile["equipped_items"][item["slot"]] = item_id
            profile["updated_at"] = _now_iso()
            payload = self._shop_payload(profile, user)
            self._save(data)
            return payload

    async def award_training_coins(self, user, attempt_key):
        attempt_key = str(attempt_key or "").strip()
        if not re.fullmatch(r"[A-Za-z0-9:_-]{8,160}", attempt_key):
            raise CommunityError("Некорректный идентификатор тренировки")
        async with self.lock:
            data = self._load()
            user_id = self._user_id(user)
            profile = self._ensure_profile(data, user)
            transaction_id = f"training:{user_id}:{attempt_key}"
            if any(item.get("id") == transaction_id for item in data["coin_transactions"]):
                return {"awarded": 0, "coins": int(profile.get("coins") or 0), "reason": "duplicate"}
            reward = 10
            profile["coins"] = int(profile.get("coins") or 0) + reward
            data["coin_transactions"].append({
                "id": transaction_id,
                "user_id": user_id,
                "amount": reward,
                "kind": "training",
                "created_at": _now_iso(),
            })
            profile["updated_at"] = _now_iso()
            self._save(data)
            result = {"awarded": reward}
            result.update(self._balance_payload(profile, user))
            return result

    async def character_catalog(self, user):
        catalog = CHARACTER_CATALOG
        async with self.lock:
            data = self._load()
            profile = self._ensure_profile(data, user)
            selected = self._ensure_character_selection(profile, catalog)
            unlocked = set(profile["unlocked_characters"].get(GLOBAL_CHARACTER_KEY, []))
            self._save(data)
            result = {
                "selectedId": selected,
                "characters": [{
                    "id": item["id"],
                    "name": item["name"],
                    "style": item["style"],
                    "price": int(item["base_price"]),
                    "category": "basic" if item["base_price"] <= 2500 else "premium",
                    "owned": int(item["base_price"]) == 0 or item["id"] in unlocked,
                    "selected": item["id"] == selected,
                } for item in catalog],
            }
            result.update(self._balance_payload(profile, user))
            return result

    async def select_character(self, user, character_id):
        catalog = CHARACTER_CATALOG
        character = next((item for item in catalog if item["id"] == character_id), None)
        if not character:
            raise CommunityError("Персонаж не найден")
        async with self.lock:
            data = self._load()
            profile = self._ensure_profile(data, user)
            unlocked = set(profile["unlocked_characters"].get(GLOBAL_CHARACTER_KEY, []))
            if character["base_price"] > 0 and character_id not in unlocked:
                raise CommunityError("Сначала откройте этого персонажа")
            profile["selected_characters"][GLOBAL_CHARACTER_KEY] = character_id
            profile["updated_at"] = _now_iso()
            self._save(data)
            result = {"selectedId": character_id}
            result.update(self._balance_payload(profile, user))
            return result

    async def purchase_character(self, user, character_id):
        catalog = CHARACTER_CATALOG
        character = next((item for item in catalog if item["id"] == character_id), None)
        if not character or character["base_price"] == 0:
            raise CommunityError("Этот персонаж доступен бесплатно")
        async with self.lock:
            data = self._load()
            user_id = self._user_id(user)
            profile = self._ensure_profile(data, user)
            grade_key = GLOBAL_CHARACTER_KEY
            price = int(character["base_price"])
            unlocked = set(profile["unlocked_characters"].get(grade_key, []))
            if character_id in unlocked:
                profile["selected_characters"][grade_key] = character_id
                self._save(data)
                return {"selectedId": character_id, "coins": int(profile.get("coins") or 0), "purchased": False}
            balance = int(profile.get("coins") or 0)
            is_admin = self._is_admin(user)
            if not is_admin and balance < price:
                raise CommunityError(f"Не хватает {price - balance} монет")
            if not is_admin:
                profile["coins"] = balance - price
            unlocked.add(character_id)
            profile["unlocked_characters"][grade_key] = sorted(unlocked)
            profile["selected_characters"][grade_key] = character_id
            profile["updated_at"] = _now_iso()
            data["coin_transactions"].append({
                "id": uuid.uuid4().hex[:16],
                "user_id": user_id,
                "amount": 0 if is_admin else -price,
                "kind": "character_purchase",
                "character_id": character_id,
                "catalog": GLOBAL_CHARACTER_KEY,
                "admin_purchase": is_admin,
                "created_at": _now_iso(),
            })
            self._save(data)
            result = {"selectedId": character_id, "purchased": True}
            result.update(self._balance_payload(profile, user))
            return result

    def avatar_path(self, filename):
        if not re.fullmatch(r"[a-f0-9]{32}\.(?:jpg|png|webp)", str(filename or "")):
            return None
        path = os.path.join(self.avatar_directory, filename)
        return path if os.path.isfile(path) else None

    async def record_attempt(self, user, payload, points=10, source="practice"):
        async with self.lock:
            data = self._load()
            profile = self._ensure_profile(data, user)
            question_id = str(payload.get("questionId") or "")
            grade = int(payload.get("grade") or profile.get("grade") or 0)
            if grade not in {8, 9, 10, 11}:
                raise CommunityError("Некорректный класс")
            profile["grade"] = grade
            is_correct = bool(payload.get("isCorrect"))
            attempt_key = str(payload.get("attemptKey") or uuid.uuid4().hex)
            if any(
                item.get("attempt_key") == attempt_key
                and item.get("question_id") == question_id
                for item in data["attempts"]
            ):
                return {"saved": False, "reason": "duplicate"}
            today = datetime.now(MOSCOW).strftime("%Y-%m-%d")
            if question_id and any(
                item.get("user_id") == self._user_id(user)
                and item.get("question_id") == question_id
                and item.get("source") == source
                and self._period_key(item["created_at"], "day") == today
                for item in data["attempts"]
            ):
                return {"saved": False, "reason": "question_already_scored_today"}
            data["attempts"].append({
                "attempt_key": attempt_key,
                "user_id": self._user_id(user),
                "question_id": question_id,
                "grade": grade,
                "correct": is_correct,
                "points": points if is_correct else 0,
                "source": source,
                "created_at": _now_iso(),
            })
            self._save(data)
            return {"saved": True}

    def _store_solution_image(self, data_url, prefix):
        if not data_url:
            return ""
        extension, payload = decode_avatar_data_url(data_url)
        os.makedirs(self.solution_directory, exist_ok=True)
        filename = f"{prefix}-{uuid.uuid4().hex}.{extension}"
        path = os.path.join(self.solution_directory, filename)
        with open(path, "wb") as target:
            target.write(payload)
        return filename

    def _adventure_view(self, session):
        if not session.get("game"):
            session["game"] = "tower" if session.get("stage") in {"crystals", "formula"} else "second_part"
        if session["game"] == "tower" and session.get("status") == "active":
            ensure_formula_round(session)
        result = {
            "id": session["id"],
            "grade": session["grade"],
            "game": session["game"],
            "stage": session["stage"],
            "status": session["status"],
            "updatedAt": session.get("updated_at"),
            "task": public_task(session.get("task") or session["grade"]),
        }
        if session["game"] == "tower":
            result["formula"] = public_formula_state(session)
        if session["game"] == "expert":
            result["expert"] = {
                "taskNumber": int((session.get("task") or {}).get("taskNumber") or 13),
                "index": int(session.get("expert_index") or 0),
                "total": len(session.get("expert_tasks") or [session.get("task")]),
                "lives": int(session.get("expert_lives") or 0),
                "maxLives": EXPERT_MAX_LIVES,
                "correct": int(session.get("expert_correct") or 0),
                "errors": int(session.get("expert_errors") or 0),
                "rewardCoins": int(session.get("expert_reward_coins") or 0),
                "rewardPerCorrect": EXPERT_REWARD_PER_CORRECT,
                "adminUnlimited": bool(session.get("admin_unlimited")),
            }
        if session.get("result"):
            result["result"] = session["result"]
        if session.get("draft"):
            result["draft"] = session["draft"]
        return result

    async def get_adventure(self, user, grade):
        grade = int(grade)
        if grade not in ADVENTURE_TASKS:
            raise CommunityError("Некорректный класс")
        async with self.lock:
            data = self._load()
            user_id = self._user_id(user)
            sessions = [
                session for session in data["adventures"].values()
                if session.get("user_id") == user_id
                and int(session.get("grade") or 0) == grade
                and session.get("status") == "active"
            ]
            if not sessions:
                return {"active": False}
            session = max(sessions, key=lambda item: item.get("updated_at") or "")
            return {"active": True, "session": self._adventure_view(session)}

    async def adventure_history(self, user, grade=None):
        requested_grade = int(grade or 0)
        if requested_grade and requested_grade not in ADVENTURE_TASKS:
            raise CommunityError("Некорректный класс")
        async with self.lock:
            data = self._load()
            user_id = self._user_id(user)
            sessions = [
                session for session in data["adventures"].values()
                if session.get("user_id") == user_id
                and session.get("status") == "complete"
                and (not requested_grade or int(session.get("grade") or 0) == requested_grade)
            ]
            sessions.sort(key=lambda item: item.get("updated_at") or "", reverse=True)
            return [{
                "id": f"adventure:{session['id']}",
                "grade": int(session["grade"]),
                "createdAt": session.get("updated_at"),
                "total": int((session.get("result") or {}).get("maxScore") or 2),
                "correct": int((session.get("result") or {}).get("score") or 0),
                "topics": [
                    "Формулы" if session.get("game") == "tower"
                    else "Экспертная оценка" if session.get("game") == "expert"
                    else "Вторая часть"
                ],
                "kind": "extended",
            } for session in sessions[:30]]

    async def used_adventure_task_ids(self, user, grade, attempt_key):
        grade = int(grade)
        if grade not in ADVENTURE_TASKS:
            raise CommunityError("Некорректный класс")
        round_key = str(attempt_key or "").strip()
        if not round_key:
            return set()
        async with self.lock:
            data = self._load()
            user_id = self._user_id(user)
            return {
                str((session.get("task") or {}).get("id") or "")
                for session in data["adventures"].values()
                if session.get("user_id") == user_id
                and int(session.get("grade") or 0) == grade
                and session.get("attempt_key") == round_key
                and (session.get("task") or {}).get("id")
            }

    async def start_adventure(self, user, grade, attempt_key, task=None, game="tower"):
        grade = int(grade)
        if grade not in ADVENTURE_TASKS:
            raise CommunityError("Некорректный класс")
        game = str(game or "tower")
        if game not in {"tower", "second_part", "expert"}:
            raise CommunityError("Неизвестная мини-игра")
        async with self.lock:
            data = self._load()
            user_id = self._user_id(user)
            active = next((
                session for session in data["adventures"].values()
                if session.get("user_id") == user_id
                and int(session.get("grade") or 0) == grade
                and (session.get("game") or ("tower" if session.get("stage") in {"crystals", "formula"} else "second_part")) == game
                and session.get("status") == "active"
            ), None)
            if active:
                return self._adventure_view(active)
            session = new_session(user_id, grade, attempt_key, task=task, game=game)
            session["admin_unlimited"] = self._is_admin(user)
            session["created_at"] = _now_iso()
            session["updated_at"] = session["created_at"]
            data["adventures"][session["id"]] = session
            self._save(data)
            return self._adventure_view(session)

    async def answer_adventure_formula(self, user, session_id, option_id):
        option_id = str(option_id or "").strip()
        if not option_id:
            raise CommunityError("Выберите вариант ответа")
        async with self.lock:
            data = self._load()
            session = data["adventures"].get(str(session_id))
            user_id = self._user_id(user)
            if not session or session.get("user_id") != user_id or session.get("status") != "active":
                raise CommunityError("Активное приключение не найдено")
            ensure_formula_round(session)
            if session.get("stage") != "formula":
                raise CommunityError("Формульная башня уже пройдена")

            index = int(session.get("formula_index") or 0)
            formula_round = session["formula_round"]
            if index >= len(formula_round):
                raise CommunityError("Раунд уже завершён")

            challenge = formula_round[index]
            valid_ids = {item["id"] for item in challenge["options"]}
            if option_id not in valid_ids:
                raise CommunityError("Неизвестный вариант ответа")

            is_correct = option_id == challenge["correctOptionId"]
            session["formula_attempts"] = int(session.get("formula_attempts") or 0) + 1
            session["formula_index"] = index + 1
            if is_correct:
                session["formula_score"] = int(session.get("formula_score") or 0) + 1
                session["formula_feedback"] = {
                    "correct": True,
                    "message": "Верно! Вы заработали 50 монет.",
                }
            else:
                session["formula_errors"] = int(session.get("formula_errors") or 0) + 1
                session["formula_feedback"] = {
                    "correct": False,
                    "message": "Ошибка {} из {}. Переходим к следующей формуле.".format(
                        session["formula_errors"], FORMULA_MAX_MISTAKES
                    ),
                }

            mistakes = int(session.get("formula_errors") or 0)
            score = int(session.get("formula_score") or 0)
            finished_by_mistakes = (
                not session.get("admin_unlimited")
                and mistakes >= FORMULA_MAX_MISTAKES
            )
            finished_all_questions = session["formula_index"] >= len(formula_round)
            if finished_by_mistakes or finished_all_questions:
                reward = score * FORMULA_REWARD_PER_CORRECT
                profile = self._ensure_profile(data, user)
                profile["coins"] = int(profile.get("coins") or 0) + reward
                profile["updated_at"] = _now_iso()
                session["status"] = "complete"
                session["stage"] = "complete"
                end_reason = "mistakes" if finished_by_mistakes else "completed"
                if finished_by_mistakes:
                    verdict = f"Раунд завершён после {FORMULA_MAX_MISTAKES} ошибок. Награда начислена за все верные ответы."
                else:
                    verdict = "Все 10 формул проверены. Награда начислена за каждый верный ответ."
                session["result"] = {
                    "score": score,
                    "maxScore": len(formula_round),
                    "mistakes": mistakes,
                    "maxMistakes": FORMULA_MAX_MISTAKES,
                    "rewardCoins": reward,
                    "coins": int(profile.get("coins") or 0),
                    "admin": self._is_admin(user),
                    "endReason": end_reason,
                    "criteria": [],
                    "verdict": verdict,
                    "engine": "formula-game",
                }
                data["attempts"].append({
                    "attempt_key": "adventure:{}".format(session["id"]),
                    "user_id": user_id,
                    "question_id": "formula-tower-{}".format(session["grade"]),
                    "grade": session["grade"],
                    "correct": score == len(formula_round),
                    "points": score,
                    "source": "formula-game",
                    "created_at": _now_iso(),
                })
                data["coin_transactions"].append({
                    "id": "formula:{}".format(session["id"]),
                    "user_id": user_id,
                    "amount": reward,
                    "kind": "formula_tower",
                    "created_at": _now_iso(),
                })

            session["updated_at"] = _now_iso()
            self._save(data)
            return self._adventure_view(session)

    async def leave_adventure(self, user, session_id):
        async with self.lock:
            data = self._load()
            session = data["adventures"].get(str(session_id))
            if (
                not session
                or session.get("user_id") != self._user_id(user)
                or session.get("status") != "active"
            ):
                raise CommunityError("Активное приключение не найдено")
            game = session.get("game")
            if game == "tower":
                ensure_formula_round(session)
            if not (
                (game == "tower" and session.get("stage") == "formula")
                or (game == "expert" and session.get("stage") in {"grading", "review"})
            ):
                raise CommunityError("Сейчас нельзя покинуть этот раунд")
            session["status"] = "abandoned"
            session["stage"] = "abandoned"
            if game == "tower":
                session["result"] = {
                    "score": 0,
                    "maxScore": len(session["formula_round"]),
                    "correctAnswers": int(session.get("formula_score") or 0),
                    "mistakes": int(session.get("formula_errors") or 0),
                    "maxMistakes": FORMULA_MAX_MISTAKES,
                    "rewardCoins": 0,
                    "endReason": "left",
                    "criteria": [],
                    "verdict": "Вы покинули раунд. Очки и монеты не начислены.",
                    "engine": "formula-game",
                }
            else:
                session["result"] = {
                    "score": int(session.get("expert_correct") or 0),
                    "maxScore": len(session.get("expert_tasks") or [session.get("task")]),
                    "mistakes": int(session.get("expert_errors") or 0),
                    "rewardCoins": int(session.get("expert_reward_coins") or 0),
                    "endReason": "left",
                    "criteria": [],
                    "verdict": "Вы покинули проверку. Уже заработанные монеты сохранены.",
                    "engine": "expert-game",
                }
            session["updated_at"] = _now_iso()
            self._save(data)
            return self._adventure_view(session)

    async def submit_expert_score(self, user, session_id, selected_score):
        try:
            selected_score = int(selected_score)
        except (TypeError, ValueError) as error:
            raise CommunityError("Выберите балл за работу") from error
        async with self.lock:
            data = self._load()
            session = data["adventures"].get(str(session_id))
            if (
                not session
                or session.get("user_id") != self._user_id(user)
                or session.get("status") != "active"
                or session.get("game") != "expert"
                or session.get("stage") != "grading"
            ):
                raise CommunityError("Активная проверка не найдена")
            task = session.get("task") or {}
            max_work_score = int(task.get("maxScore") or 0)
            expert_score = int(task.get("expertScore") or 0)
            if selected_score < 0 or selected_score > max_work_score:
                raise CommunityError(f"Выберите оценку от 0 до {max_work_score}")
            correct = selected_score == expert_score
            round_index = int(session.get("expert_index") or 0)
            if correct:
                session["expert_correct"] = int(session.get("expert_correct") or 0) + 1
                session["expert_reward_coins"] = int(session.get("expert_reward_coins") or 0) + EXPERT_REWARD_PER_CORRECT
                profile = self._ensure_profile(data, user)
                if not self._is_admin(user):
                    profile["coins"] = int(profile.get("coins") or 0) + EXPERT_REWARD_PER_CORRECT
                profile["updated_at"] = _now_iso()
                data["coin_transactions"].append({
                    "id": f"expert:{session['id']}:{round_index}",
                    "user_id": self._user_id(user),
                    "amount": 0 if self._is_admin(user) else EXPERT_REWARD_PER_CORRECT,
                    "kind": "expert_game",
                    "task_number": int(task.get("taskNumber") or 13),
                    "created_at": _now_iso(),
                })
            else:
                session["expert_errors"] = int(session.get("expert_errors") or 0) + 1
                if not session.get("admin_unlimited"):
                    session["expert_lives"] = max(0, int(session.get("expert_lives") or 0) - 1)
            result = {
                "score": int(correct),
                "maxScore": 1,
                "selectedScore": selected_score,
                "expertScore": expert_score,
                "workMaxScore": max_work_score,
                "criteria": [],
                "verdict": (
                    f"Верно: эксперт поставил {expert_score} балл."
                    if correct else
                    f"Ваша оценка — {selected_score}, оценка эксперта — {expert_score}. Изучите разбор ниже."
                ),
                "engine": "expert-game",
                "correct": correct,
                "lives": int(session.get("expert_lives") or 0),
                "rewardCoins": int(session.get("expert_reward_coins") or 0),
            }
            if not correct:
                result["answerImageUrl"] = str(task.get("answerImageUrl") or "")
            session["selected_score"] = selected_score
            session["result"] = result
            session["stage"] = "review"
            session["updated_at"] = _now_iso()
            data["attempts"].append({
                "attempt_key": f"adventure:{session['id']}",
                "user_id": self._user_id(user),
                "question_id": task.get("id") or "expert-work",
                "grade": session["grade"],
                "correct": correct,
                "points": int(correct),
                "source": "expert-game",
                "created_at": _now_iso(),
            })
            self._save(data)
            return self._adventure_view(session)

    async def continue_expert_game(self, user, session_id):
        async with self.lock:
            data = self._load()
            session = data["adventures"].get(str(session_id))
            if (
                not session
                or session.get("user_id") != self._user_id(user)
                or session.get("status") != "active"
                or session.get("game") != "expert"
                or session.get("stage") != "review"
            ):
                raise CommunityError("Разбор для продолжения не найден")
            tasks = session.get("expert_tasks") or [session.get("task")]
            next_index = int(session.get("expert_index") or 0) + 1
            no_lives = (
                not session.get("admin_unlimited")
                and int(session.get("expert_lives") or 0) <= 0
            )
            no_tasks = next_index >= len(tasks)
            if no_lives or no_tasks:
                profile = self._ensure_profile(data, user)
                session["status"] = "complete"
                session["stage"] = "complete"
                session["result"] = {
                    "score": int(session.get("expert_correct") or 0),
                    "maxScore": len(tasks),
                    "mistakes": int(session.get("expert_errors") or 0),
                    "maxMistakes": EXPERT_MAX_LIVES,
                    "rewardCoins": int(session.get("expert_reward_coins") or 0),
                    "coins": int(profile.get("coins") or 0),
                    "admin": self._is_admin(user),
                    "endReason": "lives" if no_lives else "completed",
                    "criteria": [],
                    "reviewTopics": [f"Задание {int((session.get('task') or {}).get('taskNumber') or 13)}"],
                    "verdict": (
                        "Жизни закончились. Все монеты за верные оценки сохранены."
                        if no_lives else
                        "Все доступные работы проверены. Монеты начислены за верные оценки."
                    ),
                    "engine": "expert-game",
                }
            else:
                session["expert_index"] = next_index
                session["task"] = tasks[next_index]
                session["stage"] = "grading"
                session.pop("result", None)
                session.pop("selected_score", None)
            session["updated_at"] = _now_iso()
            self._save(data)
            return self._adventure_view(session)

    async def adventure_context(self, user, session_id):
        async with self.lock:
            data = self._load()
            session = data["adventures"].get(str(session_id))
            if not session or session.get("user_id") != self._user_id(user) or session.get("status") != "active":
                raise CommunityError("Активное приключение не найдено")
            return {
                "grade": int(session["grade"]),
                "task": session.get("task") or ADVENTURE_TASKS[int(session["grade"])],
            }

    async def save_adventure_draft(self, user, session_id, payload):
        async with self.lock:
            data = self._load()
            session = data["adventures"].get(str(session_id))
            if not session or session.get("user_id") != self._user_id(user) or session.get("status") != "active":
                raise CommunityError("Активное приключение не найдено")
            answers = {
                str(key)[:40]: str(value)[:500]
                for key, value in (payload.get("answers") or {}).items()
            }
            explanation = str(payload.get("explanation") or "")[:3000]
            session["draft"] = {"answers": answers, "explanation": explanation}
            session["updated_at"] = _now_iso()
            self._save(data)
            return {"saved": True, "updatedAt": session["updated_at"]}

    async def submit_adventure(self, user, session_id, payload, expert_result=None):
        async with self.lock:
            data = self._load()
            session = data["adventures"].get(str(session_id))
            if not session or session.get("user_id") != self._user_id(user) or session.get("status") != "active":
                raise CommunityError("Активное приключение не найдено")
            if session.get("stage") != "solution":
                raise CommunityError("Сначала пройдите формульную башню")
            explanation = str(payload.get("explanation") or "").strip()
            if len(explanation) > 3000:
                raise CommunityError("Пояснение слишком длинное")
            task = session.get("task") or ADVENTURE_TASKS[int(session["grade"])]
            result = expert_result or grade_solution(task, payload.get("answers") or {}, explanation)
            result["engine"] = "expert-model" if expert_result else "structured-check"
            session["condition_image"] = self._store_solution_image(payload.get("conditionImage"), "condition")
            session["solution_image"] = self._store_solution_image(payload.get("solutionImage"), "solution")
            session["answers"] = payload.get("answers") or {}
            session["explanation"] = explanation
            session["result"] = result
            session["status"] = "complete"
            session["stage"] = "complete"
            session["updated_at"] = _now_iso()
            data["attempts"].append({
                "attempt_key": f"adventure:{session['id']}",
                "user_id": self._user_id(user),
                "question_id": task["id"],
                "grade": session["grade"],
                "correct": result["score"] == result["maxScore"],
                "points": result["score"],
                "source": "extended",
                "created_at": _now_iso(),
            })
            self._save(data)
            return self._adventure_view(session)

    @staticmethod
    def _period_key(timestamp, period):
        moment = datetime.fromisoformat(timestamp).astimezone(MOSCOW)
        return moment.strftime("%Y-%m-%d" if period == "day" else "%Y-%m")

    def _ranking(self, data, period, period_key, grade=None):
        totals = {}
        for attempt in data["attempts"]:
            if self._period_key(attempt["created_at"], period) != period_key:
                continue
            if grade and int(attempt.get("grade") or 0) != int(grade):
                continue
            user_id = attempt["user_id"]
            profile = data["profiles"].get(user_id, {})
            if not profile.get("leaderboard_consent"):
                continue
            total = totals.setdefault(user_id, {"score": 0, "correct": 0, "total": 0})
            total["score"] += int(attempt.get("points") or 0)
            total["correct"] += int(bool(attempt.get("correct")))
            total["total"] += 1
        ordered = sorted(
            totals.items(),
            key=lambda item: (
                -item[1]["score"],
                -(item[1]["correct"] / item[1]["total"] if item[1]["total"] else 0),
                -item[1]["total"],
                item[0],
            ),
        )
        return ordered

    def _finalise_awards(self, data):
        now = datetime.now(MOSCOW)
        periods = [
            ("day", (now - timedelta(days=1)).strftime("%Y-%m-%d"), DAILY_AWARDS),
            ("month", (now.replace(day=1) - timedelta(days=1)).strftime("%Y-%m"), MONTHLY_AWARDS),
        ]
        existing = {(a["user_id"], a["period"], a["period_key"]) for a in data["awards"]}
        for period, period_key, names in periods:
            for rank, (user_id, _score) in enumerate(self._ranking(data, period, period_key), start=1):
                if rank > 3:
                    break
                key = (user_id, period, period_key)
                if key in existing:
                    continue
                name, icon = names[rank]
                data["awards"].append({
                    "user_id": user_id,
                    "period": period,
                    "period_key": period_key,
                    "rank": rank,
                    "name": name,
                    "icon": icon,
                    "issued_at": _now_iso(),
                })
                existing.add(key)

    async def leaderboard(self, period="day", grade=None, viewer_id=None):
        if period not in {"day", "month"}:
            raise CommunityError("Период должен быть day или month")
        now = datetime.now(MOSCOW)
        period_key = now.strftime("%Y-%m-%d" if period == "day" else "%Y-%m")
        async with self.lock:
            data = self._load()
            self._finalise_awards(data)
            self._save(data)
            ranking = self._ranking(data, period, period_key, grade)
            award_names = DAILY_AWARDS if period == "day" else MONTHLY_AWARDS
            entries = []
            for rank, (user_id, result) in enumerate(ranking[:100], start=1):
                if not self._can_view_stats(data, str(viewer_id) if viewer_id is not None else None, user_id):
                    continue
                profile = data["profiles"].get(user_id, {})
                entry = {
                    "rank": rank,
                    "publicId": profile.get("public_id"),
                    "nickname": profile.get("nickname", "Участник"),
                    "avatarUrl": profile.get("avatar_url", ""),
                    "score": result["score"],
                    "correct": result["correct"],
                    "total": result["total"],
                }
                if rank <= 3:
                    entry["award"] = {"name": award_names[rank][0], "icon": award_names[rank][1]}
                entries.append(entry)
            return {"period": period, "periodKey": period_key, "entries": entries}

    @staticmethod
    def _find_user_by_public_id(data, public_id):
        public_id = str(public_id or "")
        return next((
            (user_id, profile)
            for user_id, profile in data["profiles"].items()
            if profile.get("public_id") == public_id
        ), (None, None))

    @staticmethod
    def _is_blocked(data, first_id, second_id):
        return any(
            {row.get("blocker_id"), row.get("blocked_id")} == {first_id, second_id}
            for row in data.get("blocks", [])
        )

    async def blocked_participants(self, user):
        async with self.lock:
            data = self._load()
            return {"entries": [
                {"publicId": profile.get("public_id"),
                 "nickname": profile.get("nickname", "Участник"),
                 "avatarUrl": profile.get("avatar_url", "")}
                for row in data["blocks"] if row.get("blocker_id") == self._user_id(user)
                for profile in [data["profiles"].get(row.get("blocked_id"), {})]
                if profile.get("public_id")
            ]}

    async def block_participant(self, user, public_id, remove=False):
        async with self.lock:
            data = self._load()
            user_id = self._user_id(user)
            target_id, _ = self._find_user_by_public_id(data, public_id)
            if not target_id or target_id == user_id:
                raise CommunityError("Участник не найден")
            own_block = lambda row: row.get("blocker_id") == user_id and row.get("blocked_id") == target_id
            if remove:
                data["blocks"] = [row for row in data["blocks"] if not own_block(row)]
            else:
                if not any(own_block(row) for row in data["blocks"]):
                    data["blocks"].append({"blocker_id": user_id, "blocked_id": target_id, "created_at": _now_iso()})
                # Keep history, but revoke relationships and outstanding invitations.
                for row in data["friendships"] + data["battle_invites"]:
                    if ({row.get("sender_id"), row.get("receiver_id")} == {user_id, target_id}
                            and row.get("status") in {"pending", "accepted"}):
                        row["status"] = "blocked"
                        row["updated_at"] = _now_iso()
            self._save(data)
            return {"blocked": not remove}

    @staticmethod
    def _friendship_between(data, first_id, second_id):
        return next((
            item for item in reversed(data["friendships"])
            if {item.get("sender_id"), item.get("receiver_id")} == {first_id, second_id}
            and item.get("status") in {"pending", "accepted"}
        ), None)

    def _can_view_stats(self, data, viewer_id, target_id):
        if not viewer_id or self._is_blocked(data, viewer_id, target_id):
            return False
        if viewer_id == target_id:
            return True
        relationship = self._friendship_between(data, viewer_id, target_id)
        return bool(relationship and relationship.get("status") == "accepted")

    def _friendship_status(self, data, viewer_id, target_id):
        if viewer_id == target_id:
            return "self"
        friendship = self._friendship_between(data, viewer_id, target_id)
        if not friendship:
            return "none"
        if friendship["status"] == "accepted":
            return "friends"
        return "incoming" if friendship["receiver_id"] == viewer_id else "outgoing"

    def _public_profile(self, data, target_id, viewer_id=None):
        profile = data["profiles"].get(target_id, {})
        grade = profile.get("grade")
        selected_characters = profile.get("selected_characters", {})
        character_id = selected_characters.get(GLOBAL_CHARACTER_KEY) or selected_characters.get(str(grade))
        character = next(
            (item for item in CHARACTER_CATALOG if item["id"] == character_id),
            None,
        )
        public = {
            "publicId": profile.get("public_id"),
            "nickname": profile.get("nickname", "Участник"),
            "avatarUrl": profile.get("avatar_url", ""),
            "grade": grade,
            "characterId": character_id,
            "characterStyle": character.get("style") if character else None,
            "friendshipStatus": self._friendship_status(data, viewer_id, target_id) if viewer_id else "none",
            "acceptsFriendRequests": profile.get("allow_friend_requests", True),
        }
        if profile.get("leaderboard_consent") and self._can_view_stats(data, viewer_id, target_id):
            now = datetime.now(MOSCOW)
            day_rank = dict(self._ranking(data, "day", now.strftime("%Y-%m-%d"))).get(target_id, {})
            month_rank = dict(self._ranking(data, "month", now.strftime("%Y-%m"))).get(target_id, {})
            completed = [
                battle for battle in data["battles"].values()
                if battle.get("status") == "complete" and target_id in battle.get("players", {})
            ]
            wins = 0
            for battle in completed:
                scores = [player.get("score", 0) for player in battle["players"].values()]
                own_score = battle["players"][target_id].get("score", 0)
                if scores and own_score == max(scores) and scores.count(max(scores)) == 1:
                    wins += 1
            public["stats"] = {
                "dayScore": int(day_rank.get("score", 0)),
                "monthScore": int(month_rank.get("score", 0)),
                "battleWins": wins,
            }
            public["awards"] = [
                {key: award[key] for key in ("period", "period_key", "rank", "name", "icon")}
                for award in data["awards"]
                if award.get("user_id") == target_id
            ]
        else:
            public["stats"] = None
            public["awards"] = []
        return public

    async def participant(self, user, public_id):
        async with self.lock:
            data = self._load()
            viewer_id = self._user_id(user)
            self._ensure_profile(data, user)
            target_id, target = self._find_user_by_public_id(data, public_id)
            friendship = self._friendship_between(data, viewer_id, target_id) if target_id else None
            can_view_friend = friendship and friendship.get("status") == "accepted"
            if not target_id or self._is_blocked(data, viewer_id, target_id) or (
                target_id != viewer_id
                and not target.get("leaderboard_consent")
                and not can_view_friend
            ):
                raise CommunityError("Профиль участника не найден")
            self._finalise_awards(data)
            self._save(data)
            return self._public_profile(data, target_id, viewer_id)

    async def search_participants(self, user, query):
        query = unicodedata.normalize("NFKC", str(query or "")).strip().casefold()
        if not 2 <= len(query) <= 24:
            raise CommunityError("Введите полный никнейм участника (2–24 символа)")
        async with self.lock:
            data = self._load()
            viewer_id = self._user_id(user)
            self._ensure_profile(data, user)
            matches = []
            for target_id, profile in data["profiles"].items():
                if (target_id == viewer_id or not profile.get("leaderboard_consent")
                        or self._is_blocked(data, viewer_id, target_id)):
                    continue
                if query != unicodedata.normalize("NFKC", str(profile.get("nickname", ""))).strip().casefold():
                    continue
                matches.append(self._public_profile(data, target_id, viewer_id))
                if len(matches) >= 20:
                    break
            self._save(data)
            return {"entries": matches}

    async def friends(self, user):
        async with self.lock:
            data = self._load()
            user_id = self._user_id(user)
            self._ensure_profile(data, user)
            groups = {"friends": [], "incoming": [], "outgoing": []}
            for item in data["friendships"]:
                if user_id not in {item.get("sender_id"), item.get("receiver_id")}:
                    continue
                target_id = item["receiver_id"] if item["sender_id"] == user_id else item["sender_id"]
                if self._is_blocked(data, user_id, target_id):
                    continue
                if target_id not in data["profiles"]:
                    continue
                record = {
                    "id": item["id"],
                    "createdAt": item["created_at"],
                    "participant": self._public_profile(data, target_id, user_id),
                }
                if item["status"] == "accepted":
                    groups["friends"].append(record)
                elif item["status"] == "pending" and item["receiver_id"] == user_id:
                    groups["incoming"].append(record)
                elif item["status"] == "pending":
                    groups["outgoing"].append(record)
            self._save(data)
            return groups

    async def request_friend(self, user, target_public_id):
        async with self.lock:
            data = self._load()
            user_id = self._user_id(user)
            self._ensure_profile(data, user)
            target_id, target = self._find_user_by_public_id(data, target_public_id)
            if (not target_id or not target.get("leaderboard_consent")
                    or self._is_blocked(data, user_id, target_id)):
                raise CommunityError("Профиль участника не найден")
            if not target.get("allow_friend_requests", True):
                raise CommunityError("Участник отключил новые заявки в друзья")
            if target_id == user_id:
                raise CommunityError("Нельзя добавить в друзья самого себя")
            existing = self._friendship_between(data, user_id, target_id)
            if existing and existing["status"] == "accepted":
                raise CommunityError("Этот участник уже у вас в друзьях")
            if existing and existing["status"] == "pending":
                if existing["receiver_id"] == user_id:
                    raise CommunityError("Откройте входящие заявки и нажмите «Принять»")
                raise CommunityError("Заявка уже отправлена")
            now = datetime.now(MOSCOW)
            sent = [row for row in data["friendships"] if row.get("sender_id") == user_id]
            recent = [row for row in sent if datetime.fromisoformat(row["created_at"]) >= now - timedelta(days=1)]
            hourly = [row for row in recent if datetime.fromisoformat(row["created_at"]) >= now - timedelta(hours=1)]
            if len(recent) >= 20 or len(hourly) >= 5:
                raise CommunityError("Лимит заявок: 5 в час и 20 в сутки. Попробуйте позже")
            if any(row.get("receiver_id") == target_id and row.get("status") in {"declined", "blocked"}
                   and datetime.fromisoformat(row.get("updated_at") or row["created_at"]) >= now - timedelta(days=7)
                   for row in sent):
                raise CommunityError("После отклонения заявки повторить её можно через 7 дней")
            request = {
                "id": uuid.uuid4().hex[:12],
                "sender_id": user_id,
                "receiver_id": target_id,
                "status": "pending",
                "created_at": _now_iso(),
                "updated_at": _now_iso(),
            }
            data["friendships"].append(request)
            self._save(data)
            return {"status": "pending", "requestId": request["id"], "targetUserId": target_id}

    async def accept_friend(self, user, request_id):
        async with self.lock:
            data = self._load()
            user_id = self._user_id(user)
            self._ensure_profile(data, user)
            request = next((item for item in data["friendships"] if item.get("id") == request_id), None)
            if not request or request.get("receiver_id") != user_id or request.get("status") != "pending":
                raise CommunityError("Заявка в друзья не найдена")
            if self._is_blocked(data, user_id, request["sender_id"]):
                raise CommunityError("Заявка в друзья не найдена")
            request["status"] = "accepted"
            request["updated_at"] = _now_iso()
            self._save(data)
            return {"status": "accepted", "targetUserId": request["sender_id"]}

    async def decline_friend(self, user, request_id):
        async with self.lock:
            data = self._load()
            user_id = self._user_id(user)
            request = next((item for item in data["friendships"] if item.get("id") == request_id), None)
            if not request or request.get("receiver_id") != user_id or request.get("status") != "pending":
                raise CommunityError("Заявка в друзья не найдена")
            request["status"] = "declined"
            request["updated_at"] = _now_iso()
            self._save(data)
            return {"status": "declined"}

    def _require_friend(self, data, user_id, target_id):
        if self._is_blocked(data, user_id, target_id):
            raise CommunityError("Взаимодействие с участником недоступно")
        friendship = self._friendship_between(data, user_id, target_id)
        if not friendship or friendship.get("status") != "accepted":
            raise CommunityError("Сначала добавьте участника в друзья")
        return friendship

    async def conversation(self, user, target_public_id):
        async with self.lock:
            data = self._load()
            user_id = self._user_id(user)
            self._ensure_profile(data, user)
            target_id, _target = self._find_user_by_public_id(data, target_public_id)
            if not target_id:
                raise CommunityError("Участник не найден")
            self._require_friend(data, user_id, target_id)
            messages = [
                item for item in data["messages"]
                if {item.get("sender_id"), item.get("receiver_id")} == {user_id, target_id}
            ][-100:]
            changed = False
            now = _now_iso()
            for item in messages:
                if item["receiver_id"] == user_id and not item.get("read_at"):
                    item["read_at"] = now
                    changed = True
            if changed:
                self._save(data)
            return {
                "participant": self._public_profile(data, target_id, user_id),
                "messages": [{
                    "id": item["id"],
                    "text": item["text"],
                    "createdAt": item["created_at"],
                    "mine": item["sender_id"] == user_id,
                    "read": bool(item.get("read_at")),
                } for item in messages],
            }

    async def send_message(self, user, target_public_id, raw_text):
        text = validate_message_text(raw_text)
        async with self.lock:
            data = self._load()
            user_id = self._user_id(user)
            self._ensure_profile(data, user)
            target_id, _target = self._find_user_by_public_id(data, target_public_id)
            if not target_id:
                raise CommunityError("Участник не найден")
            self._require_friend(data, user_id, target_id)
            cutoff = datetime.now(MOSCOW) - timedelta(seconds=30)
            recent = [
                item for item in data["messages"]
                if item.get("sender_id") == user_id
                and datetime.fromisoformat(item["created_at"]).astimezone(MOSCOW) >= cutoff
            ]
            if len(recent) >= 5:
                raise CommunityError("Слишком много сообщений. Подождите немного")
            message = {
                "id": uuid.uuid4().hex[:16],
                "sender_id": user_id,
                "receiver_id": target_id,
                "text": text,
                "created_at": _now_iso(),
                "read_at": None,
            }
            data["messages"].append(message)
            data["messages"] = data["messages"][-5000:]
            self._save(data)
            return {
                "message": {
                    "id": message["id"], "text": text, "createdAt": message["created_at"],
                    "mine": True, "read": False,
                },
                "targetUserId": target_id,
            }

    def _expire_battle_invites(self, data):
        now = datetime.now(MOSCOW)
        for invite in data["battle_invites"]:
            if invite.get("status") != "pending":
                continue
            created = datetime.fromisoformat(invite["created_at"]).astimezone(MOSCOW)
            if now - created > timedelta(hours=24):
                invite["status"] = "expired"

    async def battle_invites(self, user):
        async with self.lock:
            data = self._load()
            user_id = self._user_id(user)
            self._ensure_profile(data, user)
            self._expire_battle_invites(data)
            groups = {"incoming": [], "outgoing": []}
            for invite in data["battle_invites"]:
                if invite.get("status") != "pending" or user_id not in {invite["sender_id"], invite["receiver_id"]}:
                    continue
                target_id = invite["sender_id"] if invite["receiver_id"] == user_id else invite["receiver_id"]
                if self._is_blocked(data, user_id, target_id):
                    continue
                entry = {
                    "id": invite["id"],
                    "grade": invite["grade"],
                    "createdAt": invite["created_at"],
                    "participant": self._public_profile(data, target_id, user_id),
                }
                key = "incoming" if invite["receiver_id"] == user_id else "outgoing"
                groups[key].append(entry)
            self._save(data)
            return groups

    async def create_battle_invite(self, user, target_public_id, grade):
        grade = int(grade)
        if grade not in {8, 9, 10, 11}:
            raise CommunityError("Выберите класс от 8 до 11")
        async with self.lock:
            data = self._load()
            user_id = self._user_id(user)
            profile = self._ensure_profile(data, user)
            target_id, target = self._find_user_by_public_id(data, target_public_id)
            if not target_id:
                raise CommunityError("Участник не найден")
            self._require_friend(data, user_id, target_id)
            if not profile.get("leaderboard_consent") or not target.get("leaderboard_consent"):
                raise CommunityError("Оба участника должны включить участие в баттлах")
            self._expire_battle_invites(data)
            duplicate = next((
                item for item in data["battle_invites"]
                if item.get("status") == "pending"
                and {item["sender_id"], item["receiver_id"]} == {user_id, target_id}
            ), None)
            if duplicate:
                raise CommunityError("Приглашение в баттл уже отправлено")
            invite = {
                "id": uuid.uuid4().hex[:12],
                "sender_id": user_id,
                "receiver_id": target_id,
                "grade": grade,
                "status": "pending",
                "created_at": _now_iso(),
                "updated_at": _now_iso(),
                "battle_id": None,
            }
            data["battle_invites"].append(invite)
            self._save(data)
            return {"status": "pending", "inviteId": invite["id"], "targetUserId": target_id}

    async def accept_battle_invite(self, user, invite_id, questions):
        async with self.lock:
            data = self._load()
            user_id = self._user_id(user)
            profile = self._ensure_profile(data, user)
            self._expire_battle_invites(data)
            invite = next((item for item in data["battle_invites"] if item.get("id") == invite_id), None)
            if not invite or invite.get("receiver_id") != user_id or invite.get("status") != "pending":
                raise CommunityError("Приглашение в баттл не найдено или устарело")
            sender_id = invite["sender_id"]
            sender = data["profiles"].get(sender_id, {})
            self._require_friend(data, user_id, sender_id)
            if not profile.get("leaderboard_consent") or not sender.get("leaderboard_consent"):
                raise CommunityError("Оба участника должны включить участие в баттлах")
            grade = int(invite["grade"])
            if len(questions) < 5:
                raise CommunityError("Для баттла нужно минимум 5 заданий этого класса")
            question_map = {question.question_id: question for question in questions}
            invite_players = {user_id, sender_id}
            for battle in data["battles"].values():
                if battle.get("status") == "waiting" and invite_players & set(battle.get("players", {})):
                    battle["status"] = "cancelled"
            self._expire_battles(data, question_map)
            for battle in data["battles"].values():
                if battle.get("status") == "active" and invite_players & set(battle.get("players", {})):
                    raise CommunityError("Один из участников уже находится в активном баттле")
            selected = random.SystemRandom().sample(questions, 5)
            battle_id = uuid.uuid4().hex[:12]
            started = datetime.now(MOSCOW)
            started_at = started.isoformat()
            first_question_at = (started + timedelta(seconds=BATTLE_COUNTDOWN_SECONDS)).isoformat()
            data["battles"][battle_id] = {
                "id": battle_id,
                "grade": grade,
                "status": "active",
                "question_ids": [question.question_id for question in selected],
                "players": {
                    sender_id: {"score": 0, "answers": {}, "finished_at": None, "question_index": 0, "question_started_at": first_question_at},
                    user_id: {"score": 0, "answers": {}, "finished_at": None, "question_index": 0, "question_started_at": first_question_at},
                },
                "created_at": _now_iso(),
                "started_at": started_at,
                "countdown_until": first_question_at,
                "bonus_awarded": False,
                "invite_id": invite["id"],
            }
            invite["status"] = "accepted"
            invite["battle_id"] = battle_id
            invite["updated_at"] = _now_iso()
            self._save(data)
            return {"battleId": battle_id, "targetUserId": sender_id}

    async def decline_battle_invite(self, user, invite_id):
        async with self.lock:
            data = self._load()
            user_id = self._user_id(user)
            self._expire_battle_invites(data)
            invite = next((item for item in data["battle_invites"] if item.get("id") == invite_id), None)
            if not invite or invite.get("receiver_id") != user_id or invite.get("status") != "pending":
                raise CommunityError("Приглашение в баттл не найдено или устарело")
            invite["status"] = "declined"
            invite["updated_at"] = _now_iso()
            self._save(data)
            return {"status": "declined"}

    async def create_enrollment(self, user, payload):
        grade = int(payload.get("grade") or 0)
        if grade not in {8, 9, 10, 11}:
            raise CommunityError("Выберите класс")
        goal = str(payload.get("goal") or "").strip()
        frequency = int(payload.get("frequency") or 0)
        if not goal or frequency not in {1, 2, 3}:
            raise CommunityError("Заполните цель и частоту занятий")
        if not payload.get("consent"):
            raise CommunityError("Для отправки заявки требуется согласие")
        async with self.lock:
            data = self._load()
            profile = self._ensure_profile(data, user)
            lead = {
                "id": uuid.uuid4().hex[:10],
                "user_id": self._user_id(user),
                "telegram_username": user.get("username", ""),
                "nickname": profile.get("nickname"),
                "grade": grade,
                "goal": goal,
                "frequency": frequency,
                "diagnostic_score": payload.get("diagnosticScore"),
                "status": "new",
                "created_at": _now_iso(),
            }
            data["enrollments"].append(lead)
            self._save(data)
            return lead

    async def join_battle(self, user, grade, questions):
        grade = int(grade)
        if grade not in {8, 9, 10, 11}:
            raise CommunityError("Выберите класс")
        user_id = self._user_id(user)
        async with self.lock:
            data = self._load()
            profile = self._ensure_profile(data, user)
            if not profile.get("leaderboard_consent"):
                raise CommunityError("Для баттла включите участие в рейтинге в личном кабинете")
            profile["grade"] = grade
            question_map = {question.question_id: question for question in questions}
            self._expire_battles(data, question_map)
            for battle in data["battles"].values():
                if user_id in battle["players"] and battle["status"] in {"waiting", "active"}:
                    self._save(data)
                    return battle["id"]

            waiting = next((
                battle for battle in data["battles"].values()
                if battle["status"] == "waiting" and battle["grade"] == grade and user_id not in battle["players"]
                and not any(self._is_blocked(data, user_id, other_id) for other_id in battle["players"])
            ), None)
            if waiting:
                started = datetime.now(MOSCOW)
                started_at = started.isoformat()
                first_question_at = (started + timedelta(seconds=BATTLE_COUNTDOWN_SECONDS)).isoformat()
                waiting["players"][user_id] = {
                    "score": 0, "answers": {}, "finished_at": None,
                    "question_index": 0, "question_started_at": first_question_at,
                }
                for player in waiting["players"].values():
                    player["question_index"] = 0
                    player["question_started_at"] = first_question_at
                waiting["status"] = "active"
                waiting["started_at"] = started_at
                waiting["countdown_until"] = first_question_at
                battle_id = waiting["id"]
            else:
                if len(questions) < 5:
                    raise CommunityError("Для баттла нужно минимум 5 заданий этого класса")
                selected = random.SystemRandom().sample(questions, 5)
                battle_id = uuid.uuid4().hex[:12]
                data["battles"][battle_id] = {
                    "id": battle_id,
                    "grade": grade,
                    "status": "waiting",
                    "question_ids": [question.question_id for question in selected],
                    "players": {user_id: {"score": 0, "answers": {}, "finished_at": None, "question_index": 0, "question_started_at": None}},
                    "created_at": _now_iso(),
                    "started_at": None,
                    "countdown_until": None,
                    "bonus_awarded": False,
                }
            self._save(data)
            return battle_id

    @staticmethod
    def _is_bot(user_id):
        return user_id == BOT_PLAYER_ID

    def _start_bot_battle(self, battle):
        if BOT_PLAYER_ID in battle["players"]:
            return
        battle["players"][BOT_PLAYER_ID] = {
            "score": 0,
            "answers": {},
            "finished_at": None,
            "is_bot": True,
        }
        started = datetime.now(MOSCOW)
        battle["status"] = "active"
        battle["started_at"] = started.isoformat()
        battle["countdown_until"] = (
            started + timedelta(seconds=BATTLE_COUNTDOWN_SECONDS)
        ).isoformat()
        for user_id, player in battle["players"].items():
            if not self._is_bot(user_id):
                player["question_index"] = 0
                player["question_started_at"] = battle["countdown_until"]

    @staticmethod
    def _player_question_index(battle, player):
        question_ids = battle.get("question_ids", [])
        try:
            index = int(player.get("question_index"))
        except (TypeError, ValueError):
            index = 0
        while index < len(question_ids) and question_ids[index] in player.get("answers", {}):
            index += 1
        return index

    def _expire_player_questions(self, battle, now):
        """Mark every unanswered 30-second slot as missed on the server."""
        if battle.get("status") != "active" or not battle.get("started_at"):
            return
        question_ids = battle.get("question_ids", [])
        for user_id, player in battle.get("players", {}).items():
            if self._is_bot(user_id) or player.get("finished_at"):
                continue
            answers = player.setdefault("answers", {})
            index = self._player_question_index(battle, player)
            started_raw = player.get("question_started_at") or battle["started_at"]
            try:
                started = datetime.fromisoformat(started_raw).astimezone(MOSCOW)
            except (TypeError, ValueError):
                started = now
            while index < len(question_ids):
                deadline = started + timedelta(seconds=BATTLE_QUESTION_SECONDS)
                if now < deadline:
                    break
                question_id = question_ids[index]
                answers.setdefault(question_id, BATTLE_MISSED_ANSWER)
                index += 1
                started = deadline
            player["question_index"] = index
            player["question_started_at"] = started.isoformat() if index < len(question_ids) else None
            if index >= len(question_ids):
                player["finished_at"] = player.get("finished_at") or now.isoformat()

    def _advance_bot(self, battle, question_map, now):
        bot_player = battle["players"].get(BOT_PLAYER_ID)
        if not bot_player or bot_player.get("finished_at"):
            return
        started = datetime.fromisoformat(battle["started_at"]).astimezone(MOSCOW)
        human_finished = any(
            player.get("finished_at")
            for user_id, player in battle["players"].items()
            if not self._is_bot(user_id)
        )
        answer_count = len(battle["question_ids"]) if human_finished else min(
            len(battle["question_ids"]),
            int((now - started).total_seconds() // BOT_ANSWER_SECONDS),
        )
        for question_id in battle["question_ids"][:answer_count]:
            if question_id in bot_player["answers"] or question_id not in question_map:
                continue
            question = question_map[question_id]
            digest = int(hashlib.sha256(f"{battle['id']}:{question_id}".encode()).hexdigest()[:8], 16)
            is_correct = digest % 100 < 68
            selected_index = question.correct_index if is_correct else (question.correct_index + 1 + digest % 3) % 4
            bot_player["answers"][question_id] = selected_index
            if is_correct:
                bot_player["score"] += 1
        if len(bot_player["answers"]) >= len(battle["question_ids"]):
            bot_player["finished_at"] = _now_iso()

    def _expire_battles(self, data, question_map=None):
        now = datetime.now(MOSCOW)
        question_map = question_map or {}
        for battle in data["battles"].values():
            created = datetime.fromisoformat(battle["created_at"])
            age = now - created.astimezone(MOSCOW)
            if battle["status"] == "waiting" and age >= timedelta(seconds=BOT_WAIT_SECONDS) and question_map:
                self._start_bot_battle(battle)
            elif battle["status"] == "waiting" and age > timedelta(minutes=10):
                battle["status"] = "cancelled"
            if battle["status"] == "active":
                self._expire_player_questions(battle, now)
                self._advance_bot(battle, question_map, now)
                if len(battle["players"]) == 2 and all(
                    player.get("finished_at") for player in battle["players"].values()
                ):
                    battle["status"] = "complete"
                    self._award_battle_bonus(data, battle)
                else:
                    started = datetime.fromisoformat(battle["started_at"] or battle["created_at"])
                    active_age = now - started.astimezone(MOSCOW)
                    if active_age <= timedelta(minutes=25):
                        continue
                    battle["status"] = "complete"
                    self._award_battle_bonus(data, battle)

    def _award_battle_bonus(self, data, battle):
        if battle.get("bonus_awarded") or len(battle["players"]) < 2:
            return
        forfeited_by = battle.get("forfeited_by")
        if forfeited_by in battle["players"]:
            winners = [uid for uid in battle["players"] if uid != forfeited_by]
        else:
            best = max(player["score"] for player in battle["players"].values())
            winners = [uid for uid, player in battle["players"].items() if player["score"] == best]
        battle["rewards"] = {}
        if len(winners) == 1:
            if self._is_bot(winners[0]):
                battle["bonus_awarded"] = True
                return
            winner_id = winners[0]
            data["attempts"].append({
                "attempt_key": f"battle-win:{battle['id']}",
                "user_id": winner_id,
                "question_id": "battle-win",
                "grade": battle["grade"],
                "correct": True,
                "points": 3,
                "source": "battle_bonus",
                "created_at": _now_iso(),
            })
            profile = data["profiles"].get(winner_id)
            if profile:
                today_key = datetime.now(MOSCOW).date().isoformat()
                coin_reward = BATTLE_WIN_REWARD
                profile["coins"] = int(profile.get("coins") or 0) + coin_reward
                data["coin_transactions"].append({
                    "id": f"battle-win:{battle['id']}:{winner_id}",
                    "user_id": winner_id,
                    "amount": coin_reward,
                    "kind": "battle_win",
                    "battle_id": battle["id"],
                    "created_at": _now_iso(),
                })

                wins_today = 0
                for candidate in data["battles"].values():
                    if candidate.get("status") != "complete":
                        continue
                    completed_at = candidate.get("completed_at") or candidate.get("started_at") or candidate.get("created_at")
                    if not completed_at or self._period_key(completed_at, "day") != today_key:
                        continue
                    if self._battle_winner_id(candidate) == winner_id:
                        wins_today += 1

                profile["updated_at"] = _now_iso()
                battle["rewards"][winner_id] = {
                    "coins": coin_reward,
                    "winsToday": wins_today,
                }
        battle["bonus_awarded"] = True
        battle["completed_at"] = battle.get("completed_at") or _now_iso()

    @staticmethod
    def _battle_winner_id(battle):
        players = battle.get("players", {})
        if battle.get("status") != "complete" or len(players) < 2:
            return None
        forfeited_by = battle.get("forfeited_by")
        if forfeited_by in players:
            return next((uid for uid in players if uid != forfeited_by), None)
        best = max(int(player.get("score") or 0) for player in players.values())
        winners = [uid for uid, player in players.items() if int(player.get("score") or 0) == best]
        return winners[0] if len(winners) == 1 else None

    def _battle_reward_status(self, data, profile, user_id):
        today = datetime.now(MOSCOW).date()
        win_dates = []
        recent_win_totals = {}
        for battle in data["battles"].values():
            winner_id = self._battle_winner_id(battle)
            if not winner_id or self._is_bot(winner_id):
                continue
            timestamp = battle.get("completed_at") or battle.get("started_at") or battle.get("created_at")
            try:
                win_date = datetime.fromisoformat(timestamp).astimezone(MOSCOW).date()
            except (TypeError, ValueError):
                continue
            if 0 <= (today - win_date).days < 30:
                recent_win_totals[winner_id] = recent_win_totals.get(winner_id, 0) + 1
            if winner_id == user_id:
                win_dates.append(win_date)
        wins_today = sum(day == today for day in win_dates)
        won_days = set(win_dates)
        has_thirty_day_streak = all(today - timedelta(days=offset) in won_days for offset in range(30))
        own_recent_wins = recent_win_totals.get(user_id, 0)
        is_month_leader = own_recent_wins > 0 and own_recent_wins == max(recent_win_totals.values(), default=0)
        day_key = today.isoformat()
        month_key = today.strftime("%Y-%m")
        daily_claim = profile.setdefault("battle_daily_claims", {}).get(day_key)
        monthly_claim = profile.setdefault("battle_monthly_claims", {}).get(month_key)
        return {
            "winsToday": wins_today,
            "winningDaysInLast30": sum(today - timedelta(days=offset) in won_days for offset in range(30)),
            "winsInLast30": own_recent_wins,
            "monthLeader": is_month_leader,
            "daily": {
                "eligible": wins_today >= 3,
                "available": wins_today >= 3 and not daily_claim,
                "claimed": bool(daily_claim),
                "prize": daily_claim,
            },
            "monthly": {
                "eligible": has_thirty_day_streak and is_month_leader,
                "available": has_thirty_day_streak and is_month_leader and not monthly_claim,
                "claimed": bool(monthly_claim),
                "prize": monthly_claim,
            },
        }

    async def spin_battle_reward(self, user, tier):
        if tier not in {"daily", "monthly"}:
            raise CommunityError("Неизвестный тип награды")
        async with self.lock:
            data = self._load()
            user_id = self._user_id(user)
            profile = self._ensure_profile(data, user)
            status = self._battle_reward_status(data, profile, user_id)
            if not status[tier]["eligible"]:
                requirement = "3 победы за день" if tier == "daily" else "лидерство по победам и по одной победе в каждый из последних 30 дней"
                raise CommunityError(f"Для этой награды нужны {requirement}")
            if not status[tier]["available"]:
                raise CommunityError("Эта награда уже получена")

            now = datetime.now(MOSCOW)
            rng = random.SystemRandom()
            if tier == "daily":
                candidates = [
                    item for item in SHOP_CATALOG
                    if item.get("slot") in {"outfit", "accessory"} and int(item.get("price") or 0) <= 2500
                ]
                discounts = BATTLE_DAILY_DISCOUNTS
                item_days = coupon_days = BATTLE_DAILY_REWARD_DAYS
                claim_key = now.date().isoformat()
                claim_store = profile["battle_daily_claims"]
            else:
                candidates = [
                    item for item in SHOP_CATALOG
                    if item.get("slot") in {"outfit", "accessory"} and int(item.get("price") or 0) == 5000
                ]
                discounts = BATTLE_MONTHLY_DISCOUNTS
                item_days = BATTLE_MONTHLY_ITEM_DAYS
                coupon_days = BATTLE_MONTHLY_COUPON_DAYS
                claim_key = now.strftime("%Y-%m")
                claim_store = profile["battle_monthly_claims"]

            prize_kind = rng.choice(("item", "discount"))
            if prize_kind == "item" and candidates:
                item = rng.choice(candidates)
                expires_at = (now + timedelta(days=item_days)).isoformat()
                profile.setdefault("temporary_items", {})[item["id"]] = expires_at
                prize = {
                    "kind": "item", "itemId": item["id"], "label": item["name"],
                    "icon": item["icon"], "expiresAt": expires_at, "validDays": item_days,
                }
            else:
                percent = int(rng.choice(discounts))
                expires_at = (now + timedelta(days=coupon_days)).isoformat()
                coupon = {
                    "id": uuid.uuid4().hex[:12], "percent": percent, "created_at": _now_iso(),
                    "expires_at": expires_at, "used": False, "source": f"battle_{tier}",
                }
                profile.setdefault("discount_coupons", []).append(coupon)
                prize = {
                    "kind": "discount", "couponId": coupon["id"], "value": percent,
                    "label": f"Скидка {percent}%", "icon": "🎟️",
                    "expiresAt": expires_at, "validDays": coupon_days,
                }
            claim_store[claim_key] = prize
            profile["updated_at"] = _now_iso()
            self._save(data)
            result = self._battle_reward_status(data, profile, user_id)
            result.update({"spun": True, "tier": tier, "prize": prize})
            return result

    def _battle_view(self, data, battle, user_id, question_map):
        server_now = datetime.now(MOSCOW)
        player_ids = list(battle["players"])
        opponent_id = next((uid for uid in player_ids if uid != user_id), None)

        def public_player(uid):
            if not uid:
                return None
            player = battle["players"][uid]
            answered_values = list(player.get("answers", {}).values())
            if self._is_bot(uid):
                return {
                    "nickname": "Матан-Бот",
                    "avatarUrl": "",
                    "score": player["score"],
                    "answered": sum(value != BATTLE_MISSED_ANSWER for value in answered_values),
                    "missed": sum(value == BATTLE_MISSED_ANSWER for value in answered_values),
                    "finished": bool(player.get("finished_at")),
                    "isBot": True,
                }
            profile = data["profiles"].get(uid, {})
            return {
                "nickname": profile.get("nickname", "Участник"),
                "avatarUrl": profile.get("avatar_url", ""),
                "score": player["score"],
                "answered": sum(value != BATTLE_MISSED_ANSWER for value in answered_values),
                "missed": sum(value == BATTLE_MISSED_ANSWER for value in answered_values),
                "finished": bool(player.get("finished_at")),
                "isBot": False,
            }

        questions = [question_map[qid].as_public_dict() for qid in battle["question_ids"] if qid in question_map]
        reward_status = self._battle_reward_status(data, data["profiles"].get(user_id, {}), user_id)
        player = battle["players"][user_id]
        current_index = self._player_question_index(battle, player)
        deadline_at = None
        if battle["status"] == "active" and current_index < len(battle["question_ids"]):
            started_raw = player.get("question_started_at") or battle.get("started_at")
            if started_raw:
                deadline_at = (
                    datetime.fromisoformat(started_raw).astimezone(MOSCOW)
                    + timedelta(seconds=BATTLE_QUESTION_SECONDS)
                ).isoformat()
        countdown_remaining_ms = 0
        countdown_raw = battle.get("countdown_until")
        if countdown_raw:
            try:
                countdown_remaining_ms = max(
                    0,
                    round((datetime.fromisoformat(countdown_raw).astimezone(MOSCOW) - server_now).total_seconds() * 1000),
                )
            except (TypeError, ValueError):
                countdown_remaining_ms = 0
        question_remaining_ms = 0
        if deadline_at:
            try:
                question_remaining_ms = max(
                    0,
                    round((datetime.fromisoformat(deadline_at).astimezone(MOSCOW) - server_now).total_seconds() * 1000),
                )
            except (TypeError, ValueError):
                question_remaining_ms = 0
        review_summary = None
        if battle["status"] == "complete":
            topic_errors = {}
            answers = player.get("answers", {})
            for question_id in battle.get("question_ids", []):
                question = question_map.get(question_id)
                if not question:
                    continue
                selected = answers.get(question_id, BATTLE_MISSED_ANSWER)
                if selected != question.correct_index:
                    topic_errors[question.topic] = topic_errors.get(question.topic, 0) + 1
            review_topics = [
                topic for topic, _errors in sorted(
                    topic_errors.items(), key=lambda item: (-item[1], item[0])
                )[:3]
            ]
            review_summary = {
                "correct": int(player.get("score") or 0),
                "errors": max(0, len(battle.get("question_ids", [])) - int(player.get("score") or 0)),
                "coinsEarned": int(((battle.get("rewards") or {}).get(user_id) or {}).get("coins") or 0),
                "reviewTopics": review_topics,
            }
        return {
            "id": battle["id"],
            "grade": battle["grade"],
            "status": battle["status"],
            "me": public_player(user_id),
            "opponent": public_player(opponent_id),
            "questions": questions if battle["status"] in {"active", "complete"} else [],
            "myAnswers": battle["players"][user_id]["answers"],
            "forfeitedByMe": battle.get("forfeited_by") == user_id,
            "opponentForfeited": bool(battle.get("forfeited_by") and battle.get("forfeited_by") != user_id),
            "currentQuestionIndex": current_index,
            "serverNowAt": server_now.isoformat(),
            "countdownUntil": battle.get("countdown_until"),
            "countdownRemainingMs": countdown_remaining_ms,
            "questionDeadlineAt": deadline_at,
            "questionRemainingMs": question_remaining_ms,
            "questionSeconds": BATTLE_QUESTION_SECONDS,
            "reward": (battle.get("rewards") or {}).get(user_id, {"coins": 0}),
            "battleRewards": reward_status,
            "coins": int((data["profiles"].get(user_id) or {}).get("coins") or 0),
            "admin": self._is_admin({"id": user_id, "username": (data["profiles"].get(user_id) or {}).get("telegram_username", "")}),
            "reviewSummary": review_summary,
        }

    async def battle_stats(self, user):
        user_id = self._user_id(user)
        async with self.lock:
            data = self._load()
            profile = self._ensure_profile(data, user)
            wins = draws = losses = 0
            for battle in data["battles"].values():
                if battle.get("status") != "complete" or user_id not in battle.get("players", {}):
                    continue
                players = battle["players"]
                if len(players) < 2:
                    continue
                forfeited_by = battle.get("forfeited_by")
                if forfeited_by:
                    if forfeited_by == user_id:
                        losses += 1
                    else:
                        wins += 1
                    continue
                own_score = int(players[user_id].get("score") or 0)
                other_scores = [int(player.get("score") or 0) for uid, player in players.items() if uid != user_id]
                if not other_scores:
                    continue
                other_score = max(other_scores)
                if own_score > other_score:
                    wins += 1
                elif own_score < other_score:
                    losses += 1
                else:
                    draws += 1
            total = wins + draws + losses
            percent = lambda value: round((value * 100 / total), 1) if total else 0
            today_key = datetime.now(MOSCOW).date().isoformat()
            coins_today = sum(
                int(item.get("amount") or 0)
                for item in data["coin_transactions"]
                if item.get("user_id") == user_id
                and item.get("kind") == "battle_win"
                and self._period_key(item["created_at"], "day") == today_key
            )
            self._save(data)
            return {
                "total": total,
                "wins": wins,
                "draws": draws,
                "losses": losses,
                "winPercent": percent(wins),
                "drawPercent": percent(draws),
                "lossPercent": percent(losses),
                "coinsToday": coins_today,
                "coins": int(profile.get("coins") or 0),
                "admin": self._is_admin(user),
            }

    async def battle_state(self, user, battle_id, question_map):
        user_id = self._user_id(user)
        async with self.lock:
            data = self._load()
            self._expire_battles(data, question_map)
            battle = data["battles"].get(battle_id)
            if not battle or user_id not in battle["players"]:
                raise CommunityError("Баттл не найден")
            self._save(data)
            return self._battle_view(data, battle, user_id, question_map)

    async def active_battle(self, user):
        """Return the invited/random battle that should open in an active WebApp."""
        user_id = self._user_id(user)
        async with self.lock:
            data = self._load()
            self._ensure_profile(data, user)
            candidates = [
                battle for battle in data["battles"].values()
                if battle.get("status") == "active" and user_id in battle.get("players", {})
            ]
            candidates.sort(
                key=lambda battle: battle.get("started_at") or battle.get("created_at") or "",
                reverse=True,
            )
            return {"battleId": candidates[0]["id"] if candidates else None}

    async def forfeit_battle(self, user, battle_id, question_map):
        """Cancel a search or record a technical loss when a player leaves an active battle."""
        user_id = self._user_id(user)
        async with self.lock:
            data = self._load()
            self._expire_battles(data, question_map)
            battle = data["battles"].get(battle_id)
            if not battle or user_id not in battle.get("players", {}):
                raise CommunityError("Баттл не найден")
            if battle.get("status") == "waiting":
                battle["status"] = "cancelled"
                battle["completed_at"] = _now_iso()
            elif battle.get("status") == "active":
                now = _now_iso()
                battle["forfeited_by"] = user_id
                player = battle["players"][user_id]
                answers = player.setdefault("answers", {})
                for question_id in battle.get("question_ids", []):
                    answers.setdefault(question_id, BATTLE_MISSED_ANSWER)
                player["question_index"] = len(battle.get("question_ids", []))
                player["question_started_at"] = None
                player["finished_at"] = now
                for opponent_id, opponent in battle["players"].items():
                    if opponent_id != user_id:
                        opponent["finished_at"] = opponent.get("finished_at") or now
                battle["status"] = "complete"
                battle["completed_at"] = now
                self._award_battle_bonus(data, battle)
            self._save(data)
            return self._battle_view(data, battle, user_id, question_map)

    async def answer_battle(self, user, battle_id, question_id, selected_index, question_map):
        user_id = self._user_id(user)
        async with self.lock:
            data = self._load()
            self._expire_battles(data, question_map)
            battle = data["battles"].get(battle_id)
            if not battle or user_id not in battle["players"] or battle["status"] != "active":
                raise CommunityError("Активный баттл не найден")
            if question_id not in battle["question_ids"] or question_id not in question_map:
                raise CommunityError("Задание не относится к этому баттлу")
            player = battle["players"][user_id]
            if question_id in player["answers"]:
                if player["answers"][question_id] == BATTLE_MISSED_ANSWER:
                    raise CommunityError("30 секунд истекли — ответ на это задание не засчитывается")
                raise CommunityError("Ответ на это задание уже принят")

            current_index = self._player_question_index(battle, player)
            if current_index >= len(battle["question_ids"]):
                raise CommunityError("Все задания баттла уже завершены")
            if question_id != battle["question_ids"][current_index]:
                raise CommunityError("Сначала завершите текущее задание")
            started_raw = player.get("question_started_at")
            if started_raw:
                try:
                    question_started_at = datetime.fromisoformat(started_raw).astimezone(MOSCOW)
                except ValueError:
                    question_started_at = None
                if question_started_at and datetime.now(MOSCOW) < question_started_at:
                    raise CommunityError("Дождитесь команды «Старт»")
            try:
                selected_index = int(selected_index)
            except (TypeError, ValueError) as error:
                raise CommunityError("Выберите один из четырёх вариантов") from error
            if selected_index not in {0, 1, 2, 3}:
                raise CommunityError("Выберите один из четырёх вариантов")

            question = question_map[question_id]
            is_correct = selected_index == question.correct_index
            player["answers"][question_id] = selected_index
            if is_correct:
                player["score"] += 1
            data["attempts"].append({
                "attempt_key": f"battle:{battle_id}:{user_id}:{question_id}",
                "user_id": user_id,
                "question_id": question_id,
                "grade": battle["grade"],
                "correct": is_correct,
                "points": 2 if is_correct else 0,
                "source": "battle",
                "created_at": _now_iso(),
            })
            next_index = current_index + 1
            player["question_index"] = next_index
            player["question_started_at"] = _now_iso() if next_index < len(battle["question_ids"]) else None
            if next_index >= len(battle["question_ids"]):
                player["finished_at"] = _now_iso()
            if len(battle["players"]) == 2 and all(p.get("finished_at") for p in battle["players"].values()):
                battle["status"] = "complete"
                self._award_battle_bonus(data, battle)
            self._save(data)
            return {
                "correct": is_correct,
                "solution": question.solution,
                "solutionImageUrl": question.solution_image_url,
                "battle": self._battle_view(data, battle, user_id, question_map),
            }
