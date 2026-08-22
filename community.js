const communityState = {
    battleId: null,
    battle: null,
    battleQuestionIndex: 0,
    battlePoll: null,
    chatPublicId: null,
    chatPoll: null,
    participantReturnScreen: 'friendsScreen',
    leaderboardPeriod: 'day',
    profileReturnScreen: 'mainMenu',
    friendsReturnScreen: 'mainMenu',
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

async function openProfile(returnScreen = null) {
    communityState.profileReturnScreen = returnScreen || (currentClass ? 'mainMenu' : 'classSelection');
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

function returnFromProfile() {
    showScreen(communityState.profileReturnScreen || (currentClass ? 'mainMenu' : 'classSelection'));
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
    communityState.leaderboardPeriod = period;
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
        if (entry.publicId) {
            row.classList.add('leaderboard-row-clickable');
            row.tabIndex = 0;
            row.setAttribute('role', 'button');
            row.addEventListener('click', () => openParticipant(entry.publicId, 'leaderboardScreen'));
            row.addEventListener('keydown', (event) => {
                if (event.key === 'Enter' || event.key === ' ') openParticipant(entry.publicId, 'leaderboardScreen');
            });
        }
        list.appendChild(row);
    });
}

function createSocialAvatar(participant, className = 'leaderboard-avatar') {
    const avatar = document.createElement(participant.avatarUrl ? 'img' : 'span');
    avatar.className = className;
    if (participant.avatarUrl) {
        avatar.src = participant.avatarUrl;
        avatar.alt = '';
    } else {
        avatar.textContent = '∑';
    }
    return avatar;
}

function createSocialCard(participant, actions = []) {
    const card = document.createElement('article');
    card.className = 'social-card';
    const head = document.createElement('button');
    head.type = 'button';
    head.className = 'social-card-head';
    head.appendChild(createSocialAvatar(participant));
    const identity = document.createElement('span');
    const name = document.createElement('strong');
    name.textContent = participant.nickname;
    const grade = document.createElement('small');
    grade.textContent = participant.grade ? `${participant.grade} класс` : 'Класс пока не выбран';
    identity.append(name, grade);
    head.appendChild(identity);
    head.addEventListener('click', () => openParticipant(participant.publicId, 'friendsScreen'));
    card.appendChild(head);
    if (actions.length) {
        const buttons = document.createElement('div');
        buttons.className = 'social-card-actions';
        actions.forEach(({ label, action, secondary = false, disabled = false }) => {
            const button = document.createElement('button');
            button.type = 'button';
            button.className = secondary ? 'btn btn-secondary' : 'btn';
            button.textContent = label;
            button.disabled = disabled;
            if (!disabled) button.addEventListener('click', action);
            buttons.appendChild(button);
        });
        card.appendChild(buttons);
    }
    return card;
}

function renderEmpty(container, text) {
    const empty = document.createElement('p');
    empty.className = 'empty-state';
    empty.textContent = text;
    container.replaceChildren(empty);
}

async function openFriends(returnScreen = null) {
    if (returnScreen) communityState.friendsReturnScreen = returnScreen;
    else if (!communityState.friendsReturnScreen) communityState.friendsReturnScreen = currentClass ? 'mainMenu' : 'classSelection';
    clearInterval(communityState.chatPoll);
    showScreen('friendsScreen');
    setInlineMessage('friendMessage', 'Загружаем друзей и приглашения…');
    document.getElementById('friendSearchResults').replaceChildren();
    try {
        const [friendData, inviteData] = await Promise.all([
            communityRequest('/api/friends', { headers: telegramHeaders() }),
            communityRequest('/api/battle-invites', { headers: telegramHeaders() }),
        ]);
        renderFriends(friendData);
        renderBattleInvites(inviteData);
        setInlineMessage('friendMessage', '');
    } catch (error) {
        setInlineMessage('friendMessage', error.message, 'error');
        renderEmpty(document.getElementById('friendsList'), 'Не удалось загрузить список друзей.');
    }
}

function returnFromFriends() {
    showScreen(communityState.friendsReturnScreen || (currentClass ? 'mainMenu' : 'classSelection'));
}

