const communityState = {
    battleId: null,
    battle: null,
    battleQuestionIndex: 0,
    battlePoll: null,
    battleTimer: null,
    battleCountdownTimer: null,
    battleCountdownCompleteId: null,
    battleSyncPoll: null,
    battleRenderedQuestionId: null,
    battleTimeoutRefreshing: false,
    chatPublicId: null,
    chatPoll: null,
    participantReturnScreen: 'friendsScreen',
    leaderboardPeriod: 'day',
    profileReturnScreen: 'mainMenu',
    friendsReturnScreen: 'mainMenu',
    characterCatalog: [],
    characterIndex: 0,
    battleInvitePublicId: null,
    battleInviteReturnScreen: 'friendsScreen',
    highlightedFriendRequestId: null,
    highlightedBattleInviteId: null,
    shop: null,
    shopDepartment: null,
    shopPage: 0,
    shopSwipeReady: false,
    shopReturnScreen: 'mainMenu',
    wardrobeTab: 'outfit',
    equippedItems: {},
};
let pendingAvatarDataUrl = null;
let adminMode = false;

function telegramHeaders(json = false) {
    const headers = { 'X-Telegram-Init-Data': tg.initData || '' };
    if (json) headers['Content-Type'] = 'application/json';
    return headers;
}

async function communityRequest(url, options = {}) {
    const response = await fetch(url, {cache: 'no-store', ...options});
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(payload.error || payload.message || 'Не удалось выполнить запрос');
    return payload;
}

function syncCoinBalance(balance, isAdmin) {
    if (typeof isAdmin === 'boolean') adminMode = isAdmin;
    window.isAdminMode = adminMode;
    coins = Number(balance || 0);
    localStorage.setItem('mathCoins', coins);
    ['quizCoins', 'shopCoins', 'characterCoins', 'dailyCoins'].forEach((id) => {
        const element = document.getElementById(id);
        if (element) element.textContent = adminMode ? '∞' : coins;
    });
    const menuCoins = document.getElementById('coinsCount');
    if (menuCoins) menuCoins.textContent = adminMode ? '∞' : coins;
    if (adminMode) {
        lives = Infinity;
        ['livesCount', 'quizLives'].forEach((id) => {
            const element = document.getElementById(id);
            if (element) element.textContent = '∞';
        });
    }
}

function renderDailyLogin(payload) {
    const banner = document.getElementById('dailyRewardBanner');
    if (!banner) return;
    banner.hidden = false;
    syncCoinBalance(payload.coins, payload.admin);
    const days = document.getElementById('dailyRewardDays');
    days.replaceChildren();
    (payload.schedule || []).forEach(({day, reward, kind}) => {
        const button = document.createElement('button');
        button.type = 'button';
        button.className = 'daily-day-button';
        const isActive = day === payload.activeDay;
        const isPast = payload.claimedToday ? day <= payload.activeDay : day < payload.activeDay;
        button.classList.toggle('active', isActive && !payload.claimedToday);
        button.classList.toggle('claimed', isPast || (isActive && payload.claimedToday));
        button.disabled = !isActive || payload.claimedToday;
        const prize = kind === 'wheel' ? '🎡' : `+${reward}`;
        button.innerHTML = `<strong>День ${day}</strong><small>${isPast || (isActive && payload.claimedToday) ? '✓' : prize}</small>`;
        if (!button.disabled) button.addEventListener('click', claimDailyLogin);
        days.appendChild(button);
    });
    document.getElementById('dailyRewardTitle').textContent = payload.wheelAvailable
        ? 'Призовой барабан открыт'
        : payload.claimedToday
            ? `День ${payload.activeDay} уже получен`
            : payload.activeKind === 'wheel'
                ? `День ${payload.activeDay} · призовой барабан`
                : `День ${payload.activeDay} · +${payload.activeReward} монет`;
    document.getElementById('dailyRewardText').textContent = payload.wheelAvailable
        ? 'Крутите барабан и получите монеты или купон на скидку.'
        : payload.wheelClaimed
            ? `Ваш приз: ${payload.wheelPrize?.label || 'получен'}.`
            : payload.claimedToday
                ? 'Следующая ячейка откроется завтра.'
                : 'Нажмите на активный день, чтобы забрать награду.';
    const wheelPanel = document.getElementById('dailyWheelPanel');
    const wheelButton = document.getElementById('dailyWheelButton');
    wheelPanel.hidden = !payload.wheelAvailable && !payload.wheelClaimed;
    wheelButton.hidden = !payload.wheelAvailable;
    wheelButton.disabled = !payload.wheelAvailable;
    document.getElementById('dailyWheelResult').textContent = payload.wheelClaimed
        ? `Вы выиграли: ${payload.wheelPrize?.label || 'приз'}`
        : '';
}

async function loadDailyLogin() {
    if (!tg.initData) return;
    try {
        const payload = await communityRequest('/api/daily-login', {headers: telegramHeaders()});
        renderDailyLogin(payload);
    } catch (error) {
        console.warn('Не удалось загрузить календарь входа:', error.message);
    }
}

async function claimDailyLogin() {
    if (!tg.initData) return;
    document.querySelectorAll('.daily-day-button').forEach((button) => { button.disabled = true; });
    try {
        const payload = await communityRequest('/api/daily-login', {
            method: 'POST',
            headers: telegramHeaders(true),
            body: '{}',
        });
        renderDailyLogin(payload);
        if (payload.claimed) {
            const animation = document.getElementById('dailyRewardAnimation');
            animation.textContent = payload.activeKind === 'wheel' ? '🎡' : `+${payload.reward} 🪙`;
            animation.classList.remove('play');
            void animation.offsetWidth;
            animation.classList.add('play');
        }
    } catch (error) {
        console.warn('Не удалось начислить награду за вход:', error.message);
        await loadDailyLogin();
    }
}

