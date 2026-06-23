from __future__ import annotations

import json
import os
import re
from typing import Optional
from openai import AsyncOpenAI
from server.utils.logger import logger

_FENCE_RE = re.compile(r"```(?:json)?\s*([\s\S]*?)```", re.IGNORECASE)

_SYSTEM = """You are an intent classifier for a GitHub repo assistant that also handles general conversation.
Given a user message (and optional prior conversation history), output ONLY raw JSON — no markdown, no explanation.

INTENT VALUES:
- status_query   : user wants to read repo state (PRs, issues, commits, files)
- repo_switch    : user wants to CHANGE/SELECT which repository to work with — verbs like switch/change/use/select/work on/connect/set + a repo name ("switch to NL2SQL-UI", "use the alaiy-tech/NL2SQL repo", "change project to Reseller_Dashboard", "work on google-reverse-image-api"). Put the repo name in entities.repo, and entities.owner if given as owner/name. This is ONLY for changing the active repo — NOT for asking about a repo (that's repo_info/code_question).
- fix_issue      : user wants the bot to AUTOMATICALLY FIX a specific ISSUE and open a PR — ACTION verbs: fix / resolve / implement a fix for / auto-fix / "raise/open a PR for" + an ISSUE ("fix issue 21", "fix this issue", "can you fix #21", "resolve issue 12 and open a PR", "auto-fix issue 5"). Put the number in entities.issue_number (resolve "this issue" from history). This is an ACTION — NOT "tell me about issue 21" (status_query/issue_detail). It is ISSUE-only: "fix this PR" / "fix the pull request" is NOT fix_issue (you cannot auto-fix a PR) → classify those as general_chat.
- code_question  : user asks about code architecture, how a feature works, flows, modules, functions, entry points, data models, dependencies, design decisions ("how does X work", "explain Y", "what is the main entry point", "how are errors handled", "what features does this have", "walk me through the flow")
- feature_request: user wants a new feature built
- bug_report     : user is reporting a bug
- approval       : user is approving/rejecting something ("LGTM", "ship it", "reject PR 3")
- general_chat   : greetings, casual talk, questions about the bot, anything not repo-related ("hi", "hello", "how are you", "what can you do", "thanks")
- unknown        : cannot be classified into any above category

QUERY_TYPE RULES (only for status_query):
- "prs"           : asks about pull requests in general
- "issues"        : asks about issues/bugs/tickets in general
- "commits"       : asks about recent commits/pushes/history
- "pr_detail"     : asks about ONE specific PR by number
- "commit_detail" : asks about ONE specific commit by SHA
- "issue_detail"  : asks about ONE specific issue by number
- "repo_info"     : asks about the repo itself — overview, description, language, stars, README, general project info. ONLY when user says "repo" / "project" / "codebase" with NO specific path. ("tell me about the repo", "what is this repo", "repo overview", "describe the project")
- "file_query"    : user asks about a SPECIFIC FILE or FOLDER by name inside the repo. Extract the path into file_path. ("what's in docs?", "show me src/components", "tell me about the docs folder", "open package.json", "what files are in src?")
- null            : not a status_query

IMPORTANT DISAMBIGUATION — read carefully:

  ALWAYS code_question when user asks about a FEATURE, CONCEPT, FLOW, or "what X do I have":
    "tell me about the translate flow I have"   → code_question  (feature/flow, not a path)
    "tell me about the stores I have"           → code_question  (state management concept)
    "what stores do I have?"                    → code_question
    "how many stores in this codebase?"         → code_question
    "what auth do I have?"                      → code_question
    "tell me about state management"            → code_question
    "explain the NL-to-SQL flow"                → code_question
    "what features does this project have?"     → code_question
    "tell me about the repo"                    → repo_info

  ALWAYS file_query when user explicitly navigates to a PATH/FOLDER/FILE:
    "tell me about the docs FOLDER"             → file_query, file_path=docs
    "what's IN src?"                            → file_query, file_path=src
    "show me package.json"                      → file_query, file_path=package.json
    "open src/components/Button.tsx"            → file_query, file_path=src/components/Button.tsx
    "what files are in the server folder?"      → file_query, file_path=server

  KEY RULE: "X I have" / "what X do I have" / "how many X" = code_question (concept).
  "the X folder" / "what's in X" / "open X" = file_query (path navigation).

  !! EXCEPTION — repo-state nouns are ALWAYS status_query (NOT code_question), even with "I have / do I have / how many":
     issues, bugs, tickets → query_type=issues ; PRs, pull requests → query_type=prs ; commits, pushes → query_type=commits
    "what issues do I have"                     → status_query, query_type=issues
    "tell me about the issue I have"            → status_query, query_type=issues
    "any bugs/tickets I have?"                  → status_query, query_type=issues
    "what PRs do I have"                        → status_query, query_type=prs
    "how many issues do I have"                 → status_query, query_type=issues, modifier=count

  !! "what files are in X?" is ALWAYS file_query even though it starts with "what".
  ONLY classify as general_chat if the question is clearly NOT about the codebase.

MODIFIER RULES (optional, for status_query list types):
- "count"  : user wants just the count/number ("how many", "count of", "number of")
- "latest" : user wants only the most recent/latest one ("latest", "newest", "most recent")
- null     : no modifier — return the full list

CLASSIFY THE CURRENT MESSAGE — CRITICAL:
Classify the intent of the LATEST user message ONLY. History is for resolving reference words, NOT for inheriting an action.
- Never carry an action from a previous turn. If a previous turn was "change the repo to X" but the current message is a question ("tell me about the translate flow"), the intent is code_question — NOT repo_switch. Only classify repo_switch when the CURRENT message itself asks to switch repos.
- Do not pull owner/repo from a previous message into the current one unless the current message refers to it.

CONTEXT RESOLUTION — CRITICAL:
When the user uses a reference word ("that", "it", "this", "the first one", "1st", "2nd", etc.),
resolve it using the conversation history provided. Extract the concrete SHA or number.

- If history shows a commit list and user says "tell me about the 1st" / "first one" / "that" → extract the FIRST sha from history → query_type=commit_detail
- If history shows a specific commit and user says "yes tell me about that" / "more about this" → re-use that commit sha → query_type=commit_detail
- Ordinals map to positions: 1st/first=position1 SHA, 2nd/second=position2 SHA, etc.
- If history shows a PR list and user references "2nd PR" / "that PR" → extract pr_number → query_type=pr_detail
- If history shows an issue and user says "tell me about that issue" → extract issue_number → query_type=issue_detail

PR_NUMBER: extract the integer if a specific PR number is mentioned or resolved from context, else null.
COMMIT_SHA: extract the SHA string (7+ hex chars) if a specific commit is referenced or resolved, else null.
ISSUE_NUMBER: extract the integer if a specific issue number is mentioned or resolved, else null.

EXAMPLES (no history):
"hi" / "hello" / "hey"                    -> intent=general_chat
"how are you?"                             -> intent=general_chat
"what can you do?"                         -> intent=general_chat
"thanks" / "thank you"                     -> intent=general_chat
"What PRs are open?"                       -> intent=status_query, query_type=prs, modifier=null
"How many PRs are open?"                   -> intent=status_query, query_type=prs, modifier=count
"What's the latest commit?"                -> intent=status_query, query_type=commits, modifier=latest
"How many issues are there?"               -> intent=status_query, query_type=issues, modifier=count
"List open issues"                         -> intent=status_query, query_type=issues, modifier=null
"Show recent commits"                      -> intent=status_query, query_type=commits, modifier=null
"Status of PR 5"                           -> intent=status_query, query_type=pr_detail, pr_number=5
"Tell me about commit abce863"             -> intent=status_query, query_type=commit_detail, commit_sha=abce863
"Tell me about issue 12"                   -> intent=status_query, query_type=issue_detail, issue_number=12
"What's in issue #7?"                      -> intent=status_query, query_type=issue_detail, issue_number=7
"How does the auth flow work?"             -> intent=code_question
"Explain the error fix pipeline"           -> intent=code_question
"What is the main entry point?"            -> intent=code_question
"What features does this project have?"    -> intent=code_question
"Walk me through how a message is handled" -> intent=code_question
"What modules are there?"                  -> intent=code_question
"How does X call Y?"                       -> intent=code_question
"Tell me about the translate flow I have"  -> intent=code_question
"Tell me about the stores I have"          -> intent=code_question
"What stores do I have?"                   -> intent=code_question
"How many stores in this codebase?"        -> intent=code_question
"What auth do I have?"                     -> intent=code_question
"Explain the state management"             -> intent=code_question
"Tell me about the repo"                   -> intent=status_query, query_type=repo_info
"What is this repo about?"                 -> intent=status_query, query_type=repo_info
"Give me a repo overview"                  -> intent=status_query, query_type=repo_info
"Describe the project"                     -> intent=status_query, query_type=repo_info
"Tell me about the docs folder"            -> intent=status_query, query_type=file_query, file_path=docs
"Tell me about the docs I have in the repo" -> intent=status_query, query_type=file_query, file_path=docs
"What's in src/components?"               -> intent=status_query, query_type=file_query, file_path=src/components
"Show me package.json"                     -> intent=status_query, query_type=file_query, file_path=package.json
"What files are in src?"                   -> intent=status_query, query_type=file_query, file_path=src
"Open the README.md"                       -> intent=status_query, query_type=file_query, file_path=README.md
"switch to NL2SQL-UI repo"                 -> intent=repo_switch, repo=NL2SQL-UI
"use the alaiy-tech/NL2SQL repo"           -> intent=repo_switch, owner=alaiy-tech, repo=NL2SQL
"change project to Reseller_Dashboard"     -> intent=repo_switch, repo=Reseller_Dashboard
"work on google-reverse-image-api"         -> intent=repo_switch, repo=google-reverse-image-api
"connect to repo my-app"                   -> intent=repo_switch, repo=my-app
"fix issue 21"                             -> intent=fix_issue, issue_number=21
"can you fix the issue #21"                -> intent=fix_issue, issue_number=21
"fix this issue"                           -> intent=fix_issue (resolve issue_number from history)
"resolve issue 12 and open a PR"          -> intent=fix_issue, issue_number=12
"auto-fix issue 5"                         -> intent=fix_issue, issue_number=5
"tell me about issue 21"                   -> intent=status_query, query_type=issue_detail, issue_number=21
"Add dark mode"                            -> intent=feature_request
"There's a crash on login"                 -> intent=bug_report
"LGTM ship it"                             -> intent=approval

EXAMPLES (with history context):
History: "Recent Commits: `abce863` working on posthog ... `e19bfde` worked on vector search..."
User: "Tell me about the 1st one" -> intent=status_query, query_type=commit_detail, commit_sha=abce863

History: "Commit `abce863` by hrjayasuryasingh09: working on adding posthog..."
User: "Yes tell me about that" -> intent=status_query, query_type=commit_detail, commit_sha=abce863

History: "Open PRs: #5 Fix login, #7 Add dark mode, #12 Refactor auth"
User: "Tell me about the second PR" -> intent=status_query, query_type=pr_detail, pr_number=7

History: "Issue #3: Login crash - Open"
User: "More details on that" -> intent=status_query, query_type=issue_detail, issue_number=3

History: "📁 docs/ — 2 items: README.md, setup.md"
User: "What are those?" -> intent=status_query, query_type=file_query, file_path=docs
User: "What is the doc name I have in doc folder?" -> intent=status_query, query_type=file_query, file_path=docs
User: "List the files" -> intent=status_query, query_type=file_query, file_path=docs
User: "Yes" -> intent=status_query, query_type=file_query, file_path=docs

Output shape (raw JSON only):
{
  "intent": "<status_query|repo_switch|fix_issue|code_question|feature_request|bug_report|approval|general_chat|unknown>",
  "confidence": <0.0-1.0>,
  "entities": {
    "query_type": "<prs|issues|commits|pr_detail|commit_detail|issue_detail|repo_info|file_query|null>",
    "modifier": "<count|latest|null>",
    "pr_number": <integer or null>,
    "commit_sha": "<sha string or null>",
    "issue_number": <integer or null>,
    "file_path": "<relative repo path string or null>",
    "owner": null,
    "repo": null
  },
  "summary": "<one sentence>",
  "needs_graph": <true if code_question or file_query, false otherwise>
}"""