function renderFriends(payload) {
    const friendList = document.getElementById('friendsList');
    friendList.replaceChildren();
    (payload.friends || []).forEach(({ participant }) => {
        friendList.appendChild(createSocialCard(participant, [
            { label: 'Сообщения', action: () => openChat(participant.publicId) },
            { label: 'Вызвать в баттл', action: () => inviteToBattle(participant.publicId), secondary: true },
        ]));
    });
    if (!payload.friends?.length) renderEmpty(friendList, 'В списке пока никого нет. Найдите участника по никнейму.');

    const section = document.getElementById('friendRequestsSection');
    const requestList = document.getElementById('friendRequestsList');
    section.hidden = !(payload.incoming || []).length;
    requestList.replaceChildren();
    (payload.incoming || []).forEach(({ id, participant }) => {
        requestList.appendChild(createSocialCard(participant, [
            { label: 'Принять', action: () => respondFriendRequest(id, true) },
            { label: 'Отклонить', action: () => respondFriendRequest(id, false), secondary: true },
        ]));
    });
}

function renderBattleInvites(payload) {
    const section = document.getElementById('battleInvitesSection');
    const list = document.getElementById('battleInvitesList');
    section.hidden = !(payload.incoming || []).length;
    list.replaceChildren();
    (payload.incoming || []).forEach((invite) => {
        list.appendChild(createSocialCard(invite.participant, [
            { label: `Принять · ${invite.grade} класс`, action: () => acceptBattleInvite(invite.id) },
            { label: 'Отклонить', action: () => declineBattleInvite(invite.id), secondary: true },
        ]));
    });
}

async function searchParticipants() {
    const query = document.getElementById('friendSearchInput').value.trim();
    const list = document.getElementById('friendSearchResults');
    renderEmpty(list, 'Ищем…');
    try {
        const payload = await communityRequest(`/api/participants/search?q=${encodeURIComponent(query)}`, {
            headers: telegramHeaders(),
        });
        list.replaceChildren();
        (payload.entries || []).forEach((participant) => {
            const status = participant.friendshipStatus;
            const label = status === 'friends' ? 'Уже в друзьях' : status === 'outgoing' ? 'Заявка отправлена' : status === 'incoming' ? 'Откройте заявки выше' : 'Добавить в друзья';
            list.appendChild(createSocialCard(participant, [{
                label,
                action: () => requestFriend(participant.publicId),
                disabled: status !== 'none',
            }]));
        });
        if (!payload.entries?.length) renderEmpty(list, 'Участники с таким никнеймом не найдены.');
    } catch (error) {
        renderEmpty(list, error.message);
    }
}

async function requestFriend(publicId) {
    setInlineMessage('friendMessage', 'Отправляем заявку…');
    try {
        await communityRequest(`/api/friends/${publicId}`, {
            method: 'POST', headers: telegramHeaders(true), body: '{}',
        });
        setInlineMessage('friendMessage', 'Заявка в друзья отправлена', 'success');
        await searchParticipants();
    } catch (error) {
        setInlineMessage('friendMessage', error.message, 'error');
    }
}

async function respondFriendRequest(requestId, accepted) {
    try {
        await communityRequest(`/api/friend-requests/${requestId}/${accepted ? 'accept' : 'decline'}`, {
            method: 'POST', headers: telegramHeaders(true), body: '{}',
        });
        await openFriends();
    } catch (error) {
        setInlineMessage('friendMessage', error.message, 'error');
    }
}

async function openParticipant(publicId, returnScreen = 'friendsScreen') {
    communityState.participantReturnScreen = returnScreen;
    showScreen('participantScreen');
    const card = document.getElementById('participantCard');
    renderEmpty(card, 'Загружаем профиль…');
    document.getElementById('participantStats').replaceChildren();
    document.getElementById('participantAwards').replaceChildren();
    document.getElementById('participantActions').replaceChildren();
    setInlineMessage('participantMessage', '');
    try {
        const participant = await communityRequest(`/api/participants/${publicId}`, {
            headers: telegramHeaders(),
        });
        renderParticipant(participant);
    } catch (error) {
        renderEmpty(card, error.message);
    }
}

