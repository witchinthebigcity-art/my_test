const studentLearningState = {
    dashboard: null,
    lessonUrl: null,
    homeworkUrl: null,
    theoryReturn: false,
    unlockTimer: null,
    testRun: null,
};

function studentMessage(id, text, kind = 'info') {
    const element = document.getElementById(id);
    if (!element) return;
    element.textContent = text || '';
    element.dataset.kind = kind;
    element.hidden = !text;
}

async function studentRequest(url, options = {}) {
    const response = await fetch(url, {
        cache: 'no-store',
        ...options,
        headers: {...telegramHeaders(), ...(options.headers || {})},
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(payload.error || 'Не удалось открыть кабинет ученика');
    return payload;
}

async function refreshStudentEntry() {
    if (!tg.initData) return;
    try {
        const status = await studentRequest('/api/student/status');
        const title = document.getElementById('studentModeEntryTitle');
        if (title) title.textContent = status.authenticated ? 'Кабинет ученика' : 'Режим ученика';
    } catch (_) {
        // The ordinary app remains available if the personal area is temporarily unavailable.
    }
}

async function openStudentMode() {
    studentMessage('studentLoginMessage', 'Проверяем доступ…');
    try {
        const status = await studentRequest('/api/student/status');
        if (status.authenticated) {
            await loadStudentDashboard();
            return;
        }
        document.getElementById('studentPassword').value = '';
        studentMessage(
            'studentLoginMessage',
            status.available
                ? 'Введите пароль, полученный лично от преподавателя.'
                : 'Ваш Telegram-аккаунт пока не добавлен преподавателем.',
            status.available ? 'info' : 'error',
        );
        showScreen('studentLoginScreen');
    } catch (error) {
        studentMessage('studentLoginMessage', error.message, 'error');
        showScreen('studentLoginScreen');
    }
}

async function loginStudentMode() {
    const button = document.querySelector('#studentLoginScreen .btn');
    button.disabled = true;
    studentMessage('studentLoginMessage', 'Входим…');
    try {
        await studentRequest('/api/student/login', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                password: document.getElementById('studentPassword').value,
                reminderTime: document.getElementById('studentReminderTime').value,
            }),
        });
        document.getElementById('studentPassword').value = '';
        await refreshStudentEntry();
        await loadStudentDashboard();
    } catch (error) {
        studentMessage('studentLoginMessage', error.message, 'error');
    } finally {
        button.disabled = false;
    }
}

function renderStudentDashboard(payload) {
    studentLearningState.dashboard = payload;
    const student = payload.student;
    currentClass = Number(student.grade);
    document.body.dataset.grade = student.grade;
    document.getElementById('studentDashboardName').textContent = student.displayName;
    const goalCard = document.getElementById('studentGoalCard');
    goalCard.replaceChildren();
    const grade = document.createElement('small');
    grade.textContent = `${student.grade} класс · персональный маршрут`;
    const heading = document.createElement('strong');
    heading.textContent = 'Цель на год';
    const goal = document.createElement('p');
    goal.textContent = student.goal || 'Цель уточняется вместе с преподавателем.';
    goalCard.append(grade, heading, goal);
    const status = document.getElementById('studentLessonStatus');
    status.textContent = payload.lesson
        ? `${payload.lesson.title}${payload.lesson.testCompleted ? ` · тест ${payload.lesson.testScore}/${payload.lesson.testTotal}` : ''}`
        : 'Новый конспект пока не добавлен';
}

async function loadStudentDashboard() {
    try {
        const payload = await studentRequest('/api/student/dashboard');
        renderStudentDashboard(payload);
        studentMessage('studentDashboardMessage', '');
        showScreen('studentDashboardScreen');
    } catch (error) {
        studentMessage('studentLoginMessage', error.message, 'error');
        showScreen('studentLoginScreen');
    }
}

async function studentPdfBlob(url) {
    const response = await fetch(url, {cache: 'no-store', headers: telegramHeaders()});
    if (!response.ok) {
        const payload = await response.json().catch(() => ({}));
        throw new Error(payload.error || 'Файл пока недоступен');
    }
    return response.blob();
}

function setStudentPdf(frameId, stateKey, blob) {
    if (studentLearningState[stateKey]) URL.revokeObjectURL(studentLearningState[stateKey]);
    const url = URL.createObjectURL(blob);
    studentLearningState[stateKey] = url;
    document.getElementById(frameId).src = url;
}

