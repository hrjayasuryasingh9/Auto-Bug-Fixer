require('dotenv').config();
const { App } = require('@slack/bolt');
const axios = require('axios');

const { addHistory, getHistory } = require('./store');

const API_URL = process.env.API_URL || ' http://127.0.0.1:8023';
// Optional: restrict the bot to a single Slack user id (e.g. U0123ABCD)
const ALLOWED_USER = (process.env.ALLOWED_USER || '').trim();

// Tokens (accept the lowercase names from .env, fall back to conventional names)
const BOT_TOKEN       = process.env.slack_oauth_token   || process.env.SLACK_BOT_TOKEN;
const APP_TOKEN       = process.env.slack_api_bot_key   || process.env.SLACK_APP_TOKEN;
const SIGNING_SECRET  = process.env.slack_signing_secret || process.env.SLACK_SIGNING_SECRET;

if (!BOT_TOKEN || !APP_TOKEN) {
  console.error('❌  Missing Slack tokens. Need slack_oauth_token (xoxb-) and slack_api_bot_key (xapp-) in .env');
  process.exit(1);
}

const app = new App({
  token: BOT_TOKEN,
  appToken: APP_TOKEN,
  signingSecret: SIGNING_SECRET,
  socketMode: true,
});

// ── Dedupe: Slack may redeliver an event; ignore ones we've already handled ──
const _seen = new Set();
function alreadyHandled(id) {
  if (!id) return false;
  if (_seen.has(id)) return true;
  _seen.add(id);
  if (_seen.size > 500) _seen.delete(_seen.values().next().value);
  return false;
}

// ── Per-channel serialization ────────────────────────────────────────────────
// Messages in the same channel share one history; processing them concurrently
// corrupts that history (a second message lands before the first reply is stored),
// which mis-classifies intent. Chain tasks per channel so they run one at a time.
const _queues = new Map();
function enqueue(channel, task) {
  const prev = _queues.get(channel) || Promise.resolve();
  const next = prev.then(task, task);          // run regardless of prior outcome
  _queues.set(channel, next.catch(() => {}));  // never let the chain reject
  return next;
}

// ── Core: forward the message to the backend; render the reply ───────────────
// All logic (commands, active-repo selection, intent, routing) lives server-side.
// `meta`   = { workspace, channel, thread, user } — the production context scope.
// `target` = { channel, thread_ts, user, mention } — where/how to post the reply.
async function handleQuery(meta, text, client, target) {
  text = (text || '').trim();
  if (!text) return;

  if (ALLOWED_USER && meta.user && meta.user !== ALLOWED_USER) {
    console.log(`🚫  Ignored message from unlisted user: ${meta.user}`);
    return;
  }

  // Local history key mirrors the backend's context scope so each user keeps
  // their own thread/conversation even when several people share one channel.
  const key = `${meta.workspace}:${meta.channel}:${meta.thread}:${meta.user}`;
  const tag = target.mention ? `<@${target.user}> ` : '';
  console.log(`📩  [${key}] ${text.slice(0, 60)}`);
  const history = getHistory(key);   // prior turns only (not the current message)
  addHistory(key, 'user', text);

  // Live loader: post a placeholder, then stream REAL progress events onto it.
  let statusTs = null;
  try {
    statusTs = (await client.chat.postMessage({ channel: target.channel, text: `${tag}💭 _Thinking…_` })).ts;
  } catch (e) {
    console.error('⚠️  loader post failed:', e.data?.error || e.message);
  }

  let result;
  try {
    result = await streamProgress(client, target.channel, statusTs, tag, `${API_URL}/api/message/stream`, {
      message: text,
      history,
      workspace_id: meta.workspace,
      channel_id:   meta.channel,
      thread_id:    meta.thread,
      user_id:      meta.user,
    });
  } catch (err) {
    const errMsg = err.message || 'Unknown error';
    console.error(`❌  stream error: ${errMsg}`);
    const txt = `${tag}:x: Error: ${errMsg}`;
    if (statusTs) { try { await client.chat.update({ channel: target.channel, ts: statusTs, text: txt }); } catch { await client.chat.postMessage({ channel: target.channel, text: txt }); } }
    else { await client.chat.postMessage({ channel: target.channel, text: txt }); }
    return;
  }

  result = result || { reply: 'No response.' };
  const data = result.data;

  // "fix issue N" / "fix this issue" → continue on the SAME loader into the fix steps.
  if (data && data.type === 'fix_issue') {
    await runFix(client, target.channel, target.mention ? target.user : null, data.owner, data.repo, data.issue_number, statusTs);
    console.log(`📤  [${key}] triggered fix for #${data.issue_number}`);
    return;
  }

  const formatted = formatForSlack(result.reply || 'No response.', data);
  addHistory(key, 'assistant', formatted);
  const costInr = result.cost_inr;
  const costSuffix = (costInr != null && costInr > 0)
    ? `\n\n💰 ₹${costInr < 0.0001 ? '<0.0001' : costInr.toFixed(4)}`
    : '';
  await renderFinal(client, target.channel, statusTs, `${tag}\n${formatted}${costSuffix}`, imagesFromData(data), actionsFromData(data));
  console.log(`📤  [${key}] replied (intent: ${result.intent})`);
}