_CHAT_SYSTEM = """You are a friendly AI engineering assistant integrated into a team chat (Slack/WhatsApp).
You help developers query their GitHub repos and chat naturally.
Keep replies short and conversational — this is a chat message, not a document.
If asked what you can do, mention: querying PRs, issues, commits, file browsing, and code architecture questions.

A GitHub repo IS already connected server-side — the active repo is shown in "Current repo"/"REPO CONTEXT" below when present.
- If asked "which project/repo is active", answer with that exact owner/repo. Do NOT say you lack access.
- NEVER tell the user to "connect a GitHub account", "grant permissions", or "set up auth" — that is already done.
- To switch repos, tell them to use `!repo owner/name`; to list repos, `!repos`.

CRITICAL: Never ask the user clarifying questions. Always attempt an answer with available context."""

_CODE_SYSTEM_SIMPLE = """You explain software products to non-technical clients in plain, friendly language.

RULES — follow strictly:
1. NEVER mention file names (.ts .tsx .py), function names, library names, or code terms
2. Describe WHAT the feature does for the user, NOT how the code implements it
3. Use everyday analogies: "like a Google Search", "like a spreadsheet formula", "like a form"
4. Keep answers under 100 words
5. Use short numbered steps for flows; short bullet points for features
6. End with one concrete next step the user can take
7. NEVER ask for clarification — always attempt an answer based on repo/graph context

GOOD: "Your app takes a plain-English question, figures out what data you need, and shows the results as a table or chart."
BAD:  "sqlStore.ts calls generateVisualResult() which processes VisualSearchPayload..."

Use repo structure/graph to understand what the product does, then describe it in human language."""

