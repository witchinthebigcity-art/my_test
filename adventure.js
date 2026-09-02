const adventureState = {
    session: null,
    conditionImage: '',
    solutionImage: '',
    draftTimer: null,
};

async function updateAdventureResume() {
    const card = document.getElementById('resumeAdventureCard');
    if (!card || !currentClass || !tg.initData) return;
    try {
        const payload = await communityRequest(`/api/adventure?grade=${currentClass}`, {
            headers: telegramHeaders(),
        });
        card.hidden = !payload.active;
    } catch (_error) {
        card.hidden = true;
    }
}

function openGameUniverse() {
    closeMathKeyboard();
    showScreen('gameUniverseScreen');
}

function openExpertNumberMenu() {
    const grid = document.getElementById('expertNumberGrid');
    grid.replaceChildren();
    for (let number = 13; number <= 19; number += 1) {
        const button = document.createElement('button');
        button.type = 'button';
        button.className = `expert-number-button${number === 13 ? ' is-active' : ' is-locked'}`;
        button.disabled = number !== 13;
        const title = document.createElement('strong');
        title.textContent = `${number} номер`;
        const status = document.createElement('small');
        status.textContent = number === 13 ? 'Играть' : 'В разработке';
        button.append(title, status);
        if (number === 13) button.addEventListener('click', () => startAdventureGame('expert', number));
        grid.appendChild(button);
    }
    showScreen('expertNumberScreen');
}

async function startAdventureGame(game = 'tower', taskNumber = null) {
    try {
        const session = await communityRequest('/api/adventure/start', {
            method: 'POST',
            headers: telegramHeaders(true),
            body: JSON.stringify({grade: currentClass, attemptKey: currentAttemptKey, game, taskNumber}),
        });
        renderAdventure(session);
    } catch (error) {
        alert(error.message);
    }
}

function openAdventureAfterTraining() {
    openGameUniverse();
}

async function resumeAdventure() {
    try {
        const payload = await communityRequest(`/api/adventure?grade=${currentClass}`, {
            headers: telegramHeaders(),
        });
        if (!payload.active) return openGameUniverse();
        renderAdventure(payload.session);
    } catch (error) {
        alert(error.message);
    }
}

function renderAdventure(session) {
    adventureState.session = session;
    adventureState.conditionImage = '';
    adventureState.solutionImage = '';
    showScreen('adventureScreen');
    const isTower = session.game === 'tower';
    const isFormulaStage = isTower && session.stage === 'formula';
    const isSolutionStage = session.game === 'second_part' && session.stage === 'solution';
    const isExpertStage = session.game === 'expert' && ['grading', 'review'].includes(session.stage);
    const formula = session.formula || {};
    const screen = document.getElementById('adventureScreen');
    screen.classList.toggle('formula-game-stage', isFormulaStage);
    screen.classList.toggle('solution-game-stage', isSolutionStage || isExpertStage || session.stage === 'complete');
    document.getElementById('adventureGameEyebrow').textContent = isTower
        ? 'Активная игра · формулы'
        : session.game === 'expert' ? 'Активная игра · проверка работ' : 'Активная игра · развёрнутое решение';
    document.getElementById('adventureGameTitle').textContent = isTower
        ? 'Башня формул'
        : session.game === 'expert' ? 'Ты — эксперт' : 'Математическое расследование';
    document.getElementById('adventureStatus').textContent = isExpertStage
        ? (session.stage === 'review'
            ? 'Изучите обратную связь и нажмите «Далее», когда будете готовы.'
            : 'Изучите работу и определите, сколько баллов поставил эксперт.')
        : isSolutionStage
        ? 'Решите задание второй части — черновик сохраняется автоматически.'
        : session.stage === 'complete'
            ? (isTower ? 'Раунд завершён. Монеты начислены за каждый верный ответ.' : 'Проверка завершена. Результат сохранён в статистике.')
            : `Вопрос ${Math.min(Number(formula.index || 0) + 1, Number(formula.total || 10))} из ${Number(formula.total || 10)} · Ошибки ${Number(formula.mistakes || 0)} из ${formula.adminUnlimited ? '∞' : Number(formula.maxMistakes || 5)} · ${Number(formula.rewardPerCorrect || 50)} монет за верный ответ.`;
    document.getElementById('adventureLeaveButton').hidden = !(isFormulaStage || isExpertStage);
    if (typeof syncPageNavigationControls === 'function') syncPageNavigationControls();
    document.getElementById('adventureWorld').hidden = !isFormulaStage;
    if (isFormulaStage) renderFormulaChallenge(formula);
    const panel = document.getElementById('extendedSolutionPanel');
    panel.hidden = !isSolutionStage;
    const expertPanel = document.getElementById('expertGradingPanel');
    expertPanel.hidden = !isExpertStage;
    document.getElementById('extendedResult').hidden = session.stage !== 'complete';
    if (isSolutionStage) renderExtendedTask(session.task, session.draft || {}, session.verification || {});
    if (isExpertStage) renderExpertTask(session.task, session.expert || {}, session.stage, session.result || null);
    if (session.stage === 'complete' && session.result) {
        if (isTower) renderTowerResult(session.result);
        else if (session.game === 'expert') renderExpertResult(session.result);
        else renderExtendedResult(session.result);
    }
}

