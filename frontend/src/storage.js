// Browser storage (localStorage). Keeps the current session across refreshes and a short
// list of recent searches. Everything stays in this browser; the backend stores nothing.
// Every access is wrapped in try/catch because storage can be blocked (private mode etc.).

const SESSION_KEY = "matify.session.v2";
const HISTORY_KEY = "matify.history.v2";
const MAX_HISTORY = 12;

function read(key, fallback) {
  try {
    const raw = window.localStorage.getItem(key);
    return raw ? JSON.parse(raw) : fallback;
  } catch (_) {
    return fallback;
  }
}

function write(key, value) {
  try {
    window.localStorage.setItem(key, JSON.stringify(value));
  } catch (_) {
    /* storage full or blocked: app keeps working without it */
  }
}

export const loadSession = () => read(SESSION_KEY, null);
export const saveSession = (session) => write(SESSION_KEY, session);
export const clearSession = () => {
  try {
    window.localStorage.removeItem(SESSION_KEY);
  } catch (_) {}
};

export const loadHistory = () => read(HISTORY_KEY, []);

export function addToHistory(entry) {
  const list = loadHistory().filter((h) => h.id !== entry.id);
  list.unshift(entry);
  write(HISTORY_KEY, list.slice(0, MAX_HISTORY));
  return list.slice(0, MAX_HISTORY);
}

export function removeFromHistory(id) {
  const list = loadHistory().filter((h) => h.id !== id);
  write(HISTORY_KEY, list);
  return list;
}

export function clearHistory() {
  write(HISTORY_KEY, []);
  return [];
}
