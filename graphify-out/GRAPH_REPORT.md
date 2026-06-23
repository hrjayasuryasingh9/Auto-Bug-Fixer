# Graph Report - Auto Error Fixer  (2026-06-23)

## Corpus Check
- 51 files · ~36,241 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 816 nodes · 1164 edges · 95 communities (75 shown, 20 thin omitted)
- Extraction: 98% EXTRACTED · 2% INFERRED · 0% AMBIGUOUS · INFERRED: 19 edges (avg confidence: 0.77)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `39dc2b85`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- [[_COMMUNITY_Community 0|Community 0]]
- [[_COMMUNITY_Community 1|Community 1]]
- [[_COMMUNITY_Community 3|Community 3]]
- [[_COMMUNITY_Community 4|Community 4]]
- [[_COMMUNITY_Community 5|Community 5]]
- [[_COMMUNITY_Community 6|Community 6]]
- [[_COMMUNITY_Community 7|Community 7]]
- [[_COMMUNITY_Community 8|Community 8]]
- [[_COMMUNITY_Community 9|Community 9]]
- [[_COMMUNITY_Community 10|Community 10]]
- [[_COMMUNITY_Community 11|Community 11]]
- [[_COMMUNITY_Community 12|Community 12]]
- [[_COMMUNITY_Community 13|Community 13]]
- [[_COMMUNITY_Community 14|Community 14]]
- [[_COMMUNITY_Community 15|Community 15]]
- [[_COMMUNITY_Community 23|Community 23]]
- [[_COMMUNITY_Community 24|Community 24]]
- [[_COMMUNITY_Community 25|Community 25]]
- [[_COMMUNITY_Community 26|Community 26]]
- [[_COMMUNITY_Community 27|Community 27]]
- [[_COMMUNITY_Community 28|Community 28]]
- [[_COMMUNITY_Community 29|Community 29]]
- [[_COMMUNITY_Community 30|Community 30]]
- [[_COMMUNITY_Community 31|Community 31]]
- [[_COMMUNITY_Community 32|Community 32]]
- [[_COMMUNITY_Community 33|Community 33]]
- [[_COMMUNITY_Community 34|Community 34]]
- [[_COMMUNITY_Community 35|Community 35]]
- [[_COMMUNITY_Community 36|Community 36]]
- [[_COMMUNITY_Community 37|Community 37]]
- [[_COMMUNITY_Community 38|Community 38]]
- [[_COMMUNITY_Community 39|Community 39]]
- [[_COMMUNITY_Community 40|Community 40]]
- [[_COMMUNITY_Community 41|Community 41]]
- [[_COMMUNITY_Community 42|Community 42]]
- [[_COMMUNITY_Community 43|Community 43]]
- [[_COMMUNITY_Community 44|Community 44]]
- [[_COMMUNITY_Community 45|Community 45]]
- [[_COMMUNITY_Community 46|Community 46]]
- [[_COMMUNITY_Community 47|Community 47]]
- [[_COMMUNITY_Community 48|Community 48]]
- [[_COMMUNITY_Community 49|Community 49]]
- [[_COMMUNITY_Community 50|Community 50]]
- [[_COMMUNITY_Community 51|Community 51]]
- [[_COMMUNITY_Community 52|Community 52]]
- [[_COMMUNITY_Community 53|Community 53]]
- [[_COMMUNITY_Community 54|Community 54]]
- [[_COMMUNITY_Community 55|Community 55]]
- [[_COMMUNITY_Community 56|Community 56]]
- [[_COMMUNITY_Community 57|Community 57]]
- [[_COMMUNITY_Community 58|Community 58]]
- [[_COMMUNITY_Community 59|Community 59]]
- [[_COMMUNITY_Community 60|Community 60]]
- [[_COMMUNITY_Community 61|Community 61]]
- [[_COMMUNITY_Community 62|Community 62]]
- [[_COMMUNITY_Community 63|Community 63]]
- [[_COMMUNITY_Community 64|Community 64]]
- [[_COMMUNITY_Community 65|Community 65]]
- [[_COMMUNITY_Community 66|Community 66]]
- [[_COMMUNITY_Community 67|Community 67]]
- [[_COMMUNITY_Community 68|Community 68]]
- [[_COMMUNITY_Community 69|Community 69]]
- [[_COMMUNITY_Community 70|Community 70]]
- [[_COMMUNITY_Community 71|Community 71]]
- [[_COMMUNITY_Community 72|Community 72]]
- [[_COMMUNITY_Community 73|Community 73]]
- [[_COMMUNITY_Community 74|Community 74]]
- [[_COMMUNITY_Community 75|Community 75]]
- [[_COMMUNITY_Community 76|Community 76]]
- [[_COMMUNITY_Community 77|Community 77]]
- [[_COMMUNITY_Community 78|Community 78]]
- [[_COMMUNITY_Community 79|Community 79]]
- [[_COMMUNITY_Community 80|Community 80]]
- [[_COMMUNITY_Community 81|Community 81]]
- [[_COMMUNITY_Community 82|Community 82]]
- [[_COMMUNITY_Community 83|Community 83]]
- [[_COMMUNITY_Community 84|Community 84]]
- [[_COMMUNITY_Community 85|Community 85]]
- [[_COMMUNITY_Community 86|Community 86]]
- [[_COMMUNITY_Community 87|Community 87]]
- [[_COMMUNITY_Community 88|Community 88]]
- [[_COMMUNITY_Community 89|Community 89]]
- [[_COMMUNITY_Community 90|Community 90]]
- [[_COMMUNITY_Community 91|Community 91]]
- [[_COMMUNITY_Community 92|Community 92]]
- [[_COMMUNITY_Community 93|Community 93]]
- [[_COMMUNITY_Community 94|Community 94]]
- [[_COMMUNITY_Community 95|Community 95]]