async function spinDailyWheel() {
    const button = document.getElementById('dailyWheelButton');
    const wheel = document.getElementById('dailyWheel');
    button.disabled = true;
    document.getElementById('dailyWheelResult').textContent = 'Барабан вращается…';
    wheel.classList.remove('spinning');
    void wheel.offsetWidth;
    wheel.classList.add('spinning');
    try {
        const payload = await communityRequest('/api/daily-wheel', {
            method: 'POST', headers: telegramHeaders(true), body: '{}',
        });
        window.setTimeout(() => {
            renderDailyLogin(payload);
            document.getElementById('dailyWheelResult').textContent = `Вы выиграли: ${payload.prize.label}`;
            if (payload.prize.kind === 'coins') {
                const animation = document.getElementById('dailyRewardAnimation');
                animation.textContent = `+${payload.prize.value} 🪙`;
                animation.classList.remove('play');
                void animation.offsetWidth;
                animation.classList.add('play');
            }
        }, 2300);
    } catch (error) {
        wheel.classList.remove('spinning');
        button.disabled = false;
        document.getElementById('dailyWheelResult').textContent = error.message;
    }
}

async function awardServerTrainingCoins(attemptKey) {
    if (!tg.initData || !attemptKey) return;
    try {
        const payload = await communityRequest('/api/coins/training', {
            method: 'POST',
            headers: telegramHeaders(true),
            body: JSON.stringify({attemptKey}),
        });
        syncCoinBalance(payload.coins, payload.admin);
    } catch (error) {
        console.warn('Не удалось синхронизировать монеты:', error.message);
    }
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
        await loadWardrobe();
        await loadCharacterCatalog();
        await loadProfileBattleInvites();
        setInlineMessage('profileMessage', '');
    } catch (error) {
        setInlineMessage('profileMessage', error.message, 'error');
    }
}

function returnFromProfile() {
    window.characterViewer?.dispose();
    showScreen(communityState.profileReturnScreen || (currentClass ? 'mainMenu' : 'classSelection'));
}

async function loadWardrobe() {
    const list = document.getElementById('wardrobeList');
    if (!list) return;
    try {
        const payload = await communityRequest('/api/shop', {headers: telegramHeaders()});
        communityState.shop = payload;
        communityState.equippedItems = payload.equippedItems || {};
        syncCoinBalance(payload.coins, payload.admin);
        renderWardrobe();
    } catch (error) {
        renderEmpty(list, error.message);
    }
}

function setWardrobeTab(tab) {
    communityState.wardrobeTab = tab;
    document.querySelectorAll('[data-wardrobe]').forEach((button) => {
        button.classList.toggle('active', button.dataset.wardrobe === tab);
    });
    renderWardrobe();
}

function renderWardrobe() {
    const list = document.getElementById('wardrobeList');
    if (!list || !communityState.shop) return;
    const allItems = [...(communityState.shop.items || []), ...(communityState.shop.temporaryItems || [])];
    const items = allItems.filter((item) => item.owned && item.slot === communityState.wardrobeTab);
    list.replaceChildren();
    if (!items.length) {
        renderEmpty(list, 'В этой категории пока ничего нет. Загляните в лавку.');
        return;
    }
    items.forEach((item) => {
        const card = document.createElement('article');
        card.className = `wardrobe-item${item.equipped ? ' equipped' : ''}`;
        const expires = item.ownedUntil ? new Date(item.ownedUntil).toLocaleDateString('ru-RU') : '';
        card.innerHTML = `<span>${item.icon || '🎁'}</span><div><strong>${item.name}</strong><small>${item.temporary ? 'Награда до конца дня' : `Доступно до ${expires}`}</small></div>`;
        const button = document.createElement('button');
        button.type = 'button';
        button.className = 'small-link-button';
        button.textContent = item.equipped ? 'Снять' : item.slot === 'interior' ? 'Выбрать' : 'Надеть';
        button.addEventListener('click', () => equipWardrobeItem(item));
        card.appendChild(button);
        list.appendChild(card);
    });
}

async function equipWardrobeItem(item) {
    try {
        const payload = await communityRequest('/api/shop/equip', {
            method: 'POST', headers: telegramHeaders(true),
            body: JSON.stringify({itemId: item.id, remove: Boolean(item.equipped)}),
        });
        communityState.shop = payload;
        communityState.equippedItems = payload.equippedItems || {};
        renderWardrobe();
        renderCharacterTumbler();
    } catch (error) {
        setInlineMessage('profileMessage', error.message, 'error');
    }
}

async function loadCharacterCatalog() {
    const catalog = document.getElementById('characterCatalog');
    catalog.replaceChildren();
    const loading = document.createElement('p');
    loading.className = 'empty-state';
    loading.textContent = 'Загружаем персонажей…';
    catalog.appendChild(loading);
    setInlineMessage('characterCatalogMessage', '');
    try {
        const payload = await communityRequest('/api/characters', {
            headers: telegramHeaders(),
        });
        communityState.characterCatalog = payload.characters || [];
        renderCharacterCatalog(payload);
    } catch (error) {
        window.characterViewer?.dispose();
        document.getElementById('characterStage').replaceChildren();
        renderEmpty(catalog, error.message);
    }
}

