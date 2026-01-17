# Technical Specification – ERP Chatbot Front-End Fixes

## 1. Technical Context

- **Frontend stack**
  - Static, single-page UI in `chatbot_ui/index.html` with plain JavaScript (`chatbot_ui/script.js`) and CSS (`chatbot_ui/styles.css`).
  - No bundler or framework; assets are served directly by the FastAPI app in `chatbot_ui/web_app.py`.
  - Chat logic is encapsulated in a single `ERPChatbot` class that owns:
    - Connection config (`serviceUrl`, `apiKey`, `sessionId`)
    - Conversation state (`messages`, `conversations`, `currentConversationId`, `lastWasClarification`)
    - UI state (`isLoading`) and DOM element references (status, history, chat messages, modals, etc.).
  - Network calls use `fetch` directly against `this.serviceUrl` (currently defaulting to `http://localhost:5001`) with JSON payloads like:
    - `GET {serviceUrl}/health`
    - `POST {serviceUrl}/process_conversation` with `{ messages, api_key }`.

- **Backend / serving layer**
  - `chatbot_ui/web_app.py` is a FastAPI app that:
    - Serves `index.html`, `styles.css`, and `script.js`.
    - Exposes `/health` for the web UI itself.
    - Exposes `/config` returning:
      - `langgraph_url` (from `LANGGRAPH_URL` env, default `http://localhost:5001`)
      - `api_key_set` (bool of `API_KEY` env presence)
  - The actual chat backend (LangGraph / ERP agent) is assumed to run separately on `LANGGRAPH_URL` and is what `process_conversation` is targeting today.

- **Current UX behaviors (relevant to this task)**
  - Message send flow:
    - `sendMessage()`:
      - Validates input and `isLoading`.
      - Clears input, sets `isLoading`, shows full-screen `loadingOverlay`.
      - Calls `addMessage('user', message)` to render the user turn.
      - Pushes `{ role: 'user', content: message }` into `this.messages`.
      - Calls `sendToService(message)` and then renders the assistant response via `addMessage('bot', ...)`.
  - `sendToService(userInput)`:
      - Builds payload: `messages: this.messages.concat([{ role: 'user', content: userInput }])` and `api_key: this.apiKey`.
      - Uses `fetch(..., { timeout: 60000 })`, which is not a valid browser fetch option.
  - Assistant rendering:
    - `addMessage` creates DOM nodes and assigns `contentDiv.innerHTML = this.formatMessageContent(content)`.
    - `formatMessageContent` applies simple regex replacements for `**bold**`, `*italic*`, `` `code` ``, and newlines → `<br>` without escaping HTML first.
  - Loading state:
    - `setLoading(loading)` toggles `this.isLoading`, disables `sendBtn` when loading and shows/hides a full-screen `.loading-overlay` that blocks reading history.
  - Conversation history:
    - Stored in `this.conversations` and persisted to `localStorage` (`erp_chatbot_conversations`).
    - Rendered as clickable `<div class="conversation-item">` elements with click handlers only (not keyboard-focusable controls).
  - Settings:
    - Settings modal allows editing `serviceUrl` (readonly), `apiKey`, and `sessionId`.
    - Settings are stored in `localStorage` under `erp_chatbot_settings`, including the API key.

## 2. Scope and Difficulty

- **Scope**: Front-end behavior and security fixes plus minor backend adjustments to support safer credential handling. Includes UX improvements for loading, history accessibility, clarification messages, and autoscroll.
- **Difficulty**: **Medium**.
  - Logic changes span multiple concerns (networking, rendering, accessibility, state management).
  - No complex algorithms, but careful coordination is needed to avoid regressions in message flow and UX.

## 3. Implementation Approach

### 3.1 Correct Message Flow (Fix Duplicate User Turn)

**Problem**
- `sendMessage()` already pushes `{ role: 'user', content: message }` into `this.messages`.
- `sendToService(userInput)` then recomputes `messages` as `this.messages.concat([{ role: 'user', content: userInput }])`, effectively duplicating the latest user message in the payload sent to the backend.

**Design**
- Treat the client-side `this.messages` array as the single source of truth.
- Ensure the payload for `/process_conversation` is exactly `this.messages` (no extra concat) unless the server intentionally returns a canonical message history to replace it.

**Planned Changes**
- Update `sendToService(userInput)`:
  - Simplest change:
    - Build payload as:
      - `messages: this.messages`
      - `api_key: this.apiKey` (until credentials are moved server-side).
    - Optionally remove the now-redundant `userInput` parameter in a follow-up refactor.
