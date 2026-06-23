const fs   = require('fs');
const path = require('path');

// Conversation history only — repo selection + everything else lives server-side.
const FILE = path.join(__dirname, 'history.json');
const MAX_HISTORY = 20; // keep last 20 messages (10 pairs) per channel

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

function addHistory(key, role, content) {
  if (!_store[key]) _store[key] = [];
  // Keep enough to retain full lists (commit/PR/issue ids) for "the Nth one" refs.
  _store[key].push({ role, content: String(content).slice(0, 2000) });
  if (_store[key].length > MAX_HISTORY) {
    _store[key] = _store[key].slice(_store[key].length - MAX_HISTORY);
  }
  persist();
}

function getHistory(key) {
  return _store[key] || [];
}

module.exports = { addHistory, getHistory };