function renderCharacterCatalog(payload) {
    const catalog = document.getElementById('characterCatalog');
    syncCoinBalance(payload.coins, payload.admin);
    catalog.replaceChildren();

    if (!payload.characters?.length) {
        window.characterViewer?.dispose();
        document.getElementById('characterStage').replaceChildren();
        renderEmpty(catalog, 'Коллекция персонажей появится в следующем обновлении.');
        return;
    }

    const selectedIndex = payload.characters.findIndex((character) => character.selected || character.id === payload.selectedId);
    communityState.characterIndex = selectedIndex >= 0 ? selectedIndex : 0;
    renderCharacterTumbler();
}

function renderCharacterTumbler() {
    const characters = communityState.characterCatalog;
    if (!characters.length) return;
    const index = ((communityState.characterIndex % characters.length) + characters.length) % characters.length;
    communityState.characterIndex = index;
    const character = characters[index];
    const characterStage = document.getElementById('characterStage');
    try {
        window.characterViewer?.mount(
            characterStage,
            character.style,
            Object.values(communityState.equippedItems || {})
        );
    } catch (error) {
        window.characterViewer?.dispose();
        characterStage.replaceChildren();
        const message = document.createElement('p');
        message.className = 'empty-state';
        message.textContent = 'Не удалось показать эту модель. Переключите персонажа и попробуйте снова.';
        characterStage.appendChild(message);
        console.error(`Ошибка 3D-модели ${character.id}:`, error);
    }

    const catalog = document.getElementById('characterCatalog');
    catalog.replaceChildren();
    const tumbler = document.createElement('section');
    tumbler.className = `character-tumbler character-tumbler-${character.category}`;
    tumbler.tabIndex = 0;
    tumbler.setAttribute('aria-label', 'Выбор персонажа');

    const previous = document.createElement('button');
    previous.type = 'button';
    previous.className = 'character-tumbler-arrow';
    previous.setAttribute('aria-label', 'Предыдущий персонаж');
    previous.textContent = '‹';
    previous.addEventListener('click', () => shiftCharacter(-1));

    const next = document.createElement('button');
    next.type = 'button';
    next.className = 'character-tumbler-arrow';
    next.setAttribute('aria-label', 'Следующий персонаж');
    next.textContent = '›';
    next.addEventListener('click', () => shiftCharacter(1));

    const details = document.createElement('div');
    details.className = 'character-tumbler-details';
    const badge = document.createElement('span');
    badge.className = 'character-category-badge';
    badge.textContent = character.category === 'basic' ? 'Базовый' : 'Премиум';
    const name = document.createElement('strong');
    name.textContent = character.name;
    const counter = document.createElement('small');
    counter.textContent = `${index + 1} из ${characters.length}`;
    details.append(badge, name, counter);

    const price = document.createElement('p');
    price.className = 'character-tumbler-price';
    price.textContent = character.price === 0
        ? 'Бесплатно'
        : character.owned
            ? 'Уже куплен'
            : `🪙 ${character.price} монет`;

    const action = document.createElement('button');
    action.type = 'button';
    action.className = character.selected ? 'btn btn-secondary' : 'btn';
    action.textContent = character.selected ? 'Выбран сейчас' : character.owned ? 'Выбрать персонажа' : 'Купить персонажа';
    action.disabled = Boolean(character.selected);
    action.addEventListener('click', () => character.owned
        ? selectCharacter(character.id)
        : confirmCharacterPurchase(character));

    const hint = document.createElement('small');
    hint.className = 'character-tumbler-hint';
    hint.textContent = 'Листайте стрелками или свайпом';

    let pointerStart = null;
    tumbler.addEventListener('pointerdown', (event) => { pointerStart = event.clientX; });
    tumbler.addEventListener('pointerup', (event) => {
        if (pointerStart === null) return;
        const delta = event.clientX - pointerStart;
        pointerStart = null;
        if (Math.abs(delta) > 36) shiftCharacter(delta < 0 ? 1 : -1);
    });
    tumbler.addEventListener('pointercancel', () => { pointerStart = null; });
    tumbler.addEventListener('keydown', (event) => {
        if (event.key === 'ArrowLeft') shiftCharacter(-1);
        if (event.key === 'ArrowRight') shiftCharacter(1);
    });

    const controls = document.createElement('div');
    controls.className = 'character-tumbler-controls';
    controls.append(previous, details, next);
    tumbler.append(controls, price, action, hint);
    catalog.appendChild(tumbler);
}

function shiftCharacter(direction) {
    const total = communityState.characterCatalog.length;
    if (!total) return;
    communityState.characterIndex = (communityState.characterIndex + direction + total) % total;
    renderCharacterTumbler();
}

async function selectCharacter(characterId) {
    setInlineMessage('characterCatalogMessage', 'Меняем персонажа…');
    try {
        await communityRequest('/api/characters/select', {
            method: 'POST',
            headers: telegramHeaders(true),
            body: JSON.stringify({characterId}),
        });
        await loadCharacterCatalog();
        setInlineMessage('characterCatalogMessage', 'Персонаж выбран', 'success');
    } catch (error) {
        setInlineMessage('characterCatalogMessage', error.message, 'error');
    }
}

function confirmCharacterPurchase(character) {
    const proceed = () => purchaseCharacter(character.id);
    const message = `Открыть персонажа «${character.name}» за ${character.price} монет? Покупка останется навсегда.`;
    if (typeof tg.showConfirm === 'function') tg.showConfirm(message, (confirmed) => confirmed && proceed());
    else if (window.confirm(message)) proceed();
}

