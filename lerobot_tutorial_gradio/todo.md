# Dual-Pane Tabbed UI TODO

## Phase 0 · Preflight Safeguards
- [ ] Record baseline: archive current `app.py` (e.g., `cp app.py app.py.pre-dual-pane`) and create a git tag/branch `pre-dual-pane`.
- [x] Verify/lock Gradio version (`gradio>=4.0.0`) so `.update()` on `gr.HTML` is supported without remounting components.
- [ ] Capture current single-pane smoke-test steps so we can confirm parity after refactor.

- [x] Introduce shared Gradio state: `selected_tab` (`str`), `left_pane_config` (`dict`), `right_pane_config` (`dict`). 
  - [ ] Add a `_rendering` flag to debounce circular updates.
- [x] Replace the single-column Blocks body in `app.py` with a `gr.Row` that hosts two always-mounted `gr.Column` containers (`left_pane`, `right_pane`).
- [x] Add a top toolbar with a `gr.Radio` (tab selector), a `gr.Checkbox` (“Show right pane”), and a placeholder `gr.Dropdown` for future locale switching (`visible=False` for now).
- [x] Wrap the right pane inside a `gr.Group(visible=True)` and wire the checkbox `.change()` handler to toggle only the group visibility so component state persists.
- [x] Document the state flow and success criteria (tab change propagates to both panes within ~100 ms, right-pane toggle leaves left-pane scroll intact) and note the MVP decision: no persistence across refresh (localStorage deferred to avoid cross-origin complexity).
- [x] Decide—by the end of Phase 1—whether tab/pane state should persist across refresh (localStorage/query params/none) and document the decision even if implementation is deferred.

## Phase 2 · Tab Rendering & Content Hooks
- [x] Implement dedicated renderer functions (`render_left_pane`, `render_right_pane`) that accept `(selected_tab, pane_config)` and return `.update()` payloads for existing components.
- [x] Tab A: Reuse the existing Astro iframe; update it via `gr.HTML(..., elem_id="astro_iframe")` and `.update(value=iframe_html)` so the iframe DOM instance survives state changes, only altering wrapper markup (not the iframe `src`) unless the user explicitly changes locale.
- [x] Tab B: Add a “Debug Info” view that calls a new helper `get_build_metadata()` (dist path, build timestamp, file count, Astro version) and renders the details via `gr.Markdown`.
- [ ] Guard against infinite update loops by checking the `_rendering` flag inside event handlers before mutating shared state.
- [x] Document limitations (e.g., iframe scroll reset when `src` changes) inline for future mitigation.

## Phase 3 · UX Polish & Responsiveness
- [ ] Apply scoped CSS by assigning `elem_id` attributes (e.g., `#dual-pane`, `#left-pane`, `#right-pane`) and passing a stylesheet via `gr.Blocks(css=...)` that pins the tab strip, balances column widths, and collapses the right pane entirely below 768 px.
- [ ] Define mobile behavior: below 768 px hide the right pane (`display:none`) and expand the left pane to 100% width.
- [ ] Add iframe skeleton/loading state: render a placeholder `<div class="dual-pane__skeleton">Loading...</div>` and swap to the real iframe HTML once `onload` fires or after a short delay.
- [ ] Add clear fallback messaging when `dist/` is missing or errors occur while loading the iframe or debug data.
- [ ] Ensure the right-pane toggle does not reset iframe state by only adjusting visibility and never destroying already-rendered iframe HTML (render once, hide/show thereafter).
- [ ] Initialize the right-pane iframe lazily: render blank HTML initially and populate it only when the “Show right pane” checkbox transitions to checked, retaining the loaded state if toggled off then back on.

## Phase 4 · Regression Safety Checklist
- [ ] Validate FastAPI mounts (`/` static Astro, `/app` Gradio, `/health`) via automated curl checks or integration tests after refactor.
- [ ] Run the recorded smoke-test checklist: tab switching, pane toggling, responsive breakpoints, iframe navigation on desktop and mobile.
- [ ] Confirm iframe `src` targets remain same-origin (`/` rather than `/app`) and tab changes do not unexpectedly reload the iframe DOM.
- [ ] Document the rollback command (`git checkout pre-dual-pane -- app.py`) and verify it restores the baseline layout if regressions appear.
- [ ] Capture testing results and known limitations in the PR description or project notes.

## Phase 5 · Future Enhancements (Blocked until i18n lands)
- [ ] Enable the hidden locale dropdown and map pane config to `/` vs `/ko` iframe sources.
- [ ] Replace the debug tab with an MDX source preview or translation QA view once multilingual artifacts are generated.

## Phase 6 · Right-Pane Chat Interface
- [x] Choose OpenAI SDK (`openai` Python client ≥1.0) and pin dependency in `requirements.txt`; confirm no credentials stored server-side.
- [x] Model the chat session state: `chat_history` (list of dicts), `api_key` (str), and right-pane config flags (e.g., `chat_ready`).
- [x] Add secure API key input UI (masked textbox + helper copy) and store value in `gr.State` scoped to the user session.
- [x] Build the right-pane layout: persist the tab toggle controls, replace debug placeholder with chat container (`gr.Chatbot`, prompt box, submit button, clear button).
- [x] Implement server-side handler that validates API key, calls OpenAI completions/chat API, and gracefully surfaces errors (invalid key, rate limit, network issues).
- [x] Prevent accidental key logging: strip key from logs, avoid including it in metadata/debug views, and scrub from exceptions.
- [x] Once chat skeleton works, integrate with the tab change logic so the right pane always displays chat regardless of left tab content.
- [ ] Add optimistic UI feedback: disable send button while awaiting reply, show spinner/message when waiting for OpenAI response.
