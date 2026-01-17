# ADR-0031: ERP Chatbot Frontend Architecture – FastAPI Static SPA vs Next.js

## Status
Accepted

## Date
2026-01-17

## Context

The ERP Chatbot UI currently runs as a static single-page application (`chatbot_ui/index.html`, `styles.css`, `script.js`) served by a FastAPI app in `chatbot_ui/web_app.py`. The FastAPI layer:

- Serves the static assets.
- Exposes `/health` and `/config` for the UI itself.
- Proxies `/process_conversation` and `/backend_health` to the LangGraph/agent service at `LANGGRAPH_URL`, attaching `API_KEY` server-side.

The 2026 brief introduces a new floating-card chatbot design (AppShell + SidebarCard + ChatCard + InputBar) and a richer UX (clarification flow, typing indicator, retry, observability). We need to decide whether to:

1. Keep the current FastAPI-served static frontend and implement the new design directly in HTML/CSS/vanilla JS, or
2. Introduce a new Next.js (App Router) + Tailwind frontend that talks to the existing backend via an API proxy.

This decision should balance implementation effort for this thesis/evaluation phase, operational complexity, and future flexibility.

## Decision

For this iteration, we will **keep the FastAPI-served static frontend** and implement the floating-card chatbot UI by evolving the existing assets in `chatbot_ui/` (HTML/CSS/JS). We will **not** introduce a Next.js/Tailwind application at this stage.

The FastAPI app (`chatbot_ui/web_app.py`) remains the single entry point for:

- Serving the UI (`/`, `/styles.css`, `/script.js`).
- Providing configuration (`/config`).
- Exposing the UI health endpoint (`/health`).
- Proxying chat and backend health (`/process_conversation`, `/backend_health`) to `LANGGRAPH_URL`.

The new UI design will be applied within this architecture by:

- Refactoring `index.html` to use the AppShell/SidebarCard/ChatCard/InputBar structure described in the design spec.
- Updating `styles.css` to implement the floating-card visual system (radii, shadows, tokens, responsive layout).
- Extending `script.js` behaviors (which already include safe rendering, timeouts, clarifications, retry, autoscroll) to support any additional interactions required by the new design.

## Options and Trade-offs

### Option A – Keep FastAPI-Served Static SPA (Chosen)

**Pros**

- **Low operational complexity**: Single Python service to run and deploy; no Node.js runtime or separate hosting for a React/Next app.
- **Leverages existing implementation**: The current `ERPChatbot` class already implements:
  - Correct message flow and server-managed API keys.
  - Abortable requests with `AbortController` and a Stop button.
  - Clarification handling, retry, observability hooks, and improved accessibility.
  Reusing this logic avoids re-implementing a mature, battle-tested flow.
- **Fastest path to the new design**: The floating-card UI can be realized with structural HTML tweaks plus CSS, without re-platforming.
- **Good enough for internal/thesis use**: SEO and marketing-site concerns are irrelevant; a static SPA is sufficient for evaluation and demos.
- **Python-first stack alignment**: The broader system (LangGraph, MCP servers, evaluation tooling) is Python-centric; staying within the same operational environment simplifies local and remote deployments.

**Cons**

- **Limited componentization**: Vanilla JS and a single `script.js` file require discipline to keep code modular; React/Next would offer stronger component boundaries.
- **Less reusable design system**: Tailwind or a component library would provide a richer tokenized design system that can be shared across products.
- **No SSR/ISR**: While not needed for this app, server-side rendering and advanced routing are easier with Next.js.

### Option B – Next.js (App Router) + Tailwind Frontend (Not Chosen for Now)

**Pros**

- **Modern component model**: React components and hooks make the UI easier to reason about, test, and extend in a product setting.
- **Built-in routing and layouts**: Next.js App Router provides nested layouts and routing that could support multi-page flows (e.g., analytics, admin, evaluation dashboards).
- **Tailwind & design tokens**: Tailwind would make it straightforward to encode the design tokens from the floating-card spec and keep designs consistent.
- **Easier future integrations**: Features like authentication, analytics, and A/B testing integrate naturally with the Next/React ecosystem.

**Cons**

