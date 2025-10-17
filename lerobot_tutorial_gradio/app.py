from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

import gradio as gr
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware

try:
    from openai import OpenAI
except ImportError:  # pragma: no cover - best effort fallback
    OpenAI = None  # type: ignore[assignment]

BASE_DIR = Path(__file__).resolve().parent
DIST = BASE_DIR / "src_space/app/dist"
PACKAGE_JSON = BASE_DIR / "src_space/app/package.json"

TAB_OPTIONS: Dict[str, str] = {
    "Astro Preview": "astro",
    "Debug Info": "debug",
}
DEFAULT_TAB_KEY = "astro"
DEFAULT_TAB_LABEL = next(label for label, key in TAB_OPTIONS.items() if key == DEFAULT_TAB_KEY)
DEFAULT_OPENAI_MODEL = "gpt-4o-mini"
SYSTEM_PROMPT = (
    "You are an assistant for the LeRobot tutorial workspace. "
    "Answer concisely in the language the user uses."
)
DUAL_PANE_CSS = """
#dual-pane {
  gap: 1rem;
}
#dual-pane-toolbar {
  align-items: center;
  gap: 0.75rem;
  flex-wrap: wrap;
}
#dual-pane-panes {
  gap: 1rem;
  min-height: 60vh;
}
#left-pane,
#right-pane {
  min-height: 60vh;
  gap: 0.75rem;
}
#right-pane-group {
  transition: opacity 0.2s ease;
}
.dual-pane__iframe-wrapper {
  position: relative;
  width: 100%;
  padding-top: 70vh;
}
.dual-pane__iframe-wrapper iframe {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  border: 0;
  border-radius: 0.5rem;
  background: var(--background-fill-primary, #fff);
}
.dual-pane__iframe-loader {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--body-text-color, #444);
  background: var(--background-fill-secondary, rgba(0,0,0,0.05));
  font-size: 0.9rem;
  letter-spacing: 0.02em;
}
.dual-pane__iframe-loaded .dual-pane__iframe-loader {
  display: none;
}
.dual-pane__empty {
  padding: 1rem;
  border: 1px dashed var(--border-color, #d0d0d0);
  background: var(--background-fill-secondary, rgba(0,0,0,0.03));
  border-radius: 0.5rem;
  font-size: 0.95rem;
}
@media (max-width: 768px) {
  #dual-pane-panes {
    flex-direction: column;
  }
  #right-pane-group {
    display: none !important;
  }
  #left-pane {
    width: 100%;
  }
}
"""


class ChatError(RuntimeError):
    """Domain-specific error for chat related failures."""


class CacheControlMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):  # type: ignore[override]
        response = await call_next(request)
        path = request.url.path
        if path.startswith("/_astro/"):
            response.headers.setdefault(
                "Cache-Control", "public, max-age=31536000, immutable"
            )
        return response


class AppPathRedirectMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):  # type: ignore[override]
        if request.url.path == "/app":
            return RedirectResponse(url="/app/", status_code=307)
        return await call_next(request)


fastapi_app = FastAPI()
fastapi_app.add_middleware(GZipMiddleware, minimum_size=1000)
fastapi_app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)
fastapi_app.add_middleware(CacheControlMiddleware)
fastapi_app.add_middleware(AppPathRedirectMiddleware)


@fastapi_app.on_event("startup")
async def ensure_dist_exists() -> None:
    if not DIST.exists():
        raise RuntimeError(
            f"Astro build artifacts not found at {DIST}. "
            "Run 'npm install && npm run build' inside src_space/app/."
        )


@fastapi_app.get("/health")
async def healthcheck() -> dict[str, bool]:
    return {"ok": True, "dist_exists": DIST.exists()}


def label_to_tab(label: str) -> str:
    return TAB_OPTIONS.get(label, DEFAULT_TAB_KEY)


def tab_to_label(key: str) -> str:
    for label, value in TAB_OPTIONS.items():
        if value == key:
            return label
    return DEFAULT_TAB_LABEL


def get_build_metadata() -> Dict[str, Any]:
    exists = DIST.exists()
    file_count = 0
    latest_mtime: float | None = None
    if exists:
        files = [path for path in DIST.rglob("*") if path.is_file()]
        file_count = len(files)
        if files:
            latest_mtime = max(path.stat().st_mtime for path in files)
    astro_version = None
    if PACKAGE_JSON.exists():
        try:
            payload = json.loads(PACKAGE_JSON.read_text("utf-8"))
            deps = payload.get("dependencies", {}) or {}
            dev_deps = payload.get("devDependencies", {}) or {}
            astro_version = deps.get("astro") or dev_deps.get("astro")
        except (json.JSONDecodeError, UnicodeDecodeError):
            astro_version = None
    latest_iso = (
        datetime.fromtimestamp(latest_mtime, tz=timezone.utc).astimezone().isoformat()
        if latest_mtime
        else None
    )
    return {
        "path": str(DIST),
        "exists": exists,
        "file_count": file_count,
        "latest_iso": latest_iso,
        "astro_version": astro_version,
    }