// Replace the live loader with the final answer (update in place for plain text;
// delete+repost when we need image/button blocks).
async function renderFinal(client, channel, statusTs, body, images = [], actions = null) {
  if (images.length || actions) {
    if (statusTs) { try { await client.chat.delete({ channel, ts: statusTs }); } catch { /* ignore */ } }
    try {
      const blocks = [{ type: 'section', text: { type: 'mrkdwn', text: body.slice(0, 2900) } }];
      images.slice(0, 5).forEach((url) => blocks.push({ type: 'image', image_url: url, alt_text: 'attached image' }));
      if (actions) blocks.push(actions);
      await client.chat.postMessage({ channel, text: body, blocks });
      return;
    } catch (e) {
      console.error('⚠️  blocks failed, posting text:', e.data?.error || e.message);
      if (images.length) body = `${body}\n\n${images.map((u) => `📷 ${u}`).join('\n')}`;
    }
    await client.chat.postMessage({ channel, text: body });
    return;
  }
  if (statusTs) { try { await client.chat.update({ channel, ts: statusTs, text: body }); return; } catch { /* fall through */ } }
  await client.chat.postMessage({ channel, text: body });
}

function metaFrom(e) {
  return {
    workspace: e.team || '',
    channel:   e.channel || '',
    thread:    e.thread_ts || '',   // '' when not in a thread → channel-level context
    user:      e.user || '',
  };
}

// ── Direct messages to the bot ───────────────────────────────────────────────
app.message(async ({ message, client }) => {
  if (message.subtype || message.bot_id) return;       // ignore edits / bot posts
  if (message.channel_type !== 'im') return;            // DMs only (mentions handled below)
  if (alreadyHandled(message.client_msg_id || message.ts)) return;
  const meta = metaFrom(message);
  // DM is 1:1 — post in the DM, no self-mention needed.
  const target = { channel: message.channel, user: message.user, mention: false };
  enqueue(`${meta.channel}:${meta.user}`, () => handleQuery(meta, message.text, client, target));
});

// ── @mentions in channels ────────────────────────────────────────────────────
app.event('app_mention', async ({ event, client }) => {
  if (event.bot_id) return;
  if (alreadyHandled(event.client_msg_id || event.ts)) return;
  const meta = metaFrom(event);
  const text = (event.text || '').replace(/<@[^>]+>/g, '').trim();  // strip the bot mention
  // Post as a top-level channel message that @mentions the asker so it's clearly theirs.
  const target = { channel: event.channel, user: event.user, mention: true };
  enqueue(`${meta.channel}:${meta.user}`, () => handleQuery(meta, text, client, target));
});

// ── Autonomous issue→PR agent — shared by the button and "fix issue N" text ──
const _SPINNER = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏'];

function _inr(c) {
  return (c != null && c > 0) ? `\n\n💰 ₹${c < 0.0001 ? '<0.0001' : c.toFixed(4)}` : '';
}

