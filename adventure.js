const adventureState = {
    session: null,
    conditionImage: '',
    solutionImage: '',
    draftTimer: null,
};

const CRYSTALS = [
    {id: 'logic', icon: '◇', name: 'Логика'},
    {id: 'formula', icon: '△', name: 'Формула'},
    {id: 'focus', icon: '✦', name: 'Фокус'},
];

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
    const completed = new Set(session.crystals || []);
    document.getElementById('adventureStatus').textContent = session.stage === 'solution'
        ? 'Ворота открыты. Решение сохраняется на сервере после проверки.'
        : `Соберите кристаллы знаний: ${completed.size} из 3.`;
    const row = document.getElementById('crystalButtons');
    row.replaceChildren();
    const avatar = document.querySelector('.adventure-avatar');
    avatar.style.left = `${8 + completed.size * 17}%`;
    CRYSTALS.forEach((crystal, index) => {
        const button = document.createElement('button');
        button.type = 'button';
        button.className = 'crystal-button';
        button.classList.toggle('collected', completed.has(crystal.id));
        button.disabled = completed.has(crystal.id) || index > completed.size;
        button.hidden = index > completed.size;
        button.style.setProperty('--crystal-x', `${18 + ((index * 29 + 17) % 64)}%`);
        button.style.setProperty('--crystal-delay', `${index * -0.45}s`);
        if (completed.has(crystal.id)) button.style.left = `${12 + index * 84}px`;
        const icon = document.createElement('strong');
        icon.textContent = crystal.icon;
        const label = document.createElement('small');
        label.textContent = crystal.name;
        button.append(icon, label);
        if (!button.disabled) button.addEventListener('click', () => collectCrystal(crystal.id));
        row.appendChild(button);
    });
    document.getElementById('adventureWorld').classList.toggle('gate-open', session.stage !== 'crystals');
    const panel = document.getElementById('extendedSolutionPanel');
    panel.hidden = session.stage !== 'solution';
    document.getElementById('extendedResult').hidden = session.stage !== 'complete';
    if (session.stage === 'solution') renderExtendedTask(session.task, session.draft || {});
    if (session.stage === 'complete' && session.result) renderExtendedResult(session.result);
}

async function collectCrystal(crystal) {
    try {
        const session = await communityRequest(`/api/adventure/${adventureState.session.id}/progress`, {
            method: 'POST',
            headers: telegramHeaders(true),
            body: JSON.stringify({crystal}),
        });
        renderAdventure(session);
    } catch (error) {
        alert(error.message);
    }
}

function renderExtendedTask(task, draft = {}) {
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
        mathField.setAttribute('virtual-keyboard-mode', 'manual');
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
        wrapper.append(label, mathField);
        fields.appendChild(wrapper);
    });
    document.getElementById('extendedExplanation').value = draft.explanation || '';
    document.getElementById('extendedExplanation').oninput = scheduleAdventureDraft;
    document.getElementById('conditionImageInput').value = '';
    document.getElementById('solutionImageInput').value = '';
    document.getElementById('solutionImageInput').onchange = recognizeSolutionImage;
    document.getElementById('solutionUploadStatus').hidden = true;
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
    if (window.mathVirtualKeyboard) window.mathVirtualKeyboard.show();
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
        : 'Фотографии сохранены. Пока ключ экспертного модуля не подключён, балл рассчитан по полям MathLive и полноте объяснения.';
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