def build_debug_markdown(metadata: Dict[str, Any]) -> str:
    lines = [
        "### Astro Build Diagnostics",
        f"- `dist` path: `{metadata['path']}`",
        f"- Exists: {'✅' if metadata['exists'] else '❌'}",
    ]
    if metadata["exists"]:
        lines.append(f"- File count: {metadata['file_count']}")
        if metadata["latest_iso"]:
            lines.append(f"- Last modified: `{metadata['latest_iso']}`")
    if metadata.get("astro_version"):
        lines.append(f"- Astro version: `{metadata['astro_version']}`")
    if not metadata["exists"]:
        lines.append(
            "- Action: run `npm install && npm run build` inside `src_space/app/` to generate the static site."
        )
    return "\n".join(lines)


def make_iframe_html(locale: str, pane_id: str) -> str:
    if not DIST.exists():
        return (
            "<div class='dual-pane__empty'>"
            "Astro 빌드 산출물(`dist/`)이 없습니다. "
            "`src_space/app`에서 `npm install && npm run build`를 실행한 뒤 다시 시도하세요."
            "</div>"
        )
    src = "/" if locale == "en" else f"/{locale}"
    wrapper_id = f"{pane_id}-wrapper"
    loader_id = f"{pane_id}-loader"
    return f"""
<div class="dual-pane__iframe-wrapper" id="{wrapper_id}">
  <div class="dual-pane__iframe-loader" id="{loader_id}">Loading Astro site...</div>
  <iframe
    src="{src}"
    loading="lazy"
    title="Astro Site ({pane_id})"
    onload="document.getElementById('{wrapper_id}')?.classList.add('dual-pane__iframe-loaded');"
  ></iframe>
</div>
"""


def ensure_openai_client(api_key: str):
    key = (api_key or "").strip()
    if not key:
        raise ChatError("OpenAI API 키를 먼저 입력해주세요.")
    if OpenAI is None:
        raise ChatError(
            "`openai` 패키지를 찾을 수 없습니다. `pip install -r requirements.txt`를 다시 실행하세요."
        )
    return OpenAI(api_key=key)


def redact_api_key(text: str, api_key: str) -> str:
    if not text:
        return text
    key = (api_key or "").strip()
    if not key:
        return text
    redacted = text.replace(key, "[redacted]")
    if key.startswith("sk-") and len(key) >= 8:
        redacted = redacted.replace(key[:8], "sk-****")
    return redacted


def build_openai_messages(
    history: List[Tuple[str, str]], user_message: str
) -> List[Dict[str, str]]:
    messages: List[Dict[str, str]] = [{"role": "system", "content": SYSTEM_PROMPT}]
    for user, assistant in history:
        if user:
            messages.append({"role": "user", "content": user})
        if assistant:
            messages.append({"role": "assistant", "content": assistant})
    messages.append({"role": "user", "content": user_message})
    return messages


def request_chat_completion(
    api_key: str, history: List[Tuple[str, str]], user_message: str
) -> str:
    client = ensure_openai_client(api_key)
    messages = build_openai_messages(history, user_message)
    try:
        response = client.chat.completions.create(
            model=DEFAULT_OPENAI_MODEL,
            messages=messages,
        )
    except Exception as exc:  # pragma: no cover - surface clean error to UI
        safe_message = redact_api_key(str(exc), api_key)
        raise ChatError(f"OpenAI 호출에 실패했습니다: {safe_message}") from exc
    choices = getattr(response, "choices", None) or []
    if not choices:
        raise ChatError("OpenAI에서 빈 응답을 반환했습니다.")
    first_choice = choices[0]
    content = getattr(first_choice.message, "content", None)
    if isinstance(content, list):
        content = "".join(
            part.get("text", "")
            for part in content
            if isinstance(part, dict)
        )
    if not content:
        raise ChatError("OpenAI 응답에 메시지가 없습니다.")
    return str(content).strip()