- Keep existing behavior where, if `response.messages` is present and an array, we replace `this.messages` with it; otherwise we append a single assistant turn.

### 3.2 Safe Assistant Rendering (XSS Mitigation)

**Problem**
- Assistant content is interpolated directly into the DOM via:
  - `contentDiv.innerHTML = formatMessageContent(content);`
- `formatMessageContent` injects HTML (`<strong>`, `<em>`, `<code>`, `<br>`) but does **not** escape HTML characters first.
- A malicious or buggy backend could return strings containing `<script>` tags or event handlers that will execute in the user’s browser (classic XSS).

**Design Choice**
- For this sprint, adopt a **safe-HTML-with-minimal-formatting** approach:
  - Escape user/assistant-supplied content before applying the light Markdown-style formatting.
  - Keep the existing Markdown subset (bold, italic, inline code, line breaks) without adding heavy dependencies.
- Leave open a future enhancement to swap in a Markdown renderer + sanitizer (e.g., marked + DOMPurify) if the UI grows more complex.

**Planned Changes**
- Add a small utility (inside `ERPChatbot` or as a local helper) to escape HTML:
  - `escapeHtml(str: string): string` that replaces `&`, `<`, `>`, `"`, `'` with their HTML entities.
- Update `formatMessageContent(content)` to:
  - Handle falsy inputs robustly (`content || ''`).
  - Apply `escapeHtml` first, then the existing regex replacements to produce safe, structured HTML:
    - `**bold**` → `<strong>…</strong>`
    - `*italic*` → `<em>…</em>`
    - `` `code` `` → `<code>…</code>`
    - Newlines → `<br>`
- Keep using `innerHTML` in `addMessage`, but ensure the only tags present are the ones we inject after escaping.

### 3.3 Reliable Fetch Timeouts + Stop Button (AbortController)

**Problem**
- Calls to `fetch` currently pass a `timeout` option, which is ignored by browsers:
  - `fetch(url, { method: 'GET', timeout: 5000 })` (health check)
  - `fetch(url, { method: 'POST', ..., timeout: 60000 })` (chat requests)
- Long-running or stuck requests cannot be cancelled; UI only has a blocking overlay.

**Design**
- Introduce a reusable `fetchWithTimeout` helper that wraps `fetch` with `AbortController`.
- Track the in-flight controller on the `ERPChatbot` instance to enable:
  - Automatic timeout abort.
  - Manual user cancellation via a “Stop” button.
- Replace the full-screen loading overlay with:
  - Inline typing indicator (P1 UX improvement).
  - A Stop button in the input area to cancel the current request.

**Planned Changes**
- Add instance property:
  - `this.currentRequestController = null;`
- Implement `async fetchWithTimeout(url, options = {}, timeoutMs = 60000)`:
  - Create `const controller = new AbortController();`
  - Merge `options.signal` with `controller.signal` (respect a pre-provided signal if needed).
  - Start a timer: `setTimeout(() => controller.abort(), timeoutMs);`
  - Save `this.currentRequestController = controller` for manual cancellation.
  - Call `fetch(url, { ...options, signal: controller.signal })`.
  - Clear the timeout in `finally` and reset `this.currentRequestController = null`.
  - Normalize abort errors to a clear message (“Request timed out” or “Request was cancelled.”).
- Update network callers:
  - `checkServiceHealth()` → use `fetchWithTimeout(this.serviceUrl + '/health', { method: 'GET' }, 5000)`.
  - `sendToService()` → use `fetchWithTimeout(this.serviceUrl + '/process_conversation', { method: 'POST', headers, body }, 60000)`.
- Add a `stopCurrentRequest()` method:
  - If `this.currentRequestController` is set, call `.abort()`.
  - Reset loading state and typing indicator appropriately.
- UI changes:
  - Add a `Stop` button in the input area (e.g., next to char counter) in `index.html`:
    - `<button id="stopBtn" class="stop-btn" type="button" aria-label="Stop response" hidden>⏹</button>`
  - Wire it in `bindEvents()` to call `stopCurrentRequest()`.
  - Update `setLoading(loading)` to:
    - Toggle visibility/enabled state of `stopBtn`.
    - Manage inline typing indicator (see 3.6).
  - Keep `sendBtn` disabled while loading, but keep input readable so the user can review history.

### 3.4 API Key Handling and Local Storage (Security / Architecture)

**Problem**
- The API key is:
  - Hardcoded initially in `script.js` as `'supersecretapikey'`.
  - Editable via settings modal and stored in `localStorage` under `erp_chatbot_settings`.