function renderFormulaChallenge(formula) {
    const challenge = formula.challenge;
    const floors = document.getElementById('formulaFloors');
    floors.replaceChildren();
    for (let index = 0; index < Number(formula.total || 10); index += 1) {
        const floor = document.createElement('i');
        floor.className = index < Number(formula.index || 0) ? 'opened' : '';
        floor.setAttribute('aria-label', `Этаж ${index + 1}`);
        floors.appendChild(floor);
    }
    if (!challenge) return;
    document.getElementById('formulaPrompt').textContent = challenge.prompt;
    const expression = document.getElementById('formulaExpression');
    expression.hidden = !challenge.formula;
    setMathContent(expression, challenge.formula || '');
    const hint = document.getElementById('formulaHint');
    hint.textContent = challenge.hint || '';
    hint.hidden = !challenge.hint;
    const options = document.getElementById('formulaOptions');
    options.replaceChildren();
    (challenge.options || []).forEach((option) => {
        const button = document.createElement('button');
        button.type = 'button';
        button.className = 'formula-option';
        button.dataset.optionId = option.id;
        setMathContent(button, option.text);
        button.addEventListener('click', () => answerFormula(option.id, button));
        options.appendChild(button);
    });
    const feedback = document.getElementById('formulaFeedback');
    feedback.textContent = formula.feedback?.message || `Верных ответов: ${Number(formula.score || 0)} · ошибок: ${Number(formula.mistakes || 0)} из ${formula.adminUnlimited ? '∞' : Number(formula.maxMistakes || 5)}`;
    feedback.className = `formula-feedback${formula.feedback ? (formula.feedback.correct ? ' correct' : ' wrong') : ''}`;
}

function appendGameNavigation(panel, nextGame) {
    const actions = document.createElement('div');
    actions.className = 'game-result-actions';
    const next = document.createElement('button');
    next.type = 'button';
    next.className = 'btn adventure-launch-button';
    if (nextGame) {
        next.textContent = 'Следующая игра';
        next.addEventListener('click', () => startAdventureGame(nextGame));
    } else {
        next.textContent = 'Следующая игра — в проекте';
        next.disabled = true;
    }
    actions.appendChild(next);
    const universe = document.createElement('button');
    universe.type = 'button';
    universe.className = 'btn';
    universe.textContent = 'Вселенная игр';
    universe.addEventListener('click', openGameUniverse);
    const menu = document.createElement('button');
    menu.type = 'button';
    menu.className = 'btn btn-secondary';
    menu.textContent = 'Главное меню';
    menu.addEventListener('click', () => showScreen('mainMenu'));
    actions.append(universe, menu);
    panel.appendChild(actions);
}