def handle_api_key_submit(
    raw_key: str, current_cfg: Dict[str, Any] | None
) -> Tuple[str, Dict[str, Any], str, Dict[str, Any]]:
    cleaned = (raw_key or "").strip()
    cfg = dict(current_cfg or {})
    if not cleaned:
        cfg["chat_ready"] = False
        return (
            "⚠️ OpenAI API 키를 입력한 뒤 저장을 눌러주세요.",
            gr.update(),
            "",
            cfg,
        )
    cfg["chat_ready"] = True
    return (
        "✅ OpenAI API 키가 세션에 저장되었습니다. 새로고침하면 다시 입력해야 합니다.",
        gr.update(value=""),
        cleaned,
        cfg,
    )


def handle_api_key_clear(
    current_cfg: Dict[str, Any] | None,
) -> Tuple[str, Dict[str, Any], str, Dict[str, Any]]:
    cfg = dict(current_cfg or {})
    cfg["chat_ready"] = False
    return (
        "ℹ️ 저장된 API 키를 삭제했습니다. 다른 키로 다시 저장할 수 있습니다.",
        gr.update(value=""),
        "",
        cfg,
    )


def handle_chat_submit(
    user_message: str,
    history: List[Tuple[str, str]],
    api_key: str,
) -> Tuple[List[Tuple[str, str]], Dict[str, Any], List[Tuple[str, str]], str]:
    message = (user_message or "").strip()
    if not message:
        return history, gr.update(), history, "⚠️ 전송할 메시지를 입력해주세요."

    new_history = list(history)
    new_history.append((message, ""))
    if not api_key:
        new_history[-1] = (
            message,
            "먼저 우측의 OpenAI API 키 입력란에 키를 저장해주세요.",
        )
        return (
            new_history,
            gr.update(value=""),
            new_history,
            "⚠️ OpenAI API 키가 필요합니다.",
        )

    try:
        assistant_reply = request_chat_completion(api_key, history, message)
    except ChatError as err:
        new_history[-1] = (message, f"❌ {err}")
        return (
            new_history,
            gr.update(value=""),
            new_history,
            f"❌ {err}",
        )

    new_history[-1] = (message, assistant_reply)
    return (
        new_history,
        gr.update(value=""),
        new_history,
        "✅ 응답을 받았습니다.",
    )


def handle_chat_clear(
    history: List[Tuple[str, str]]
) -> Tuple[List[Tuple[str, str]], List[Tuple[str, str]], str]:
    if not history:
        return history, history, "ℹ️ 초기화할 대화가 없습니다."
    return [], [], "ℹ️ 대화를 초기화했습니다."


def compute_updates(
    tab_key: str,
    show_right: bool,
    _left_cfg: Dict[str, Any],
    right_cfg: Dict[str, Any],
) -> Tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any], Dict[str, Any]]:
    metadata = get_build_metadata()
    debug_markdown = build_debug_markdown(metadata)

    left_astro_update = gr.update(visible=tab_key == "astro")
    left_debug_kwargs: Dict[str, Any] = {"visible": tab_key == "debug"}
    if tab_key == "debug":
        left_debug_kwargs["value"] = debug_markdown
    left_debug_update = gr.update(**left_debug_kwargs)

    right_group_update = gr.update(visible=show_right)
    new_right_cfg = dict(right_cfg)
    return left_astro_update, left_debug_update, right_group_update, new_right_cfg


def handle_tab_change(
    selected_label: str,
    _current_key: str,
    left_cfg: Dict[str, Any],
    right_cfg: Dict[str, Any],
    show_right: bool,
) -> Tuple[str, Dict[str, Any], Dict[str, Any], Dict[str, Any], Dict[str, Any]]:
    tab_key = label_to_tab(selected_label)
    (
        left_astro_update,
        left_debug_update,
        right_group_update,
        new_right_cfg,
    ) = compute_updates(tab_key, show_right, left_cfg, right_cfg)
    return (
        tab_key,
        left_astro_update,
        left_debug_update,
        right_group_update,
        new_right_cfg,
    )