## God Nodes (most connected - your core abstractions)
1. `run_assistant()` - 35 edges
2. `parse_intent()` - 22 edges
3. `str` - 20 edges
4. `handle_status_query()` - 20 edges
5. `WhatsApp Bridge - Complete Flow Documentation` - 20 edges
6. `fix_issue()` - 19 edges
7. `AI Autonomous Engineering Agent — Architecture & Implementation` - 18 edges
8. `get_repo_tree_summary()` - 17 edges
9. `_throttled_get()` - 16 edges
10. `search_files_in_repo()` - 16 edges

## Surprising Connections (you probably didn't know these)
- `whatsapp-bridge Application` --implements--> `WhatsApp Integration Flow`  [INFERRED]
  whatsapp-bridge/package.json → ai-autonomous-engineering-agent.md
- `Anthropic Python SDK` --implements--> `Claude Opus 4.7 LLM`  [INFERRED]
  requirements.txt → ai-autonomous-engineering-agent.md
- `GitHub Token (Per-request)` --references--> `Create PR Service`  [INFERRED]
  .env.example → Project-details.md
- `FastAPI` --implements--> `POST /api/ai-fix/ Endpoint`  [INFERRED]
  requirements.txt → FRONTEND_INTEGRATION.md
- `parse_intent()` --calls--> `AsyncAnthropic`  [INFERRED]
  server/agents/intent_parser.py → server/utils/ai.py

## Hyperedges (group relationships)
- **Multi-Agent Processing Pipeline** — ai_agent_md_planner_agent, ai_agent_md_coder_agent, ai_agent_md_reviewer_agent, ai_agent_md_fixer_agent [EXTRACTED 1.00]
- **Frontend Error-to-PR Fix Pipeline** — project_details_md_error_tracking, project_details_md_analyze_error, project_details_md_generate_fix, project_details_md_apply_patch, project_details_md_validate_fix, project_details_md_create_pr [EXTRACTED 1.00]

## Communities (95 total, 20 thin omitted)