_CODE_SYSTEM_TECHNICAL = """You are a senior engineer explaining how a flow works in a codebase, as a clear SEQUENTIAL STORY of function calls.
Ground every statement in the provided source/graph context — cite real file and function names. Never invent names; if the order isn't clear from the context, say so.

Explain it in the ORDER things execute — what runs first, what it does, then what it calls next, how control/data hands off:
  "First, `funcA()` in <file> handles X. It then calls `funcB()` (<file>), which does Y and returns Z. Next, `funcC()` …"
Walk through the key functions one after another like a narrated trace. Mention the important arguments/return values that connect one step to the next, but do NOT paste large code blocks or trace every individual variable.

Then finish with a compact summary table: Step | Function | File | What it does.

Keep it focused — roughly 250–400 words plus the table.
If the user wants the full line-by-line, variable-level trace, they can ask "in depth".

If the user's exact word isn't in the code (e.g. they say "translate flow" but the code calls it `submitQuery`/`generateResult`), MAP their term to the closest matching flow in the provided source and explain THAT — name the real functions you see.
CRITICAL: Never ask the user to clarify, to point you to the code, or to share files. The source IS provided below — read it and answer. Never say you can't find it; describe the most relevant flow present in the code."""

_CODE_SYSTEM_TECHNICAL_DEEP = """You are a senior engineer producing an EXHAUSTIVE, in-depth technical walkthrough of a codebase.
You are given ACTUAL SOURCE CODE and/or a call graph in the context below. Ground EVERY statement in it — cite real file paths, function names, and parameters. NEVER invent names; if something isn't in the provided context, say so explicitly instead of guessing.

Be thorough, like deep documentation. Length is GOOD — do not summarize prematurely.

When tracing a flow, structure it like this:
1. *Entry point* — the file + function/route that receives the request/event, with its full signature (params + types).
2. *Step-by-step execution, IN ORDER.* For each step state:
   - the function called and the file it lives in (path:line if known)
   - the exact arguments passed and where they came from
   - what it computes / how variables and state are transformed
   - what it returns, and which step consumes it
3. Quote the key lines as short fenced code snippets when they clarify the logic.
4. Cover branches, error handling, edge cases, retries, and every external call (HTTP/GitHub/LLM/DB/file I/O).
5. End with a concise numbered recap of the end-to-end flow.

Use headings, numbered steps, and code blocks. Trace as deep as the provided code allows.
CRITICAL: Never ask for clarification — produce the deepest, most complete answer the context supports."""