// Shared SSE consumer: streams REAL backend events onto `statusTs` as a growing
// checklist (in-progress step shows a spinner + live elapsed time). Returns the
// final `result` from the {stage:"done", result} event.
async function streamProgress(client, channel, statusTs, tag, url, body, title = null) {
  const done = [];            // completed step labels (real events)
  let current = null;         // { stage, message }
  let stepStart = Date.now(), spin = 0, rendering = false, result = null;
  const header = title ? `*${title}*\n` : '';

  const render = async () => {
    if (!statusTs || rendering) return;
    rendering = true;
    const lines = done.map((l) => `✓ ${l}`);
    if (current) {
      const s = _SPINNER[spin % _SPINNER.length];
      const el = Math.round((Date.now() - stepStart) / 1000);
      lines.push(`${s} ${current.message}…  _(${el}s)_`);
    }
    try { await client.chat.update({ channel, ts: statusTs, text: `${tag}${header}${lines.join('\n')}` }); }
    catch { /* ignore transient update errors */ }
    rendering = false;
  };

  // Tick the elapsed/spinner of the CURRENT real step (keeps long steps alive
  // without faking progress — phases only advance on real backend events).
  const timer = setInterval(() => { spin += 1; render(); }, 1500);

  const onEvent = (ev) => {
    if (ev.stage === 'done') { result = ev.result; return; }
    if (current && current.stage !== ev.stage) done.push(current.message);
    current = { stage: ev.stage, message: ev.message };
    stepStart = Date.now();
    spin = 0;
    render();
  };

  try {
    const res = await axios.post(url, body, { responseType: 'stream', timeout: 600000 });
    await new Promise((resolve, reject) => {
      let buf = '';
      res.data.on('data', (chunk) => {
        buf += chunk.toString('utf8');
        let i;
        while ((i = buf.indexOf('\n\n')) >= 0) {
          const block = buf.slice(0, i);
          buf = buf.slice(i + 2);
          const dl = block.split('\n').find((l) => l.startsWith('data:'));
          if (!dl) continue;
          try { onEvent(JSON.parse(dl.replace(/^data:\s*/, ''))); } catch { /* ignore */ }
        }
      });
      res.data.on('end', resolve);
      res.data.on('error', reject);
    });
  } finally {
    clearInterval(timer);
  }
  return result;
}

// Autonomous issue→PR agent — shared by the button and the "fix issue N" text path.
// Reuses an existing loader message (`statusTs`) when continuing from a query.
async function runFix(client, channel, user, owner, repo, issue_number, statusTs = null) {
  const tag = user ? `<@${user}> ` : '';
  console.log(`🛠  fix_issue: ${owner}/${repo}#${issue_number}`);

  if (!statusTs) {
    try { statusTs = (await client.chat.postMessage({ channel, text: `${tag}🛠 Starting a fix for issue #${issue_number}…` })).ts; }
    catch { /* ignore */ }
  }

  let result;
  try {
    result = await streamProgress(client, channel, statusTs, tag, `${API_URL}/api/fix-issue/stream`,
      { owner, repo, issue_number }, `Fixing issue #${issue_number}`);
  } catch (e) {
    const msg = e.message || 'connection error';
    const txt = `${tag}❌ Fix failed for issue #${issue_number}: ${msg}`;
    if (statusTs) { try { await client.chat.update({ channel, ts: statusTs, text: txt }); } catch { await client.chat.postMessage({ channel, text: txt }); } }
    else { await client.chat.postMessage({ channel, text: txt }); }
    return;
  }

  const d = result || { success: false, error: 'no result from server' };
  const cost = _inr(d.cost_inr);
  let txt;
  if (d.success) {
    const files = (d.files || []).map((f) => `\`${f}\``).join(', ');
    txt = `${tag}✅ Opened a draft PR for issue #${issue_number}:\n${d.pr_url}\n\n` +
      `*What I did:* ${d.summary || ''}` + (files ? `\n*Files:* ${files}` : '') + cost;
  } else {
    txt = `${tag}❌ Couldn't auto-fix issue #${issue_number}: ${d.error || 'unknown error'}${cost}`;
  }
  if (statusTs) { try { await client.chat.update({ channel, ts: statusTs, text: txt }); return; } catch { /* fall through */ } }
  await client.chat.postMessage({ channel, text: txt });
}

// "Fix this issue" button
app.action('fix_issue', async ({ ack, body, action, client }) => {
  await ack();
  let p;
  try { p = JSON.parse(action.value); } catch { return; }
  await runFix(client, body.channel?.id, body.user?.id, p.owner, p.repo, p.issue_number);
});

// ── Issue/PR lifecycle buttons (close, delete, merge) ────────────────────────
// Shared driver: post a working message, hit the backend action endpoint, then
// update the message with the outcome (`render` maps the response → final text).
async function runAction(client, channel, user, working, url, payload, render) {
  const tag = user ? `<@${user}> ` : '';
  let statusTs = null;
  try { statusTs = (await client.chat.postMessage({ channel, text: `${tag}${working}` })).ts; }
  catch { /* ignore */ }

  let data;
  try {
    data = (await axios.post(url, payload, { timeout: 60000 })).data;
  } catch (e) {
    data = { success: false, error: e.response?.data?.error || e.message };
  }

  const txt = `${tag}${render(data)}`;
  if (statusTs) { try { await client.chat.update({ channel, ts: statusTs, text: txt }); return; } catch { /* fall through */ } }
  await client.chat.postMessage({ channel, text: txt });
}