async function purchaseCharacter(characterId) {
    setInlineMessage('characterCatalogMessage', 'Проверяем баланс…');
    try {
        const result = await communityRequest('/api/characters/purchase', {
            method: 'POST',
            headers: telegramHeaders(true),
            body: JSON.stringify({characterId}),
        });
        coins = Number(result.coins || 0);
        localStorage.setItem('mathCoins', coins);
        await loadCharacterCatalog();
        setInlineMessage('characterCatalogMessage', result.purchased === false ? 'Персонаж уже был открыт' : 'Персонаж открыт навсегда!', 'success');
    } catch (error) {
        setInlineMessage('characterCatalogMessage', error.message, 'error');
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
        await loadCharacterCatalog();
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

async function loadProfileBattleInvites() {
    const section = document.getElementById('profileBattleInvitesSection');
    const list = document.getElementById('profileBattleInvitesList');
    try {
        const payload = await communityRequest('/api/battle-invites', {headers: telegramHeaders()});
        const incoming = payload.incoming || [];
        section.hidden = !incoming.length;
        list.replaceChildren();
        incoming.forEach((invite) => {
            list.appendChild(createSocialCard(invite.participant, [
                {label: `Принять · ${invite.grade} класс`, action: () => acceptBattleInvite(invite.id)},
                {label: 'Отклонить', action: () => declineBattleInvite(invite.id), secondary: true},
            ]));
        });
    } catch (error) {
        section.hidden = true;
    }
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
        focusDeepLinkedSocialItem();
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
        const card = createSocialCard(participant, [
            { label: 'Принять', action: () => respondFriendRequest(id, true) },
            { label: 'Отклонить', action: () => respondFriendRequest(id, false), secondary: true },
        ]);
        card.id = `friend-request-${id}`;
        if (id === communityState.highlightedFriendRequestId) card.classList.add('deep-link-highlight');
        requestList.appendChild(card);
    });
}

function renderBattleInvites(payload) {
    const section = document.getElementById('battleInvitesSection');
    const list = document.getElementById('battleInvitesList');
    section.hidden = !(payload.incoming || []).length;
    list.replaceChildren();
    (payload.incoming || []).forEach((invite) => {
        const card = createSocialCard(invite.participant, [
            { label: `Принять · ${invite.grade} класс`, action: () => acceptBattleInvite(invite.id) },
            { label: 'Отклонить', action: () => declineBattleInvite(invite.id), secondary: true },
        ]);
        card.id = `battle-invite-${invite.id}`;
        if (invite.id === communityState.highlightedBattleInviteId) card.classList.add('deep-link-highlight');
        list.appendChild(card);
    });
}

function focusDeepLinkedSocialItem() {
    const targetId = communityState.highlightedBattleInviteId
        ? `battle-invite-${communityState.highlightedBattleInviteId}`
        : communityState.highlightedFriendRequestId
            ? `friend-request-${communityState.highlightedFriendRequestId}`
            : null;
    if (!targetId) return;
    const target = document.getElementById(targetId);
    if (target) {
        window.setTimeout(() => target.scrollIntoView({ behavior: 'smooth', block: 'center' }), 60);
    } else {
        setInlineMessage('friendMessage', 'Эта заявка уже принята, отклонена или устарела.', 'info');
    }
    communityState.highlightedBattleInviteId = null;
    communityState.highlightedFriendRequestId = null;
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
    const characterStage = document.getElementById('participantCharacterStage');
    characterStage.hidden = true;
    characterStage.replaceChildren();
    window.characterViewer?.dispose();
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

    const characterStage = document.getElementById('participantCharacterStage');
    if (participant.characterStyle) {
        characterStage.hidden = false;
        window.characterViewer?.mount(characterStage, participant.characterStyle);
    } else {
        characterStage.hidden = true;
    }

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
    window.characterViewer?.dispose();
    if (communityState.participantReturnScreen === 'leaderboardScreen') openLeaderboard(communityState.leaderboardPeriod);
    else openFriends();
}

function inviteToBattle(publicId) {
    communityState.battleInvitePublicId = publicId;
    communityState.battleInviteReturnScreen = document.getElementById('participantScreen').classList.contains('active')
        ? 'participantScreen'
        : 'friendsScreen';
    document.getElementById('battleInviteGradeButtons').hidden = false;
    setInlineMessage('battleInviteGradeMessage', '');
    showScreen('battleInviteGradeScreen');
}

async function sendBattleInvite(grade) {
    if (!communityState.battleInvitePublicId) return;
    setInlineMessage('battleInviteGradeMessage', 'Отправляем вызов…');
    try {
        await communityRequest('/api/battle-invites', {
            method: 'POST', headers: telegramHeaders(true),
            body: JSON.stringify({publicId: communityState.battleInvitePublicId, grade: Number(grade)}),
        });
        document.getElementById('battleInviteGradeButtons').hidden = true;
        setInlineMessage('battleInviteGradeMessage', `Вызов отправлен. Друг получит уведомление: задания за ${grade} класс.`, 'success');
    } catch (error) {
        setInlineMessage('battleInviteGradeMessage', error.message, 'error');
    }
}

function returnFromBattleInviteGrade() {
    communityState.battleInvitePublicId = null;
    if (communityState.battleInviteReturnScreen === 'participantScreen') showScreen('participantScreen');
    else openFriends();
}

async function acceptBattleInvite(inviteId) {
    const messageTarget = document.getElementById('profileScreen').classList.contains('active') ? 'profileMessage' : 'friendMessage';
    setInlineMessage(messageTarget, 'Готовим одинаковые задания…');
    try {
        const battle = await communityRequest(`/api/battle-invites/${inviteId}/accept`, {
            method: 'POST', headers: telegramHeaders(true), body: '{}',
        });
        communityState.battleId = battle.id;
        showScreen('battleScreen');
        handleBattleState(battle);
        startBattlePolling();
    } catch (error) {
        setInlineMessage(messageTarget, error.message, 'error');
    }
}