- Any script running in the page context (including injected scripts in case of XSS) can read this key.
- This is not suitable for anything beyond local dev/demo.

**Design Goal**
- Move API key handling to the backend where possible and minimize exposure in the frontend.
- For local dev flexibility, allow optional client-provided keys but avoid persisting them across sessions by default.

**Backend Plan (web_app.py)**
- Extend `web_app.py` to act as a thin proxy for chat requests:
  - Add a `POST /process_conversation` endpoint that:
    - Reads the incoming body (user messages).
    - Attaches the server-side API key from `os.getenv("API_KEY")` if required by the LangGraph service (e.g., via request header or `api_key` field).
    - Forwards the request to `LANGGRAPH_URL + '/process_conversation'`.
    - Returns the proxied response.
- Optionally expose service health and status from the backend:
  - Add `/backend_health` on `web_app.py` that calls `LANGGRAPH_URL/health` with server-side credentials and returns a simplified status for the UI.

**Frontend Plan (script.js / index.html)**
- Configuration:
  - On initialization, fetch `/config` to derive:
    - `this.serviceUrl` → either:
      - Same-origin proxy (preferred): e.g., `this.serviceUrl = ''` and always call `'/process_conversation'`, or
      - Direct service URL (fallback): use `config.langgraph_url`.
    - A flag `this.apiKeyIsServerManaged = config.api_key_set`.
  - Remove the hardcoded default `'supersecretapikey'`.
- Settings modal behavior:
  - If `api_key_set` is `true`, treat the API key as managed by the server:
    - Hide or disable the API key input and show a read-only “Configured on server” indicator.
  - For dev-only scenarios where the user must provide a key:
    - Keep the input but **do not persist** the key in `localStorage`.
    - Only hold it in memory (`this.apiKey`) for the session if absolutely necessary.
- Local storage:
  - Update `saveSettings()` and `loadSettings()` to:
    - Stop reading/writing `apiKey` from/to `localStorage`.
    - Keep persisting only non-sensitive preferences (e.g., `serviceUrl`, `sessionId` if needed).
- Request payload:
  - Once proxying is in place, remove `api_key` from the payload entirely; server will inject it.
  - Until proxying is complete, keep support for `api_key` in payload but avoid persisting it in `localStorage`.

### 3.5 Accessibility Improvements (History, Buttons, Modals, Log)

**Problems**
- Conversation history entries are `<div class="conversation-item">` with click handlers only:
  - Not keyboard-focusable by default.
  - Lack ARIA semantics for screen readers.
- Icon-only buttons (`helpBtn`, `settingsBtn`, `sendBtn`, `clearHistoryBtn`, modal close buttons) rely solely on `title` or visual icons.
- Modals lack focus management and ARIA dialog semantics.
- Chat message list is a plain `<div>` without `role="log"` or `aria-live` attributes.

**Design**
- Use semantic controls and ARIA attributes to make the UI keyboard- and screen-reader-friendly.

**Planned Changes**
- Conversation history (`renderConversationHistory` and CSS):
  - Change each history item from a `<div>` to a `<button>`:
    - `const item = document.createElement('button');`
    - Set `type="button"` and `className = 'conversation-item';`.
    - Add `aria-label` summarizing the conversation (e.g., `"Conversation: {title}"`).
  - Update CSS to support `.conversation-item` as a button (reset default button styles as needed).
  - This automatically enables Tab navigation and Enter/Space activation.
- Icon-only buttons (`index.html`):
  - Add `aria-label` attributes:
    - Help: `"Open help"`.
    - Settings: `"Open settings"`.
    - Clear history: `"Clear all conversations"`.
    - Send: `"Send message"`.
    - Modal close buttons: `"Close help"`, `"Close settings"`.
  - Ensure each button uses `type="button"` to avoid form submission defaults.
- Modals:
  - Add ARIA roles:
    - On `.modal` or `.modal-content`: `role="dialog"`, `aria-modal="true"`.
    - Add `id` to each modal heading (`helpModalTitle`, `settingsModalTitle`) and set `aria-labelledby` on the dialog container.
  - Focus management in `script.js`:
    - Track the previously focused element when opening a modal (`this.lastFocusedElement`).
    - On `showModal`, move focus to the modal’s first focusable control (e.g., close button or first interactive element).
    - Implement a simple focus trap:
      - On `keydown` within the modal, intercept Tab/Shift+Tab and cycle through focusable elements inside the modal.
    - On `hideModal`, restore focus to `this.lastFocusedElement`.
- Chat message list:
  - Update `index.html` to set:
    - `role="log"`, `aria-live="polite"`, `aria-relevant="additions"` on `#chatMessages`.
  - Ensure new messages are appended at the end and content changes are incremental to support assistive tech.