// "Mark as fixed" → close the issue
app.action('mark_fixed', async ({ ack, body, action, client }) => {
  await ack();
  let p; try { p = JSON.parse(action.value); } catch { return; }
  await runAction(client, body.channel?.id, body.user?.id,
    `✅ Marking issue #${p.issue_number} as fixed…`,
    `${API_URL}/api/actions/issue/close`, p,
    (d) => d.success
      ? `✅ Issue #${p.issue_number} marked as fixed (closed).`
      : `❌ Couldn't mark issue #${p.issue_number} as fixed: ${d.error || 'unknown error'}`);
});

// "Delete issue" → permanently delete the issue
app.action('delete_issue', async ({ ack, body, action, client }) => {
  await ack();
  let p; try { p = JSON.parse(action.value); } catch { return; }
  await runAction(client, body.channel?.id, body.user?.id,
    `🗑 Deleting issue #${p.issue_number}…`,
    `${API_URL}/api/actions/issue/delete`, p,
    (d) => d.success
      ? `🗑 Issue #${p.issue_number} deleted.`
      : `❌ Couldn't delete issue #${p.issue_number}: ${d.error || 'unknown error'}`);
});

// "Merge with main" → merge the PR
app.action('merge_pr', async ({ ack, body, action, client }) => {
  await ack();
  let p; try { p = JSON.parse(action.value); } catch { return; }
  await runAction(client, body.channel?.id, body.user?.id,
    `🔀 Merging PR #${p.pr_number} into main…`,
    `${API_URL}/api/actions/pr/merge`, p,
    (d) => d.success
      ? `🔀 PR #${p.pr_number} merged into main. ✅`
      : `❌ Couldn't merge PR #${p.pr_number}: ${d.message || d.error || 'not mergeable'}`);
});

// "Delete PR" → close the PR and delete its branch
app.action('delete_pr', async ({ ack, body, action, client }) => {
  await ack();
  let p; try { p = JSON.parse(action.value); } catch { return; }
  await runAction(client, body.channel?.id, body.user?.id,
    `🗑 Deleting PR #${p.pr_number}…`,
    `${API_URL}/api/actions/pr/close`, p,
    (d) => d.success
      ? `🗑 PR #${p.pr_number} closed${d.branch_deleted ? ` and branch \`${d.branch}\` deleted` : ''}.`
      : `❌ Couldn't delete PR #${p.pr_number}: ${d.error || 'unknown error'}`);
});

app.error(async (error) => {
  console.error('⚠️  Bolt error:', error?.message || error);
});

