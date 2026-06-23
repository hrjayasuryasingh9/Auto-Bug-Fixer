# AI Autonomous Engineering Agent — Architecture & Implementation

> A WhatsApp-driven, multi-agent system that converts natural-language product requests into shipped code: issues created, branches cut, code written, PRs opened, reviewed, and merged — all autonomously, with humans in the loop only where it matters.

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [High-Level Architecture](#2-high-level-architecture)
3. [WhatsApp Integration Flow](#3-whatsapp-integration-flow)
4. [GitHub Issue Management](#4-github-issue-management)
5. [PR Creation & Merge Workflows](#5-pr-creation--merge-workflows)
6. [Multi-Agent Architecture](#6-multi-agent-architecture)
7. [Queue System](#7-queue-system)
8. [Repo Intelligence Layer](#8-repo-intelligence-layer)
9. [UI Analysis Engine](#9-ui-analysis-engine)
10. [Feature Implementation Workflows](#10-feature-implementation-workflows)
11. [Suggested Directory Structure](#11-suggested-directory-structure)
12. [Step-by-Step Implementation Phases](#12-step-by-step-implementation-phases)
13. [Recommended Tech Stack](#13-recommended-tech-stack)
14. [Future Scaling Ideas](#14-future-scaling-ideas)

---

## 1. System Overview

### What it does

A user sends a WhatsApp message like *"Add dark mode to the settings page"* or *"Fix the bug where login fails on Safari"*. The system:

1. Parses the intent.
2. Locates the relevant repo and code.
3. Creates a GitHub issue.
4. Spins up a coding agent that writes the implementation.
5. Opens a PR with the changes.
6. Runs CI, self-review, and (optionally) human review.
7. Merges the PR and reports back on WhatsApp with a link.

### Design principles

- **Async by default** — every long-running step goes through a queue.
- **Idempotent** — re-running any step produces the same result.
- **Observable** — every agent action is logged, traceable, and replayable.
- **Human-overrideable** — any step can be paused, reviewed, or rejected.
- **Repo-aware** — agents understand the codebase before changing it.

---

## 2. High-Level Architecture

```
┌─────────────┐      ┌──────────────┐      ┌─────────────────┐
│  WhatsApp   │─────▶│  Gateway API │─────▶│ Intent Parser   │
│   (User)    │◀─────│  (Webhook)   │      │  (LLM Router)   │
└─────────────┘      └──────────────┘      └────────┬────────┘
                                                    │
                                                    ▼
                                          ┌──────────────────┐
                                          │   Task Queue     │
                                          │  (BullMQ/Redis)  │
                                          └────────┬─────────┘
                                                   │
                          ┌────────────────────────┼────────────────────────┐
                          ▼                        ▼                        ▼
                 ┌────────────────┐      ┌────────────────┐       ┌────────────────┐
                 │ Planner Agent  │      │  Coder Agent   │       │ Reviewer Agent │
                 └────────┬───────┘      └────────┬───────┘       └────────┬───────┘
                          │                       │                        │
                          └───────────┬───────────┴────────────────────────┘
                                      ▼
                          ┌────────────────────────┐
                          │   Repo Intelligence    │
                          │  (Embeddings + Graph)  │
                          └───────────┬────────────┘
                                      ▼
                          ┌────────────────────────┐
                          │       GitHub API       │
                          │  (Issues + PRs + CI)   │
                          └────────────────────────┘
```

### Core components

| Component | Responsibility |
|---|---|
| **Gateway API** | Receives WhatsApp webhooks, authenticates users, enqueues tasks |
| **Intent Parser** | LLM-based classifier that maps messages to task types |
| **Task Queue** | Durable, retryable job queue for async work |
| **Agent Orchestrator** | Routes tasks to specialized agents and manages handoffs |
| **Repo Intelligence** | Maintains semantic + structural knowledge of each repo |
| **UI Analysis** | Vision-based component & layout understanding |
| **GitHub Adapter** | Wraps Octokit with retry, rate-limit, and audit logging |
| **Notifier** | Sends progress and results back to WhatsApp |

---

## 3. WhatsApp Integration Flow

### Provider options

- **WhatsApp Business Cloud API** (Meta, recommended for production)
- **Twilio API for WhatsApp** (faster setup, higher per-message cost)
- **Self-hosted via Baileys** (cheaper, riskier — ToS gray area)

### Inbound flow

1. User sends a message to the registered WhatsApp business number.
2. WhatsApp posts a webhook to `POST /webhooks/whatsapp`.
3. Gateway verifies the signature (`X-Hub-Signature-256`).
4. Message is normalized: `{ from, body, mediaUrls[], timestamp }`.
5. User is resolved against the `users` table (phone → account → allowed repos).
6. Message is enqueued onto the `intent.parse` queue.
7. Gateway returns `200 OK` within 5 seconds (WhatsApp's hard timeout).

### Outbound flow

- Agents emit `notify(userId, message)` events.
- A dedicated `notify-worker` debounces updates (max 1 message per 10s per user) so the user isn't spammed.
- Status updates use templates: `🛠️ Working on it…`, `✅ PR opened: <link>`, `❌ Failed: <reason>`.

### Message types supported

| Type | Example | Routed to |
|---|---|---|
| Feature request | *"Add a CSV export to the orders page"* | Planner → Coder |
| Bug report | *"Login button doesn't work on iOS"* | Triage → Coder |
| Screenshot + ask | *(image)* *"Make this look like the design"* | UI Analysis → Coder |
| Status query | *"Status of yesterday's tasks"* | Status agent |
| Approval | *"Approve PR 142"* | GitHub adapter |

---

## 4. GitHub Issue Management

### Issue lifecycle

```
created → triaged → planned → in-progress → in-review → merged
                                              └─────────→ rejected
```

### Automated issue creation

When a request enters the system, the Planner agent generates a structured issue:

```markdown
**Title:** Add CSV export to /orders page

**Origin:** WhatsApp (+91-XXXXX, 2026-05-25 10:14 IST)
**Confidence:** 0.92
**Repo:** acme/web-app
**Affected files (predicted):**
- src/pages/orders/index.tsx
- src/lib/export/csv.ts (new)

**Acceptance criteria:**
- [ ] Button labeled "Export CSV" visible to admin users
- [ ] CSV includes columns: id, customer, total, status, createdAt
- [ ] Download triggered client-side, no server round-trip
- [ ] Unit test covers empty + populated states

**Generated by:** ai-engineer-bot
```

### Labels applied automatically

- `ai-generated` — every AI-created issue
- `needs-human-review` — confidence < 0.75 or touches sensitive paths
- `area:<module>` — derived from repo intelligence
- `priority:<p1|p2|p3>` — inferred from user language ("urgent", "blocker")

### Sensitive path guard

Any change touching paths in `.ai-engineer.yml` `protected:` (e.g. `infra/`, `migrations/`, `auth/`) auto-applies `needs-human-review` and blocks auto-merge.

---

## 5. PR Creation & Merge Workflows

### Branch & PR naming

- Branch: `ai/<issue-number>-<short-slug>` (e.g. `ai/142-csv-export`)
- PR title: same as issue title
- PR body: links the issue, summarizes diff, lists test coverage

### Standard PR template

```markdown
Closes #142

## Summary
<one-paragraph description of what changed and why>

## Changes
- src/pages/orders/index.tsx — added export button + handler
- src/lib/export/csv.ts — new CSV serializer
- src/lib/export/csv.test.ts — unit tests

## Testing
- [x] Unit tests pass (`pnpm test`)
- [x] Type check passes (`pnpm typecheck`)
- [x] Lint passes (`pnpm lint`)
- [x] Manual smoke test against staging

## Risk
Low — additive change, no schema/auth/infra touched.

🤖 Generated by ai-engineer-bot
```

### Merge policy (configurable per-repo)

| Condition | Action |
|---|---|
| CI green + low-risk paths + confidence > 0.85 | Auto-merge (squash) |
| CI green + medium risk | Wait for human approval |
| CI red | Reviewer agent attempts fix (max 2 retries) |
| CI red after retries | Notify user, mark `needs-human-review` |
| Touches protected paths | Always require human approval |

### Conflict resolution

If `main` has moved while the PR was open, the Coder agent rebases automatically. If the rebase produces conflicts it can't resolve confidently, it leaves a comment and pings the user.

---

## 6. Multi-Agent Architecture

A single monolithic agent is brittle. The system uses **specialized agents** that communicate through a shared context store.

### Agents

| Agent | Role | Key tools |
|---|---|---|
| **Router** | Classifies incoming intent, picks downstream agent | Intent classifier, user permissions |
| **Planner** | Decomposes a feature into concrete file-level changes | Repo intel, code search |
| **Coder** | Writes the code, runs tests locally in sandbox | File I/O, sandboxed shell, test runner |
| **Reviewer** | Reads the diff, flags issues, suggests improvements | Static analysis, lint, AST tools |
| **UI Critic** | For visual changes, compares screenshots against intent | Vision model, headless browser |
| **Fixer** | Runs only when CI fails; reads logs and patches | CI logs, sandboxed shell |
| **Triage** | Reproduces bugs, isolates faulty commit via bisect | Git history, log search |
| **Status** | Answers user queries about in-flight work | DB read-only |

### Shared context

Every agent reads/writes a `TaskContext` object:

```ts
type TaskContext = {
  taskId: string;
  userId: string;
  repo: string;
  issueNumber?: number;
  prNumber?: number;
  branch?: string;
  history: AgentStep[];     // append-only audit log
  artifacts: {              // files, screenshots, logs
    [key: string]: string;
  };
  confidence: number;
  status: 'queued' | 'running' | 'blocked' | 'done' | 'failed';
};
```

### Handoff protocol

Agents don't call each other directly — they emit events to the queue. This keeps each agent stateless and independently scalable.

```
Planner → emits 'plan.ready' → Coder picks up
Coder   → emits 'code.ready' → Reviewer picks up
Reviewer→ emits 'review.ok'  → GitHub adapter opens PR
```

---

## 7. Queue System

### Why a queue

LLM calls are slow (5–60s). Builds and tests are slower (1–10m). The webhook must reply in 5s. A durable queue lets the system absorb spikes, retry failures, and run jobs in parallel.

### Queue topology (BullMQ + Redis)

| Queue | Concurrency | Notes |
|---|---|---|
| `intent.parse` | 20 | Cheap, LLM call only |
| `plan.create` | 10 | LLM + repo intel lookup |
| `code.write` | 4 | Heavy; sandboxed VM per job |
| `code.review` | 8 | Mostly static analysis |
| `pr.open` | 20 | Just GitHub API |
| `ci.watch` | 50 | Idle polling, very cheap |
| `notify.send` | 30 | WhatsApp send + retry |

### Retry policy

- Transient errors (network, 5xx): exponential backoff, 5 attempts.
- LLM-specific errors (rate limit, context overflow): retry with reduced context.
- Logical errors (test failure, conflict): hand off to Fixer; do not retry blindly.

### Job priorities

- `priority:p1` jobs (user said "urgent", "blocker", "production down") jump the queue.
- Status queries are always high-priority (user is waiting in chat).

---

## 8. Repo Intelligence Layer

The single biggest predictor of agent quality is **how well the agent understands the repo**. This layer pre-computes and maintains that understanding.

### Components

#### 8.1 Symbol graph

Built from tree-sitter ASTs. For every repo:

- Functions, classes, exports, imports
- Call graph (who calls whom)
- Type/interface graph
- File-to-file dependency map

Stored in **DuckDB** or **Postgres** with an adjacency table; refreshed on every push via webhook.

#### 8.2 Semantic embeddings

- Every function/file is chunked and embedded (`text-embedding-3-large` or local model).
- Stored in **pgvector** or **Qdrant**.
- Queried at plan time: *"find the 10 chunks most relevant to 'CSV export of orders'"*.

#### 8.3 Convention extractor

Parses the repo for patterns the agent must match:

- Test framework (`vitest` vs `jest` vs `pytest`)
- Component patterns (RSC vs client, hooks naming)
- Folder conventions (feature folders vs type folders)
- Lint/format config
- Commit-message style (Conventional Commits, etc.)

Result is cached as `repo-conventions.json` and prepended to every Coder prompt.

#### 8.4 Hot-path map

Tracks files most often edited together (from git history). Used to predict the *blast radius* of a change — e.g. editing `OrderList.tsx` historically requires touching `OrderList.test.tsx` and `orders.api.ts`.

#### 8.5 Indexing pipeline

```
push → webhook → enqueue index job
                 ↓
   parse AST → extract symbols → build graph
                 ↓
   chunk files → embed → upsert to vector store
                 ↓
   diff conventions → cache
```

Full re-index runs nightly; incremental updates run per-push.

---

## 9. UI Analysis Engine

For frontend changes, raw code understanding isn't enough — the agent must *see* the UI.

### Capabilities

| Capability | How |
|---|---|
| Read user-uploaded screenshots | GPT-4o / Claude vision model |
| Take screenshots of the running app | Playwright headless |
| Compare before/after visually | Pixelmatch + diff overlay |
| Identify components in a screenshot | Vision + DOM querying |
| Map design → existing component | Embedding similarity over component library |

### Visual review loop

1. User sends a Figma frame or screenshot.
2. UI Critic extracts: layout regions, typography, color palette, spacing, components.
3. Planner maps each region to either existing components or new ones to create.
4. After Coder finishes, a Playwright job renders the changed page.
5. UI Critic compares against the target; emits a `visual.match.score` (0–1).
6. If score < 0.85, Coder iterates (max 3 times) before escalating to human review.

### Component library awareness

The agent maintains an index of the design system (Storybook stories, Chromatic snapshots, or a hand-curated `components.json`). It prefers reusing over rebuilding.

---

## 10. Feature Implementation Workflows

### 10.1 New feature (greenfield within an existing repo)

1. Router → classifies as `feature.new`.
2. Planner generates: issue spec, file plan, test plan, risk assessment.
3. User confirms over WhatsApp (one tap).
4. Coder creates branch, scaffolds files, writes code + tests.
5. Reviewer runs lint/type/test/static analysis; sends issues back to Coder.
6. Once clean, PR is opened with full context.
7. CI runs; auto-merge if policy allows; otherwise wait for approval.
8. On merge, notify user with the deployed URL (if preview deploys exist).

### 10.2 Bug fix

1. Router → classifies as `bug`.
2. Triage agent attempts repro:
   - Searches logs/issue history for similar reports.
   - If a Sentry/Datadog integration exists, pulls the stack trace.
   - Runs `git bisect` against failing test (if test exists).
3. Coder writes a failing test that reproduces the bug.
4. Coder writes the fix; reviewer verifies the test now passes.
5. PR is opened with both the test and the fix.

### 10.3 Visual change from screenshot

1. Router → classifies as `ui.change`.
2. UI Critic extracts visual intent.
3. Planner picks affected files using component-name matching + repo intel.
4. Coder edits styles/markup.
5. Playwright renders; UI Critic scores match.
6. Iterate up to 3 times.
7. PR opened with before/after screenshots embedded in the description.

### 10.4 Refactor / chore

1. Router → classifies as `refactor`.
2. Planner produces a step-by-step migration plan (often multi-PR).
3. Each step opened as a separate PR for reviewability.
4. Each PR must keep the test suite green — no behavioral changes.

---

## 11. Suggested Directory Structure

```
ai-engineer/
├── apps/
│   ├── gateway/                  # Express/Fastify, receives webhooks
│   │   ├── src/
│   │   │   ├── routes/
│   │   │   │   ├── whatsapp.ts
│   │   │   │   └── github.ts
│   │   │   ├── auth/
│   │   │   └── server.ts
│   │   └── package.json
│   │
│   ├── orchestrator/             # Queue workers + agent runtime
│   │   ├── src/
│   │   │   ├── agents/
│   │   │   │   ├── router.ts
│   │   │   │   ├── planner.ts
│   │   │   │   ├── coder.ts
│   │   │   │   ├── reviewer.ts
│   │   │   │   ├── uiCritic.ts
│   │   │   │   ├── fixer.ts
│   │   │   │   ├── triage.ts
│   │   │   │   └── status.ts
│   │   │   ├── prompts/          # versioned prompt templates
│   │   │   ├── tools/            # tool functions agents can call
│   │   │   ├── queue/
│   │   │   └── runtime/
│   │   └── package.json
│   │
│   ├── indexer/                  # Repo intelligence pipeline
│   │   ├── src/
│   │   │   ├── ast/
│   │   │   ├── embeddings/
│   │   │   ├── conventions/
│   │   │   └── jobs/
│   │   └── package.json
│   │
│   └── dashboard/                # Internal web UI (Next.js)
│       ├── app/
│       │   ├── tasks/
│       │   ├── agents/
│       │   └── repos/
│       └── package.json
│
├── packages/
│   ├── shared/                   # Types, schemas (Zod), constants
│   ├── github-adapter/           # Wraps Octokit
│   ├── whatsapp-adapter/         # Wraps Meta/Twilio
│   ├── llm-client/               # Unified Claude/OpenAI/local
│   ├── sandbox/                  # Isolated code-execution env
│   └── observability/            # Logging, tracing, metrics
│
├── infra/
│   ├── docker/
│   ├── terraform/
│   └── k8s/
│
├── .ai-engineer.yml              # Per-repo config (consumed by agents)
├── docker-compose.yml
├── pnpm-workspace.yaml
└── README.md
```

### Per-target-repo config (`.ai-engineer.yml`)

```yaml
version: 1
auto_merge:
  enabled: true
  min_confidence: 0.85
protected_paths:
  - infra/**
  - migrations/**
  - src/auth/**
test_commands:
  unit: pnpm test
  e2e: pnpm test:e2e
lint_command: pnpm lint
typecheck_command: pnpm typecheck
preview_deploy: vercel
reviewers:
  human_fallback: ["@alice", "@bob"]
```

---

## 12. Step-by-Step Implementation Phases

### Phase 0 — Foundations (Week 1)

- Monorepo scaffold (pnpm + Turborepo).
- Postgres + Redis running in Docker.
- Auth model: users, phone numbers, repo permissions.
- WhatsApp webhook receiving + echoing messages.

### Phase 1 — Read-only assistant (Week 2–3)

- Status agent: *"What PRs are open?"*, *"Status of issue 42?"*.
- GitHub adapter with rate-limit + audit logging.
- WhatsApp outbound with template rendering.
- **Milestone:** can query repo state from WhatsApp.

### Phase 2 — Issue creation (Week 3–4)

- Intent parser + Planner agent.
- Auto-creates issues from feature/bug requests.
- Human-friendly confirmation flow in chat.
- **Milestone:** WhatsApp → GitHub issue, no code yet.

### Phase 3 — Repo intelligence (Week 4–6)

- AST extraction with tree-sitter.
- Embedding pipeline + vector store.
- Convention extractor.
- **Milestone:** Planner produces file-level plans grounded in the actual repo.

### Phase 4 — Code writing (Week 6–9)

- Sandboxed execution environment (Firecracker / Docker-in-Docker / E2B).
- Coder agent with tool-use loop.
- Reviewer agent with lint/type/test integration.
- PR creation with template.
- **Milestone:** end-to-end happy path, low-risk PR auto-merged.

### Phase 5 — UI workflows (Week 9–11)

- Playwright integration.
- UI Critic with vision model.
- Component library indexing.
- **Milestone:** screenshot → PR with passing visual diff.

### Phase 6 — Bug fixing (Week 11–13)

- Triage agent + Sentry/Datadog integration.
- Auto-bisect.
- Failing-test-first workflow.
- **Milestone:** real production bug fixed end-to-end.

### Phase 7 — Hardening (Week 13–15)

- Confidence calibration on historical data.
- Cost/budget controls per task.
- Internal dashboard for observability.
- Disaster recovery: replay any task from the audit log.

### Phase 8 — Production rollout (Week 15+)

- Onboard first external repo.
- Shadow mode: agent proposes, humans always approve.
- Gradually relax to auto-merge on low-risk paths.

---

## 13. Recommended Tech Stack

| Layer | Choice | Why |
|---|---|---|
| **Language (server)** | TypeScript (Node 22) | Strong typing, huge ecosystem, agent SDKs are TS-first |
| **Web framework** | Fastify | Faster than Express, plugin model, good for webhooks |
| **Queue** | BullMQ on Redis | Mature, observable, supports priorities + delayed jobs |
| **DB** | Postgres + pgvector | Relational truth + embeddings in one place |
| **Graph/AST store** | DuckDB (embedded) or Postgres | DuckDB for fast columnar queries on symbol graph |
| **LLM** | Claude Opus 4.7 (Anthropic) for reasoning; Sonnet for routine | Best-in-class for tool use and long-context coding |
| **Embedding model** | `text-embedding-3-large` or `bge-large` | Quality + cost balance |
| **Vision** | Claude Opus 4.7 vision or GPT-4o | UI critique, screenshot understanding |
| **Sandbox** | E2B, Modal, or Firecracker microVMs | Strong isolation for running untrusted code |
| **Browser automation** | Playwright | Best stability across Chromium/WebKit/Firefox |
| **AST parsing** | tree-sitter | Fast, language-agnostic |
| **Source control** | GitHub via Octokit | Mature webhooks + Apps model |
| **Messaging** | WhatsApp Business Cloud API | Official, scalable, supports templates |
| **Observability** | OpenTelemetry → Grafana + Loki + Tempo | Open, vendor-neutral, end-to-end tracing |
| **Secrets** | Doppler / Vault / AWS Secrets Manager | Centralized, rotated |
| **CI** | GitHub Actions (for our repo) | Native integration |
| **Deploy** | Fly.io or AWS ECS / EKS | Multi-region, supports stateful workers |
| **Frontend (dashboard)** | Next.js 15 + shadcn/ui + Tailwind | Fast to build, polished defaults |
| **Auth (dashboard)** | Clerk or WorkOS | SSO, low-effort |

### Why not LangChain / LangGraph as the runtime

For agent orchestration we recommend a thin custom runtime over a heavyweight framework: each step is just a queued job with typed inputs/outputs. This makes debugging and replaying tasks dramatically easier, and avoids version churn. Use the **Anthropic SDK** or **OpenAI SDK** directly for the LLM call; keep "agent" logic as plain TypeScript.

---

## 14. Future Scaling Ideas

### Product

- **Slack & Linear adapters** alongside WhatsApp — same agent, more inboxes.
- **Voice messages** — transcribe with Whisper and accept spoken specs.
- **Multi-repo features** — one request that spans backend + frontend + infra repos atomically.
- **Design-system bootstrapping** — point at a Figma file, generate the matching component library.
- **Spec-from-conversation** — the agent listens to a recorded meeting and produces a complete issue tree.

### Engineering quality

- **Reinforcement from outcomes** — every merged PR (that *stays* merged) becomes positive training signal; reverts become negative. Fine-tune Planner/Reviewer prompts from this.
- **Property-based testing** — Reviewer generates property tests via Hypothesis/fast-check to catch edge cases.
- **Mutation testing** — confirm the test suite actually constrains the change.
- **Spec-driven generation** — for typed APIs, generate the implementation from an OpenAPI/GraphQL schema.

### Infrastructure

- **Per-tenant isolation** — separate Redis/Postgres per customer for enterprise.
- **Cold/warm sandbox pools** — keep N sandboxes pre-warmed per repo to cut p50 latency.
- **Local LLM fallback** — run a smaller open model on-prem for cost-sensitive customers.
- **Cost budgets per repo / per user / per day** — automatic throttling when a budget is exceeded.

### Safety & governance

- **Policy-as-code** — OPA/Cedar rules over what agents can change and when.
- **Replay & rollback** — every task can be replayed deterministically; every merge can be reverted by chat command.
- **Audit export** — SOC2-friendly export of all agent actions per repo.
- **Red-team harness** — adversarial prompts run nightly to catch regressions in refusal & sensitive-path detection.

### Research bets

- **Self-improving prompts** — the system A/B tests prompt variants on real tasks and promotes winners.
- **Cross-repo learning** — patterns learned in one customer's repo (with permission, anonymized) accelerate others.
- **Long-horizon planning** — multi-day epics broken into PRs the agent executes over time, checking in via WhatsApp.

---

## Appendix A — Glossary

| Term | Meaning |
|---|---|
| **Task** | A single end-to-end unit of work triggered by one user message |
| **Step** | One agent invocation within a task |
| **Artifact** | Any file/screenshot/log produced during a task |
| **Confidence** | 0–1 score the Planner attaches to its plan |
| **Blast radius** | Predicted set of files affected by a change |
| **Protected path** | A file path that always requires human approval |

## Appendix B — Open Questions

- How do we handle **monorepos with 500+ packages**? Probably per-package indexing + lazy loading.
- How do we **prove correctness** beyond tests for safety-critical code? Possibly require formal review for paths tagged `safety-critical`.
- What's the right **failure UX on WhatsApp** when the agent gives up? A short summary + a one-tap "page a human" button.

---

*Document version: 1.0 — living document; update as architecture evolves.*