async function declineBattleInvite(inviteId) {
    try {
        await communityRequest(`/api/battle-invites/${inviteId}/decline`, {
            method: 'POST', headers: telegramHeaders(true), body: '{}',
        });
        if (document.getElementById('profileScreen').classList.contains('active')) await loadProfileBattleInvites();
        else await openFriends();
    } catch (error) {
        const target = document.getElementById('profileScreen').classList.contains('active') ? 'profileMessage' : 'friendMessage';
        setInlineMessage(target, error.message, 'error');
    }
}

async function openBattleById(battleId) {
    communityState.battleId = battleId;
    showScreen('battleScreen');
    document.getElementById('battleFinishActions').hidden = true;
    const exitButton = document.getElementById('battleLeaveButton');
    exitButton.textContent = 'Назад';
    exitButton.classList.remove('btn-danger', 'active-battle-leave');
    exitButton.hidden = false;
    document.getElementById('battleRewardPanel').hidden = true;
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

async function openShop() {
    const activeScreen = document.querySelector('.screen.active');
    communityState.shopReturnScreen = activeScreen?.id === 'profileScreen'
        ? 'profileScreen'
        : (currentClass ? 'mainMenu' : 'classSelection');
    showScreen('shopScreen');
    closeShopDepartment();
    setInlineMessage('shopMessage', 'Загружаем товары…');
    try {
        const payload = await communityRequest('/api/shop', {headers: telegramHeaders()});
        communityState.shop = payload;
        communityState.equippedItems = payload.equippedItems || {};
        syncCoinBalance(payload.coins, payload.admin);
        setInlineMessage(
            'shopMessage',
            payload.bestDiscount ? `Активен купон −${payload.bestDiscount}%. Он применится к следующей покупке.` : '',
            'success',
        );
    } catch (error) {
        setInlineMessage('shopMessage', error.message, 'error');
    }
}

function returnFromShop() {
    closeShopDepartment();
    if (communityState.shopReturnScreen === 'profileScreen') openProfile(communityState.profileReturnScreen);
    else showScreen(communityState.shopReturnScreen || (currentClass ? 'mainMenu' : 'classSelection'));
}

function closeShopDepartment() {
    const panel = document.getElementById('shopDepartment');
    if (panel) panel.hidden = true;
    communityState.shopDepartment = null;
}

function openShopDepartment(department) {
    if (!communityState.shop) {
        setInlineMessage('shopMessage', 'Каталог ещё загружается…');
        return;
    }
    communityState.shopDepartment = department;
    communityState.shopPage = 0;
    document.getElementById('shopDepartment').hidden = false;
    const titles = {book: 'Книга с пособиями', magazine: 'Журнал одежды и интерьера', laptop: 'Интернет-магазин гаджетов'};
    document.getElementById('shopDepartmentTitle').textContent = titles[department] || 'Каталог';
    ensureShopSwipe();
    renderShopPage();
    document.getElementById('shopDepartment').scrollIntoView({behavior: 'smooth', block: 'nearest'});
}

function ensureShopSwipe() {
    if (communityState.shopSwipeReady) return;
    const page = document.getElementById('shopDepartmentPages');
    let pointerStart = null;
    page.addEventListener('pointerdown', (event) => { pointerStart = event.clientX; });
    page.addEventListener('pointerup', (event) => {
        if (pointerStart === null) return;
        const delta = event.clientX - pointerStart;
        pointerStart = null;
        if (Math.abs(delta) > 42) turnShopPage(delta < 0 ? 1 : -1);
    });
    page.addEventListener('pointercancel', () => { pointerStart = null; });
    communityState.shopSwipeReady = true;
}

function shopDepartmentPages() {
    const items = (communityState.shop?.items || []).filter((item) => item.department === communityState.shopDepartment);
    const pageSize = communityState.shopDepartment === 'book' ? 1 : 2;
    const pages = [];
    for (let index = 0; index < items.length; index += pageSize) pages.push(items.slice(index, index + pageSize));
    return pages;
}

function turnShopPage(direction) {
    const pages = shopDepartmentPages();
    if (!pages.length) return;
    communityState.shopPage = (communityState.shopPage + direction + pages.length) % pages.length;
    renderShopPage();
}

function renderShopPage() {
    const pages = shopDepartmentPages();
    const container = document.getElementById('shopDepartmentPages');
    container.replaceChildren();
    if (!pages.length) {
        renderEmpty(container, 'В этом отделе товары скоро появятся.');
        return;
    }
    communityState.shopPage = Math.min(communityState.shopPage, pages.length - 1);
    pages[communityState.shopPage].forEach((item) => {
        const card = document.createElement('article');
        card.className = `shop-product shop-product-${communityState.shopDepartment}`;
        const tier = item.price >= 10000 ? 'premium' : item.price >= 5000 ? 'rare' : item.price >= 2500 ? 'uncommon' : 'basic';
        const tierNames = {basic: 'Базовый', uncommon: 'Необычный', rare: 'Редкий', premium: 'Премиум'};
        card.dataset.tier = tier;
        const icon = document.createElement('span');
        icon.className = 'shop-product-icon';
        icon.textContent = item.icon;
        const copy = document.createElement('div');
        copy.innerHTML = `<span class="shop-rarity">${tierNames[tier]}</span><strong>${item.name}</strong><p>${item.description}</p><small>${item.owned ? `Куплено до ${new Date(item.ownedUntil).toLocaleDateString('ru-RU')}` : 'Доступ на 30 дней'}</small>`;
        const action = document.createElement('button');
        action.type = 'button';
        action.className = item.owned ? 'btn btn-secondary' : 'btn';
        action.textContent = item.owned
            ? 'Уже приобретено'
            : item.discountedPrice < item.price
                ? `Купить · ${item.discountedPrice} 🪙 (−${communityState.shop.bestDiscount}%)`
                : `Купить · ${item.price} 🪙`;
        action.disabled = Boolean(item.owned);
        action.addEventListener('click', () => purchaseShopItem(item));
        card.append(icon, copy, action);
        container.appendChild(card);
    });
    document.getElementById('shopPageNumber').textContent = `${communityState.shopPage + 1} / ${pages.length}`;
}

async function purchaseShopItem(item) {
    setInlineMessage('shopMessage', `Покупаем «${item.name}»…`);
    try {
        const payload = await communityRequest('/api/shop/purchase', {
            method: 'POST', headers: telegramHeaders(true),
            body: JSON.stringify({itemId: item.id}),
        });
        communityState.shop = payload;
        communityState.equippedItems = payload.equippedItems || {};
        syncCoinBalance(payload.coins, payload.admin);
        const discountText = payload.discountApplied ? ` Купон −${payload.discountApplied}% применён.` : '';
        setInlineMessage('shopMessage', `«${item.name}» доступен 30 дней и добавлен в личный кабинет.${discountText}`, 'success');
        renderShopPage();
    } catch (error) {
        setInlineMessage('shopMessage', error.message, 'error');
    }
}

function openBattle() {
    showScreen('battleScreen');
    document.getElementById('battleLobby').hidden = false;
    document.getElementById('battleGame').hidden = true;
    document.getElementById('battleFinishActions').hidden = true;
    const exitButton = document.getElementById('battleLeaveButton');
    exitButton.textContent = 'Назад';
    exitButton.classList.remove('btn-danger', 'active-battle-leave');
    exitButton.hidden = false;
    document.getElementById('battleRewardPanel').hidden = true;
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
    communityState.battlePoll = setInterval(refreshBattle, 1000);
}

function clearBattleQuestionTimer() {
    clearInterval(communityState.battleTimer);
    communityState.battleTimer = null;
}

function clearBattleCountdown() {
    clearInterval(communityState.battleCountdownTimer);
    communityState.battleCountdownTimer = null;
    const countdown = document.getElementById('battleCountdown');
    const game = document.getElementById('battleGame');
    if (countdown) countdown.hidden = true;
    if (game) game.classList.remove('is-counting-down');
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
    if (Number.isFinite(Number(battle.coins))) syncCoinBalance(battle.coins, battle.admin);
    if (battle.status === 'waiting') {
        clearBattleQuestionTimer();
        clearBattleCountdown();
        communityState.battleRenderedQuestionId = null;
        document.getElementById('battleLobby').hidden = false;
        document.getElementById('battleGame').hidden = true;
        document.getElementById('battleFinishActions').hidden = true;
        const exitButton = document.getElementById('battleLeaveButton');
        exitButton.textContent = 'Назад';
        exitButton.classList.remove('btn-danger', 'active-battle-leave');
        exitButton.hidden = false;
        document.getElementById('battleRewardPanel').hidden = true;
        setInlineMessage('battleStatus', 'Ищем ученика вашего класса. Если за 20 секунд пара не найдётся, начнётся баттл с Матан-Ботом.');
        return;
    }
    if (battle.status === 'cancelled') {
        clearBattleQuestionTimer();
        clearBattleCountdown();
        clearInterval(communityState.battlePoll);
        setInlineMessage('battleStatus', 'За 10 минут соперник не нашёлся. Попробуйте ещё раз позже.');
        document.getElementById('battleFinishActions').hidden = false;
        document.getElementById('battleLeaveButton').hidden = true;
        return;
    }

    document.getElementById('battleLobby').hidden = true;
    document.getElementById('battleGame').hidden = false;
    const exitButton = document.getElementById('battleLeaveButton');
    exitButton.textContent = 'Покинуть баттл';
    exitButton.classList.add('btn-danger', 'active-battle-leave');
    exitButton.hidden = false;
    renderBattlePlayers(battle);

    const countdownDeadline = Date.parse(battle.countdownUntil || '');
    if (
        Number.isFinite(countdownDeadline)
        && countdownDeadline > Date.now()
        && communityState.battleCountdownCompleteId !== battle.id
    ) {
        renderBattleCountdown(countdownDeadline);
        return;
    }
    clearBattleCountdown();
    communityState.battleCountdownCompleteId = battle.id;

    const unansweredIndex = Number.isInteger(Number(battle.currentQuestionIndex))
        ? Number(battle.currentQuestionIndex)
        : battle.questions.findIndex((question) => !(question.id in battle.myAnswers));
    if (unansweredIndex >= 0 && unansweredIndex < battle.questions.length && battle.status === 'active') {
        communityState.battleQuestionIndex = unansweredIndex;
        const question = battle.questions[unansweredIndex];
        if (question && communityState.battleRenderedQuestionId !== question.id) renderBattleQuestion();
        else startBattleQuestionTimer();
        return;
    }
    clearBattleQuestionTimer();
    communityState.battleRenderedQuestionId = null;
    renderBattleFinish(battle);
}

function renderBattleCountdown(deadline) {
    clearBattleQuestionTimer();
    clearInterval(communityState.battleCountdownTimer);
    const game = document.getElementById('battleGame');
    const countdown = document.getElementById('battleCountdown');
    const value = document.getElementById('battleCountdownValue');
    if (!game || !countdown || !value) return;
    game.classList.add('is-counting-down');
    countdown.hidden = false;

    const update = () => {
        const remaining = Math.max(0, Math.ceil((deadline - Date.now()) / 1000));
        if (remaining > 0) {
            value.textContent = String(Math.min(3, remaining));
            countdown.classList.remove('go');
            return;
        }
        clearInterval(communityState.battleCountdownTimer);
        communityState.battleCountdownTimer = null;
        communityState.battleCountdownCompleteId = communityState.battle?.id || null;
        value.textContent = 'СТАРТ!';
        countdown.classList.add('go');
        game.classList.remove('is-counting-down');
        communityState.battleRenderedQuestionId = null;
        renderBattleQuestion();
        window.setTimeout(() => {
            countdown.hidden = true;
            countdown.classList.remove('go');
        }, 520);
    };
    update();
    if (communityState.battleCountdownCompleteId !== communityState.battle?.id) {
        communityState.battleCountdownTimer = setInterval(update, 100);
    }
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
        const completed = player ? Number(player.answered || 0) + Number(player.missed || 0) : 0;
        result.textContent = player ? `${player.score} баллов · ${completed}/5` : '—';
        card.append(name, result);
        container.appendChild(card);
    });
}