### Community 0 - "Community 0"
Cohesion: 0.07
Nodes (45): { addHistory, getHistory }, ALLOWED_NUMBER, axios, client, { Client, LocalAuth }, formatCommitDetail(), formatCommitList(), formatDirectory() (+37 more)

### Community 1 - "Community 1"
Cohesion: 0.06
Nodes (53): ErrorReport, FixResponse, handle_error(), FixIssueRequest, handle_fix_issue(), Issue → PR endpoint. Triggered by the Slack "Fix this issue" button / command., stream_fix_issue(), RuntimeError (+45 more)

### Community 3 - "Community 3"
Cohesion: 0.26
Nodes (10): AsyncAnthropic, int, str, str, apply_window(), extract_window(), generate_fix(), Return (snippet, start_line, end_line) — 1-indexed, inclusive. (+2 more)

### Community 4 - "Community 4"
Cohesion: 0.17
Nodes (11): dependencies, axios, dotenv, qrcode-terminal, whatsapp-web.js, description, main, name (+3 more)

### Community 5 - "Community 5"
Cohesion: 0.07
Nodes (46): { addHistory, getHistory }, { addHistory, getHistory, getRepo, setRepo }, ALLOWED_USER, { App }, axios, files, _FIX_PHASES, fixButtonFromData() (+38 more)

### Community 6 - "Community 6"
Cohesion: 0.06
Nodes (65): _extract_images(), fetch_image_b64(), fetch_image_bytes(), get_commit(), get_file_content(), get_file_or_dir(), get_issue_detail(), get_open_issues() (+57 more)

### Community 7 - "Community 7"
Cohesion: 0.25
Nodes (8): Agent Orchestrator, Coder Agent, Fixer Agent, Planner Agent, Repo Intelligence Layer, Reviewer Agent, Semantic Embeddings (pgvector/Qdrant), Symbol Graph (tree-sitter AST)

### Community 8 - "Community 8"
Cohesion: 0.36
Nodes (5): Logger, _FlushFileHandler, _FlushHandler, Flushes immediately so logs appear in real-time., _setup_logger()

### Community 9 - "Community 9"
Cohesion: 0.33
Nodes (6): GitHub Token (Per-request), Analyze Error Service, Apply Patch Service, Create PR Service, Generate Fix Service, Validate Fix Service

### Community 11 - "Community 11"
Cohesion: 0.50
Nodes (4): WhatsApp Business Cloud API (Meta), WhatsApp Integration Flow, whatsapp-bridge Application, whatsapp-web.js

### Community 13 - "Community 13"
Cohesion: 0.67
Nodes (3): Claude Opus 4.7 LLM, Anthropic API Key (Server-side), Anthropic Python SDK

### Community 31 - "Community 31"
Cohesion: 0.12
Nodes (11): 6.1 Clone Repository Service, 6.2 Generate Fix Service, 6.3 Apply Patch Service, 6.4 Validate Fix Service, 6.5 Create PR Service, 6.6 Intent Parser Service, 6.7 Status Agent Service, 6. Service Specifications (+3 more)

### Community 32 - "Community 32"
Cohesion: 0.12
Nodes (16): AI Autonomous Frontend Error Fixing System, code:txt (Frontend Application), code:txt (You are an expert frontend debugging AI.), code:ts (import express from "express";), code:ts (import fs from "fs";), Final Goal, Goal, Goal (+8 more)