// Public image URLs the backend resolved (issue/PR screenshots, etc.)
function imagesFromData(data) {
  const item = (data && data.item) || {};
  const imgs = item.images || [];
  return Array.isArray(imgs) ? imgs.filter((u) => typeof u === 'string' && /^https?:\/\//.test(u)) : [];
}

// Interactive buttons for a detail view.
//  • issue_detail → Fix this issue / Mark as fixed / Delete issue
//  • pr_detail    → Merge with main (only when no conflicts) / Delete PR
function actionsFromData(data) {
  if (!data) return null;
  const it = data.item || {};

  if (data.type === 'issue_detail') {
    if (!it.owner || !it.repo || !it.number) return null;
    if (it.state && it.state !== 'open') return null;   // closed issue → no actions
    const value = JSON.stringify({ owner: it.owner, repo: it.repo, issue_number: it.number });
    return {
      type: 'actions',
      elements: [
        { type: 'button', text: { type: 'plain_text', text: '🛠 Fix this issue', emoji: true }, action_id: 'fix_issue',   style: 'primary', value },
        { type: 'button', text: { type: 'plain_text', text: '✅ Mark as fixed',  emoji: true }, action_id: 'mark_fixed',  value },
        { type: 'button', text: { type: 'plain_text', text: '🗑 Delete issue',   emoji: true }, action_id: 'delete_issue', style: 'danger', value },
      ],
    };
  }

  if (data.type === 'pr_detail') {
    if (!it.owner || !it.repo || !it.number) return null;
    if (it.state !== 'open' || it.merged) return null;  // only open, un-merged PRs are actionable
    const value = JSON.stringify({ owner: it.owner, repo: it.repo, pr_number: it.number });
    const elements = [];
    // mergeable: true = clean, false = conflicts, null = GitHub still computing → stay optimistic
    // (the backend merge call refuses gracefully if it turns out unmergeable).
    if (it.mergeable !== false) {
      elements.push({ type: 'button', text: { type: 'plain_text', text: '🔀 Merge with main', emoji: true }, action_id: 'merge_pr', style: 'primary', value });
    }
    elements.push({ type: 'button', text: { type: 'plain_text', text: '🗑 Delete PR', emoji: true }, action_id: 'delete_pr', style: 'danger', value });
    return { type: 'actions', elements };
  }

  return null;
}

// ── Slack mrkdwn formatters ──────────────────────────────────────────────────
// Slack mrkdwn matches WhatsApp closely: *bold*, _italic_, `code`, ```blocks```.
// Bare URLs auto-link, so the 🔗 lines render fine.
function formatForSlack(fallback, data) {
  if (!data || !data.type) return fallback;
  switch (data.type) {
    case 'pr_list':         return formatPRList(data);
    case 'issue_list':      return formatIssueList(data);
    case 'commit_list':     return formatCommitList(data);
    case 'pr_detail':       return formatPRDetail(data.item);
    case 'commit_detail':   return formatCommitDetail(data.item);
    case 'issue_detail':    return formatIssueDetail(data.item);
    case 'repo_info':       return formatRepoInfo(data.item);
    case 'directory':       return formatDirectory(data);
    case 'file_content':    return formatFileContent(data);
    case 'file_suggestions':return formatFileSuggestions(data);
    case 'count':           return `*${data.label}*\n${data.count}`;
    case 'empty':           return data.message || fallback;
    default:                return fallback;
  }
}

function formatPRList(data) {
  const lines = [`*Open PRs — ${data.repo}* (${data.items.length})\n`];
  data.items.forEach(pr =>
    lines.push(`*#${pr.number}* ${pr.title}\n   👤 ${pr.author}\n   🔗 ${pr.url}`)
  );
  return lines.join('\n\n');
}

function formatIssueList(data) {
  const lines = [`*Open Issues — ${data.repo}* (${data.items.length})\n`];
  data.items.forEach(i =>
    lines.push(`*#${i.number}* ${i.title}\n   👤 ${i.author}\n   🔗 ${i.url}`)
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
  const lines  = [`*PR #${pr.number}: ${pr.title}*`, `Status: ${status}`, `Author: ${pr.author}`];
  if (pr.state === 'open' && !pr.merged) {
    const mergeNote = pr.mergeable === false ? 'Has conflicts ⚠️' : pr.mergeable === true ? 'No conflicts — ready to merge ✅' : 'Mergeability: checking…';
    lines.push(mergeNote);
  }
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
  const lines = [`📄 *${data.name}*  (${sizeKb} KB)\n`];
  if (data.content) {
    const preview = data.content.slice(0, 800);
    lines.push(`\`\`\`\n${preview}${data.content.length > 800 ? '\n…[truncated]' : ''}\n\`\`\``);
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
  const lines = [`*${r.full_name}*  ${r.private ? '🔒 Private' : '🌐 Public'}`];
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
    `Status: ${status}  Author: ${issue.author}`,
  ];
  if (issue.labels?.length) {
    lines.push(`Labels: ${issue.labels.map(l => l.name).join(', ')}`);
  }
  if (issue.body) {
    lines.push(`\n_${issue.body.slice(0, 300)}${issue.body.length > 300 ? '…' : ''}_`);
  }
  // Images are rendered as image blocks (below) — no text/link listing here.
  if (issue.comments?.length) {
    lines.push(`\n💬 *${issue.comments_count} comment(s):*`);
    issue.comments.slice(0, 3).forEach(c =>
      lines.push(`  ${c.author}: ${c.body.slice(0, 130)}${c.body.length > 130 ? '…' : ''}`)
    );
  }
  lines.push(`\n🔗 ${issue.url}`);
  return lines.join('\n');
}

// ── Start ────────────────────────────────────────────────────────────────────
(async () => {
  await app.start();
  console.log('🚀  Slack bridge running (Socket Mode)');
  console.log(`    API → ${API_URL}`);
  console.log('    DM the bot or @mention it in a channel it has been added to.');
})();
