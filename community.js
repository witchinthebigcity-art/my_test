const communityState = {
    battleId: null,
    battle: null,
    battleQuestionIndex: 0,
    battlePoll: null,
};
let pendingAvatarDataUrl = null;

function telegramHeaders(json = false) {
    const headers = { 'X-Telegram-Init-Data': tg.initData || '' };
    if (json) headers['Content-Type'] = 'application/json';
    return headers;
}

async function communityRequest(url, options = {}) {
    const response = await fetch(url, options);
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(payload.error || payload.message || 'Не удалось выполнить запрос');
    return payload;
}

function setInlineMessage(id, message, kind = 'info') {
    const element = document.getElementById(id);
    element.textContent = message;
    element.dataset.kind = kind;
    element.hidden = !message;
}

function setAvatar(image, placeholder, url) {
    image.hidden = !url;
    placeholder.hidden = Boolean(url);
    if (url) image.src = url;
    else image.removeAttribute('src');
}

function startDiagnostic() {
    window.diagnosticMode = true;
    startQuizWithConsent(false);
}

function chooseProfileAvatar() {
    document.getElementById('profileAvatarInput').click();
}

async function compressAvatar(file) {
    if (!file || !['image/jpeg', 'image/png', 'image/webp'].includes(file.type)) {
        throw new Error('Выберите изображение JPG, PNG или WebP');
    }
    if (file.size > 8 * 1024 * 1024) throw new Error('Исходный файл должен быть меньше 8 МБ');
    const objectUrl = URL.createObjectURL(file);
    try {
        const image = new Image();
        image.src = objectUrl;
        await image.decode();
        const side = Math.min(image.naturalWidth, image.naturalHeight);
        if (!side) throw new Error('Не удалось прочитать изображение');
        const canvas = document.createElement('canvas');
        canvas.width = 320;
        canvas.height = 320;
        const context = canvas.getContext('2d');
        const sourceX = (image.naturalWidth - side) / 2;
        const sourceY = (image.naturalHeight - side) / 2;
        context.drawImage(image, sourceX, sourceY, side, side, 0, 0, 320, 320);
        return canvas.toDataURL('image/jpeg', 0.86);
    } finally {
        URL.revokeObjectURL(objectUrl);
    }
}

async function handleProfileAvatarFile(event) {
    setInlineMessage('profileMessage', 'Обрабатываем изображение…');
    try {
        pendingAvatarDataUrl = await compressAvatar(event.target.files?.[0]);
        setAvatar(
            document.getElementById('profileAvatar'),
            document.getElementById('profileAvatarPlaceholder'),
            pendingAvatarDataUrl
        );
        setInlineMessage('profileMessage', 'Аватарка готова. Нажмите «Сохранить профиль».', 'success');
    } catch (error) {
        pendingAvatarDataUrl = null;
        setInlineMessage('profileMessage', error.message, 'error');
    } finally {
        event.target.value = '';
    }
}

async function restoreTelegramAvatar() {
    setInlineMessage('profileMessage', 'Восстанавливаем фото Telegram…');
    try {
        const profile = await communityRequest('/api/profile', {
            method: 'POST',
            headers: telegramHeaders(true),
            body: JSON.stringify({ useTelegramAvatar: true }),
        });
        pendingAvatarDataUrl = null;
        setAvatar(
            document.getElementById('profileAvatar'),
            document.getElementById('profileAvatarPlaceholder'),
            profile.avatar_url
        );
        setInlineMessage('profileMessage', 'Фото Telegram восстановлено', 'success');
    } catch (error) {
        setInlineMessage('profileMessage', error.message, 'error');
    }
}