def handle_right_toggle(
    show_right: bool,
    tab_key: str,
    _left_cfg: Dict[str, Any],
    right_cfg: Dict[str, Any],
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    (
        _,
        _,
        right_group_update,
        new_right_cfg,
    ) = compute_updates(tab_key, show_right, _left_cfg, right_cfg)
    return right_group_update, new_right_cfg


initial_metadata = get_build_metadata()

with gr.Blocks(title="MDX→Astro 뷰어", css=DUAL_PANE_CSS) as ui:
    selected_tab_state = gr.State(DEFAULT_TAB_KEY)  # No persistence across refresh by design
    left_config_state = gr.State({"locale": "en"})
    right_config_state = gr.State({"chat_ready": False})
    api_key_state = gr.State("")
    chat_history_state = gr.State([])  # list[tuple[user, assistant]]

    with gr.Column(elem_id="dual-pane"):
        gr.Markdown(
            "### Astro로 빌드된 문서를 좌/우 탭으로 확인하세요. 오른쪽 패널은 필요할 때만 열 수 있습니다."
        )
        with gr.Row(elem_id="dual-pane-toolbar"):
            tab_radio = gr.Radio(
                choices=list(TAB_OPTIONS.keys()),
                value=tab_to_label(DEFAULT_TAB_KEY),
                label="View",
                show_label=False,
            )
            right_toggle = gr.Checkbox(label="Show right pane", value=True)
            gr.Dropdown(
                choices=["en", "ko"],
                value="en",
                label="Locale (coming soon)",
                visible=False,
                interactive=False,
            )

        with gr.Row(elem_id="dual-pane-panes"):
            with gr.Column(elem_id="left-pane"):
                left_astro = gr.HTML(
                    make_iframe_html("en", "left"), elem_id="left-pane-astro"
                )
                left_debug = gr.Markdown(
                    build_debug_markdown(initial_metadata),
                    visible=False,
                    elem_id="left-pane-debug",
                )
            with gr.Group(elem_id="right-pane-group", visible=True) as right_group:
                with gr.Column(elem_id="right-pane"):
                    gr.Markdown(
                        "### OpenAI 기반 대화\nAPI 키는 브라우저 세션에만 저장되며 서버에는 기록되지 않습니다.",
                        elem_id="right-pane-heading",
                    )
                    with gr.Row():
                        api_key_input = gr.Textbox(
                            label="OpenAI API Key",
                            placeholder="sk-...",
                            type="password",
                            scale=4,
                        )
                        save_api_key_button = gr.Button("저장", variant="primary", scale=1)
                        clear_api_key_button = gr.Button("삭제", scale=1)
                    api_key_status = gr.Markdown("", elem_id="right-pane-api-key-status")
                    chatbot = gr.Chatbot(
                        label="Chat",
                        value=[],
                        elem_id="right-pane-chatbot",
                        height=420,
                    )
                    with gr.Row():
                        chat_message = gr.Textbox(
                            label="메시지",
                            placeholder="질문을 입력하고 Enter 또는 전송 버튼을 누르세요.",
                            lines=2,
                            scale=4,
                        )
                        send_button = gr.Button("전송", variant="primary", scale=1)
                    clear_chat_button = gr.Button("대화 초기화")
                    chat_status = gr.Markdown(
                        "",
                        elem_id="right-pane-chat-status",
                    )

    tab_radio.change(
        handle_tab_change,
        inputs=[
            tab_radio,
            selected_tab_state,
            left_config_state,
            right_config_state,
            right_toggle,
        ],
        outputs=[
            selected_tab_state,
            left_astro,
            left_debug,
            right_group,
            right_config_state,
        ],
    )

    right_toggle.change(
        handle_right_toggle,
        inputs=[right_toggle, selected_tab_state, left_config_state, right_config_state],
        outputs=[right_group, right_config_state],
    )

    save_api_key_button.click(
        handle_api_key_submit,
        inputs=[api_key_input, right_config_state],
        outputs=[api_key_status, api_key_input, api_key_state, right_config_state],
    )
    clear_api_key_button.click(
        handle_api_key_clear,
        inputs=[right_config_state],
        outputs=[api_key_status, api_key_input, api_key_state, right_config_state],
    )

    send_button.click(
        handle_chat_submit,
        inputs=[chat_message, chat_history_state, api_key_state],
        outputs=[chatbot, chat_message, chat_history_state, chat_status],
    )
    chat_message.submit(
        handle_chat_submit,
        inputs=[chat_message, chat_history_state, api_key_state],
        outputs=[chatbot, chat_message, chat_history_state, chat_status],
    )
    clear_chat_button.click(
        handle_chat_clear,
        inputs=[chat_history_state],
        outputs=[chatbot, chat_history_state, chat_status],
    )

# Gradio는 /app 하위 경로에 마운트 (정적은 아래에서 루트에 마운트)
app = gr.mount_gradio_app(fastapi_app, ui, path="/app")

# Gradio 마운트 후에 Astro 정적 자산을 루트('/')로 마운트 (경로 우선순위 보장)
app.mount("/", StaticFiles(directory=str(DIST), html=True, check_dir=False), name="site")