function renderTowerResult(result) {
    document.getElementById('extendedSolutionPanel').hidden = true;
    const panel = document.getElementById('extendedResult');
    panel.replaceChildren();
    panel.hidden = false;
    const score = document.createElement('strong');
    score.className = 'extended-score';
    score.textContent = `${result.score} / ${result.maxScore} верных ответов`;
    const verdict = document.createElement('p');
    verdict.textContent = result.verdict || 'Башня формул пройдена.';
    const reward = document.createElement('p');
    reward.className = 'formula-result-reward';
    reward.textContent = `Награда: ${Number(result.rewardCoins || 0)} монет · ошибок: ${Number(result.mistakes || 0)} из ${Number(result.maxMistakes || 5)}`;
    panel.append(score, verdict, reward);
    if (Number.isFinite(Number(result.coins)) && typeof syncCoinBalance === 'function') {
        syncCoinBalance(Number(result.coins), Boolean(result.admin));
    }
    appendGameNavigation(panel, 'second_part');
}

async function leaveAdventureGame() {
    const session = adventureState.session;
    if (!session || !['formula', 'grading', 'review'].includes(session.stage)) return;
    const confirmed = await new Promise((resolve) => {
        const message = session.game === 'expert'
            ? 'Покинуть проверку? Уже заработанные монеты сохранятся, но раунд завершится.'
            : 'Покинуть игру? Очки и монеты за этот раунд не сохранятся.';
        if (tg && typeof tg.showConfirm === 'function') tg.showConfirm(message, resolve);
        else resolve(window.confirm(message));
    });
    if (!confirmed) return;
    try {
        await communityRequest(`/api/adventure/${session.id}/leave`, {
            method: 'POST',
            headers: telegramHeaders(true),
            body: JSON.stringify({}),
        });
        adventureState.session = null;
        openGameUniverse();
        updateAdventureResume();
    } catch (error) {
        alert(error.message);
    }
}

function renderExpertTask(task, run = {}, stage = 'grading', result = null) {
    document.getElementById('expertTaskKind').textContent = task.kind || 'Проверка работы';
    document.getElementById('expertTaskTitle').textContent = task.title;
    document.getElementById('expertTaskQuestion').textContent = task.question;
    const image = document.getElementById('expertTaskImage');
    image.src = task.imageUrl;
    document.getElementById('expertRunStats').textContent =
        `Работа ${Number(run.index || 0) + 1} из ${Number(run.total || 1)} · ` +
        `❤️ ${run.adminUnlimited ? '∞' : `${Number(run.lives || 0)} из ${Number(run.maxLives || 5)}`} · ` +
        `Верно: ${Number(run.correct || 0)} · Награда: ${Number(run.rewardCoins || 0)} 🪙`;
    const criteriaImages = document.getElementById('expertCriteriaImages');
    criteriaImages.replaceChildren();
    (task.criteriaImageUrls || []).forEach((url, index) => {
        const criteria = document.createElement('img');
        criteria.className = 'question-media expert-criteria-image';
        criteria.src = url;
        criteria.alt = `Критерии, страница ${index + 1}`;
        criteriaImages.appendChild(criteria);
    });
    document.getElementById('expertCriteriaPanel').hidden = true;
    document.getElementById('expertCriteriaButton').textContent = 'Критерии';
    const options = document.getElementById('expertScoreOptions');
    options.replaceChildren();
    for (let score = 0; score <= Number(task.maxScore || 2); score += 1) {
        const button = document.createElement('button');
        button.type = 'button';
        button.className = 'expert-score-button';
        button.textContent = `${score}`;
        button.setAttribute('aria-label', `${score} баллов`);
        button.addEventListener('click', () => submitExpertScore(score));
        options.appendChild(button);
    }
    document.getElementById('expertAnswerControls').hidden = stage !== 'grading';
    const scoreMessage = document.getElementById('expertScoreMessage');
    scoreMessage.hidden = true;
    const review = document.getElementById('expertReviewPanel');
    review.replaceChildren();
    review.hidden = stage !== 'review';
    if (stage === 'review' && result) renderExpertReview(review, result);
}