async function openProfile() {
    showScreen('profileScreen');
    setInlineMessage('profileMessage', 'Загружаем профиль…');
    try {
        const profile = await communityRequest('/api/profile', { headers: telegramHeaders() });
        document.getElementById('profileNickname').value = profile.nickname || '';
        document.getElementById('profilePreviewName').textContent = profile.nickname || 'Участник';
        document.getElementById('leaderboardConsent').checked = Boolean(profile.leaderboard_consent);
        setAvatar(
            document.getElementById('profileAvatar'),
            document.getElementById('profileAvatarPlaceholder'),
            profile.avatar_url
        );
        renderAwards(profile.awards || []);
        setInlineMessage('profileMessage', '');
    } catch (error) {
        setInlineMessage('profileMessage', error.message, 'error');
    }
}

async function saveProfile() {
    setInlineMessage('profileMessage', 'Сохраняем…');
    try {
        const payload = await communityRequest('/api/profile', {
            method: 'POST',
            headers: telegramHeaders(true),
            body: JSON.stringify({
                nickname: document.getElementById('profileNickname').value,
                leaderboardConsent: document.getElementById('leaderboardConsent').checked,
                grade: currentClass,
                avatarDataUrl: pendingAvatarDataUrl,
            }),
        });
        pendingAvatarDataUrl = null;
        document.getElementById('profilePreviewName').textContent = payload.nickname;
        setAvatar(
            document.getElementById('profileAvatar'),
            document.getElementById('profileAvatarPlaceholder'),
            payload.avatar_url
        );
        renderAwards(payload.awards || []);
        setInlineMessage('profileMessage', 'Профиль сохранён', 'success');
    } catch (error) {
        setInlineMessage('profileMessage', error.message, 'error');
    }
}

function renderAwards(awards) {
    const shelf = document.getElementById('awardShelf');
    shelf.replaceChildren();
    if (!awards.length) {
        const empty = document.createElement('p');
        empty.className = 'empty-state';
        empty.textContent = 'Награды появятся после попадания в тройку лучших.';
        shelf.appendChild(empty);
        return;
    }
    awards.slice().reverse().forEach((award) => {
        const card = document.createElement('div');
        card.className = `award-card award-${award.period}`;
        const icon = document.createElement('span');
        icon.className = 'award-icon';
        icon.textContent = award.icon;
        const text = document.createElement('div');
        const name = document.createElement('strong');
        name.textContent = award.name;
        const period = document.createElement('small');
        period.textContent = award.period_key;
        text.append(name, period);
        card.append(icon, text);
        shelf.appendChild(card);
    });
}

async function openLeaderboard(period = 'day') {
    if (!currentClass) return;
    showScreen('leaderboardScreen');
    document.getElementById('leaderboardGrade').textContent = currentClass;
    document.getElementById('ratingDayButton').classList.toggle('active', period === 'day');
    document.getElementById('ratingMonthButton').classList.toggle('active', period === 'month');
    const list = document.getElementById('leaderboardList');
    list.replaceChildren();
    const loading = document.createElement('p');
    loading.className = 'empty-state';
    loading.textContent = 'Загружаем результаты…';
    list.appendChild(loading);
    try {
        const payload = await communityRequest(`/api/leaderboard?period=${period}&grade=${currentClass}`);
        renderLeaderboard(payload.entries || []);
    } catch (error) {
        list.replaceChildren();
        const message = document.createElement('p');
        message.className = 'empty-state';
        message.textContent = error.message;
        list.appendChild(message);
    }
}

function renderLeaderboard(entries) {
    const list = document.getElementById('leaderboardList');
    list.replaceChildren();
    if (!entries.length) {
        const message = document.createElement('p');
        message.className = 'empty-state';
        message.textContent = 'Пока нет участников с результатами. Можно стать первым.';
        list.appendChild(message);
        return;
    }
    entries.forEach((entry) => {
        const row = document.createElement('div');
        row.className = `leaderboard-row rank-${entry.rank}`;
        const rank = document.createElement('span');
        rank.className = 'leaderboard-rank';
        rank.textContent = entry.award?.icon || entry.rank;
        const avatar = document.createElement(entry.avatarUrl ? 'img' : 'span');
        avatar.className = 'leaderboard-avatar';
        if (entry.avatarUrl) {
            avatar.src = entry.avatarUrl;
            avatar.alt = '';
        } else {
            avatar.textContent = '∑';
        }
        const identity = document.createElement('div');
        identity.className = 'leaderboard-identity';
        const nickname = document.createElement('strong');
        nickname.textContent = entry.nickname;
        const result = document.createElement('small');
        result.textContent = `${entry.correct} из ${entry.total} верно`;
        identity.append(nickname, result);
        const score = document.createElement('strong');
        score.className = 'leaderboard-score';
        score.textContent = `${entry.score} баллов`;
        row.append(rank, avatar, identity, score);
        list.appendChild(row);
    });
}