function renderParticipant(participant) {
    const card = document.getElementById('participantCard');
    card.replaceChildren(createSocialAvatar(participant, 'participant-avatar'));
    const identity = document.createElement('div');
    const title = document.createElement('h2');
    title.textContent = participant.nickname;
    const grade = document.createElement('p');
    grade.className = 'supporting-text';
    grade.textContent = participant.grade ? `${participant.grade} класс` : 'Класс пока не выбран';
    identity.append(title, grade);
    card.appendChild(identity);

    const stats = document.getElementById('participantStats');
    stats.replaceChildren();
    if (participant.stats) {
        [['Сегодня', participant.stats.dayScore], ['За месяц', participant.stats.monthScore], ['Побед в баттлах', participant.stats.battleWins]].forEach(([label, value]) => {
            const item = document.createElement('div');
            const strong = document.createElement('strong');
            strong.textContent = value;
            const small = document.createElement('small');
            small.textContent = label;
            item.append(strong, small);
            stats.appendChild(item);
        });
    } else {
        renderEmpty(stats, 'Участник не публикует результаты.');
    }

    const awards = document.getElementById('participantAwards');
    awards.replaceChildren();
    if (participant.awards?.length) {
        participant.awards.slice().reverse().forEach((award) => {
            const item = document.createElement('article');
            item.className = `award-card award-${award.period}`;
            const icon = document.createElement('span');
            icon.className = 'award-icon';
            icon.textContent = award.icon;
            const label = document.createElement('div');
            const name = document.createElement('strong');
            name.textContent = award.name;
            const period = document.createElement('small');
            period.textContent = award.period_key;
            label.append(name, period);
            item.append(icon, label);
            awards.appendChild(item);
        });
    }

    const actions = document.getElementById('participantActions');
    actions.replaceChildren();
    const addAction = (label, handler, secondary = false) => {
        const button = document.createElement('button');
        button.className = secondary ? 'btn btn-secondary' : 'btn';
        button.textContent = label;
        button.addEventListener('click', handler);
        actions.appendChild(button);
    };
    if (participant.friendshipStatus === 'none') addAction('Добавить в друзья', () => requestFriendFromProfile(participant.publicId));
    if (participant.friendshipStatus === 'outgoing') {
        const pending = document.createElement('p');
        pending.className = 'soft-pill';
        pending.textContent = 'Заявка в друзья отправлена';
        actions.appendChild(pending);
    }
    if (participant.friendshipStatus === 'incoming') addAction('Открыть входящую заявку', openFriends);
    if (participant.friendshipStatus === 'friends') {
        addAction('Написать сообщение', () => openChat(participant.publicId));
        addAction('Вызвать в баттл', () => inviteToBattle(participant.publicId), true);
    }
}

async function requestFriendFromProfile(publicId) {
    setInlineMessage('participantMessage', 'Отправляем заявку…');
    try {
        await communityRequest(`/api/friends/${publicId}`, {
            method: 'POST', headers: telegramHeaders(true), body: '{}',
        });
        await openParticipant(publicId, communityState.participantReturnScreen);
        setInlineMessage('participantMessage', 'Заявка отправлена', 'success');
    } catch (error) {
        setInlineMessage('participantMessage', error.message, 'error');
    }
}

function returnFromParticipant() {
    if (communityState.participantReturnScreen === 'leaderboardScreen') openLeaderboard(communityState.leaderboardPeriod);
    else openFriends();
}

async function inviteToBattle(publicId) {
    const target = document.getElementById('participantScreen').classList.contains('active') ? 'participantMessage' : 'friendMessage';
    if (!currentClass) {
        setInlineMessage(target, 'Сначала вернитесь к выбору и укажите класс для заданий баттла.', 'error');
        return;
    }
    const grade = Number(currentClass);
    setInlineMessage(target, 'Отправляем вызов…');
    try {
        await communityRequest('/api/battle-invites', {
            method: 'POST', headers: telegramHeaders(true),
            body: JSON.stringify({ publicId, grade }),
        });
        setInlineMessage(target, `Вызов отправлен. Задания: ${grade} класс.`, 'success');
    } catch (error) {
        setInlineMessage(target, error.message, 'error');
    }
}