function toggleExpertCriteria() {
    const panel = document.getElementById('expertCriteriaPanel');
    panel.hidden = !panel.hidden;
    document.getElementById('expertCriteriaButton').textContent = panel.hidden ? 'Критерии' : 'Скрыть критерии';
}

function renderExpertReview(panel, result) {
    const verdict = document.createElement('p');
    verdict.className = `inline-message ${result.correct ? 'success' : 'error'}`;
    verdict.textContent = result.verdict;
    panel.appendChild(verdict);
    if (result.answerImageUrl) {
        const heading = document.createElement('h3');
        heading.textContent = 'Ответ и разбор эксперта';
        const answer = document.createElement('img');
        answer.className = 'question-media expert-answer-image';
        answer.src = result.answerImageUrl;
        answer.alt = 'Ответ и разбор эксперта';
        panel.append(heading, answer);
    }
    const next = document.createElement('button');
    next.type = 'button';
    next.className = 'btn adventure-launch-button';
    next.textContent = Number(result.lives || 0) > 0 ? 'Далее' : 'Завершить игру';
    next.addEventListener('click', continueExpertGame);
    panel.appendChild(next);
}

async function continueExpertGame() {
    try {
        const session = await communityRequest(`/api/adventure/${adventureState.session.id}/expert-next`, {
            method: 'POST',
            headers: telegramHeaders(true),
            body: JSON.stringify({}),
        });
        renderAdventure(session);
    } catch (error) {
        alert(error.message);
    }
}

async function submitExpertScore(score) {
    const buttons = document.querySelectorAll('#expertScoreOptions button');
    buttons.forEach((button) => { button.disabled = true; });
    const message = document.getElementById('expertScoreMessage');
    message.hidden = false;
    message.textContent = 'Сверяем с оценкой эксперта…';
    try {
        const session = await communityRequest(`/api/adventure/${adventureState.session.id}/expert-score`, {
            method: 'POST',
            headers: telegramHeaders(true),
            body: JSON.stringify({score}),
        });
        renderAdventure(session);
        document.getElementById('resumeAdventureCard').hidden = true;
    } catch (error) {
        message.textContent = error.message;
        buttons.forEach((button) => { button.disabled = false; });
    }
}

function renderExpertResult(result) {
    document.getElementById('extendedSolutionPanel').hidden = true;
    document.getElementById('expertGradingPanel').hidden = true;
    const panel = document.getElementById('extendedResult');
    panel.replaceChildren();
    panel.hidden = false;
    const score = document.createElement('strong');
    score.className = 'extended-score';
    score.textContent = `${Number(result.score || 0)} из ${Number(result.maxScore || 0)} оценок верны`;
    const verdict = document.createElement('p');
    verdict.textContent = result.verdict;
    panel.append(score, verdict);
    const summary = document.createElement('p');
    summary.textContent = `Ошибок: ${Number(result.mistakes || 0)} · заработано: ${Number(result.rewardCoins || 0)} монет.`;
    panel.appendChild(summary);
    if (Number.isFinite(Number(result.coins)) && typeof syncCoinBalance === 'function') {
        syncCoinBalance(Number(result.coins), Boolean(result.admin));
    }
    appendGameNavigation(panel, null);
}