- **Higher operational and tooling overhead**:
  - Requires Node.js, package management, build steps, and potentially a separate deployment target.
  - Increases CI/CD complexity compared to a pure-Python stack.
- **Significant reimplementation cost**:
  - All existing behaviors in `script.js` (message flow, clarifications, retry, autoscroll, accessibility, observability) would need to be reimplemented in React.
  - Increases short-term risk of regressions in a UI that is already functioning well.
- **Overkill for current scope**:
  - The main user journey is a single chat screen; dynamic routing and SSR bring little immediate benefit.
  - For a thesis-style evaluation, added complexity does not materially improve research outcomes.

## Integration Plan with `/process_conversation` and `/health`

### Chosen Architecture – FastAPI Static SPA

**API surface (FastAPI)**

- `GET /` → serves `index.html` (floating-card UI once implemented).
- `GET /styles.css` → serves CSS (including new design tokens and responsive layout).
- `GET /script.js` → serves the client logic (`ERPChatbot`).
- `GET /health` → UI service health.
- `GET /config` → returns:
  - `langgraph_url` (backend base URL, default `http://localhost:5001`).
  - `api_key_set` (whether `API_KEY` is configured server-side).
  - UI `version`.
- `GET /backend_health` → proxies to `${LANGGRAPH_URL}/health`, classifies result as `online` / `degraded`.
- `POST /process_conversation` → proxies to `${LANGGRAPH_URL}/process_conversation`, attaching `API_KEY` if present.

**Browser integration (`script.js`)**

- On startup, `initConfig()`:
  - Calls `GET /config`.
  - If `api_key_set` is `true`, treats the API key as **server-managed**:
    - Uses same-origin calls (`/process_conversation`, `/backend_health`) for chat and health.
    - Disables the API key input in the settings modal and marks it as “Configured on server”.
  - If `api_key_set` is `false`, falls back to direct calls to `langgraph_url` and allows a dev-only, in-memory API key.
- Health behavior:
  - If server-managed: `checkServiceHealth()` calls `/backend_health`.
  - Otherwise: calls `{serviceUrl}/health` or `/health` as a fallback.
- Chat behavior:
  - `sendToService()` sends `{ messages: this.messages }` (and `api_key` only when not server-managed) to:
    - `POST /process_conversation` when server-managed, or
    - `POST {serviceUrl}/process_conversation` in dev-only direct mode.
- The new floating-card UI does **not** change these endpoints; it only changes layout and styling. All integration remains centered on FastAPI’s `/process_conversation`, `/backend_health`, `/health`, and `/config`.

### Alternative Architecture – Next.js + Tailwind (Reference Only)

If a future iteration introduces Next.js, the intended integration pattern would be:

- Run the Next.js app as a separate frontend (e.g., `frontend/`), with:
  - `app/api/chat/route.ts` proxying to `POST /process_conversation` on the FastAPI service (or directly to `LANGGRAPH_URL`), attaching `API_KEY` from Next environment variables.
  - `app/api/health/route.ts` proxying to `GET /backend_health` or `GET /health`.
- Client-side React components:
  - Use `fetch('/api/chat', ...)` and `fetch('/api/health')` from the browser, never exposing credentials.
  - Implement the same UX behaviors (clarifications, retry, autoscroll, typing indicator) using the existing design spec as the source of truth.
- In that world, `chatbot_ui/web_app.py` may:
  - Continue to serve as the backend API only (no longer serving HTML/CSS/JS), or
  - Be replaced by a dedicated backend service behind an API gateway.

This alternative is explicitly **not part of the current implementation** but is documented here to make the transition path clear if a full React/Next frontend becomes a priority.

## Consequences

- All front-end work for the “front-end-fixes” sprint and the floating-card redesign will:
  - Live in `chatbot_ui/index.html`, `chatbot_ui/styles.css`, and `chatbot_ui/script.js`.
  - Reuse the existing FastAPI proxy and configuration endpoints unchanged.
- The project remains a **Python-first, single-service** deployment for now, which:
  - Simplifies local development and thesis/evaluation workflows.
  - Avoids introducing new build tooling and runtime dependencies.
- If a future ADR decides to adopt Next.js, this document and the existing design spec provide a clear mapping from the current vanilla JS implementation to a component-based React UI.