async function acceptBattleInvite(inviteId) {
    setInlineMessage('friendMessage', 'Готовим одинаковые задания…');
    try {
        const battle = await communityRequest(`/api/battle-invites/${inviteId}/accept`, {
            method: 'POST', headers: telegramHeaders(true), body: '{}',
        });
        communityState.battleId = battle.id;
        showScreen('battleScreen');
        handleBattleState(battle);
        startBattlePolling();
    } catch (error) {
        setInlineMessage('friendMessage', error.message, 'error');
    }
}

async function declineBattleInvite(inviteId) {
    try {
        await communityRequest(`/api/battle-invites/${inviteId}/decline`, {
            method: 'POST', headers: telegramHeaders(true), body: '{}',
        });
        await openFriends();
    } catch (error) {
        setInlineMessage('friendMessage', error.message, 'error');
    }
}

async function openBattleById(battleId) {
    communityState.battleId = battleId;
    showScreen('battleScreen');
    setInlineMessage('battleStatus', 'Открываем приглашённый баттл…');
    try {
        const battle = await communityRequest(`/api/battles/${battleId}`, {
            headers: telegramHeaders(),
        });
        handleBattleState(battle);
        if (battle.status !== 'complete') startBattlePolling();
    } catch (error) {
        setInlineMessage('battleStatus', error.message, 'error');
    }
}

async function openChat(publicId) {
    communityState.chatPublicId = publicId;
    showScreen('chatScreen');
    setInlineMessage('chatMessage', '');
    await refreshChat(true);
    clearInterval(communityState.chatPoll);
    communityState.chatPoll = setInterval(() => refreshChat(false), 4000);
}

async function refreshChat(scrollToBottom = false) {
    if (!communityState.chatPublicId) return;
    try {
        const payload = await communityRequest(`/api/messages/${communityState.chatPublicId}`, {
            headers: telegramHeaders(),
        });
        renderChat(payload, scrollToBottom);
    } catch (error) {
        setInlineMessage('chatMessage', error.message, 'error');
        clearInterval(communityState.chatPoll);
    }
}

function renderChat(payload, scrollToBottom) {
    const participant = document.getElementById('chatParticipant');
    participant.replaceChildren(createSocialAvatar(payload.participant));
    const name = document.createElement('strong');
    name.textContent = payload.participant.nickname;
    participant.appendChild(name);
    const list = document.getElementById('chatMessages');
    const wasNearBottom = list.scrollHeight - list.scrollTop - list.clientHeight < 80;
    list.replaceChildren();
    (payload.messages || []).forEach((message) => {
        const bubble = document.createElement('div');
        bubble.className = `chat-bubble ${message.mine ? 'chat-bubble-mine' : 'chat-bubble-theirs'}`;
        const text = document.createElement('p');
        text.textContent = message.text;
        const time = document.createElement('small');
        time.textContent = new Date(message.createdAt).toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' });
        bubble.append(text, time);
        list.appendChild(bubble);
    });
    if (!payload.messages?.length) renderEmpty(list, 'Начните диалог — сообщения видны только вам двоим.');
    if (scrollToBottom || wasNearBottom) list.scrollTop = list.scrollHeight;
}

async function sendChatMessage() {
    const input = document.getElementById('chatInput');
    const text = input.value.trim();
    if (!text) return;
    setInlineMessage('chatMessage', 'Отправляем…');
    try {
        await communityRequest(`/api/messages/${communityState.chatPublicId}`, {
            method: 'POST', headers: telegramHeaders(true), body: JSON.stringify({ text }),
        });
        input.value = '';
        setInlineMessage('chatMessage', '');
        await refreshChat(true);
    } catch (error) {
        setInlineMessage('chatMessage', error.message, 'error');
    }
}

function closeChat() {
    clearInterval(communityState.chatPoll);
    communityState.chatPublicId = null;
    openFriends();
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

const deepLinkedBattleId = new URLSearchParams(window.location.search).get('battle');
if (deepLinkedBattleId && /^[a-f0-9]{12}$/.test(deepLinkedBattleId)) {
    window.setTimeout(() => openBattleById(deepLinkedBattleId), 0);
}

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