function renderBattleQuestion() {
    const battle = communityState.battle;
    const question = battle.questions[communityState.battleQuestionIndex];
    if (!question) return;
    communityState.battleRenderedQuestionId = question.id;
    communityState.battleTimeoutRefreshing = false;
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
        button.className = 'battle-option';
        setMathContent(button, option);
        button.addEventListener('click', () => answerBattle(question.id, selectedIndex));
        options.appendChild(button);
    });
    startBattleQuestionTimer();
}

function startBattleQuestionTimer() {
    clearBattleQuestionTimer();
    const timer = document.getElementById('battleTimer');
    const deadline = Date.parse(communityState.battle?.questionDeadlineAt || '');
    if (!timer || !Number.isFinite(deadline)) {
        if (timer) timer.textContent = '';
        return;
    }
    const update = () => {
        const remainingMs = deadline - Date.now();
        const seconds = Math.max(0, Math.ceil(remainingMs / 1000));
        timer.textContent = `${seconds} сек`;
        timer.classList.toggle('urgent', seconds <= 10);
        if (remainingMs > 0 || communityState.battleTimeoutRefreshing) return;
        communityState.battleTimeoutRefreshing = true;
        clearBattleQuestionTimer();
        document.querySelectorAll('#battleOptions button').forEach((button) => { button.disabled = true; });
        setInlineMessage('battleFeedback', 'Время вышло. Ответ не засчитан.', 'error');
        window.setTimeout(refreshBattle, 500);
    };
    update();
    if (!communityState.battleTimeoutRefreshing) communityState.battleTimer = setInterval(update, 200);
}