### Community 33 - "Community 33"
Cohesion: 0.15
Nodes (12): 1. Drop-in Error Tracker, 2. React Error Boundary, 3. Error flow end to end, code:ts (const AI_FIXER_ENDPOINT = "http://localhost:5000/api/ai-fix/), code:ts (// main.tsx or index.tsx), code:tsx (import React from "react";), code:tsx (// App.tsx), code:block5 (User hits a runtime crash) (+4 more)

### Community 34 - "Community 34"
Cohesion: 0.18
Nodes (11): 7.1 Error Fix Endpoint, 7.2 WhatsApp Webhook Endpoint, 7.3 Chat Completion Endpoint, 7. API Contracts, code:json ({), code:json ({), code:json ({), code:json ({) (+3 more)

### Community 35 - "Community 35"
Cohesion: 0.15
Nodes (12): 13. Recommended Tech Stack, 1. System Overview, 2. High-Level Architecture, AI Autonomous Engineering Agent — Architecture & Implementation, Appendix A — Glossary, Appendix B — Open Questions, code:block1 (┌─────────────┐      ┌──────────────┐      ┌────────────────), Core components (+4 more)

### Community 36 - "Community 36"
Cohesion: 0.20
Nodes (10): 12. Step-by-Step Implementation Phases, Phase 0 — Foundations (Week 1), Phase 1 — Read-only assistant (Week 2–3), Phase 2 — Issue creation (Week 3–4), Phase 3 — Repo intelligence (Week 4–6), Phase 4 — Code writing (Week 6–9), Phase 5 — UI workflows (Week 9–11), Phase 6 — Bug fixing (Week 11–13) (+2 more)

### Community 37 - "Community 37"
Cohesion: 0.15
Nodes (12): 15.1 Tech Stack Summary, 15. Technical Stack & Dependencies, 17. Security Considerations, 18. Quick Reference: Message Flow Summary, 1. System Overview, code:block31 (whatsapp-bridge/), code:block34 (⚠️  Security Notes:), code:block35 (User sends WhatsApp message) (+4 more)

### Community 38 - "Community 38"
Cohesion: 0.17
Nodes (11): 11. Technology Stack Summary, 12. Known Limitations & Future Work, 13. Quick Reference: File Map, 1. System Overview, AI Autonomous Engineering Agent - Complete Architecture Documentation, code:block37 (server/), Current Limitations, Key Capabilities (+3 more)

### Community 39 - "Community 39"
Cohesion: 0.25
Nodes (8): 8.1 Symbol graph, 8.2 Semantic embeddings, 8.3 Convention extractor, 8.4 Hot-path map, 8.5 Indexing pipeline, 8. Repo Intelligence Layer, code:block7 (push → webhook → enqueue index job), Components

### Community 40 - "Community 40"
Cohesion: 0.25
Nodes (8): 4.1 Frontend Error Tracking, 4.2 Backend Service Architecture, 4.3 Data Model - ErrorReport, 4. Component Architecture, code:python (class ErrorReport(BaseModel):), code:block7 (frontend/), code:typescript (// Error Tracker: Sends to backend), code:block9 (server/)

### Community 41 - "Community 41"
Cohesion: 0.29
Nodes (7): 4. GitHub Issue Management, Automated issue creation, code:block2 (created → triaged → planned → in-progress → in-review → merg), code:markdown (**Title:** Add CSV export to /orders page), Issue lifecycle, Labels applied automatically, Sensitive path guard

### Community 42 - "Community 42"
Cohesion: 0.29
Nodes (7): 10.1 Drop-in Error Tracker, 10.2 React Error Boundary, 10. Integration Guide for Frontend, code:typescript (// src/lib/errorTracker.ts), code:typescript (// main.tsx or index.tsx), code:typescript (// src/components/ErrorBoundary.tsx), code:typescript (// App.tsx)

### Community 43 - "Community 43"
Cohesion: 0.29
Nodes (7): 14. Getting Started, code:bash (# Backend), code:bash (# Terminal 1: Backend), code:typescript (// In browser console), Local Development, Prerequisites, Send First Error

### Community 44 - "Community 44"
Cohesion: 0.29
Nodes (7): 2.1 System Architecture Diagram, 2.2 Request Flow - Error to PR, 2.3 Intent Parsing & Multi-Agent Routing, 2. High-Level Design (HLD), code:mermaid (graph TB), code:mermaid (sequenceDiagram), code:mermaid (graph TB)

### Community 45 - "Community 45"
Cohesion: 0.29
Nodes (7): 3.1 Error Fix Pipeline - 6-Step Orchestration, 3.2 Service Call Graph - Error Fix Pipeline, 3.3 WhatsApp Message Flow - Intent Parsing & Routing, 3. Low-Level Design (LLD), code:mermaid (graph TD), code:mermaid (graph LR), code:mermaid (graph TB)

### Community 46 - "Community 46"
Cohesion: 0.29
Nodes (7): 9.1 Environment Variables, 9.2 Container Deployment (Docker), 9.3 Scaling Considerations, 9.4 Monitoring & Observability, 9. Deployment & Scaling, code:bash (# FastAPI), code:dockerfile (FROM python:3.11-slim)

### Community 47 - "Community 47"
Cohesion: 0.29
Nodes (7): code:ts (users.map(...)), code:ts (users?.map(...)), code:tsx (return <Dashboard data={data} />;), code:tsx (if (!data) return <Loader />;), Example Fixes AI Can Perform, Missing Loading State, Undefined Errors

### Community 48 - "Community 48"
Cohesion: 0.29
Nodes (7): 2.1 Component Diagram, 2.2 File Organization, 2.3 Data Flow Overview, 2. Architecture & Components, code:mermaid (graph TB), code:block2 (whatsapp-bridge/), code:mermaid (graph LR)

### Community 49 - "Community 49"
Cohesion: 0.29
Nodes (7): 7.1 Formatting Pipeline, 7.2 Formatter Functions Reference, 7.3 Example: PR List Formatter, 7. Response Formatting, code:mermaid (graph TD), code:block13 (formatForWhatsApp(fallback, data)), code:javascript (formatPRList(data) {)

### Community 50 - "Community 50"
Cohesion: 0.29
Nodes (7): 8.1 Session Structure, 8.2 Session State Diagram, 8.3 Store.js Functions, 8. State Management, code:javascript ({), code:mermaid (stateDiagram-v2), code:javascript (// Get existing session or create new one)

### Community 51 - "Community 51"
Cohesion: 0.29
Nodes (7): 9.1 Error Handling Flow, 9.2 Validation Points, 9.3 GitHub API Validation Errors, 9. Error Handling, code:mermaid (graph TD), code:mermaid (graph TB), code:javascript (validateToken(token) {)

### Community 52 - "Community 52"
Cohesion: 0.33
Nodes (6): 14. Future Scaling Ideas, Engineering quality, Infrastructure, Product, Research bets, Safety & governance

### Community 53 - "Community 53"
Cohesion: 0.33
Nodes (6): 5. PR Creation & Merge Workflows, Branch & PR naming, code:markdown (Closes #142), Conflict resolution, Merge policy (configurable per-repo), Standard PR template

### Community 54 - "Community 54"
Cohesion: 0.33
Nodes (6): 6. Multi-Agent Architecture, Agents, code:ts (type TaskContext = {), code:block6 (Planner → emits 'plan.ready' → Coder picks up), Handoff protocol, Shared context

### Community 55 - "Community 55"
Cohesion: 0.33
Nodes (6): AI Code Processing, Backend, Frontend, Git Operations, Tech Stack, Validation

### Community 56 - "Community 56"
Cohesion: 0.40
Nodes (5): 10.1 New feature (greenfield within an existing repo), 10.2 Bug fix, 10.3 Visual change from screenshot, 10.4 Refactor / chore, 10. Feature Implementation Workflows

### Community 57 - "Community 57"
Cohesion: 0.40
Nodes (5): 3. WhatsApp Integration Flow, Inbound flow, Message types supported, Outbound flow, Provider options

### Community 58 - "Community 58"
Cohesion: 0.40
Nodes (5): 7. Queue System, Job priorities, Queue topology (BullMQ + Redis), Retry policy, Why a queue

### Community 59 - "Community 59"
Cohesion: 0.40
Nodes (5): 5.1 Complete Request Flow: Error → PR, 5.2 WhatsApp → GitHub Status Flow, 5. Data Flow Diagrams, code:mermaid (graph TB), code:mermaid (graph TB)

### Community 60 - "Community 60"
Cohesion: 0.40
Nodes (5): 8.1 Pipeline Error Handling, 8.2 Validation Rules, 8. Error Handling & Validation, code:mermaid (graph TB), code:python (# Prevent path traversal)

### Community 61 - "Community 61"
Cohesion: 0.40
Nodes (5): 10.1 Per-Phone Processing Lock, 10.2 Why Lock is Needed, 10. Lock Mechanism (Concurrency Control), code:mermaid (graph TD), code:block22 (Problem:)

### Community 62 - "Community 62"
Cohesion: 0.40
Nodes (5): 11.1 Natural Language Project Change Patterns, 11.2 Project Change Flow, 11. Project Change Detection, code:javascript (Supported patterns:), code:mermaid (graph TD)

### Community 63 - "Community 63"
Cohesion: 0.40
Nodes (5): 12.1 Startup Sequence, 12.2 Client Configuration, 12. Initialization & Lifecycle, code:mermaid (sequenceDiagram), code:javascript (const client = new Client({)

### Community 64 - "Community 64"
Cohesion: 0.40
Nodes (5): 14.1 Conversational Setup Flow with Follow-ups, 14.2 Graph Build Trigger, 14. Advanced Flows, code:mermaid (graph TD), code:mermaid (graph TD)

### Community 65 - "Community 65"
Cohesion: 0.40
Nodes (5): 16.1 Console Logs, 16.2 Debugging Checklist, 16. Monitoring & Debugging, code:block32 ([startup] 🚀  Starting WhatsApp bridge...), code:block33 (If messages not being processed:)

### Community 66 - "Community 66"
Cohesion: 0.40
Nodes (5): 3.1 Complete Message Flow, 3.2 Message Type Detection & Routing, 3. Message Lifecycle, code:mermaid (sequenceDiagram), code:mermaid (graph TD)

### Community 67 - "Community 67"
Cohesion: 0.40
Nodes (5): 4.1 Setup State Machine, 4.2 Setup Step Flow Diagram, 4. Setup Flow, code:mermaid (stateDiagram-v2), code:mermaid (graph TB)

### Community 68 - "Community 68"
Cohesion: 0.40
Nodes (5): 5.1 Command Router, 5.2 Supported Commands Reference, 5. Command Processing, code:mermaid (graph TD), code:mermaid (graph TB)

### Community 69 - "Community 69"
Cohesion: 0.40
Nodes (5): 6.1 Query Processing Flow, 6.2 Backend API Call Details, 6. Query Processing Pipeline, code:mermaid (graph TD), code:mermaid (graph LR)

### Community 70 - "Community 70"
Cohesion: 0.50
Nodes (4): 11. Suggested Directory Structure, code:block8 (ai-engineer/), code:yaml (version: 1), Per-target-repo config (`.ai-engineer.yml`)

### Community 71 - "Community 71"
Cohesion: 0.50
Nodes (4): 9. UI Analysis Engine, Capabilities, Component library awareness, Visual review loop

### Community 72 - "Community 72"
Cohesion: 0.50
Nodes (4): Recommended MVP, Version 1, Version 2, Version 3

### Community 73 - "Community 73"
Cohesion: 0.50
Nodes (4): 13.1 Session Persistence, 13. Environment Variables & Configuration, code:bash (# .env file), code:bash (# .gitignore)

### Community 74 - "Community 74"
Cohesion: 0.18
Nodes (10): dependencies, axios, dotenv, @slack/bolt, description, main, name, scripts (+2 more)

### Community 75 - "Community 75"
Cohesion: 0.09
Nodes (39): parse_incoming(), Return list of {from, text, message_id} for each text message in a webhook paylo, send_text(), Connection, _build_ctx(), handle(), handle_stream(), MessageRequest (+31 more)

### Community 76 - "Community 76"
Cohesion: 0.67
Nodes (3): 1. Source Map Parsing, 2. AST-Based Fixing, Advanced Features

### Community 77 - "Community 77"
Cohesion: 0.67
Nodes (3): ALWAYS:, NEVER:, Safety Rules

### Community 78 - "Community 78"
Cohesion: 0.67
Nodes (3): code:ts (import OpenAI from "openai";), services/generateFix.ts, Step 6 — Generate AI Fix

### Community 79 - "Community 79"
Cohesion: 0.67
Nodes (3): code:ts (import fs from "fs";), services/applyPatch.ts, Step 7 — Apply Fix

### Community 80 - "Community 80"
Cohesion: 0.67
Nodes (3): code:bash (npm install @octokit/rest), Install, Step 9 — Create GitHub Pull Request

### Community 81 - "Community 81"
Cohesion: 0.67
Nodes (3): code:ts (import { Octokit } from "@octokit/rest";), Example, Step 10 — GitHub API PR Creation

### Community 82 - "Community 82"
Cohesion: 0.67
Nodes (3): code:ts (window.addEventListener("error", async (event) => {), errorTracker.ts, Frontend SDK

### Community 83 - "Community 83"
Cohesion: 0.67
Nodes (3): code:bash (npm install express cors dotenv simple-git axios openai), Install Dependencies, Step 2 — Backend API

### Community 84 - "Community 84"
Cohesion: 0.67
Nodes (3): code:ts (import { Router } from "express";), routes/aiFix.ts, Step 3 — Receive Error

### Community 85 - "Community 85"
Cohesion: 0.67
Nodes (3): code:ts (import simpleGit from "simple-git";), services/cloneRepo.ts, Step 4 — Clone Repository

### Community 86 - "Community 86"
Cohesion: 0.05
Nodes (57): calc_cost_inr(), generate_chat_reply(), parse_intent(), Classify intent using OpenAI gpt-4o-mini.      `api_key` is the OpenAI key; fall, Classify intent using OpenAI gpt-4o-mini.      `api_key` is the OpenAI key; fall, Classify intent using OpenAI gpt-4o-mini.      `api_key` is the OpenAI key; fall, Classify intent using OpenAI gpt-4o-mini.      `api_key` is the OpenAI key; fall, Classify intent using OpenAI gpt-4o-mini.      `api_key` is the OpenAI key; fall (+49 more)

### Community 95 - "Community 95"
Cohesion: 0.12
Nodes (28): BackgroundTasks, Path, build_graph_bg(), build_graph_sync(), BuildRequest, graph_status(), query_graph_endpoint(), QueryRequest (+20 more)

## Knowledge Gaps
- **269 isolated node(s):** `PreToolUse`, `allow`, `Request`, `bool`, `bytes` (+264 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **20 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Path` connect `Community 95` to `Community 0`, `Community 5`?**
  _High betweenness centrality (0.092) - this node is a cross-community bridge._
- **Why does `build_graph()` connect `Community 95` to `Community 1`?**
  _High betweenness centrality (0.071) - this node is a cross-community bridge._
- **Why does `run_assistant()` connect `Community 86` to `Community 75`, `Community 6`, `Community 95`?**
  _High betweenness centrality (0.049) - this node is a cross-community bridge._
- **What connects `PreToolUse`, `allow`, `Request` to the rest of the system?**
  _378 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Community 0` be split into smaller, more focused modules?**
  _Cohesion score 0.06914893617021277 - nodes in this community are weakly interconnected._
- **Should `Community 1` be split into smaller, more focused modules?**
  _Cohesion score 0.060515873015873016 - nodes in this community are weakly interconnected._
- **Should `Community 5` be split into smaller, more focused modules?**
  _Cohesion score 0.06636500754147813 - nodes in this community are weakly interconnected._