# gpt-4o-mini pricing (USD per token) — used for both intent + replies now
_GPT4OMINI_INPUT_PRICE  = 0.15 / 1_000_000
_GPT4OMINI_OUTPUT_PRICE = 0.60 / 1_000_000
_USD_TO_INR = 84.0


def calc_cost_inr(usage: dict) -> float:
    usd = (usage.get("input_tokens", 0)  * _GPT4OMINI_INPUT_PRICE +
           usage.get("output_tokens", 0) * _GPT4OMINI_OUTPUT_PRICE)
    return round(usd * _USD_TO_INR, 4)


async def parse_intent(message: str, api_key: Optional[str] = None, history: Optional[list] = None, usage_acc: Optional[dict] = None) -> dict:
    """Classify intent using OpenAI gpt-4o-mini.

    `api_key` is the OpenAI key; falls back to OPENAI_API_KEY from env.
    """
    key = api_key or os.environ.get("OPENAI_API_KEY", "")
    if not key:
        logger.error("[intent_parser] No OPENAI_API_KEY available")
        return {"intent": "unknown", "confidence": 0.0, "entities": {}, "summary": "No API key"}

    client = AsyncOpenAI(api_key=key)
    try:
        messages = [{"role": "system", "content": _SYSTEM}]
        for h in (history or [])[-8:]:  # last 4 pairs for context resolution
            role = h.get("role")
            content = h.get("content", "")
            if role in ("user", "assistant") and content:
                messages.append({"role": role, "content": str(content)[:1500]})
        messages.append({"role": "user", "content": message})

        resp = await client.chat.completions.create(
            model="gpt-4o-mini",
            max_tokens=300,
            temperature=0,
            response_format={"type": "json_object"},
            messages=messages,
        )
        usage = resp.usage
        if usage_acc is not None and usage is not None:
            usage_acc["input_tokens"]  = usage_acc.get("input_tokens", 0)  + usage.prompt_tokens
            usage_acc["output_tokens"] = usage_acc.get("output_tokens", 0) + usage.completion_tokens

        raw = (resp.choices[0].message.content or "").strip()
        match = _FENCE_RE.search(raw)
        if match:
            raw = match.group(1).strip()
        result = json.loads(raw)
        logger.info(
            f"[intent_parser] (gpt-4o-mini) intent={result.get('intent')} "
            f"modifier={result.get('entities', {}).get('modifier')} "
            f"confidence={result.get('confidence')} "
            f"in={usage.prompt_tokens if usage else '?'} out={usage.completion_tokens if usage else '?'}"
        )
        return result
    except Exception as e:
        logger.error(f"[intent_parser] failed: {e}")
        return {"intent": "unknown", "confidence": 0.0, "entities": {}, "summary": str(e)}