async function answerBattle(questionId, selectedIndex) {
    clearBattleQuestionTimer();
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
        window.setTimeout(() => {
            if (communityState.battleRenderedQuestionId === questionId && communityState.battle?.status === 'active') {
                nextBattleQuestion();
            }
        }, 900);
    } catch (error) {
        setInlineMessage('battleFeedback', error.message, 'error');
        window.setTimeout(refreshBattle, 500);
    }
}

function nextBattleQuestion() {
    communityState.battleRenderedQuestionId = null;
    handleBattleState(communityState.battle);
}

function renderBattleFinish(battle) {
    clearBattleQuestionTimer();
    clearBattleCountdown();
    document.getElementById('battleOptions').replaceChildren();
    document.getElementById('battleNextButton').hidden = true;
    document.getElementById('battleQuestionImage').hidden = true;
    document.getElementById('battleTopic').textContent = battle.status === 'complete' ? 'Баттл завершён' : 'Ответы приняты';
    const question = document.getElementById('battleQuestion');
    if (battle.status !== 'complete') {
        question.textContent = 'Ожидаем, пока соперник закончит свои пять заданий.';
    } else if (battle.opponentForfeited) {
        const reward = battle.reward || {};
        const coinText = reward.coins ? ` +${reward.coins} монет.` : '';
        question.textContent = `Соперник покинул баттл. Победа!${coinText}`;
    } else if (battle.forfeitedByMe) {
        question.textContent = 'Вы покинули баттл. В статистике зафиксировано поражение, награда не начислена.';
    } else if (battle.me.score > battle.opponent.score) {
        const reward = battle.reward || {};
        const coinText = reward.coins ? ` +${reward.coins} монет.` : '';
        question.textContent = `Победа!${coinText}`;
    } else if (battle.me.score < battle.opponent.score) {
        question.textContent = 'В этот раз победил соперник. Можно вызвать нового участника.';
    } else {
        question.textContent = 'Ничья — одинаковое количество правильных ответов.';
    }
    const complete = battle.status === 'complete';
    document.getElementById('battleFinishActions').hidden = !complete;
    document.getElementById('battleLeaveButton').hidden = complete;
    renderBattleRewardStatus(complete ? battle.battleRewards : null);
    if (complete) clearInterval(communityState.battlePoll);
}

function renderBattleRewardStatus(rewards) {
    const panel = document.getElementById('battleRewardPanel');
    const buttons = document.getElementById('battleRewardButtons');
    const result = document.getElementById('battleRewardResult');
    buttons.replaceChildren();
    result.textContent = '';
    if (!rewards || (!rewards.daily?.available && !rewards.monthly?.available)) {
        panel.hidden = true;
        return;
    }
    panel.hidden = false;
    const messages = [];
    if (rewards.daily?.available) messages.push(`Побед сегодня: ${rewards.winsToday}. Дневной приз действует 7 дней.`);
    if (rewards.monthly?.available) messages.push('30 победных дней подряд: вещь действует 20 дней, купон — 30 дней.');
    document.getElementById('battleRewardText').textContent = messages.join(' ');
    [['daily', 'Крутить дневной барабан'], ['monthly', 'Крутить барабан за 30 дней']].forEach(([tier, label]) => {
        if (!rewards[tier]?.available) return;
        const button = document.createElement('button');
        button.type = 'button';
        button.className = 'btn';
        button.textContent = label;
        button.addEventListener('click', () => spinBattleReward(tier));
        buttons.appendChild(button);
    });
}

