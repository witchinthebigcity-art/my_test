import asyncio
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
            "leaderboard_consent": False,
            "grade": None,
            "updated_at": _now_iso(),
        })
        if user.get("photo_url"):
            profile["avatar_url"] = user["photo_url"]
        return profile

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
            profile["updated_at"] = _now_iso()
            self._save(data)
            return {**profile, "awards": [a for a in data["awards"] if a["user_id"] == self._user_id(user)]}

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
            self._expire_battles(data)
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

    def _expire_battles(self, data):
        now = datetime.now(MOSCOW)
        for battle in data["battles"].values():
            created = datetime.fromisoformat(battle["created_at"])
            age = now - created.astimezone(MOSCOW)
            if battle["status"] == "waiting" and age > timedelta(minutes=10):
                battle["status"] = "cancelled"
            elif battle["status"] == "active" and age > timedelta(minutes=25):
                battle["status"] = "complete"
                self._award_battle_bonus(data, battle)

    def _award_battle_bonus(self, data, battle):
        if battle.get("bonus_awarded") or len(battle["players"]) < 2:
            return
        best = max(player["score"] for player in battle["players"].values())
        winners = [uid for uid, player in battle["players"].items() if player["score"] == best]
        if len(winners) == 1:
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
            profile = data["profiles"].get(uid, {})
            player = battle["players"][uid]
            return {
                "nickname": profile.get("nickname", "Участник"),
                "avatarUrl": profile.get("avatar_url", ""),
                "score": player["score"],
                "answered": len(player["answers"]),
                "finished": bool(player.get("finished_at")),
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
            self._expire_battles(data)
            battle = data["battles"].get(battle_id)
            if not battle or user_id not in battle["players"]:
                raise CommunityError("Баттл не найден")
            self._save(data)
            return self._battle_view(data, battle, user_id, question_map)

    async def answer_battle(self, user, battle_id, question_id, selected_index, question_map):
        user_id = self._user_id(user)
        async with self.lock:
            data = self._load()
            self._expire_battles(data)
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