### 3.6 Inline Typing Indicator and Non-Blocking Loading

**Problems**
- Full-screen loading overlay (`#loadingOverlay`) blocks:
  - Reading previous messages while waiting.
  - Accessing conversation history.
- Users cannot cancel a long-running response except by closing the page.

**Design**
- Replace the blocking overlay with:
  - Inline typing indicator inside the message list.
  - A Stop button integrated into the chat input (see 3.3).
- Keep the overlay component available for future full-page failure states if desired but decouple it from the standard send flow.

**Planned Changes**
- Typing indicator:
  - Add methods on `ERPChatbot`:
    - `showTypingIndicator()`:
      - Append a dedicated element to `#chatMessages`, e.g., `<div class="message bot typing-indicator">` with a subtle animated dot or text such as “Assistant is thinking…”.
    - `hideTypingIndicator()`:
      - Remove or hide that element.
  - Call `showTypingIndicator()` from `setLoading(true)` and `hideTypingIndicator()` from `setLoading(false)` and when a request is aborted.
  - Add styles in `styles.css` for `.typing-indicator`.
- Loading overlay:
  - Stop toggling `loadingOverlay` in `setLoading`.
  - Optionally repurpose `loadingOverlay` for non-standard states (e.g., initial boot failure) or leave it unused but harmless.

### 3.7 Clarification UX Enhancements

**Current Behavior**
- Backend responses may indicate clarifications via fields like:
  - `response.clarify` or `response.operation === 'clarify'`.
- UI:
  - Derives `isClarification` from these flags.
  - Passes `isClarification` into `addMessage`, which adds the `.clarification` CSS class (already styled in `styles.css`).
  - When rehydrating a conversation (`loadConversation`), uses a simple heuristic `message.content.includes('🤔')` to classify clarifications.

**Design**
- Make clarifications visually clearer and support optional quick replies if the backend provides options.

**Planned Changes**
- Clarification labelling:
  - Extend `addMessage` for bot messages with `isClarification`:
    - Inject a small label above the content (e.g., `Clarification needed`) using a child element within `.message-content`.
    - Preserve existing `.message.clarification` styles for background/border.
- Quick reply chips (optional, backend-dependent):
  - If the response payload includes a structured list of clarification options (e.g., `response.clarification_options` or similar), render them as a set of buttons beneath the clarification message.
  - Clicking a chip:
    - Inserts the chosen text into the input or directly sends it as the next user message (configurable).
  - For now, design the hooks (e.g., an optional `options` argument to `addMessage`) so backend integration can be wired with minimal changes once the actual field name is confirmed.
- Conversation reload behavior:
  - Keep the `.clarification` class mapping when rehydrating but prefer metadata from stored messages (if available) over emoji heuristics in future iterations.

### 3.8 Autoscroll Behavior & “Jump to Latest”

**Problem**
- After every message is added, `addMessage` forces:
  - `this.chatMessages.scrollTop = this.chatMessages.scrollHeight;`
- This can be frustrating if the user scrolls up to review earlier messages while new responses arrive.

**Design**
- Auto-scroll only when the user is already near the bottom of the message list.
- When the user has scrolled up, keep their scroll position and show a small “Jump to latest” control when new messages arrive.

**Planned Changes**
- State and scroll tracking:
  - Add `this.isUserNearBottom = true;`.
  - Attach a `scroll` listener to `#chatMessages`:
    - Compute `distanceFromBottom = scrollHeight - scrollTop - clientHeight`.
    - If `distanceFromBottom > 100px`, set `this.isUserNearBottom = false`.
    - Otherwise, set `this.isUserNearBottom = true`.
- Message append behavior:
  - In `addMessage`, replace unconditional scroll with:
    - `if (this.isUserNearBottom) { scrollToBottom(); }` where `scrollToBottom()` sets `scrollTop` to `scrollHeight`.
- “Jump to latest” UI:
  - Add a small pill/button (e.g., `#jumpToLatestBtn`) overlayed near the bottom of the chat area in `index.html`.
  - Show the button when:
    - New messages arrive and `!this.isUserNearBottom`.
  - Clicking the button:
    - Scrolls to bottom and hides the button.
  - Style via `styles.css` as a subtle but noticeable control (e.g., rounded pill with text “Jump to latest”).

### 3.9 Observability and Retry Hooks (Optional Enhancements)

