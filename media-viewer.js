(() => {
    const state = {
        page: 1,
        totalPages: 1,
        scale: 1,
        x: 0,
        y: 0,
        loadPage: null,
        requestToken: 0,
        pointers: new Map(),
        pinchDistance: 0,
        pinchScale: 1,
        telegramFullscreen: false,
    };

    const byId = (id) => document.getElementById(id);
    const clamp = (value, minimum, maximum) => Math.min(maximum, Math.max(minimum, value));

    function clampPosition() {
        const stage = byId('mediaViewerStage');
        const maxX = Math.max(0, stage.clientWidth * (state.scale - 1) / 2);
        const maxY = Math.max(0, stage.clientHeight * (state.scale - 1) / 2);
        state.x = clamp(state.x, -maxX, maxX);
        state.y = clamp(state.y, -maxY, maxY);
        if (state.scale <= 1) {
            state.x = 0;
            state.y = 0;
        }
    }

    function applyTransform() {
        clampPosition();
        byId('mediaViewerImage').style.transform = `translate3d(${state.x}px, ${state.y}px, 0) scale(${state.scale})`;
        byId('mediaViewerZoomValue').textContent = `${Math.round(state.scale * 100)}%`;
    }

    function resetTransform() {
        state.scale = 1;
        state.x = 0;
        state.y = 0;
        state.pointers.clear();
        state.pinchDistance = 0;
        applyTransform();
    }

    function updateControls() {
        byId('mediaViewerPrev').disabled = state.page <= 1;
        byId('mediaViewerNext').disabled = state.page >= state.totalPages;
        byId('mediaViewerPageIndicator').textContent = `${state.page} / ${state.totalPages}`;
        byId('mediaViewerPageControls').hidden = state.totalPages <= 1;
    }

    async function showPage(page) {
        if (!state.loadPage) return;
        const targetPage = clamp(Number(page) || 1, 1, state.totalPages);
        const token = ++state.requestToken;
        const loading = byId('mediaViewerLoading');
        const image = byId('mediaViewerImage');
        loading.hidden = false;
        loading.dataset.kind = 'loading';
        image.classList.add('is-loading');
        let failed = false;
        try {
            const source = await state.loadPage(targetPage);
            if (token !== state.requestToken) return;
            image.src = source;
            await image.decode().catch(() => {});
            if (token !== state.requestToken) return;
            state.page = targetPage;
            resetTransform();
            updateControls();
        } catch (error) {
            failed = true;
            if (token === state.requestToken) {
                loading.textContent = error.message || 'Не удалось открыть страницу';
                loading.dataset.kind = 'error';
            }
            return;
        } finally {
            if (token === state.requestToken) {
                loading.hidden = !failed;
                if (!failed) loading.textContent = 'Открываем страницу…';
                image.classList.remove('is-loading');
            }
        }
    }

    window.openMediaViewer = async function openMediaViewer(config = {}) {
        const overlay = byId('mediaViewer');
        state.page = clamp(Number(config.initialPage) || 1, 1, Math.max(1, Number(config.totalPages) || 1));
        state.totalPages = Math.max(1, Number(config.totalPages) || 1);
        state.loadPage = config.loadPage || (async () => config.src || '');
        byId('mediaViewerTitle').textContent = config.title || 'Просмотр';
        overlay.hidden = false;
        overlay.setAttribute('aria-hidden', 'false');
        document.body.classList.add('media-viewer-open');
        window.Telegram?.WebApp?.expand?.();
        try {
            if (typeof window.Telegram?.WebApp?.requestFullscreen === 'function') {
                window.Telegram.WebApp.requestFullscreen();
                state.telegramFullscreen = true;
            }
        } catch (_) {
            state.telegramFullscreen = false;
        }
        updateControls();
        await showPage(state.page);
    };

    window.closeMediaViewer = function closeMediaViewer() {
        state.requestToken += 1;
        byId('mediaViewer').hidden = true;
        byId('mediaViewer').setAttribute('aria-hidden', 'true');
        byId('mediaViewerImage').removeAttribute('src');
        document.body.classList.remove('media-viewer-open');
        if (state.telegramFullscreen) {
            try { window.Telegram?.WebApp?.exitFullscreen?.(); } catch (_) {}
        }
        state.telegramFullscreen = false;
        state.loadPage = null;
        resetTransform();
    };

    window.changeMediaViewerPage = (delta) => showPage(state.page + Number(delta || 0));
    window.changeMediaViewerZoom = (delta) => {
        state.scale = clamp(state.scale + Number(delta || 0), 1, 5);
        applyTransform();
    };

    const stage = byId('mediaViewerStage');
    stage.addEventListener('pointerdown', (event) => {
        event.preventDefault();
        stage.setPointerCapture?.(event.pointerId);
        state.pointers.set(event.pointerId, {x: event.clientX, y: event.clientY});
        if (state.pointers.size === 2) {
            const [first, second] = [...state.pointers.values()];
            state.pinchDistance = Math.hypot(second.x - first.x, second.y - first.y);
            state.pinchScale = state.scale;
        }
    });
    stage.addEventListener('pointermove', (event) => {
        if (!state.pointers.has(event.pointerId)) return;
        event.preventDefault();
        const previous = state.pointers.get(event.pointerId);
        state.pointers.set(event.pointerId, {x: event.clientX, y: event.clientY});
        if (state.pointers.size >= 2) {
            const [first, second] = [...state.pointers.values()];
            const distance = Math.hypot(second.x - first.x, second.y - first.y);
            if (state.pinchDistance > 0) state.scale = clamp(state.pinchScale * distance / state.pinchDistance, 1, 5);
        } else if (state.scale > 1) {
            state.x += event.clientX - previous.x;
            state.y += event.clientY - previous.y;
        }
        applyTransform();
    });
    const releasePointer = (event) => {
        state.pointers.delete(event.pointerId);
        state.pinchDistance = 0;
        state.pinchScale = state.scale;
    };
    stage.addEventListener('pointerup', releasePointer);
    stage.addEventListener('pointercancel', releasePointer);
    stage.addEventListener('wheel', (event) => {
        event.preventDefault();
        state.scale = clamp(state.scale + (event.deltaY < 0 ? 0.25 : -0.25), 1, 5);
        applyTransform();
    }, {passive: false});
    stage.addEventListener('dblclick', () => {
        state.scale = state.scale > 1 ? 1 : 2.5;
        applyTransform();
    });
    document.addEventListener('keydown', (event) => {
        if (event.key === 'Escape' && !byId('mediaViewer').hidden) window.closeMediaViewer();
        if (event.key === 'ArrowLeft' && !byId('mediaViewer').hidden) showPage(state.page - 1);
        if (event.key === 'ArrowRight' && !byId('mediaViewer').hidden) showPage(state.page + 1);
    });
})();