async function answerFormula(optionId, selectedButton) {
    document.querySelectorAll('#formulaOptions button').forEach((button) => { button.disabled = true; });
    selectedButton.classList.add('selected');
    try {
        const session = await communityRequest(`/api/adventure/${adventureState.session.id}/formula`, {
            method: 'POST',
            headers: telegramHeaders(true),
            body: JSON.stringify({optionId}),
        });
        const correct = Boolean(session.formula?.feedback?.correct);
        selectedButton.classList.add(correct ? 'is-correct' : 'is-wrong');
        document.getElementById('formulaFeedback').textContent = session.formula?.feedback?.message || '';
        document.getElementById('formulaFeedback').className = `formula-feedback ${correct ? 'correct' : 'wrong'}`;
        window.setTimeout(() => renderAdventure(session), 680);
    } catch (error) {
        alert(error.message);
        document.querySelectorAll('#formulaOptions button').forEach((button) => { button.disabled = false; });
    }
}

function renderExtendedTask(task, draft = {}, verification = {}) {
    document.getElementById('extendedTaskKind').textContent = task.kind;
    document.getElementById('extendedTaskTitle').textContent = task.title;
    const question = document.getElementById('extendedTaskQuestion');
    if (typeof setMathContent === 'function') setMathContent(question, task.question);
    else question.textContent = task.question;
    const taskImage = document.getElementById('extendedTaskImage');
    taskImage.hidden = !task.imageUrl;
    if (task.imageUrl) taskImage.src = task.imageUrl;
    else taskImage.removeAttribute('src');
    document.getElementById('extendedCriteriaSource').textContent = task.criteriaSource;
    const fields = document.getElementById('extendedMathFields');
    fields.replaceChildren();
    task.fields.forEach((field) => {
        const wrapper = document.createElement('label');
        wrapper.className = 'math-answer-card';
        const label = document.createElement('span');
        label.textContent = field.label;
        const mathField = document.createElement('math-field');
        mathField.dataset.fieldId = field.id;
        mathField.setAttribute('math-virtual-keyboard-policy', 'manual');
        mathField.setAttribute('placeholder', field.hint || 'Введите выражение');
        mathField.setAttribute('aria-label', field.label);
        const draftValue = (draft.answers || {})[field.id] || '';
        if (draftValue) {
            mathField.setAttribute('value', draftValue);
            customElements.whenDefined('math-field').then(() => {
                if (typeof mathField.setValue === 'function') mathField.setValue(draftValue);
            });
        }
        mathField.addEventListener('input', scheduleAdventureDraft);
        mathField.addEventListener('focusin', showCompactMathKeyboard);
        wrapper.append(label, mathField);
        fields.appendChild(wrapper);
    });
    document.getElementById('extendedExplanation').value = draft.explanation || '';
    document.getElementById('extendedExplanation').oninput = scheduleAdventureDraft;
    document.getElementById('conditionImageInput').value = '';
    document.getElementById('solutionImageInput').value = '';
    document.getElementById('solutionImageInput').onchange = recognizeSolutionImage;
    const status = document.getElementById('solutionUploadStatus');
    status.hidden = false;
    status.textContent = verification.expertCheck
        ? 'Автопроверка решения и фотографий включена.'
        : 'Автопроверка ответа и структуры включена. Неясные символы уточняйте через математическую клавиатуру.';
}

function currentExtendedAnswers() {
    const answers = {};
    document.querySelectorAll('#extendedMathFields math-field').forEach((field) => {
        answers[field.dataset.fieldId] = typeof field.getValue === 'function'
            ? field.getValue('latex')
            : (field.value || field.getAttribute('value') || '');
    });
    return answers;
}

function scheduleAdventureDraft() {
    clearTimeout(adventureState.draftTimer);
    adventureState.draftTimer = setTimeout(saveAdventureDraft, 650);
}

