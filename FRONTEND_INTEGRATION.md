# Frontend Integration Guide

## What you're integrating

Your frontend captures errors and sends them to `POST http://localhost:5000/api/ai-fix/`. Two mechanisms cover different error types:

| Mechanism | Catches |
|-----------|---------|
| `window.onerror` / `window.addEventListener` | Unhandled JS exceptions, script errors |
| React Error Boundary | React render/lifecycle crashes |

---

## 1. Drop-in Error Tracker

Create this file anywhere in your project — e.g. `src/lib/errorTracker.ts`:

```ts
const AI_FIXER_ENDPOINT = "http://localhost:5000/api/ai-fix/";

const CONFIG = {
  repo_url: "https://github.com/YOUR_ORG/YOUR_REPO.git",
  repo_name: "YOUR_REPO",
  target_file: "src/pages/Dashboard.tsx",   // update per error if needed
  github_token: "ghp_...",
  github_owner: "YOUR_ORG",
  github_repo: "YOUR_REPO",
  anthropic_api_key: "sk-ant-...",
};

async function reportError(payload: object) {
  try {
    await fetch(AI_FIXER_ENDPOINT, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  } catch (err) {
    console.error("AI Fixer reporting failed", err);
  }
}

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
```

Import it once at your app entry point:

```ts
// main.tsx or index.tsx
import "./lib/errorTracker";
```

---

## 2. React Error Boundary

Create `src/components/ErrorBoundary.tsx`:

```tsx
import React from "react";

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

interface Props {
  targetFile?: string;   // override per boundary
  children: React.ReactNode;
}

interface State {
  hasError: boolean;
}

class ErrorBoundary extends React.Component<Props, State> {
  state = { hasError: false };

  componentDidCatch(error: Error, info: React.ErrorInfo) {
    fetch(AI_FIXER_ENDPOINT, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        ...CONFIG,
        target_file: this.props.targetFile ?? CONFIG.target_file,
        message: error.message,
        stack: error.stack,
        componentStack: info.componentStack,
        url: window.location.href,
        timestamp: Date.now(),
      }),
    });
  }

  static getDerivedStateFromError() {
    return { hasError: true };
  }

  render() {
    if (this.state.hasError) return <p>Something went wrong.</p>;
    return this.props.children;
  }
}

export default ErrorBoundary;
```

Wrap any component tree — and pass `targetFile` to tell the AI exactly which file to fix:

```tsx
// App.tsx
import ErrorBoundary from "./components/ErrorBoundary";

function App() {
  return (
    <ErrorBoundary targetFile="src/pages/Dashboard.tsx">
      <Dashboard />
    </ErrorBoundary>
  );
}
```

---

## 3. Error flow end to end

```
User hits a runtime crash
        │
        ▼
window.onerror  OR  ErrorBoundary.componentDidCatch
        │
        ▼
POST /api/ai-fix/  (with error + repo + keys)
        │
        ▼
Backend clones repo → Claude generates fix → validates → opens draft PR
        │
        ▼
You get a GitHub PR link — review and merge
```

---

## Tips

- **`targetFile`** — the more accurately this points to the crashing file, the better Claude's fix. Parse it from the stack trace for full automation.
- **Keep keys server-side in production** — expose a thin proxy endpoint on your own backend that injects `github_token` and `anthropic_api_key`, so they never ship to the browser.
- **`target_file` from stack trace** — you can extract it automatically:
  ```ts
  const match = event.error?.stack?.match(/src\/[^\s:)]+/);
  const target_file = match?.[0] ?? "src/pages/Dashboard.tsx";
  ```