**Current Behavior**
- `logInteraction(userInput, response)` logs a structured object (timestamp, sessionId, userInput, response, conversationId) to `console.log`.
- No explicit measurement of latency or error classification beyond HTTP status mapping in `sendToService`.
- No explicit “Retry” action in the UI for failed responses.

**Design**
- Improve observability for evaluation and debugging while keeping privacy in mind.

**Planned Changes**
- Latency and error metrics:
  - Record request start time in `sendMessage` before calling `sendToService`.
  - On success or failure, compute `durationMs` and include in `logInteraction`.
  - Include a simple `status` field (e.g., `"ok"`, `"network_error"`, `"timeout"`, `"backend_error"`).
- Retry affordance:
  - For failed assistant responses (network errors, timeouts, non-2xx), render a small “Retry” button alongside the error message.
  - Implement a helper (`retryLastUserMessage`) that:
    - Re-sends the last user message using the current conversation state.
    - Tracks retries to avoid infinite loops.
  - This will be implemented carefully to avoid re-duplicating messages, leveraging the fixed message flow from 3.1.

## 4. Source Code Structure Changes

**Frontend**
- `chatbot_ui/script.js`
  - Modify:
    - `ERPChatbot` constructor: initialize new state fields (`currentRequestController`, `apiKeyIsServerManaged`, `isUserNearBottom`).
    - `initializeElements`: capture new DOM references (`stopBtn`, `jumpToLatestBtn`, possibly typing indicator container).
    - `bindEvents`: attach listeners for:
      - Stop button click.
      - `scroll` on `chatMessages`.
      - Modal focus trap handling.
    - `sendMessage` and `sendToService`: integrate with `fetchWithTimeout`, measure latency, and remove duplicate user turn from payload.
    - `checkServiceHealth`: switch to `fetchWithTimeout` and optionally use `/backend_health`.
    - `addMessage` and `formatMessageContent`: implement escaping, safe formatting, and updated scroll logic.
    - `setLoading`, `showTypingIndicator`, `hideTypingIndicator`, `stopCurrentRequest`: manage inline loading and cancellation.
    - `saveSettings` / `loadSettings`: stop persisting `apiKey` and handle `/config`-derived configuration.
  - Add:
    - `escapeHtml` helper for safe content rendering.
    - `fetchWithTimeout` helper.
    - Optional helpers for focus management within modals and retry logic.

- `chatbot_ui/index.html`
  - Update markup for:
    - Chat messages container: add ARIA attributes (`role="log"`, `aria-live`, `aria-relevant`).
    - Conversation history container: ensure it can host `<button>`-based items.
    - Icon buttons: add `aria-label` and `type="button"`.
    - Modals: add `role="dialog"`, `aria-modal`, `aria-labelledby`.
    - Input area: add Stop button and “Jump to latest” button/pill element.
    - Optionally tweak settings modal copy to reflect server-managed API key.

- `chatbot_ui/styles.css`
  - Adjust:
    - `.conversation-item` styles to support `<button>` elements (reset default button borders/backgrounds).
    - Add styles for:
      - `.typing-indicator` message.
      - `#jumpToLatestBtn` pill/button.
      - `.stop-btn` near input.
    - Ensure focus-visible styles are present for new focusable elements (history items, Stop, Jump buttons).
  - Optionally de-emphasize or repurpose `.loading-overlay` if no longer used in the main flow.

**Backend**
- `chatbot_ui/web_app.py`
  - Add proxy route(s):
    - `POST /process_conversation` to forward chat payloads to `LANGGRAPH_URL` with `API_KEY` from environment.
    - Optionally `GET /backend_health` for consolidated health display.
  - No breaking changes to existing `/`, `/styles.css`, `/script.js`, or `/config` endpoints.

## 5. Data Model / API / Interface Changes

- **Frontend conversation state**
  - No structural changes to the in-memory `messages` and `conversations` data shapes; they remain arrays of `{ role, content, ... }`.
  - Clarification options (if implemented) may be stored transiently or as metadata on messages, but the core `{ role, content }` shape remains for backend compatibility.

- **Network payloads**
  - Short-term:
    - Continue sending `{ messages, api_key? }` to the chat backend as today.
    - Fix duplication by sending `messages: this.messages` only.
  - Mid-term (after proxying):
    - Frontend sends only `{ messages }` to `web_app.py`’s `/process_conversation`.
    - Backend attaches API key from environment and forwards.

- **Local storage**
  - `erp_chatbot_settings`:
    - Remove `apiKey` from stored settings.
    - Keep only non-sensitive fields (e.g., `serviceUrl` if still user-configurable, `sessionId` if we decide it should persist).
  - `erp_chatbot_conversations`:
    - No schema change; still an array of conversation objects `{ id, title, messages, timestamp, lastMessage }`.