async function saveAdventureDraft() {
    if (!adventureState.session || adventureState.session.stage !== 'solution') return;
    try {
        await communityRequest(`/api/adventure/${adventureState.session.id}/draft`, {
            method: 'POST',
            headers: telegramHeaders(true),
            body: JSON.stringify({
                answers: currentExtendedAnswers(),
                explanation: document.getElementById('extendedExplanation').value,
            }),
        });
        document.getElementById('adventureStatus').textContent = 'Черновик сохранён автоматически.';
    } catch (_error) {
        document.getElementById('adventureStatus').textContent = 'Черновик сохранится при восстановлении связи.';
    }
}

async function recognizeSolutionImage() {
    const status = document.getElementById('solutionUploadStatus');
    status.hidden = false;
    status.textContent = 'Распознаём математическую запись…';
    try {
        adventureState.solutionImage = await prepareSolutionImage(document.getElementById('solutionImageInput'));
        if (!adventureState.solutionImage) {
            status.hidden = true;
            return;
        }
        const result = await communityRequest('/api/adventure/recognize', {
            method: 'POST',
            headers: telegramHeaders(true),
            body: JSON.stringify({image: adventureState.solutionImage}),
        });
        if (!result.configured) {
            status.textContent = result.message;
            return;
        }
        const explanation = document.getElementById('extendedExplanation');
        if (!explanation.value.trim() && result.text) explanation.value = result.text;
        const confidence = Math.round(Number(result.confidence || 0) * 100);
        status.textContent = result.needsConfirmation
            ? `Распознано примерно на ${confidence}%. Проверьте сомнительные символы через MathLive.`
            : `Решение распознано (${confidence}%). Проверьте итоговый ответ.`;
        if (result.needsConfirmation) focusFirstMathField();
    } catch (error) {
        status.textContent = `${error.message}. Можно продолжить через математическую клавиатуру.`;
    }
}

function focusFirstMathField() {
    const field = document.querySelector('#extendedMathFields math-field');
    if (!field) return;
    field.focus();
    showCompactMathKeyboard();
}

function showCompactMathKeyboard() {
    if (!window.mathVirtualKeyboard) return;
    window.mathVirtualKeyboard.layouts = ['numeric', 'symbols'];
    window.mathVirtualKeyboard.show({animate: true});
    document.body.classList.add('math-keyboard-open');
    const closeButton = document.getElementById('mathKeyboardClose');
    if (closeButton) closeButton.hidden = false;
}

function closeMathKeyboard() {
    if (window.mathVirtualKeyboard) window.mathVirtualKeyboard.hide({animate: true});
    document.body.classList.remove('math-keyboard-open');
    const closeButton = document.getElementById('mathKeyboardClose');
    if (closeButton) closeButton.hidden = true;
}

async function prepareSolutionImage(input) {
    const file = input.files && input.files[0];
    if (!file) return '';
    if (!file.type.startsWith('image/')) throw new Error('Выберите изображение');
    return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onerror = () => reject(new Error('Не удалось прочитать фото'));
        reader.onload = () => {
            const image = new Image();
            image.onerror = () => reject(new Error('Не удалось открыть фото'));
            image.onload = () => {
                // Keep two uploaded pages comfortably below Telegram WebView and server limits.
                const scale = Math.min(1, 1000 / Math.max(image.width, image.height));
                const canvas = document.createElement('canvas');
                canvas.width = Math.max(1, Math.round(image.width * scale));
                canvas.height = Math.max(1, Math.round(image.height * scale));
                canvas.getContext('2d').drawImage(image, 0, 0, canvas.width, canvas.height);
                resolve(canvas.toDataURL('image/jpeg', 0.65));
            };
            image.src = reader.result;
        };
        reader.readAsDataURL(file);
    });
}