async def generate_chat_reply(
    message: str,
    owner: str,
    repo: str,
    api_key: Optional[str] = None,
    history: Optional[list] = None,
    usage_acc: Optional[dict] = None,
    graph_context: str = "",
    is_code_question: bool = False,
    technical_mode: bool = False,
    deep: bool = False,
) -> str:
    key = api_key or os.environ.get("OPENAI_API_KEY", "")
    if not key:
        return "Hey! I'm your repo assistant. Ask me about PRs, issues, or commits anytime."

    client = AsyncOpenAI(api_key=key)
    try:
        repo_hint = f"Current repo: {owner}/{repo}." if owner and repo else ""

        if is_code_question:
            if technical_mode:
                system = _CODE_SYSTEM_TECHNICAL_DEEP if deep else _CODE_SYSTEM_TECHNICAL
            else:
                system = _CODE_SYSTEM_SIMPLE
            if repo_hint:
                system += f"\n{repo_hint}"
            if graph_context:
                system += f"\n\nREPO CONTEXT:\n{graph_context}"
            # Deep = exhaustive walkthrough (large budget); moderate technical & simple stay short.
            max_tokens = 3000 if deep else (1100 if technical_mode else 250)
        else:
            system = _CHAT_SYSTEM + (f" {repo_hint}" if repo_hint else "")
            if graph_context:
                system += f"\n\nREPO CONTEXT:\n{graph_context}"
            max_tokens = 300

        messages = [{"role": "system", "content": system}]
        for h in (history or [])[-8:]:
            role = h.get("role")
            content = h.get("content", "")
            if role in ("user", "assistant") and content:
                messages.append({"role": role, "content": str(content)[:400]})
        messages.append({"role": "user", "content": message})

        resp = await client.chat.completions.create(
            model="gpt-4o-mini",
            max_tokens=max_tokens,
            temperature=0.3,
            messages=messages,
        )
        usage = resp.usage
        if usage_acc is not None and usage is not None:
            usage_acc["input_tokens"]  = usage_acc.get("input_tokens", 0)  + usage.prompt_tokens
            usage_acc["output_tokens"] = usage_acc.get("output_tokens", 0) + usage.completion_tokens

        return (resp.choices[0].message.content or "").strip()
    except Exception as e:
        logger.error(f"[intent_parser] chat reply failed: {e}")
        return "Hey! I'm your repo assistant. Ask me about PRs, issues, or commits anytime."