- **UI interfaces**
  - New user-facing controls:
    - Stop button for cancelling in-flight responses.
    - Jump to latest button when user is scrolled up.
    - Clarification label and optional quick reply chips on clarification messages.
  - Accessibility:
    - Conversation history items become accessible buttons.
    - Modals and chat log gain ARIA semantics and focus management.

## 6. Verification Approach

- **Static checks / linting**
  - There is no dedicated JS lint configuration in this repo; changes will be validated by:
    - Ensuring `script.js` remains valid ES syntax and runs in modern browsers.
    - Running `python -m compileall` for Python changes (especially `web_app.py`) as a basic syntax check if needed.

- **Manual functional testing**
  - Start the web UI server:
    - From repo root: `python chatbot_ui/web_app.py`.
  - Ensure the LangGraph / ERP backend is running at the configured `LANGGRAPH_URL` (default `http://localhost:5001`) or that the proxy in `web_app.py` can reach it.
  - Test cases:
    - **Message flow**
      - Send a simple query; inspect network payload (browser devtools) to confirm:
        - Each user turn appears exactly once in `messages`.
      - Confirm messages display in correct order with timestamps and roles.
    - **XSS safety**
      - From backend or via mocked response, return content containing HTML tags (e.g., `<script>alert(1)</script>`, `<img onerror="...">`).
      - Verify:
        - Tags are rendered as text, not executed.
        - Existing Markdown-like formatting still works.
    - **Timeouts and Stop**
      - Simulate a slow backend or use an artificial delay endpoint.
      - Confirm:
        - Requests are aborted after the configured timeout with a user-visible error.
        - Clicking “Stop” cancels the response and clears the typing indicator.
    - **API key handling**
      - With `API_KEY` set on the backend:
        - Confirm the UI reports that an API key is configured (via `/config`).
        - Ensure no API key is ever visible in devtools storage (`localStorage`) or in the page source.
      - Without `API_KEY` set:
        - If a dev-mode UI flow is implemented, confirm providing a key does not persist it in `localStorage`.
    - **Accessibility / keyboard navigation**
      - Use Tab/Shift+Tab to:
        - Navigate to conversation history items and activate them with Enter/Space.
        - Open and close modals and verify focus is trapped within and restored on close.
      - Verify that screen readers announce chat updates from `#chatMessages` due to ARIA `role="log"` and `aria-live`.
    - **Inline typing & autoscroll**
      - While a response is in progress:
        - Confirm conversation history and previous messages remain scrollable.
        - Verify the inline typing indicator appears and disappears correctly.
      - Scroll up during a long response:
        - Confirm the UI does not force-scroll.
        - Confirm a “Jump to latest” control appears, and clicking it scrolls back to the bottom.
    - **Clarification UX**
      - Trigger clarification responses from the backend (where `clarify` or `operation === 'clarify'` is set).
      - Confirm:
        - Clarification messages have distinct styling and label.
        - (If implemented) quick reply chips appear and send follow-up messages correctly.

- **Regression checks**
  - Ensure:
    - Existing conversation persistence (`localStorage` conversations) continues to work.
    - Sample queries, status indicator, and modals function as before, with improved accessibility and no new console errors.

## 7. Notes on Upcoming Design Changes

- The user plans to provide updated visual design concepts.
- This implementation plan intentionally keeps structural HTML changes minimal and focused on semantics/accessibility so that:
  - New visual styles can be applied mostly via CSS updates.
  - The underlying JS behaviors (timeouts, accessibility, security) remain compatible with redesigned layouts.

## 8. New Floating-Card Chatbot UI – Design Spec

This section defines the target “floating-card” UI that will replace the current split-screen layout. It is deliberately implementation-agnostic so it can be realized either in the existing static HTML app or in a future Next.js/Tailwind implementation.

### 8.1 Layout & Regions

- **AppShell**
  - Full-viewport container with a subtle, dark gradient background and a centered content column.
  - Max width `1200–1280px`, horizontal padding `24px` desktop, `16px` mobile.
  - Uses a vertical flex layout: top spacing → main content grid → small bottom padding.
  - Provides a consistent background for both cards so they appear as elevated surfaces floating over the shell.

- **Main Grid (Desktop)**
  - Two-column grid inside the AppShell:
    - Column 1 (SidebarCard): fixed width `320px`.
    - Column 2 (ChatCard): flexible width (`minmax(0, 1fr)`), taking remaining space.
  - Column gap `24px`.
  - Cards share the same vertical height where possible; ChatCard scrolls internally for messages.