function syncStudentLessonControls() {
    const lesson = studentLearningState.dashboard?.lesson;
    const hasLesson = Boolean(lesson?.hasNotes);
    document.getElementById('studentLessonFrame').hidden = !hasLesson;
    document.getElementById('studentLessonEmpty').hidden = hasLesson;
    document.getElementById('studentReadButton').hidden = !hasLesson || lesson.testUnlocked;
    const testButton = document.getElementById('studentTestButton');
    testButton.hidden = !hasLesson || !lesson.testReady;
    testButton.disabled = !lesson.testUnlocked;
    testButton.textContent = lesson.testCompleted ? 'Пройти тест ещё раз' : 'Пройти тест';
}

async function openStudentLesson() {
    let lesson = studentLearningState.dashboard?.lesson;
    showScreen('studentLessonScreen');
    studentMessage('studentLessonMessage', '');
    if (!lesson) {
        syncStudentLessonControls();
        return;
    }
    document.getElementById('studentLessonTitle').textContent = lesson.title;
    try {
        const payload = await studentRequest(`/api/student/lessons/${lesson.id}/open`, {method: 'POST'});
        renderStudentDashboard(payload);
        lesson = payload.lesson;
        const blob = await studentPdfBlob(`/api/student/lessons/${lesson.id}/notes`);
        setStudentPdf('studentLessonFrame', 'lessonUrl', blob);
        syncStudentLessonControls();
        clearTimeout(studentLearningState.unlockTimer);
        if (!lesson.testUnlocked) {
            studentLearningState.unlockTimer = setTimeout(async () => {
                try {
                    const fresh = await studentRequest('/api/student/dashboard');
                    renderStudentDashboard(fresh);
                    syncStudentLessonControls();
                } catch (_) {}
            }, 10 * 60 * 1000 + 1000);
        }
    } catch (error) {
        studentMessage('studentLessonMessage', error.message, 'error');
    }
}

async function confirmStudentLessonRead() {
    const lesson = studentLearningState.dashboard?.lesson;
    if (!lesson) return;
    try {
        const payload = await studentRequest(`/api/student/lessons/${lesson.id}/read`, {method: 'POST'});
        renderStudentDashboard(payload);
        syncStudentLessonControls();
        studentMessage('studentLessonMessage', 'Тест открыт. Он проверит понимание темы на новых примерах.', 'success');
    } catch (error) {
        studentMessage('studentLessonMessage', error.message, 'error');
    }
}

async function openStudentTest() {
    const lesson = studentLearningState.dashboard?.lesson;
    if (!lesson) return;
    studentMessage('studentTestResult', 'Загружаем тест…');
    showScreen('studentTestScreen');
    try {
        const test = await studentRequest(`/api/student/lessons/${lesson.id}/test`);
        document.getElementById('studentTestTitle').textContent = test.title;
        if (!test.questions.length) throw new Error('В этом уроке пока нет вопросов');
        studentLearningState.testRun = {
            questions: test.questions,
            index: 0,
            answers: Array(test.questions.length).fill(null),
            checking: false,
        };
        renderStudentTestQuestion();
        studentMessage('studentTestResult', '');
    } catch (error) {
        studentMessage('studentTestResult', error.message, 'error');
    }
}

function renderStudentTestQuestion() {
    const run = studentLearningState.testRun;
    if (!run) return;
    const question = run.questions[run.index];
    const form = document.getElementById('studentTestForm');
    form.replaceChildren();

    const progress = document.createElement('p');
    progress.className = 'student-test-progress';
    progress.textContent = `Вопрос ${run.index + 1} из ${run.questions.length}`;
    form.appendChild(progress);

    const card = document.createElement('section');
    card.className = 'student-test-question';
    const title = document.createElement('strong');
    title.textContent = question.question;
    card.appendChild(title);
    question.options.forEach((option, optionIndex) => {
        const label = document.createElement('label');
        label.className = 'student-test-option';
        const input = document.createElement('input');
        input.type = 'radio';
        input.name = 'studentCurrentAnswer';
        input.value = String(optionIndex);
        input.required = true;
        const text = document.createElement('span');
        text.textContent = option;
        label.append(input, text);
        card.appendChild(label);
    });
    form.appendChild(card);

    const submit = document.createElement('button');
    submit.type = 'submit';
    submit.className = 'btn';
    submit.textContent = 'Проверить ответ';
    form.appendChild(submit);
    studentMessage('studentTestResult', '');
}

