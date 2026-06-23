# AI Autonomous Engineering Agent - Complete Architecture Documentation

> A WhatsApp-driven, multi-service AI platform that converts frontend errors and natural-language product requests into shipped code with autonomous branching, PR creation, and deployment workflows.

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [High-Level Design (HLD)](#2-high-level-design-hld)
3. [Low-Level Design (LLD)](#3-low-level-design-lld)
4. [Component Architecture](#4-component-architecture)
5. [Data Flow Diagrams](#5-data-flow-diagrams)
6. [Service Specifications](#6-service-specifications)
7. [API Contracts](#7-api-contracts)
8. [Error Handling & Validation](#8-error-handling--validation)
9. [Deployment & Scaling](#9-deployment--scaling)

---

## 1. System Overview

### Purpose

This system is a **fully autonomous AI engineering agent** that:

1. **Captures frontend errors** via error tracking SDK
2. **Routes intent** through WhatsApp or HTTP API
3. **Analyzes code** using Claude AI + repository intelligence
4. **Generates fixes** with context awareness
5. **Validates & deploys** through GitHub pull requests
6. **Reports status** back to users via WhatsApp in real-time

### Key Capabilities

| Feature | Purpose | Status |
|---------|---------|--------|
| **Error Detection** | Catches unhandled JS exceptions in production | ✅ Live |
| **Automated Fixes** | AI-generated code patches with validation | ✅ Live |
| **GitHub Integration** | Creates PRs, branches, commits autonomously | ✅ Live |
| **WhatsApp Interface** | Natural language commands + status queries | ✅ Live |
| **Multi-Agent System** | Planner, Coder, Reviewer agents (planned) | 🔄 Planned |
| **Repository Intelligence** | Semantic + AST-based code understanding | 🔄 Planned |

---

## 2. High-Level Design (HLD)

### 2.1 System Architecture Diagram

```mermaid
graph TB
    subgraph Client["🖥️ Client Layer"]
        FE["Frontend App<br/>(React/Next.js)"]
        EB["Error Boundary<br/>(React)"]
        ET["Error Tracker<br/>(window.onerror)"]
    end

    subgraph Gateway["🌐 Gateway Layer"]
        WA["WhatsApp Adapter<br/>(WhatsApp-Web.js)"]
        HTTP["HTTP API<br/>(FastAPI)"]
        WH["Webhook Handler<br/>(Verification + Auth)"]
    end

    subgraph Core["⚙️ Core Services"]
        IP["Intent Parser<br/>(Claude LLM)"]
        ERRFIX["Error Fix Pipeline<br/>(6-step orchestration)"]
        STATUS["Status Agent<br/>(GitHub queries)"]
        SESSION["Session Store<br/>(User credentials)"]
    end

    subgraph Services["🔧 Microservices"]
        CR["Clone/Update Repo"]
        AF["Analyze & Fix Generation<br/>(Claude)"]
        VAL["Validate Fix<br/>(npm build/lint)"]
        APPLY["Apply Patch<br/>(File manipulation)"]
        PR["Create PR<br/>(GitHub API)"]
    end

    subgraph External["☁️ External APIs"]
        GH["GitHub API<br/>(Octokit)"]
        CLAUDE["Claude API<br/>(Anthropic)"]
        WHP["WhatsApp API<br/>(Meta)"]
    end

    subgraph Storage["💾 Storage"]
        LOGS["Logs<br/>(Real-time)"]
        GRAPHS["Graph Cache<br/>(graphify)"]
        TEMP["Temp Repos<br/>(Git clones)"]
    end

    FE --> ET
    EB --> ET
    ET --> HTTP
    WA --> WH
    HTTP --> WH
    WH --> IP
    IP --> SESSION
    IP --> ERRFIX
    IP --> STATUS
    ERRFIX --> CR
    ERRFIX --> AF
    ERRFIX --> APPLY
    ERRFIX --> VAL
    ERRFIX --> PR
    AF --> CLAUDE
    PR --> GH
    WH --> WHP
    CR --> TEMP
    STATUS --> GH
    AF --> LOGS
    CR --> LOGS
    SESSION --> GRAPHS

    style Client fill:#2563eb,stroke:#1e40af,color:#fff
    style Gateway fill:#7c3aed,stroke:#6d28d9,color:#fff
    style Core fill:#059669,stroke:#047857,color:#fff
    style Services fill:#dc2626,stroke:#b91c1c,color:#fff
    style External fill:#f59e0b,stroke:#d97706,color:#fff
    style Storage fill:#6366f1,stroke:#4f46e5,color:#fff
```

### 2.2 Request Flow - Error to PR

```mermaid
sequenceDiagram
    participant FE as Frontend App
    participant EB as Error Boundary
    participant ET as Error Tracker
    participant API as FastAPI Server
    participant IP as Intent Parser
    participant ERRFIX as Error Fix Pipeline
    participant GH as GitHub API
    participant WHP as WhatsApp API

    FE->>+EB: Render component
    EB->>-FE: Error thrown
    FE->>ET: window.onerror triggered
    ET->>+API: POST /api/ai-fix/ (ErrorReport)
    API->>+ERRFIX: process_error(ErrorReport)

    ERRFIX->>ERRFIX: Step 1: Clone/Update Repo
    ERRFIX->>ERRFIX: Step 2: Read target file
    ERRFIX->>+IP: Step 3: Send to Claude for fix
    IP->>IP: Extract error context window
    IP-->>-ERRFIX: Fixed code snippet

    ERRFIX->>ERRFIX: Step 4: Apply patch to file
    ERRFIX->>ERRFIX: Step 5: Validate (npm build/lint)
    ERRFIX->>+GH: Step 6: Create PR + branch
    GH-->>-ERRFIX: PR URL, branch name

    ERRFIX-->>-API: FixResponse { success, pr_url }
    API-->>-ET: JSON response
    ET->>ET: Log success
    WHP->>WHP: Webhook notification (async)

    Note over FE,WHP: Total latency: ~30-90s depending on repo size
```

### 2.3 Intent Parsing & Multi-Agent Routing

```mermaid
graph TB
    WH["Webhook<br/>(Text message)"]
    IP["Intent Parser<br/>(Claude LLM)"]

    IP -->|status_query| SA["Status Agent<br/>(GitHub queries)"]
    IP -->|code_question| CA["Code Agent<br/>(Repo analysis)"]
    IP -->|feature_request| PA["Planner Agent<br/>(Requirements)"]
    IP -->|bug_report| BA["Bug Agent<br/>(Issue creation)"]
    IP -->|general_chat| GC["Chat Response<br/>(Claude)"]

    WH --> IP

    SA -->|prs| GH["Get Open PRs"]
    SA -->|issues| GH["Get Open Issues"]
    SA -->|commits| GH["Get Recent Commits"]
    SA -->|pr_detail| GH["Get PR Details"]
    SA -->|issue_detail| GH["Get Issue Details"]

    CA -->|analysis| GR["Repository Intelligence<br/>(AST + Embeddings)"]

    PA -->|code_gen| ERRFIX["Error Fix Pipeline"]

    style IP fill:#8b5cf6,color:#fff
    style SA fill:#06b6d4,color:#fff
    style CA fill:#10b981,color:#fff
    style PA fill:#f59e0b,color:#fff
    style BA fill:#ef4444,color:#fff
    style GC fill:#6366f1,color:#fff
```

---

## 3. Low-Level Design (LLD)

### 3.1 Error Fix Pipeline - 6-Step Orchestration

```mermaid
graph TD
    Start["Start: ErrorReport received"]
    
    Step1["📥 Step 1: Clone/Update Repo<br/>- Git clone with auth<br/>- Cache management<br/>- Fetch + reset origin/HEAD"]
    Step2["📄 Step 2: Read Target File<br/>- Load file from fs<br/>- Validate path exists<br/>- Encode UTF-8"]
    Step3["🤖 Step 3: Claude Fix Generation<br/>- Extract error context window<br/>- Build system prompt<br/>- Send to Claude Opus<br/>- Return fixed snippet"]
    Step4["✏️ Step 4: Apply Patch<br/>- Extract error window<br/>- Replace lines with fix<br/>- Write back to file<br/>- Validate syntax"]
    Step5["✅ Step 5: Validate Fix<br/>- npm run build<br/>- npm run lint<br/>- npm run test (optional)<br/>- Assert no new errors"]
    Step6["🚀 Step 6: Create GitHub PR<br/>- Create feature branch<br/>- Commit changes<br/>- Push to origin<br/>- Open PR via GitHub API"]
    
    End["✨ Success: Return PR URL<br/>+ branch name"]
    Error["❌ Error Handler<br/>- Log exception<br/>- Revert changes<br/>- Return error message"]

    Start --> Step1
    Step1 --> Step2
    Step2 --> Step3
    Step3 --> Step4
    Step4 --> Step5
    Step5 --> Step6
    Step6 --> End
    
    Step1 -.->|fail| Error
    Step2 -.->|fail| Error
    Step3 -.->|fail| Error
    Step4 -.->|fail| Error
    Step5 -.->|fail| Error
    Step6 -.->|fail| Error
    Error --> End

    style Start fill:#34d399,stroke:#059669,color:#000
    style Step1 fill:#60a5fa,stroke:#1e40af,color:#fff
    style Step2 fill:#60a5fa,stroke:#1e40af,color:#fff
    style Step3 fill:#a78bfa,stroke:#7c3aed,color:#fff
    style Step4 fill:#f472b6,stroke:#be185d,color:#fff
    style Step5 fill:#fbbf24,stroke:#d97706,color:#000
    style Step6 fill:#34d399,stroke:#059669,color:#000
    style End fill:#34d399,stroke:#059669,color:#000
    style Error fill:#ef4444,stroke:#991b1b,color:#fff
```

### 3.2 Service Call Graph - Error Fix Pipeline

```mermaid
graph LR
    API["FastAPI Router<br/>/api/ai-fix/"]
    PROCESS["process_error()"]
    CLONE["clone_repo()"]
    GENERATE["generate_fix()"]
    APPLY["apply_patch()"]
    VALIDATE["validate_fix()"]
    PR["create_pull_request()"]

    CLONE_SHELL["run_cmd()<br/>git operations"]
    AI["AsyncAnthropic<br/>Claude API"]
    VALIDATE_SHELL["run_cmd()<br/>npm build/lint"]
    GH_API["GitHub API<br/>Octokit"]

    API --> PROCESS

    PROCESS --> CLONE
    PROCESS --> GENERATE
    PROCESS --> APPLY
    PROCESS --> VALIDATE
    PROCESS --> PR

    CLONE --> CLONE_SHELL
    GENERATE --> AI
    VALIDATE --> VALIDATE_SHELL
    PR --> GH_API

    style API fill:#2563eb,stroke:#1e40af,color:#fff
    style PROCESS fill:#059669,stroke:#047857,color:#fff
    style CLONE fill:#7c3aed,stroke:#6d28d9,color:#fff
    style GENERATE fill:#8b5cf6,stroke:#7c3aed,color:#fff
    style APPLY fill:#f472b6,stroke:#be185d,color:#fff
    style VALIDATE fill:#fbbf24,stroke:#d97706,color:#000
    style PR fill:#34d399,stroke:#059669,color:#000
    style AI fill:#f59e0b,stroke:#d97706,color:#000
    style GH_API fill:#666,color:#fff
```

### 3.3 WhatsApp Message Flow - Intent Parsing & Routing

```mermaid
graph TB
    WH["Webhook POST<br/>/webhooks/whatsapp"]
    PARSE["parse_incoming()<br/>Extract messages"]
    HANDLE["_handle_message()"]

    SETUP["Setup Command?<br/>token/owner/repo/key"]
    HELP["Help/Hi Command?"]
    STATUS["Status Command?"]
    INTENT["parse_intent()<br/>LLM classification"]

    SETUP_HANDLER["Update Session<br/>Save credentials"]
    HELP_HANDLER["Send Help Text"]
    STATUS_HANDLER["Get Session<br/>Format response"]
    INTENT_ROUTER["Route by intent"]

    STATUS_ROUTE["status_query"]
    CODE_ROUTE["code_question"]
    FEATURE_ROUTE["feature_request"]
    CHAT_ROUTE["general_chat"]

    STATUS_AGENT["Status Agent<br/>GitHub queries"]
    CODE_AGENT["Code Agent<br/>Repo analysis"]
    FEATURE_AGENT["Planner Agent<br/>Create issue"]
    CHAT_AGENT["Chat Response"]

    SEND["send_text()"]

    WH --> PARSE
    PARSE --> HANDLE
    
    HANDLE -->|cmd| SETUP
    HANDLE -->|cmd| HELP
    HANDLE -->|cmd| STATUS
    HANDLE -->|msg| INTENT

    SETUP --> SETUP_HANDLER
    HELP --> HELP_HANDLER
    STATUS --> STATUS_HANDLER
    INTENT --> INTENT_ROUTER

    INTENT_ROUTER --> STATUS_ROUTE
    INTENT_ROUTER --> CODE_ROUTE
    INTENT_ROUTER --> FEATURE_ROUTE
    INTENT_ROUTER --> CHAT_ROUTE

    STATUS_ROUTE --> STATUS_AGENT
    CODE_ROUTE --> CODE_AGENT
    FEATURE_ROUTE --> FEATURE_AGENT
    CHAT_ROUTE --> CHAT_AGENT

    SETUP_HANDLER --> SEND
    HELP_HANDLER --> SEND
    STATUS_HANDLER --> SEND
    STATUS_AGENT --> SEND
    CODE_AGENT --> SEND
    FEATURE_AGENT --> SEND
    CHAT_AGENT --> SEND

    style WH fill:#2563eb,stroke:#1e40af,color:#fff
    style PARSE fill:#7c3aed,stroke:#6d28d9,color:#fff
    style HANDLE fill:#7c3aed,stroke:#6d28d9,color:#fff
    style INTENT fill:#8b5cf6,stroke:#7c3aed,color:#fff
    style INTENT_ROUTER fill:#a78bfa,stroke:#7c3aed,color:#fff
    style STATUS_AGENT fill:#06b6d4,stroke:#0891b2,color:#fff
    style CODE_AGENT fill:#10b981,stroke:#047857,color:#fff
    style FEATURE_AGENT fill:#f59e0b,stroke:#d97706,color:#000
    style CHAT_AGENT fill:#6366f1,stroke:#4f46e5,color:#fff
    style SEND fill:#34d399,stroke:#059669,color:#000
```

---

## 4. Component Architecture

### 4.1 Frontend Error Tracking

```
frontend/
├── index.html                    # Standalone UI dashboard
├── errorTracker.ts              # Error capture SDK (to integrate)
│   ├── window.onerror          # Unhandled exceptions
│   ├── unhandledrejection       # Promise rejections
│   └── reportError()            # HTTP POST to /api/ai-fix/
│
└── ErrorBoundary.tsx            # React error boundary
    ├── componentDidCatch()       # Lifecycle hook
    ├── reportError()             # Send to backend
    └── Fallback UI               # Error display
```

**Key Functions:**

```typescript
// Error Tracker: Sends to backend
window.addEventListener("error", (event) => {
  reportError({
    message: event.message,
    stack: event.error?.stack,
    line_number: event.lineno,
    column_number: event.colno,
    url: window.location.href,
    repo_url, github_token, github_owner, github_repo,
    anthropic_api_key, target_file
  });
});

// React Error Boundary: Catches render errors
class ErrorBoundary extends React.Component {
  componentDidCatch(error, errorInfo) {
    reportError({
      message: error.message,
      componentStack: errorInfo.componentStack,
      ...CONFIG
    });
  }
}
```

### 4.2 Backend Service Architecture

```
server/
├── main.py                       # FastAPI app + CORS + middleware
├── routes/
│   ├── ai_fix.py                # POST /api/ai-fix/ (error fix endpoint)
│   ├── whatsapp.py              # WhatsApp webhook + intent routing
│   ├── chat.py                  # Chat completion endpoint
│   └── graph.py                 # Repository intelligence queries
├── services/
│   ├── analyze_error.py         # Main orchestration (process_error)
│   ├── clone_repo.py            # Git operations
│   ├── generate_fix.py          # Claude API integration
│   ├── apply_patch.py           # File manipulation
│   ├── validate_fix.py          # npm build/lint execution
│   ├── create_pr.py             # GitHub PR creation
│   ├── graph_service.py         # Graph queries (planned)
│   └── session_store.py         # User session management
├── agents/
│   ├── intent_parser.py         # LLM-based intent classification
│   ├── status_agent.py          # GitHub status queries
│   └── [coder_agent.py]         # (Planned) Code generation
├── adapters/
│   ├── github_adapter.py        # GitHub API wrapper
│   └── whatsapp_adapter.py      # WhatsApp message parsing
├── models/
│   └── schemas.py               # Pydantic data models
├── utils/
│   ├── ai.py                    # Anthropic SDK wrapper
│   ├── github.py                # GitHub API utilities
│   ├── logger.py                # Real-time logging
│   ├── shell.py                 # Shell command execution
│   └── indexing.py              # (Planned) AST indexing
└── graphs/
    └── [repo_graphs]/            # Cached graph data per repo
```

### 4.3 Data Model - ErrorReport

```python
class ErrorReport(BaseModel):
    # Error details
    message: str                   # Error message
    stack: Optional[str]          # Stack trace
    line_number: Optional[int]    # Where error occurred
    column_number: Optional[int]  
    
    # Frontend context
    url: Optional[str]            # Page URL
    userAgent: Optional[str]      # Browser info
    timestamp: Optional[int]      # Unix timestamp
    componentStack: Optional[str] # React component stack
    sessionId: Optional[str]      # User session
    
    # Repository context
    repo_url: str                 # GitHub repo HTTPS URL
    repo_name: str                # Repo name for caching
    target_file: str              # File containing error
    
    # Credentials (client-provided)
    github_token: str             # PAT for git operations
    github_owner: str             # Repo owner
    github_repo: str              # Repo name
    anthropic_api_key: str        # Claude API key
```

---

## 5. Data Flow Diagrams

### 5.1 Complete Request Flow: Error → PR

```mermaid
graph TB
    A["1️⃣ Frontend Error<br/>window.onerror fired"]
    B["2️⃣ Capture Error Context<br/>message, stack, line_no"]
    C["3️⃣ Build ErrorReport<br/>+ repo credentials"]
    D["4️⃣ POST to /api/ai-fix/"]
    E["5️⃣ FastAPI Router<br/>Validates schema"]
    F["6️⃣ process_error()"]
    G["7️⃣ Git Clone/Update"]
    H["8️⃣ Read Target File"]
    I["9️⃣ Send to Claude<br/>Error context window"]
    J["🔟 Claude Returns Fix"]
    K["1️⃣1️⃣ Apply Patch"]
    L["1️⃣2️⃣ Run Validation<br/>npm build/lint"]
    M["1️⃣3️⃣ Create Git Branch"]
    N["1️⃣4️⃣ Commit + Push"]
    O["1️⃣5️⃣ Create GitHub PR"]
    P["1️⃣6️⃣ Return PR URL<br/>to Frontend"]

    A --> B
    B --> C
    C --> D
    D --> E
    E --> F
    F --> G
    G --> H
    H --> I
    I --> J
    J --> K
    K --> L
    L --> M
    M --> N
    N --> O
    O --> P

    style A fill:#ef4444,color:#fff
    style B fill:#f97316,color:#fff
    style C fill:#eab308,color:#000
    style D fill:#84cc16,color:#000
    style E fill:#22c55e,color:#fff
    style F fill:#10b981,color:#fff
    style G fill:#06b6d4,color:#fff
    style H fill:#0ea5e9,color:#fff
    style I fill:#6366f1,color:#fff
    style J fill:#8b5cf6,color:#fff
    style K fill:#a855f7,color:#fff
    style L fill:#d946ef,color:#fff
    style M fill:#ec4899,color:#fff
    style N fill:#f472b6,color:#fff
    style O fill:#f43f5e,color:#fff
    style P fill:#22c55e,color:#fff
```

### 5.2 WhatsApp → GitHub Status Flow

```mermaid
graph TB
    A["User sends WhatsApp<br/>'What PRs are open?'"]
    B["Webhook received<br/>Parse message"]
    C["Intent Parser<br/>Classify as status_query"]
    D["Extract query_type=prs"]
    E["Status Agent<br/>GitHub API call"]
    F["GitHub returns PR list"]
    G["Format for WhatsApp<br/>(markdown → text)"]
    H["Send via WhatsApp API"]
    I["User receives response"]

    A --> B
    B --> C
    C --> D
    D --> E
    E --> F
    F --> G
    G --> H
    H --> I

    style A fill:#06b6d4,color:#fff
    style B fill:#0891b2,color:#fff
    style C fill:#8b5cf6,color:#fff
    style D fill:#a78bfa,color:#fff
    style E fill:#06b6d4,color:#fff
    style F fill:#10b981,color:#fff
    style G fill:#f59e0b,color:#000
    style H fill:#34d399,color:#000
    style I fill:#06b6d4,color:#fff
```

---

## 6. Service Specifications

### 6.1 Clone Repository Service

**File:** [server/services/clone_repo.py](server/services/clone_repo.py)

**Purpose:** Clone or update a Git repository with GitHub token authentication.

**Function Signature:**
```python
async def clone_repo(
    repo_url: str,                    # "https://github.com/owner/repo.git"
    repo_name: str,                   # "repo" (for caching)
    github_token: str = ""            # PAT for authentication
) -> str:                             # Returns: repo_path
```

**Algorithm:**
1. Compute cache directory: `server/temp_repos/{repo_name}`
2. If cached `.git` exists:
   - Try to update: `git fetch --all && git reset --hard origin/HEAD`
   - On failure, delete and re-clone
3. If not cached:
   - Inject token into HTTPS URL: `https://x-access-token:{token}@github.com/...`
   - Clone: `git clone {auth_url} {dest}`
4. Return path or raise exception

**Key Behaviors:**
- Windows-safe recursive delete (handles read-only git files)
- Automatic cleanup of stale directories
- Token injection for private repos
- Idempotent (safe to call multiple times)

---

### 6.2 Generate Fix Service

**File:** [server/services/generate_fix.py](server/services/generate_fix.py)

**Purpose:** Send error context to Claude and receive fixed code.

**Function Signature:**
```python
async def generate_fix(
    error_data: dict,                 # ErrorReport fields
    file_content: str,                # Full file content
    file_path: str,                   # For logging
    api_key: str                      # Anthropic API key
) -> str:                             # Returns: fixed_code (full file)
```

**Algorithm:**
1. **Extract Error Window:**
   - If `line_number` is known, extract ±40 lines around error
   - Include context: declarations, imports, related functions
   - Lines are 1-indexed, inclusive

2. **Build Claude Prompt:**
   - System prompt: "You are an expert frontend debugging AI"
   - User message: Error context + snippet
   - Temperature: 0.7 (balanced deterministic + creative)

3. **Call Claude Opus:**
   - Send via AsyncAnthropic
   - Stream or collect full response
   - Extract fixed snippet

4. **Splice Back:**
   - Replace original lines [start, end] with fixed lines
   - Return full file content

**Example Window Extraction:**
```
error line: 42
window: lines 2–82 (40 before + error + 40 after)

Send to Claude:
"""
Error: TypeError: Cannot read property 'map' of undefined
Stack: at DashboardCard.render (Dashboard.tsx:42:15)

Context (lines 2–82):
import React from 'react';
import { useQuery } from 'react-query';
... [40 lines before] ...
const DashboardCard = () => {
  const { data } = useQuery(...);  // ← error here at line 42
  return <div>{data.map(...)}</div>;
}
... [40 lines after] ...
"""
```

---

### 6.3 Apply Patch Service

**File:** [server/services/apply_patch.py](server/services/apply_patch.py)

**Purpose:** Write the fixed code back to the filesystem.

**Function Signature:**
```python
async def apply_patch(
    file_path: str,                   # Full path to target file
    fixed_code: str                   # Fixed file content
) -> None:
```

**Algorithm:**
1. Write fixed_code to file_path (UTF-8)
2. Validate no syntax errors (optional: import ast/js parser)
3. Log success

---

### 6.4 Validate Fix Service

**File:** [server/services/validate_fix.py](server/services/validate_fix.py)

**Purpose:** Ensure fix doesn't break the build.

**Function Signature:**
```python
async def validate_fix(repo_path: str) -> None:
```

**Validation Steps:**
1. `npm run build` — TypeScript compilation + bundling
2. `npm run lint` — ESLint rules
3. (Optional) `npm run test` — Unit tests
4. Raise if any step fails

**Behavior:**
- Runs from repo_path
- Logs all output
- Fails-fast: first error stops validation
- Rollback on failure (delete branch, revert file)

---

### 6.5 Create PR Service

**File:** [server/services/create_pr.py](server/services/create_pr.py)

**Purpose:** Create a GitHub PR with the fixed code.

**Function Signature:**
```python
async def create_pull_request(
    repo_path: str,
    error_message: str,               # Used in commit message
    github_token: str,
    github_owner: str,
    github_repo: str
) -> tuple[str, str]:                 # Returns: (pr_url, branch_name)
```

**Algorithm:**
1. **Create Branch:**
   - Name: `ai-fix/{timestamp}-{error-type}`
   - Example: `ai-fix/1718900000-typeerror`
   - Checkout: `git checkout -b {branch}`

2. **Commit Changes:**
   - Stage all: `git add .`
   - Commit: `git commit -m "fix: Auto-fixed error — {error_message[:80]}"`
   - Committer: configured git user (from env or default)

3. **Push to Remote:**
   - `git push origin {branch}`

4. **Create PR via GitHub API:**
   - Title: `Auto-fix: {error_message[:80]}`
   - Body: Includes:
     - Original error message
     - Stack trace
     - File affected
     - Validation results
   - Base: `main` or `develop` (configurable)

5. **Return:**
   - PR URL (e.g., `https://github.com/owner/repo/pull/123`)
   - Branch name

---

### 6.6 Intent Parser Service

**File:** [server/agents/intent_parser.py](server/agents/intent_parser.py)

**Purpose:** Classify user intent from WhatsApp messages using Claude.

**Function Signature:**
```python
async def parse_intent(
    text: str,                        # User message
    history: Optional[List] = None    # Conversation history
) -> dict:                            # Returns: { intent, query_type, ... }
```

**Intent Classification:**

| Intent | Meaning | Example |
|--------|---------|---------|
| `status_query` | User asks for repo info | "What PRs are open?" |
| `code_question` | User asks how code works | "Explain the auth flow" |
| `feature_request` | User wants new feature | "Add dark mode" |
| `bug_report` | User reports a bug | "Login fails on Safari" |
| `approval` | User approves/rejects | "LGTM, ship it" |
| `general_chat` | Casual conversation | "Hi!", "Thanks", "How are you?" |
| `unknown` | Cannot classify | Garbled text |

**Query Types (for status_query only):**

| Type | Query | Example |
|------|-------|---------|
| `prs` | All PRs | "List open PRs" |
| `issues` | All issues | "Show open issues" |
| `commits` | Recent commits | "What's the latest commit?" |
| `pr_detail` | One PR | "Status of PR 5?" |
| `issue_detail` | One issue | "Tell me about issue 12" |
| `commit_detail` | One commit | "Show commit abc1234" |
| `repo_info` | Repo metadata | "Tell me about the repo" |
| `file_query` | File/folder | "Show me src/components/" |

---

### 6.7 Status Agent Service

**File:** [server/agents/status_agent.py](server/agents/status_agent.py)

**Purpose:** Query GitHub for repository status.

**Function Signature:**
```python
async def handle_status_query(
    query_type: str,                  # prs, issues, commits, pr_detail, ...
    session: dict,                    # { github_token, owner, repo }
    filters: dict = {}                # { pr_number, commit_sha, issue_number, ... }
) -> str:                             # Returns: formatted WhatsApp-safe text
```

**Supported Queries:**
1. `prs` → List all open PRs (title, number, author, updated_at)
2. `issues` → List all open issues (title, number, author, updated_at)
3. `commits` → List recent commits (sha, author, message, date)
4. `pr_detail` → Get one PR (number, title, description, status, review state)
5. `issue_detail` → Get one issue (number, title, description, labels, status)
6. `commit_detail` → Get one commit (sha, author, date, message, files changed)
7. `repo_info` → Repo metadata (description, language, stars, watchers)
8. `file_query` → List files in a path (with metadata)

**Example Response:**
```
PR #42: "Fix login validation"
  Author: alice
  Status: Approved (2/3)
  Updated: 2 hours ago
  
PR #38: "Add dark mode"
  Author: bob
  Status: Pending Review
  Updated: 6 hours ago
```

---

## 7. API Contracts

### 7.1 Error Fix Endpoint

**POST** `/api/ai-fix/`

**Request Body:**
```json
{
  "message": "TypeError: Cannot read property 'map' of undefined",
  "stack": "at DashboardCard.render...",
  "line_number": 42,
  "column_number": 15,
  "url": "https://myapp.com/dashboard",
  "userAgent": "Mozilla/5.0...",
  "timestamp": 1718900000,
  "repo_url": "https://github.com/owner/repo.git",
  "repo_name": "repo",
  "target_file": "src/components/Dashboard.tsx",
  "github_token": "ghp_xxxxxx",
  "github_owner": "owner",
  "github_repo": "repo",
  "anthropic_api_key": "sk-ant-xxxxx"
}
```

**Response (Success):**
```json
{
  "success": true,
  "pr_url": "https://github.com/owner/repo/pull/123",
  "branch_name": "ai-fix/1718900000-typeerror",
  "message": "Fix applied and PR created successfully"
}
```

**Response (Error):**
```json
{
  "success": false,
  "error": "Target file not found in repo: src/components/Dashboard.tsx",
  "message": null
}
```

**Status Codes:**
- `200 OK` — Fix generated and PR created
- `400 Bad Request` — Invalid ErrorReport schema
- `500 Internal Server Error` — Pipeline failed (clone, fix generation, validation, etc.)

---

### 7.2 WhatsApp Webhook Endpoint

**GET** `/webhooks/whatsapp?hub.mode=subscribe&hub.verify_token=xxx&hub.challenge=yyy`

**Purpose:** Meta verification handshake

**Response:** Returns `hub.challenge` parameter if verified

---

**POST** `/webhooks/whatsapp`

**Request Body (Meta Format):**
```json
{
  "object": "whatsapp_business_account",
  "entry": [
    {
      "id": "WHATSAPP_ACCOUNT_ID",
      "changes": [
        {
          "value": {
            "messaging_product": "whatsapp",
            "messages": [
              {
                "from": "1234567890",
                "id": "msg_id",
                "timestamp": "1718900000",
                "type": "text",
                "text": {
                  "body": "What PRs are open?"
                }
              }
            ]
          }
        }
      ]
    }
  ]
}
```

**Response:**
```json
{
  "status": "ok"
}
```

**Side Effects:**
- Parses message and user phone
- Routes to intent parser
- Sends response via WhatsApp API

---

### 7.3 Chat Completion Endpoint

**POST** `/api/chat/`

**Request:**
```json
{
  "message": "Explain the error fix pipeline",
  "history": [
    { "role": "user", "content": "How does this project work?" },
    { "role": "assistant", "content": "It's an AI error fixer..." }
  ]
}
```

**Response:**
```json
{
  "message": "The error fix pipeline is a 6-step orchestration that...",
  "cost_inr": 0.05
}
```

---

## 8. Error Handling & Validation

### 8.1 Pipeline Error Handling

```mermaid
graph TB
    STEP1["Clone Repo"]
    STEP2["Read File"]
    STEP3["Generate Fix"]
    STEP4["Apply Patch"]
    STEP5["Validate"]
    STEP6["Create PR"]

    STEP1 -->|fail| E1["Error:<br/>Git auth failed<br/>Repo not found"]
    STEP2 -->|fail| E2["Error:<br/>File not found<br/>Permission denied"]
    STEP3 -->|fail| E3["Error:<br/>Claude API error<br/>Rate limited"]
    STEP4 -->|fail| E4["Error:<br/>Write failed<br/>Syntax error"]
    STEP5 -->|fail| E5["Error:<br/>Build failed<br/>Lint failed<br/>Test failed"]
    STEP6 -->|fail| E6["Error:<br/>PR creation failed<br/>Branch already exists"]

    E1 --> CLEANUP["🔄 Cleanup:<br/>Delete temp dir<br/>Log error"]
    E2 --> CLEANUP
    E3 --> CLEANUP
    E4 --> CLEANUP
    E5 --> CLEANUP
    E6 --> CLEANUP

    CLEANUP --> RETURN["Return FixResponse<br/>{ success: false, error }"]

    style STEP1 fill:#60a5fa,color:#fff
    style STEP2 fill:#60a5fa,color:#fff
    style STEP3 fill:#a78bfa,color:#fff
    style STEP4 fill:#f472b6,color:#fff
    style STEP5 fill:#fbbf24,color:#000
    style STEP6 fill:#34d399,color:#000
    style E1 fill:#ef4444,color:#fff
    style E2 fill:#ef4444,color:#fff
    style E3 fill:#ef4444,color:#fff
    style E4 fill:#ef4444,color:#fff
    style E5 fill:#ef4444,color:#fff
    style E6 fill:#ef4444,color:#fff
    style CLEANUP fill:#fbbf24,color:#000
    style RETURN fill:#ef4444,color:#fff
```

### 8.2 Validation Rules

**ErrorReport Schema Validation:**
- `message` — required, non-empty string, ≤500 chars
- `repo_url` — required, valid GitHub HTTPS URL
- `repo_name` — required, alphanumeric + `-_`, ≤100 chars
- `target_file` — required, relative path, no `../` traversal
- `github_token` — required, starts with `ghp_`
- `anthropic_api_key` — required, starts with `sk-ant-`
- `line_number` — optional, positive integer if provided
- `column_number` — optional, positive integer if provided

**File Path Validation:**
```python
# Prevent path traversal
if "../" in target_file or target_file.startswith("/"):
    raise ValueError("Invalid target_file path")

# Check file exists after clone
if not os.path.exists(full_path):
    raise FileNotFoundError(f"File not found: {target_file}")
```

---

## 9. Deployment & Scaling

### 9.1 Environment Variables

```bash
# FastAPI
FASTAPI_ENV=production
LOG_LEVEL=INFO

# GitHub
GITHUB_TOKEN=ghp_xxx              # (optional fallback)
GITHUB_OWNER=myorg                # (can be overridden per request)

# Anthropic
ANTHROPIC_API_KEY=sk-ant-xxx

# WhatsApp
WHATSAPP_PHONE_ID=xxx
WHATSAPP_BUSINESS_ACCOUNT_ID=xxx
WHATSAPP_ACCESS_TOKEN=xxx
WHATSAPP_APP_SECRET=xxx
WHATSAPP_VERIFY_TOKEN=xxx

# WhatsApp Bridge (Node.js)
ALLOWED_NUMBER=1234567890
API_URL=http://localhost:8000

# Logging
LOG_FILE=server/logs/app.log
LOG_RETENTION_DAYS=7
```

### 9.2 Container Deployment (Docker)

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install -r requirements.txt

# Copy source
COPY server/ ./server/
COPY frontend/ ./frontend/

# Expose port
EXPOSE 8000

# Run
CMD ["uvicorn", "server.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### 9.3 Scaling Considerations

| Component | Scaling Strategy | Rationale |
|-----------|------------------|-----------|
| **FastAPI** | Horizontal (multiple uvicorn workers) | Stateless request processing |
| **Git Cloning** | Local cache + cleanup | Disk I/O bound; LRU eviction for large repos |
| **Claude API** | Rate limit queue (BullMQ/Redis) | Expensive; batch requests |
| **GitHub API** | Rate limit tracking + backoff | 5000 req/hr per token; use multiple tokens |
| **WhatsApp Bridge** | Single Node.js instance | WebSocket maintains 1 session per number |
| **Logging** | Async file handler (non-blocking) | Real-time log streaming |
| **Repository Intelligence** | Lazy loading + disk cache | AST parsing on-demand for new repos |

### 9.4 Monitoring & Observability

**Key Metrics:**
- Error fix success rate (%)
- Average pipeline latency (seconds)
- Claude API cost per fix (USD)
- GitHub API request volume
- WhatsApp message throughput
- Validation failure rate (%)
- Disk usage (temp_repos/)
- Log file size

**Alerting:**
- Pipeline failure rate > 10% → alert
- Claude API rate limit hit → queue requests
- GitHub API rate limit hit → backoff
- Disk usage > 80% → cleanup old repos
- Log file > 1GB → rotate

---

## 10. Integration Guide for Frontend

### 10.1 Drop-in Error Tracker

```typescript
// src/lib/errorTracker.ts

const AI_FIXER_ENDPOINT = "http://localhost:5000/api/ai-fix/";

const CONFIG = {
  repo_url: "https://github.com/YOUR_ORG/YOUR_REPO.git",
  repo_name: "YOUR_REPO",
  target_file: "src/pages/Dashboard.tsx",
  github_token: "ghp_...",
  github_owner: "YOUR_ORG",
  github_repo: "YOUR_REPO",
  anthropic_api_key: "sk-ant-...",
};

async function reportError(payload: object) {
  try {
    const response = await fetch(AI_FIXER_ENDPOINT, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const result = await response.json();
    console.log("AI Fixer Response:", result);
  } catch (err) {
    console.error("AI Fixer reporting failed", err);
  }
}

// Capture unhandled exceptions
window.addEventListener("error", (event) => {
  reportError({
    ...CONFIG,
    message: event.message,
    stack: event.error?.stack,
    line_number: event.lineno,
    column_number: event.colno,
    url: window.location.href,
    userAgent: navigator.userAgent,
    timestamp: Date.now(),
  });
});

// Capture unhandled promise rejections
window.addEventListener("unhandledrejection", (event) => {
  reportError({
    ...CONFIG,
    message: String(event.reason),
    stack: event.reason?.stack,
    url: window.location.href,
    userAgent: navigator.userAgent,
    timestamp: Date.now(),
  });
});

export { reportError };
```

**Usage:**
```typescript
// main.tsx or index.tsx
import "./lib/errorTracker";
```

### 10.2 React Error Boundary

```typescript
// src/components/ErrorBoundary.tsx

import React, { ReactNode } from "react";

const CONFIG = {
  repo_url: "https://github.com/YOUR_ORG/YOUR_REPO.git",
  repo_name: "YOUR_REPO",
  github_token: "ghp_...",
  // ... rest of config
};

interface Props {
  targetFile?: string;
  children: ReactNode;
}

interface State {
  hasError: boolean;
  error?: Error;
  prUrl?: string;
}

class ErrorBoundary extends React.Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError(error: Error) {
    return { hasError: true, error };
  }

  async componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    console.error("Error Boundary caught:", error, errorInfo);

    const payload = {
      ...CONFIG,
      target_file: this.props.targetFile || "src/pages/App.tsx",
      message: error.message,
      stack: error.stack,
      componentStack: errorInfo.componentStack,
      timestamp: Date.now(),
    };

    try {
      const res = await fetch("http://localhost:5000/api/ai-fix/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const result = await res.json();
      if (result.success) {
        this.setState({ prUrl: result.pr_url });
      }
    } catch (err) {
      console.error("Failed to report error", err);
    }
  }

  render() {
    if (this.state.hasError) {
      return (
        <div style={{ padding: "20px", fontFamily: "monospace" }}>
          <h1>❌ Something went wrong</h1>
          <p>{this.state.error?.message}</p>
          {this.state.prUrl && (
            <p>
              ✅ AI fix PR created:{" "}
              <a href={this.state.prUrl} target="_blank">
                {this.state.prUrl}
              </a>
            </p>
          )}
        </div>
      );
    }

    return this.props.children;
  }
}

export default ErrorBoundary;
```

**Usage:**
```typescript
// App.tsx
import ErrorBoundary from "./components/ErrorBoundary";

export default function App() {
  return (
    <ErrorBoundary targetFile="src/pages/App.tsx">
      <Dashboard />
    </ErrorBoundary>
  );
}
```

---

## 11. Technology Stack Summary

| Layer | Technology | Purpose |
|-------|-----------|---------|
| **Frontend Error Tracking** | JavaScript (window.onerror) | Capture runtime errors |
| **React Error Boundary** | React.Component | Catch render errors |
| **Backend API** | FastAPI (Python) | HTTP API server |
| **AI/LLM** | Claude Opus (Anthropic) | Fix generation + intent parsing |
| **GitHub Integration** | Octokit.js + git CLI | PR creation, repo cloning |
| **WhatsApp Integration** | WhatsApp-Web.js + Meta API | Message routing |
| **Session Management** | SQLite + custom store.js | Persist user credentials |
| **Logging** | Python logging + file handler | Real-time debugging |
| **Validation** | npm build/lint | Ensure fixes don't break code |
| **Code Analysis** | (Planned: tree-sitter, AST) | Repository intelligence |
| **Async Processing** | (Planned: BullMQ/Redis) | Queue & worker pattern |

---

## 12. Known Limitations & Future Work

### Current Limitations
- ⚠️ Single-threaded WhatsApp bridge (one session per number)
- ⚠️ No rate limiting on API endpoints
- ⚠️ No user authentication (relies on credentials in payload)
- ⚠️ Temp repos stored locally (disk space limited)
- ⚠️ No PR auto-merge (manual approval required)
- ⚠️ Limited to single file fixes (no multi-file changes)

### Planned Features
- 🔄 Multi-repo intelligence with semantic embeddings
- 🔄 Multi-agent planner/coder/reviewer workflow
- 🔄 Async job queue (BullMQ/Redis)
- 🔄 Database persistence (PostgreSQL)
- 🔄 PR auto-merge with confidence scores
- 🔄 Web UI dashboard with real-time logs
- 🔄 IDE plugin (VS Code extension)
- 🔄 Analytics & cost tracking
- 🔄 Team workspace management

---

## 13. Quick Reference: File Map

```
server/
├── main.py                           # FastAPI app entry
├── routes/
│   ├── ai_fix.py                    # POST /api/ai-fix/
│   ├── whatsapp.py                  # WhatsApp webhook
│   ├── chat.py                      # Chat completion
│   └── graph.py                     # Repository queries
├── services/
│   ├── clone_repo.py                # Git operations
│   ├── analyze_error.py             # Main pipeline
│   ├── generate_fix.py              # Claude integration
│   ├── apply_patch.py               # File patching
│   ├── validate_fix.py              # Build validation
│   ├── create_pr.py                 # PR creation
│   ├── graph_service.py             # (Planned)
│   └── session_store.py             # User sessions
├── agents/
│   ├── intent_parser.py             # LLM intent classifier
│   ├── status_agent.py              # GitHub status queries
│   ├── [coder_agent.py]             # (Planned)
│   └── [reviewer_agent.py]          # (Planned)
├── adapters/
│   ├── github_adapter.py            # GitHub API wrapper
│   └── whatsapp_adapter.py          # WhatsApp parser
├── models/
│   └── schemas.py                   # Pydantic models
├── utils/
│   ├── ai.py                        # Anthropic SDK
│   ├── github.py                    # GitHub utilities
│   ├── logger.py                    # Logging setup
│   ├── shell.py                     # Shell execution
│   └── [indexing.py]                # (Planned)
└── graphs/
    └── [repo_caches]/               # Cached graph data

frontend/
├── index.html                        # Standalone UI
├── [errorTracker.ts]                # (To integrate)
└── [ErrorBoundary.tsx]              # (To integrate)

whatsapp-bridge/
├── index.js                         # WhatsApp client
├── store.js                         # Session persistence
└── package.json

tests/
├── [test_ai_fix.py]                 # (Recommended)
└── [test_intent_parser.py]          # (Recommended)
```

---

## 14. Getting Started

### Prerequisites
```bash
# Backend
Python 3.11+
pip install -r requirements.txt

# WhatsApp Bridge
Node.js 16+
npm install

# GitHub
GitHub PAT (Personal Access Token)
Permissions: repo, workflow

# Anthropic
Anthropic API key
```

### Local Development
```bash
# Terminal 1: Backend
cd server
python -m uvicorn main:app --reload

# Terminal 2: WhatsApp Bridge
cd whatsapp-bridge
node index.js

# Terminal 3: Frontend (optional)
npm run dev
```

### Send First Error
```typescript
// In browser console
fetch("http://localhost:8000/api/ai-fix/", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({
    message: "Test error",
    stack: "Error: Test stack",
    line_number: 42,
    repo_url: "https://github.com/owner/repo.git",
    repo_name: "repo",
    target_file: "src/test.tsx",
    github_token: "ghp_xxx",
    github_owner: "owner",
    github_repo: "repo",
    anthropic_api_key: "sk-ant-xxx"
  })
}).then(r => r.json()).then(console.log);
```

---

**Document Version:** 1.0  
**Last Updated:** June 2026  
**Status:** Production Ready ✅