- **SidebarCard**
  - A vertically-stacked card with three primary zones:
    - Header:
      - Product name/title (e.g., “ERP Assistant”).
      - Small subtitle (“Workspace: <env>” or “ERP SQL Assistant” as copy).
      - Service status indicator inline with subtitle (dot + text).
    - Body:
      - Conversation history list (scrollable).
      - Optional filters or chips (e.g., “All / Today / Starred”) can be added later.
    - Footer:
      - `New chat` primary action.
      - `Clear history` secondary action.
  - Scroll behavior:
    - The card itself does not scroll; only the conversation list scrolls within the body area.

- **ChatCard**
  - A vertically-stacked card with the following sub-regions:
    - Header:
      - Page title (“Ask about your ERP data”).
      - Short supporting text (“Query your database using natural language”).
      - Right-aligned icon buttons for Help and Settings.
    - Conversation body:
      - MessageList area with messages stacked top-to-bottom.
      - “Quick actions” / sample prompts section visible when there is no conversation yet and collapsed once messages exist.
      - Inline typing indicator and error banners appear at the bottom of the MessageList, just above the InputBar.
    - InputBar:
      - Sticky, anchored to the bottom of the card.
      - Contains the multiline text input, Send button, Stop button, character counter, and keyboard shortcut hint.
  - The MessageList is the primary scroll container for the ChatCard.

- **InputBar**
  - Lives inside the ChatCard; does not float separately at the window edge.
  - Layout:
    - Main row: textarea + Send button + Stop button.
    - Secondary row: character counter on the left; keyboard shortcut hint on the right.
  - Behavior:
    - Textarea auto-resizes up to a max height, then scrolls.
    - Send is disabled when empty or while loading.
    - Stop is visible only when a request is in-flight.

### 8.2 Visual Design Tokens

Tokens should be defined so they can map either to CSS custom properties (current app) or Tailwind theme tokens (future Next.js app).

- **Color Tokens**
  - Neutrals:
    - `--color-bg-app`: dark desaturated background (reuse `--primary-dark`).
    - `--color-bg-card`: light surface for cards (reuse `--light-background` / `#F8F8F8`).
    - `--color-bg-subtle`: slightly darker than card (e.g., `#EEF0F4`) for nested elements.
    - `--color-border-subtle`: soft border for cards and inputs (reuse `--darker-grey-4`).
  - Accent / Brand:
    - `--color-accent`: primary brand blue (reuse `--primary-accent`).
    - `--color-accent-soft`: tint of accent for chips, badges.
    - `--color-accent-strong`: darker accent for hover/active states (`--blue-hover` / `--blue-active`).
  - Semantic:
    - `--color-success`, `--color-warning`, `--color-error` reusing existing tokens.
    - Text colors:
      - `--color-text-primary`: dark text on light surfaces (`#111827`-ish).
      - `--color-text-secondary`: muted text (`--darker-grey-2`).
      - `--color-text-inverse`: white on dark/accent backgrounds.

- **Radius Tokens**
  - `--radius-xs`: `4px` (chips, small buttons).
  - `--radius-sm`: `8px` (buttons, small surfaces).
  - `--radius-md`: `12px` (inputs, message bubbles).
  - `--radius-lg`: `16px` (current welcome card, modals).
  - `--radius-xl`: `24px` (SidebarCard, ChatCard outer corners to emphasize “floating”).

- **Shadow Tokens**
  - `--shadow-soft`: `0 4px 14px rgba(15, 23, 42, 0.18)` – default card elevation.
  - `--shadow-strong`: `0 18px 45px rgba(15, 23, 42, 0.35)` – hover/focus or modal.
  - Cards should appear subtly elevated from the app background but not overly “glassy”.

- **Typography**
  - Font family: continue using Inter system stack.
  - Type scale (desktop):
    - Heading XL (hero): `28px` / `1.2` line height – ChatCard header title.
    - Heading M: `20px` – modal titles, SidebarCard title.
    - Body: `14–16px` – primary text in messages and prompts.
    - Caption: `12px` – timestamps, helper text, char counter.
  - Weights:
    - 600 for headings.
    - 500 for key labels/actions.
    - 400 for body text.

- **Spacing**
  - Base spacing unit: `4px`.
  - Common paddings:
    - Card outer padding: `20–24px`.
    - MessageList padding: `20px` horizontal, `24px` top/bottom.
    - InputBar padding: `16–20px` top and bottom inside card.

### 8.3 Responsive Behavior

