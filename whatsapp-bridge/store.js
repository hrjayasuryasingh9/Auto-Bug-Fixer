const fs   = require('fs');
const path = require('path');

// Conversation history only — credentials now live in the server's .env.
const FILE = path.join(__dirname, 'history.json');
const MAX_HISTORY = 20; // keep last 20 messages (10 pairs) per user

let _store = {};
try {
  _store = JSON.parse(fs.readFileSync(FILE, 'utf8'));
} catch { /* first run */ }

function persist() {
  try {
    fs.writeFileSync(FILE, JSON.stringify(_store, null, 2), 'utf8');
  } catch (e) {
    console.error('[store] write failed:', e.message);
  }
}

function addHistory(phone, role, content) {
  if (!_store[phone]) _store[phone] = [];
  // Keep enough to retain full lists (commit/PR/issue ids) for "the Nth one" refs.
  _store[phone].push({ role, content: String(content).slice(0, 2000) });
  if (_store[phone].length > MAX_HISTORY) {
    _store[phone] = _store[phone].slice(_store[phone].length - MAX_HISTORY);
  }
  persist();
}

function getHistory(phone) {
  return _store[phone] || [];
}

module.exports = { addHistory, getHistory };