function openBattle() {
    showScreen('battleScreen');
    document.getElementById('battleLobby').hidden = false;
    document.getElementById('battleGame').hidden = true;
    setInlineMessage('battleStatus', '');
}

async function joinBattle() {
    setInlineMessage('battleStatus', 'Ищем соперника вашего класса…');
    try {
        const battle = await communityRequest('/api/battles/join', {
            method: 'POST',
            headers: telegramHeaders(true),
            body: JSON.stringify({ grade: currentClass }),
        });
        communityState.battleId = battle.id;
        handleBattleState(battle);
        startBattlePolling();
    } catch (error) {
        setInlineMessage('battleStatus', error.message, 'error');
    }
}

function startBattlePolling() {
    clearInterval(communityState.battlePoll);
    communityState.battlePoll = setInterval(refreshBattle, 2500);
}

async function refreshBattle() {
    if (!communityState.battleId) return;
    try {
        const battle = await communityRequest(`/api/battles/${communityState.battleId}`, {
            headers: telegramHeaders(),
        });
        handleBattleState(battle);
    } catch (error) {
        clearInterval(communityState.battlePoll);
        setInlineMessage('battleStatus', error.message, 'error');
    }
}

function handleBattleState(battle) {
    communityState.battle = battle;
    if (battle.status === 'waiting') {
        document.getElementById('battleLobby').hidden = false;
        document.getElementById('battleGame').hidden = true;
        setInlineMessage('battleStatus', 'Ищем ученика вашего класса. Если за 20 секунд пара не найдётся, начнётся баттл с Матан-Ботом.');
        return;
    }
    if (battle.status === 'cancelled') {
        clearInterval(communityState.battlePoll);
        setInlineMessage('battleStatus', 'За 10 минут соперник не нашёлся. Попробуйте ещё раз позже.');
        return;
    }

    document.getElementById('battleLobby').hidden = true;
    document.getElementById('battleGame').hidden = false;
    renderBattlePlayers(battle);

    const unansweredIndex = battle.questions.findIndex((question) => !(question.id in battle.myAnswers));
    if (unansweredIndex >= 0 && battle.status === 'active') {
        communityState.battleQuestionIndex = unansweredIndex;
        renderBattleQuestion();
        return;
    }
    renderBattleFinish(battle);
}

function renderBattlePlayers(battle) {
    const container = document.getElementById('battlePlayers');
    container.replaceChildren();
    [battle.me, battle.opponent].forEach((player, index) => {
        const card = document.createElement('div');
        card.className = 'battle-player';
        const name = document.createElement('strong');
        name.textContent = player ? `${player.isBot ? '🤖 ' : ''}${player.nickname}` : (index ? 'Ожидание…' : 'Вы');
        const result = document.createElement('small');
        result.textContent = player ? `${player.score} баллов · ${player.answered}/5` : '—';
        card.append(name, result);
        container.appendChild(card);
    });
}

function renderBattleQuestion() {
    const battle = communityState.battle;
    const question = battle.questions[communityState.battleQuestionIndex];
    document.getElementById('battleProgress').textContent = `Задание ${communityState.battleQuestionIndex + 1} из ${battle.questions.length}`;
    setMathContent(document.getElementById('battleTopic'), question.topic);
    setMathContent(document.getElementById('battleQuestion'), question.question);
    setQuestionImage('battleQuestionImage', question.imageUrl);
    document.getElementById('battleFeedback').hidden = true;
    document.getElementById('battleNextButton').hidden = true;
    const options = document.getElementById('battleOptions');
    options.replaceChildren();
    question.options.forEach((option, selectedIndex) => {
        const button = document.createElement('button');
        button.className = 'btn btn-secondary';
        setMathContent(button, option);
        button.addEventListener('click', () => answerBattle(question.id, selectedIndex));
        options.appendChild(button);
    });
}