async function submitStudentTest(event) {
    event.preventDefault();
    const lesson = studentLearningState.dashboard?.lesson;
    const run = studentLearningState.testRun;
    if (!lesson || !run || run.checking) return;
    const selected = new FormData(event.currentTarget).get('studentCurrentAnswer');
    if (selected === null) {
        studentMessage('studentTestResult', 'Выберите один вариант ответа.', 'error');
        return;
    }
    const answer = Number(selected);
    run.checking = true;
    try {
        const result = await studentRequest(`/api/student/lessons/${lesson.id}/test/check`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({questionIndex: run.index, answer}),
        });
        run.answers[run.index] = answer;
        event.currentTarget.querySelectorAll('input').forEach((input) => { input.disabled = true; });
        event.currentTarget.querySelector('button[type="submit"]')?.remove();

        const feedback = document.createElement('div');
        feedback.className = `student-test-feedback ${result.correct ? 'is-correct' : 'is-wrong'}`;
        if (result.correct) {
            feedback.textContent = '✓ Верно!';
        } else {
            const question = run.questions[run.index];
            const labels = ['А', 'Б', 'В', 'Г'];
            const correctOption = question.options[result.correctIndex] || '';
            feedback.textContent = (
                `Неверно. Правильный ответ: ${labels[result.correctIndex] || result.correctIndex + 1}) ${correctOption}\n\n`
                + (result.explanation || 'Пояснение к этому вопросу не добавлено.')
            );
        }
        event.currentTarget.appendChild(feedback);

        const next = document.createElement('button');
        next.type = 'button';
        next.className = 'btn';
        next.textContent = run.index + 1 < run.questions.length ? 'Следующий вопрос' : 'Завершить тест';
        next.addEventListener('click', advanceStudentTest);
        event.currentTarget.appendChild(next);
    } catch (error) {
        studentMessage('studentTestResult', error.message, 'error');
    } finally {
        run.checking = false;
    }
}

async function advanceStudentTest(event) {
    const lesson = studentLearningState.dashboard?.lesson;
    const run = studentLearningState.testRun;
    if (!lesson || !run || run.checking) return;
    if (run.index + 1 < run.questions.length) {
        run.index += 1;
        renderStudentTestQuestion();
        return;
    }
    run.checking = true;
    event.currentTarget.disabled = true;
    try {
        const result = await studentRequest(`/api/student/lessons/${lesson.id}/test`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({answers: run.answers}),
        });
        document.getElementById('studentTestForm').replaceChildren();
        studentMessage(
            'studentTestResult',
            `Результат: ${result.score} из ${result.total}. Результат сохранён в кабинете.`,
            result.score === result.total ? 'success' : 'info',
        );
        const fresh = await studentRequest('/api/student/dashboard');
        renderStudentDashboard(fresh);
    } catch (error) {
        event.currentTarget.disabled = false;
        studentMessage('studentTestResult', error.message, 'error');
    } finally {
        run.checking = false;
    }
}

function openStudentHomework() {
    document.getElementById('studentHomeworkFiles').value = '';
    studentMessage('studentHomeworkMessage', '');
    showScreen('studentHomeworkScreen');
}

async function openStudentHomeworkFile() {
    const lesson = studentLearningState.dashboard?.lesson;
    if (!lesson?.hasHomework) {
        studentMessage('studentHomeworkMessage', 'Персональный файл ДЗ пока не готов.', 'error');
        return;
    }
    try {
        const blob = await studentPdfBlob(`/api/student/lessons/${lesson.id}/homework`);
        setStudentPdf('studentHomeworkFrame', 'homeworkUrl', blob);
        document.getElementById('studentHomeworkTitle').textContent = lesson.title;
        showScreen('studentHomeworkDocumentScreen');
    } catch (error) {
        studentMessage('studentHomeworkMessage', error.message, 'error');
    }
}

async function submitStudentHomework() {
    const lesson = studentLearningState.dashboard?.lesson;
    const input = document.getElementById('studentHomeworkFiles');
    if (!lesson || !input.files.length) {
        studentMessage('studentHomeworkMessage', 'Сначала выберите фотографии или PDF.', 'error');
        return;
    }
    const form = new FormData();
    form.append('lessonId', lesson.id);
    [...input.files].forEach((file) => form.append('files', file, file.name));
    studentMessage('studentHomeworkMessage', 'Загружаем файлы…');
    try {
        const result = await studentRequest('/api/student/homework', {method: 'POST', body: form});
        input.value = '';
        studentMessage('studentHomeworkMessage', `Готово: преподавателю отправлено файлов — ${result.files}.`, 'success');
    } catch (error) {
        studentMessage('studentHomeworkMessage', error.message, 'error');
    }
}

function openStudentTheory() {
    const student = studentLearningState.dashboard?.student;
    if (!student) return;
    currentClass = Number(student.grade);
    studentLearningState.theoryReturn = true;
    openTheory();
}

function returnFromTheory() {
    if (studentLearningState.theoryReturn) {
        studentLearningState.theoryReturn = false;
        showScreen('studentDashboardScreen');
    } else {
        showScreen(currentClass ? 'mainMenu' : 'classSelection');
    }
}

document.addEventListener('DOMContentLoaded', refreshStudentEntry);
