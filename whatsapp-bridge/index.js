require('dotenv').config();
const { Client, LocalAuth } = require('whatsapp-web.js');
const qrcode = require('qrcode-terminal');
const axios  = require('axios');

const API_URL        = process.env.API_URL        || 'http://localhost:8000';
const ALLOWED_NUMBER = (process.env.ALLOWED_NUMBER || '').replace(/\D/g, '');

const { addHistory, getHistory } = require('./store');

// ── Per-phone processing lock ─────────────────────────────────────────────
// message_create fires for every sent message including the bot's own replies.
// Locking on the phone number is the simplest reliable guard.
const _processing = new Set();

async function send(msg, text) {
  await msg.reply(text);
}

// ── WhatsApp client ───────────────────────────────────────────────────────
const client = new Client({
  authStrategy: new LocalAuth({ dataPath: './.wwebjs_auth' }),
  puppeteer: {
    headless: true,
    args: ['--no-sandbox', '--disable-setuid-sandbox'],
  },
});

client.on('qr', (qr) => {
  console.log('\n📱  Scan this QR code with WhatsApp (Linked Devices → Link a Device):\n');
  qrcode.generate(qr, { small: true });
});

client.on('ready', () => {
  console.log('\n✅  WhatsApp connected! Waiting for messages...\n');
  console.log('    Tip: message yourself (Saved Messages) to test the bot.\n');
});

client.on('auth_failure', (msg) => console.error('❌  Auth failed:', msg));
client.on('disconnected', (reason) => console.log('⚠️   Disconnected:', reason));

// ── Message handler ───────────────────────────────────────────────────────
// Flow: message → classify intent (backend AI agent) → call intent-based endpoint.
client.on('message_create', async (msg) => {
  if (msg.fromMe) return;
  if (msg.isGroupMsg || msg.from === 'status@broadcast') return;

  const phone = msg.from.replace(/@\S+$/, '');

  if (ALLOWED_NUMBER && phone !== ALLOWED_NUMBER) {
    console.log(`🚫  Ignored message from unlisted number: ${phone}`);
    return;
  }

  if (_processing.has(phone)) return;

  const text = msg.body.trim();
  if (!text) return;

  _processing.add(phone);
  console.log(`📩  [${phone}] ${text.slice(0, 60)}`);

  try {
    await send(msg, '⏳ Checking...');
    addHistory(phone, 'user', text);
    const history = getHistory(phone);

    // Forward to the backend — it handles commands, repo selection, intent & routing.
    const res = await axios.post(
      `${API_URL}/api/message/`,
      { session_id: phone, message: text, history },
      { timeout: 60000 }
    );

    const replyText = res.data.reply || 'No response.';
    const data      = res.data.data;
    const costInr   = res.data.cost_inr;

    const formatted = formatForWhatsApp(replyText, data);
    addHistory(phone, 'assistant', formatted);
    const costSuffix = (costInr != null && costInr > 0)
      ? `\n\n💰 ₹${costInr < 0.0001 ? '<0.0001' : costInr.toFixed(4)}`
      : '';
    await send(msg, formatted + costSuffix);
    console.log(`📤  [${phone}] replied (intent: ${res.data.intent})`);

  } catch (err) {
    const errMsg = err.response?.data?.detail
      || (err.response?.data ? JSON.stringify(err.response.data) : null)
      || err.message
      || 'Unknown error';
    console.error(`❌  API error [${err.response?.status || 'no response'}]: ${errMsg}`);
    await send(msg, `❌ Error: ${errMsg}`);
  } finally {
    _processing.delete(phone);
  }
});

// ── WhatsApp formatters ───────────────────────────────────────────────────
function formatForWhatsApp(fallback, data) {
  if (!data || !data.type) return fallback;
  switch (data.type) {
    case 'pr_list':       return formatPRList(data);
    case 'issue_list':    return formatIssueList(data);
    case 'commit_list':   return formatCommitList(data);
    case 'pr_detail':     return formatPRDetail(data.item);
    case 'commit_detail': return formatCommitDetail(data.item);
    case 'issue_detail':  return formatIssueDetail(data.item);
    case 'repo_info':       return formatRepoInfo(data.item);
    case 'directory':       return formatDirectory(data);
    case 'file_content':    return formatFileContent(data);
    case 'file_suggestions':return formatFileSuggestions(data);
    case 'count':         return `*${data.label}*\n${data.count}`;
    case 'empty':         return data.message || fallback;
    default:              return fallback;
  }
}

function formatPRList(data) {
  const lines = [`*Open PRs — ${data.repo}* (${data.items.length})\n`];
  data.items.forEach(pr =>
    lines.push(`*#${pr.number}* ${pr.title}\n   👤 @${pr.author}\n   🔗 ${pr.url}`)
  );
  return lines.join('\n\n');
}

function formatIssueList(data) {
  const lines = [`*Open Issues — ${data.repo}* (${data.items.length})\n`];
  data.items.forEach(i =>
    lines.push(`*#${i.number}* ${i.title}\n   👤 @${i.author}\n   🔗 ${i.url}`)
  );
  return lines.join('\n\n');
}

function formatCommitList(data) {
  const lines = [`*Recent Commits — ${data.repo}*\n`];
  data.items.forEach(c =>
    lines.push(`\`${c.sha}\`  ${c.message}\n   👤 ${c.author}`)
  );
  return lines.join('\n\n');
}

function formatPRDetail(pr) {
  const status = pr.merged ? 'Merged ✅' : pr.draft ? 'Draft 📝' : pr.state === 'open' ? 'Open 🟢' : 'Closed 🔴';
  const lines  = [`*PR #${pr.number}: ${pr.title}*`, `Status: ${status}`, `Author: @${pr.author}`];
  if (pr.body) lines.push(`\n_${pr.body.slice(0, 300)}${pr.body.length > 300 ? '…' : ''}_`);
  lines.push(`\n🔗 ${pr.url}`);
  return lines.join('\n');
}

