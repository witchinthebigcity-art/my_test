// DOM-unit tests only: no browser, network, real Telegram credentials or profiles.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

class Element {
    constructor() {
        this.children = []; this.events = {}; this.style = {}; this.hidden = false;
        this.classList = {add() {}, remove() {}, toggle() {}, contains() { return false; }};
    }
    append(...children) { this.children.push(...children); }
    appendChild(child) { this.children.push(child); return child; }
    replaceChildren(...children) { this.children = children; }
    addEventListener(name, fn) { this.events[name] = fn; }
    setAttribute(name, value) { this[name] = value; }
    removeAttribute(name) { delete this[name]; }
}
const elements = new Map();
const document = {
    addEventListener() {},
    createElement: () => new Element(),
    getElementById: (id) => {
        if (!elements.has(id)) elements.set(id, new Element());
        return elements.get(id);
    },
};
let request;
const context = vm.createContext({
    document, window: {addEventListener() {}}, console,
    tg: {initData: 'synthetic-session'},
    fetch: async (url, options) => {
        request = {url, options};
        return {ok: true, json: async () => ({ok: true})};
    },
});
vm.runInContext(fs.readFileSync(path.join(__dirname, '..', 'community.js'), 'utf8'), context);
const allText = (el) => [el.textContent || '', ...el.children.map(allText)].join(' ');

(async () => {
    await context.communityRequest('/api/leaderboard');
    assert.equal(request.options.headers['X-Telegram-Init-Data'], 'synthetic-session');
    await context.communityRequest('/api/profile', {method: 'POST', headers: {'Content-Type': 'application/json'}});
    assert.equal(request.options.headers['Content-Type'], 'application/json');
    assert.equal(request.options.headers['X-Telegram-Init-Data'], 'synthetic-session');

    const participant = {publicId: 'synthetic-id', nickname: 'Участник', grade: 8};
    context.renderFriends({friends: [{participant}], incoming: [{id: 'request-id', participant}]});
    assert.match(allText(elements.get('friendsList')), /Заблокировать/);
    assert.match(allText(elements.get('friendRequestsList')), /Принять.*Отклонить.*Заблокировать/);

    let unblocked;
    context.blockParticipant = (id, remove) => { unblocked = {id, remove}; };
    context.renderBlockedParticipants({entries: [participant]});
    const blocked = elements.get('blockedParticipantsList');
    assert.equal(elements.get('blockedParticipantsSection').hidden, false);
    blocked.children[0].children[1].events.click();
    assert.equal(unblocked.id, 'synthetic-id');
    assert.equal(unblocked.remove, true);
    context.renderBlockedParticipants({entries: []});
    assert.equal(elements.get('blockedParticipantsSection').hidden, true);

    context.renderParticipant({...participant, friendshipStatus: 'none', acceptsFriendRequests: false, awards: []});
    assert.doesNotMatch(allText(elements.get('participantActions')), /Добавить в друзья/);
    assert.match(allText(elements.get('participantActions')), /Заблокировать/);
    console.log('Privacy UI: 4 checks passed (auth headers, request actions, unblock, request preference).');
})().catch((error) => { console.error(error); process.exitCode = 1; });
