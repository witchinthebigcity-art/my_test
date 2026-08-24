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

async function openAdventureAfterTraining() {
    try {
        const session = await communityRequest('/api/adventure/start', {
            method: 'POST',
            headers: telegramHeaders(true),
            body: JSON.stringify({grade: currentClass, attemptKey: currentAttemptKey}),
        });
        renderAdventure(session);
    } catch (error) {
        alert(error.message);
    }
}

async function resumeAdventure() {
    try {
        const payload = await communityRequest(`/api/adventure?grade=${currentClass}`, {
            headers: telegramHeaders(),
        });
        if (!payload.active) return openAdventureAfterTraining();
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
    const isFormulaStage = session.stage === 'formula';
    const isSolutionStage = session.stage === 'solution';
    const screen = document.getElementById('adventureScreen');
    screen.classList.toggle('formula-game-stage', isFormulaStage);
    screen.classList.toggle('solution-game-stage', isSolutionStage || session.stage === 'complete');
    document.getElementById('adventureGameTitle').textContent = isFormulaStage
        ? 'Башня формул'
        : 'Лаборатория решений';
    document.getElementById('adventureStatus').textContent = isSolutionStage
        ? 'Башня пройдена. Теперь восстановите доказательство — черновик сохраняется автоматически.'
        : session.stage === 'complete'
            ? 'Проверка завершена. Результат сохранён в статистике.'
            : `Откройте ${Number(session.formula?.total || 4)} этажа: на каждом выберите верную формулу.`;
    document.getElementById('adventureWorld').hidden = !isFormulaStage;
    if (isFormulaStage) renderFormulaChallenge(session.formula || {});
    const panel = document.getElementById('extendedSolutionPanel');
    panel.hidden = !isSolutionStage;
    document.getElementById('extendedResult').hidden = session.stage !== 'complete';
    if (isSolutionStage) renderExtendedTask(session.task, session.draft || {}, session.verification || {});
    if (session.stage === 'complete' && session.result) renderExtendedResult(session.result);
}

function renderFormulaChallenge(formula) {
    const challenge = formula.challenge;
    const floors = document.getElementById('formulaFloors');
    floors.replaceChildren();
    for (let index = 0; index < Number(formula.total || 4); index += 1) {
        const floor = document.createElement('i');
        floor.className = index < Number(formula.index || 0) ? 'opened' : '';
        floor.setAttribute('aria-label', `Этаж ${index + 1}`);
        floors.appendChild(floor);
    }
    if (!challenge) return;
    document.getElementById('formulaPrompt').textContent = challenge.prompt;
    document.getElementById('formulaHint').textContent = challenge.hint || '';
    const options = document.getElementById('formulaOptions');
    options.replaceChildren();
    (challenge.options || []).forEach((option) => {
        const button = document.createElement('button');
        button.type = 'button';
        button.className = 'formula-option';
        button.dataset.optionId = option.id;
        if (typeof setMathContent === 'function') setMathContent(button, `$${option.formula}$`);
        else button.textContent = option.formula;
        button.addEventListener('click', () => answerFormula(option.id, button));
        options.appendChild(button);
    });
    const feedback = document.getElementById('formulaFeedback');
    feedback.textContent = formula.feedback?.message || `Этаж ${Number(formula.index || 0) + 1} из ${formula.total || 4}`;
    feedback.className = `formula-feedback${formula.feedback ? (formula.feedback.correct ? ' correct' : ' wrong') : ''}`;
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
        window.setTimeout(() => renderAdventure(session), correct ? 560 : 820);
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
        next.addEventListener('click', openAdventureAfterTraining);
        panel.appendChild(next);
    }
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