function formatCommitDetail(c) {
  const lines = [
    `*Commit \`${c.sha}\`*`,
    `👤 ${c.author}`,
    `📅 ${c.date ? new Date(c.date).toLocaleString() : ''}`,
    ``,
    `_${c.message}_`,
    ``,
    `📊 *+${c.additions}* additions  *-${c.deletions}* deletions  *${c.files.length}* file(s)`,
  ];
  if (c.files.length) {
    lines.push('\n*Files changed:*');
    c.files.forEach(f => lines.push(`  • \`${f.filename}\`  [${f.status}]  +${f.additions}/-${f.deletions}`));
  }
  lines.push(`\n🔗 ${c.url}`);
  return lines.join('\n');
}

function formatDirectory(data) {
  if (!data.files || data.files.length === 0) {
    return `📁 *${data.path}/* is empty.\n\n🔗 ${data.url}`;
  }
  const nameList = data.files.map(f => f.name).join(', ');
  const lines = [`📁 *${data.path}/* — ${data.files.length} item(s)\n${nameList}\n`];
  data.files.forEach(f => {
    const icon = f.type === 'dir' ? '📁' : '📄';
    const size = f.type === 'file' && f.size ? `  (${(f.size / 1024).toFixed(1)} KB)` : '';
    lines.push(`  ${icon} ${f.name}${size}`);
  });
  lines.push(`\n🔗 ${data.url}`);
  return lines.join('\n');
}

function formatFileContent(data) {
  const sizeKb = (data.size / 1024).toFixed(1);
  const ext = data.name.split('.').pop().toLowerCase();
  const lang = { js:'js', ts:'ts', py:'python', json:'json', md:'markdown', tsx:'tsx', jsx:'jsx', html:'html', css:'css', yaml:'yaml', yml:'yaml', sh:'bash' }[ext] || '';
  const lines = [`📄 *${data.name}*  (${sizeKb} KB)\n`];
  if (data.content) {
    const preview = data.content.slice(0, 800);
    lines.push(`\`\`\`${lang}\n${preview}${data.content.length > 800 ? '\n…[truncated]' : ''}\n\`\`\``);
  }
  lines.push(`\n🔗 ${data.url}`);
  return lines.join('\n');
}

function formatFileSuggestions(data) {
  const lines = [`🔍 *Found ${data.matches.length} result(s) for "${data.query}":*\n`];
  data.matches.slice(0, 8).forEach(m => {
    const icon = m.type === 'directory' ? '📁' : '📄';
    lines.push(`  ${icon} ${m.path}`);
  });
  lines.push('\nAsk about any specific one, e.g:');
  if (data.matches.length > 0) {
    lines.push(`  "Tell me about ${data.matches[0].path}"`);
  }
  return lines.join('\n');
}

function formatRepoInfo(r) {
  const lines = [
    `*${r.full_name}*  ${r.private ? '🔒 Private' : '🌐 Public'}`,
  ];
  if (r.description) lines.push(`_${r.description}_`);
  lines.push('');
  lines.push(`🔤 Language: ${r.language || 'Unknown'}`);
  lines.push(`⭐ Stars: ${r.stars}   🍴 Forks: ${r.forks}   🐛 Open issues: ${r.open_issues}`);
  lines.push(`🌿 Default branch: ${r.default_branch}`);
  if (r.license)              lines.push(`📄 License: ${r.license}`);
  if (r.topics && r.topics.length) lines.push(`🏷️  Topics: ${r.topics.join(', ')}`);
  if (r.pushed_at)            lines.push(`📅 Last push: ${new Date(r.pushed_at).toLocaleDateString()}`);
  if (r.readme_excerpt) {
    lines.push('');
    lines.push(`📖 *README:*\n${r.readme_excerpt.slice(0, 300)}${r.readme_excerpt.length > 300 ? '…' : ''}`);
  }
  if (r.top_files && r.top_files.length) {
    lines.push('');
    lines.push(`📁 *Top-level files:*\n  ${r.top_files.slice(0, 12).join('  •  ')}`);
  }
  lines.push('');
  lines.push(`🔗 ${r.url}`);
  return lines.join('\n');
}

function formatIssueDetail(issue) {
  const status = issue.state === 'open' ? 'Open 🟢' : 'Closed 🔴';
  const lines = [
    `*Issue #${issue.number}: ${issue.title}*`,
    `Status: ${status}  Author: @${issue.author}`,
  ];
  if (issue.labels?.length) {
    lines.push(`Labels: ${issue.labels.map(l => l.name).join(', ')}`);
  }
  if (issue.body) {
    lines.push(`\n_${issue.body.slice(0, 300)}${issue.body.length > 300 ? '…' : ''}_`);
  }
  if (issue.images?.length) {
    lines.push(`\n📷 *${issue.images.length} image(s) attached:*`);
    issue.images.slice(0, 3).forEach(url => lines.push(`  ${url}`));
  }
  if (issue.comments?.length) {
    lines.push(`\n💬 *${issue.comments_count} comment(s):*`);
    issue.comments.slice(0, 3).forEach(c =>
      lines.push(`  @${c.author}: ${c.body.slice(0, 130)}${c.body.length > 130 ? '…' : ''}`)
    );
  }
  lines.push(`\n🔗 ${issue.url}`);
  return lines.join('\n');
}

// ── Start ─────────────────────────────────────────────────────────────────
console.log('🚀  Starting WhatsApp bridge...');
console.log(`    API → ${API_URL}`);
client.initialize();