async function submitExtendedSolution() {
    const button = document.getElementById('submitExtendedButton');
    const status = document.getElementById('solutionUploadStatus');
    button.disabled = true;
    status.hidden = false;
    status.textContent = 'Готовим фотографии и проверяем решение…';
    try {
        adventureState.conditionImage = await prepareSolutionImage(document.getElementById('conditionImageInput'));
        adventureState.solutionImage = await prepareSolutionImage(document.getElementById('solutionImageInput'));
        const answers = currentExtendedAnswers();
        const session = await communityRequest(`/api/adventure/${adventureState.session.id}/submit`, {
            method: 'POST',
            headers: telegramHeaders(true),
            body: JSON.stringify({
                answers,
                explanation: document.getElementById('extendedExplanation').value,
                conditionImage: adventureState.conditionImage,
                solutionImage: adventureState.solutionImage,
            }),
        });
        renderAdventure(session);
        document.getElementById('resumeAdventureCard').hidden = true;
    } catch (error) {
        status.textContent = error.message;
    } finally {
        button.disabled = false;
    }
}

function renderExtendedResult(result) {
    document.getElementById('extendedSolutionPanel').hidden = true;
    const panel = document.getElementById('extendedResult');
    panel.replaceChildren();
    panel.hidden = false;
    const score = document.createElement('strong');
    score.className = 'extended-score';
    score.textContent = `${result.score} / ${result.maxScore} балла`;
    const verdict = document.createElement('p');
    verdict.textContent = result.verdict;
    const list = document.createElement('div');
    list.className = 'criteria-results';
    (result.criteria || []).forEach((criterion) => {
        const row = document.createElement('div');
        row.textContent = `${criterion.correct ? '✓' : '○'} ${criterion.label}: ${criterion.earned}/${criterion.max}`;
        row.classList.toggle('passed', criterion.correct);
        list.appendChild(row);
    });
    const note = document.createElement('small');
    note.textContent = result.engine === 'expert-model'
        ? 'Фотографии сохранены. Решение проверено математическим экспертным модулем по рубрике задания.'
        : 'Автоматическая проверка ответа, обязательных шагов и полноты объяснения выполнена. Фотографии сохранены вместе с попыткой.';
    panel.append(score, verdict, list, note);
    if ((adventureState.session?.task?.id || '').startsWith('drive-extended-')) {
        const next = document.createElement('button');
        next.type = 'button';
        next.className = 'btn adventure-launch-button';
        next.textContent = 'Следующее задание без повторов';
        next.addEventListener('click', () => startAdventureGame('second_part'));
        panel.appendChild(next);
    }
    appendGameNavigation(panel, null);
}

window.addEventListener('pagehide', () => {
    if (adventureState.session?.stage === 'solution') saveAdventureDraft();
});

async function openTrainingHistory() {
    showScreen('trainingHistoryScreen');
    const list = document.getElementById('trainingHistoryList');
    list.innerHTML = '<p class="empty-state">Загружаем историю…</p>';
    try {
        const suffix = currentClass ? `?grade=${currentClass}` : '';
        const payload = await communityRequest(`/api/training-history${suffix}`, {headers: telegramHeaders()});
        list.replaceChildren();
        if (!(payload.entries || []).length) {
            list.innerHTML = '<p class="empty-state">Завершённых тренировок пока нет.</p>';
            return;
        }
        payload.entries.forEach((entry) => {
            const card = document.createElement('article');
            card.className = 'training-history-card';
            const date = entry.createdAt ? new Date(entry.createdAt).toLocaleString('ru-RU', {day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit'}) : 'Ранее';
            const heading = document.createElement('div');
            heading.innerHTML = `<strong>${entry.grade} класс · ${entry.percent}%</strong><small>${date}</small>`;
            const bar = document.createElement('div');
            bar.className = 'history-progress';
            const fill = document.createElement('span');
            fill.style.width = `${entry.percent}%`;
            bar.appendChild(fill);
            const meta = document.createElement('p');
            meta.textContent = `${entry.correct} из ${entry.total} · ${(entry.topics || []).join(', ') || 'Общее'}`;
            card.append(heading, bar, meta);
            list.appendChild(card);
        });
    } catch (error) {
        list.innerHTML = `<p class="empty-state"></p>`;
        list.querySelector('p').textContent = error.message;
    }
}
