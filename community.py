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

    values = dict(parse_qsl(init_data, keep_blank_values=True))
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
    if auth_date <= 0 or abs(time.time() - auth_date) > max_age_seconds:
        raise CommunityError("Сессия Telegram устарела. Откройте приложение заново")

    try:
        user = json.loads(values.get("user", "{}"))
    except json.JSONDecodeError as error:
        raise CommunityError("Некорректный Telegram-профиль") from error
    if not user.get("id"):
        raise CommunityError("Telegram не передал идентификатор пользователя")
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
        "version": 1,
        "profiles": {},
        "attempts": [],
        "awards": [],
        "battles": {},
        "enrollments": [],
    }


class CommunityStore:
    def __init__(self, path):
        self.path = path
        self.avatar_directory = os.path.join(os.path.dirname(path) or ".", "avatars")
        self.lock = asyncio.Lock()

    def _load(self):
        if not os.path.exists(self.path):
            return _default_data()
        with open(self.path, "r", encoding="utf-8") as source:
            data = json.load(source)
        default = _default_data()
        for key, value in default.items():
            data.setdefault(key, value)
        return data

    def _save(self, data):
        directory = os.path.dirname(self.path) or "."
        os.makedirs(directory, exist_ok=True)
        temporary_path = f"{self.path}.tmp"
        with open(temporary_path, "w", encoding="utf-8") as target:
            json.dump(data, target, ensure_ascii=False, indent=2)
        os.replace(temporary_path, self.path)

    @staticmethod
    def _user_id(user):
        return str(user["id"])

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
            "leaderboard_consent": False,
            "grade": None,
            "updated_at": _now_iso(),
        })
        profile.setdefault("avatar_source", "telegram")
        profile["telegram_avatar_url"] = user.get("photo_url", profile.get("telegram_avatar_url", ""))
        if user.get("photo_url") and profile.get("avatar_source") != "custom":
            profile["avatar_url"] = user["photo_url"]
        return profile

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
            self._save(data)
            return {
                **profile,
                "awards": [award for award in data["awards"] if award["user_id"] == self._user_id(user)],
            }

    async def update_profile(self, user, payload):
        async with self.lock:
            data = self._load()
            profile = self._ensure_profile(data, user)
            if "nickname" in payload:
                profile["nickname"] = validate_nickname(payload["nickname"])
            if "leaderboardConsent" in payload:
                profile["leaderboard_consent"] = bool(payload["leaderboardConsent"])
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
            self._save(data)
            return {**profile, "awards": [a for a in data["awards"] if a["user_id"] == self._user_id(user)]}

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
            is_correct = bool(payload.get("isCorrect"))
            attempt_key = str(payload.get("attemptKey") or uuid.uuid4().hex)
            if any(item.get("attempt_key") == attempt_key for item in data["attempts"]):
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

    async def leaderboard(self, period="day", grade=None):
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
                profile = data["profiles"].get(user_id, {})
                entry = {
                    "rank": rank,
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
            ), None)
            if waiting:
                waiting["players"][user_id] = {"score": 0, "answers": {}, "finished_at": None}
                waiting["status"] = "active"
                waiting["started_at"] = _now_iso()
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
                    "players": {user_id: {"score": 0, "answers": {}, "finished_at": None}},
                    "created_at": _now_iso(),
                    "started_at": None,
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
        battle["status"] = "active"
        battle["started_at"] = _now_iso()

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
        best = max(player["score"] for player in battle["players"].values())
        winners = [uid for uid, player in battle["players"].items() if player["score"] == best]
        if len(winners) == 1:
            if self._is_bot(winners[0]):
                battle["bonus_awarded"] = True
                return
            data["attempts"].append({
                "attempt_key": f"battle-win:{battle['id']}",
                "user_id": winners[0],
                "question_id": "battle-win",
                "grade": battle["grade"],
                "correct": True,
                "points": 3,
                "source": "battle_bonus",
                "created_at": _now_iso(),
            })
        battle["bonus_awarded"] = True

    def _battle_view(self, data, battle, user_id, question_map):
        player_ids = list(battle["players"])
        opponent_id = next((uid for uid in player_ids if uid != user_id), None)

        def public_player(uid):
            if not uid:
                return None
            player = battle["players"][uid]
            if self._is_bot(uid):
                return {
                    "nickname": "Матан-Бот",
                    "avatarUrl": "",
                    "score": player["score"],
                    "answered": len(player["answers"]),
                    "finished": bool(player.get("finished_at")),
                    "isBot": True,
                }
            profile = data["profiles"].get(uid, {})
            return {
                "nickname": profile.get("nickname", "Участник"),
                "avatarUrl": profile.get("avatar_url", ""),
                "score": player["score"],
                "answered": len(player["answers"]),
                "finished": bool(player.get("finished_at")),
                "isBot": False,
            }

        questions = [question_map[qid].as_public_dict() for qid in battle["question_ids"] if qid in question_map]
        return {
            "id": battle["id"],
            "grade": battle["grade"],
            "status": battle["status"],
            "me": public_player(user_id),
            "opponent": public_player(opponent_id),
            "questions": questions if battle["status"] in {"active", "complete"} else [],
            "myAnswers": battle["players"][user_id]["answers"],
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
                raise CommunityError("Ответ на это задание уже принят")

            question = question_map[question_id]
            is_correct = int(selected_index) == question.correct_index
            player["answers"][question_id] = int(selected_index)
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
            if len(player["answers"]) >= len(battle["question_ids"]):
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