async function answerBattle(questionId, selectedIndex) {
    document.querySelectorAll('#battleOptions button').forEach((button) => button.disabled = true);
    try {
        const result = await communityRequest(`/api/battles/${communityState.battleId}/answer`, {
            method: 'POST',
            headers: telegramHeaders(true),
            body: JSON.stringify({ questionId, selectedIndex }),
        });
        communityState.battle = result.battle;
        renderBattlePlayers(result.battle);
        const feedback = document.getElementById('battleFeedback');
        setMathContent(feedback, result.correct ? 'Верно!' : `Ответ неверный. ${result.solution}`);
        feedback.dataset.kind = result.correct ? 'success' : 'error';
        feedback.hidden = false;
        document.getElementById('battleNextButton').hidden = false;
    } catch (error) {
        setInlineMessage('battleFeedback', error.message, 'error');
    }
}

function nextBattleQuestion() {
    handleBattleState(communityState.battle);
}

function renderBattleFinish(battle) {
    document.getElementById('battleOptions').replaceChildren();
    document.getElementById('battleNextButton').hidden = true;
    document.getElementById('battleQuestionImage').hidden = true;
    document.getElementById('battleTopic').textContent = battle.status === 'complete' ? 'Баттл завершён' : 'Ответы приняты';
    const question = document.getElementById('battleQuestion');
    if (battle.status !== 'complete') {
        question.textContent = 'Ожидаем, пока соперник закончит свои пять заданий.';
    } else if (battle.me.score > battle.opponent.score) {
        question.textContent = 'Победа! Вы получаете бонус рейтинга.';
    } else if (battle.me.score < battle.opponent.score) {
        question.textContent = 'В этот раз победил соперник. Можно вызвать нового участника.';
    } else {
        question.textContent = 'Ничья — одинаковое количество правильных ответов.';
    }
    if (battle.status === 'complete') clearInterval(communityState.battlePoll);
}

document.getElementById('profileAvatarInput')?.addEventListener('change', handleProfileAvatarFile);

function leaveBattleScreen() {
    clearInterval(communityState.battlePoll);
    showScreen('mainMenu');
}

function openEnrollment() {
    document.getElementById('enrollmentGrade').value = String(currentClass || 8);
    document.getElementById('enrollmentFormContent').hidden = false;
    document.getElementById('enrollmentSuccessActions').hidden = true;
    setInlineMessage('enrollmentMessage', '');
    showScreen('enrollmentScreen');
}

function openAuthor() {
    showScreen('authorScreen');
}

async function submitEnrollment() {
    setInlineMessage('enrollmentMessage', 'Отправляем заявку…');
    try {
        const result = await communityRequest('/api/enrollments', {
            method: 'POST',
            headers: telegramHeaders(true),
            body: JSON.stringify({
                grade: Number(document.getElementById('enrollmentGrade').value),
                goal: document.getElementById('enrollmentGoal').value,
                frequency: Number(document.getElementById('enrollmentFrequency').value),
                consent: document.getElementById('enrollmentConsent').checked,
                diagnosticScore: window.lastDiagnosticScore ?? null,
            }),
        });
        setInlineMessage('enrollmentMessage', `Заявка ${result.leadId} отправлена. Можно написать преподавателю сейчас или вернуться в главное меню.`, 'success');
        document.getElementById('enrollmentFormContent').hidden = true;
        document.getElementById('enrollmentSuccessActions').hidden = false;
    } catch (error) {
        setInlineMessage('enrollmentMessage', error.message, 'error');
    }
}