- **Desktop (≥ 1024px)**
  - AppShell:
    - Uses a centered two-column grid as described above.
    - SidebarCard width locked at `320px`, ChatCard grows with viewport up to max width.
  - Cards share the same vertical rhythm—top padding aligns, and InputBar aligns with bottom of SidebarCard footer.
  - InputBar:
    - Sticky within the ChatCard; when message list overflows, only the MessageList scrolls.

- **Tablet (768–1023px)**
  - AppShell:
    - Switch to a stacked layout: SidebarCard on top, ChatCard below.
    - Cards full width of the content column (still centered with outer padding).
  - Conversation history remains visible, but the height is reduced; conversation list scrolls in a constrained area.
  - InputBar remains sticky at the bottom of the ChatCard; the viewport scrolls the entire ChatCard while keeping the InputBar in view as much as possible.

- **Mobile (< 768px)**
  - Default view prioritizes the ChatCard:
    - ChatCard full-width, edge-to-edge within content padding.
    - SidebarCard is hidden behind a “History” affordance (e.g., button in the ChatCard header).
  - Sidebar behavior:
    - Tapping the History button reveals the SidebarCard as:
      - Either a full-screen slide-over from the left, or
      - A bottom sheet that covers ~80% of the height.
    - Sidebar overlay includes a close button and trap focus while open.
  - InputBar:
    - Sticks to the bottom of the viewport (safe-area aware on mobile devices).
    - MessageList scrolls in the space above InputBar; “Jump to latest” pill appears as needed.

### 8.4 Mapping Existing UX Features Into the New Layout

- **Service Status Indicator**
  - Moves into the SidebarCard header under the assistant title, using:
    - Status dot + label (“Connecting…”, “Service online”, “Service offline”, “Degraded”).
    - Color mapping aligned with semantic tokens (success/warning/error).
  - On mobile, when Sidebar is hidden, a compact status chip (icon + text) appears in the ChatCard header to keep status visible.

- **Conversation History**
  - Lives entirely inside the SidebarCard body as the primary scrollable region.
  - Conversation items retain:
    - Button semantics (keyboard focusable, `aria-label` with conversation title).
    - Title + last message preview + timestamp.
  - “New chat” primary button appears above the list (or in the Sidebar footer) to differentiate “start fresh thread” from “Clear history”.

- **Sample Prompts / Quick Actions**
  - On empty state:
    - Display inside ChatCard as a “Quick actions” section at the top of the MessageList area.
    - Each sample prompt is a pill-like button in a responsive grid (1–2 columns on mobile, 2–3 on desktop).
  - After the user sends at least one message:
    - Collapse the quick actions into a small row of chips under the ChatCard header, or hide them to avoid vertical clutter.

- **Typing Indicator**
  - Rendered inline at the bottom of the MessageList within ChatCard:
    - Appears above the InputBar when `isLoading` is true.
    - Uses subtle dots animation and text like “Assistant is thinking…”.
  - On mobile, ensure it remains visible in the scrollable area and does not push the InputBar off-screen.

- **Errors and Clarifications**
  - Error messages:
    - Appear as standard bot bubbles styled with an error variant (border + icon).
    - Include a Retry button inline, consistent with current implementation.
  - Clarification messages:
    - Use the `.clarification` style, but visually aligned with the new card aesthetic (e.g., warm background, label “Clarification needed”, quick-reply chips beneath).

- **Help & Settings**
  - Triggered from icon buttons in the ChatCard header.
  - Modal patterns remain the same (focus trap, ESC to close) but align visually with the floating-card theme:
    - Centered dialogs with `--radius-lg` and `--shadow-strong`.

- **Observability Hooks**
  - Thumbs up/down controls (if added later) live at the bottom-right of each assistant message bubble in the ChatCard.
  - Minimal additional chrome so as not to conflict with the card’s clean aesthetic.

### 8.5 States & Visual Feedback

- **Empty State**
  - ChatCard shows a welcoming hero (icon + title + description) and the Quick actions section.
  - SidebarCard shows “No conversations yet” copy, consistent with current history empty state.

- **Busy State**
  - No full-screen overlay; instead:
    - InputBar shows the Stop button.
    - Typing indicator appears at the bottom of the MessageList.
    - Send button disabled while a request is active.

- **Error State**
  - Affected assistant bubble uses error styling plus Retry.
  - Optionally, a small non-blocking toast (existing `showNotification`) can appear aligned to the top-right of the AppShell for global issues (e.g., service offline).

- **Offline / Degraded**
  - Status dot and label in SidebarCard header reflect the state.
  - The Send button can be disabled when “offline”, with tooltip text indicating connectivity issues.