async function spinBattleReward(tier) {
    const wheel = document.getElementById('battleRewardWheel');
    const result = document.getElementById('battleRewardResult');
    document.querySelectorAll('#battleRewardButtons button').forEach((button) => { button.disabled = true; });
    result.textContent = 'Барабан вращается…';
    wheel.classList.remove('spinning');
    void wheel.offsetWidth;
    wheel.classList.add('spinning');
    try {
        const payload = await communityRequest('/api/battle-rewards/spin', {
            method: 'POST', headers: telegramHeaders(true), body: JSON.stringify({tier}),
        });
        window.setTimeout(() => {
            renderBattleRewardStatus(payload);
            document.getElementById('battleRewardPanel').hidden = false;
            document.getElementById('battleRewardResult').textContent = `${payload.prize.icon || '🎁'} ${payload.prize.label}. Действует ${payload.prize.validDays} дней.`;
        }, 2300);
    } catch (error) {
        result.textContent = error.message;
        document.querySelectorAll('#battleRewardButtons button').forEach((button) => { button.disabled = false; });
    }
}

document.getElementById('profileAvatarInput')?.addEventListener('change', handleProfileAvatarFile);

document.addEventListener('DOMContentLoaded', loadDailyLogin);

async function pollActiveBattle() {
    if (!tg.initData || document.visibilityState === 'hidden') return;
    try {
        const payload = await communityRequest('/api/battles/active', {headers: telegramHeaders()});
        if (payload.battleId && payload.battleId !== communityState.battleId) {
            await openBattleById(payload.battleId);
        }
    } catch (error) {
        console.warn('Не удалось проверить активный баттл:', error.message);
    }
}

function startActiveBattleSync() {
    clearInterval(communityState.battleSyncPoll);
    communityState.battleSyncPoll = setInterval(pollActiveBattle, 1000);
    pollActiveBattle();
}

document.addEventListener('DOMContentLoaded', startActiveBattleSync);

async function openDeepLinkedView() {
    if (!tg.initData) return;
    const params = new URLSearchParams(window.location.search);
    const view = params.get('view');
    const battleId = params.get('battle');
    const publicId = params.get('publicId');
    const requestId = params.get('request');
    const inviteId = params.get('invite');
    const validId = (value) => Boolean(value && /^[a-f0-9]{12}$/.test(value));

    if ((!view || view === 'battle') && validId(battleId)) {
        await openBattleById(battleId);
        return;
    }
    if (view === 'chat' && validId(publicId)) {
        await openChat(publicId);
        return;
    }
    if (view === 'battle-invite' && validId(inviteId)) {
        communityState.highlightedBattleInviteId = inviteId;
        await openFriends('classSelection');
        return;
    }
    if (view === 'friends') {
        communityState.highlightedFriendRequestId = validId(requestId) ? requestId : null;
        await openFriends('classSelection');
    }
}

document.addEventListener('DOMContentLoaded', () => window.setTimeout(openDeepLinkedView, 0));

async function leaveBattleScreen() {
    const battleId = communityState.battleId;
    const shouldForfeit = battleId && ['waiting', 'active'].includes(communityState.battle?.status);
    if (shouldForfeit) {
        try {
            await communityRequest(`/api/battles/${battleId}/forfeit`, {
                method: 'POST', headers: telegramHeaders(true), body: '{}',
            });
        } catch (error) {
            setInlineMessage('battleFeedback', error.message, 'error');
            return;
        }
    }
    clearInterval(communityState.battlePoll);
    clearBattleQuestionTimer();
    clearBattleCountdown();
    communityState.battleId = null;
    communityState.battle = null;
    communityState.battleRenderedQuestionId = null;
    communityState.battleCountdownCompleteId = null;
    currentClass = null;
    showScreen('classSelection');
}

async function openBattleStats() {
    showScreen('battleStatsScreen');
    setInlineMessage('battleStatsMessage', 'Загружаем статистику…');
    try {
        const stats = await communityRequest('/api/battle-stats', {headers: telegramHeaders()});
        syncCoinBalance(stats.coins, stats.admin);
        const summary = document.getElementById('battleStatsSummary');
        summary.innerHTML = `
            <article><strong>${stats.total}</strong><small>баттлов</small></article>
            <article><strong>${stats.wins}</strong><small>побед</small></article>
            <article><strong>${stats.draws}</strong><small>ничьих</small></article>
            <article><strong>${stats.losses}</strong><small>поражений</small></article>`;
        const bars = document.getElementById('battleStatsBars');
        bars.replaceChildren();
        [['Победы', stats.winPercent, 'win'], ['Ничьи', stats.drawPercent, 'draw'], ['Поражения', stats.lossPercent, 'loss']].forEach(([label, value, kind]) => {
            const row = document.createElement('div');
            row.className = `battle-stat-row battle-stat-${kind}`;
            row.innerHTML = `<div><strong>${label}</strong><span>${value}%</span></div><div class="battle-stat-track"><i style="width:${value}%"></i></div>`;
            bars.appendChild(row);
        });
        setInlineMessage('battleStatsMessage', `Сегодня за победы заработано ${stats.coinsToday} монет. Дневного лимита нет.`, 'success');
    } catch (error) {
        setInlineMessage('battleStatsMessage', error.message, 'error');
    }
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
