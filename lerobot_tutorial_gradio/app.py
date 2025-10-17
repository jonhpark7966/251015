from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Tuple

import gradio as gr
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware

BASE_DIR = Path(__file__).resolve().parent
DIST = BASE_DIR / "src_space/app/dist"
PACKAGE_JSON = BASE_DIR / "src_space/app/package.json"

TAB_OPTIONS: Dict[str, str] = {
    "Astro Preview": "astro",
    "Debug Info": "debug",
}
DEFAULT_TAB_KEY = "astro"
DEFAULT_TAB_LABEL = next(label for label, key in TAB_OPTIONS.items() if key == DEFAULT_TAB_KEY)
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


def compute_updates(
    tab_key: str,
    show_right: bool,
    _left_cfg: Dict[str, Any],
    right_cfg: Dict[str, Any],
) -> Tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any], Dict[str, Any], Dict[str, Any], Dict[str, Any]]:
    metadata = get_build_metadata()
    debug_markdown = build_debug_markdown(metadata)

    left_astro_update = gr.update(visible=tab_key == "astro")
    left_debug_kwargs: Dict[str, Any] = {"visible": tab_key == "debug"}
    if tab_key == "debug":
        left_debug_kwargs["value"] = debug_markdown
    left_debug_update = gr.update(**left_debug_kwargs)

    right_group_update = gr.update(visible=show_right)
    right_updates_locale = right_cfg.get("locale", "en")
    prev_dist_exists = right_cfg.get("last_dist_exists")
    new_right_cfg = dict(right_cfg)
    new_right_cfg["last_dist_exists"] = metadata["exists"]
    if prev_dist_exists is not None and prev_dist_exists != metadata["exists"]:
        new_right_cfg["astro_loaded"] = False

    right_astro_kwargs: Dict[str, Any] = {"visible": tab_key == "astro" and show_right}
    needs_astro_value = (
        tab_key == "astro"
        and show_right
        and (
            not new_right_cfg.get("astro_loaded")
            or prev_dist_exists != metadata["exists"]
        )
    )
    if needs_astro_value:
        right_astro_kwargs["value"] = make_iframe_html(right_updates_locale, "right")
        new_right_cfg["astro_loaded"] = True
        new_right_cfg["last_dist_exists"] = metadata["exists"]
    right_astro_update = gr.update(**right_astro_kwargs)

    right_debug_kwargs: Dict[str, Any] = {"visible": tab_key == "debug" and show_right}
    if tab_key == "debug" and show_right:
        right_debug_kwargs["value"] = debug_markdown
    right_debug_update = gr.update(**right_debug_kwargs)

    return (
        left_astro_update,
        left_debug_update,
        right_group_update,
        right_astro_update,
        right_debug_update,
        new_right_cfg,
    )


def handle_tab_change(
    selected_label: str,
    _current_key: str,
    left_cfg: Dict[str, Any],
    right_cfg: Dict[str, Any],
    show_right: bool,
) -> Tuple[str, Dict[str, Any], Dict[str, Any], Dict[str, Any], Dict[str, Any], Dict[str, Any], Dict[str, Any]]:
    tab_key = label_to_tab(selected_label)
    (
        left_astro_update,
        left_debug_update,
        right_group_update,
        right_astro_update,
        right_debug_update,
        new_right_cfg,
    ) = compute_updates(tab_key, show_right, left_cfg, right_cfg)
    return (
        tab_key,
        left_astro_update,
        left_debug_update,
        right_group_update,
        right_astro_update,
        right_debug_update,
        new_right_cfg,
    )


def handle_right_toggle(
    show_right: bool,
    tab_key: str,
    _left_cfg: Dict[str, Any],
    right_cfg: Dict[str, Any],
) -> Tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any], Dict[str, Any]]:
    (
        _,
        _,
        right_group_update,
        right_astro_update,
        right_debug_update,
        new_right_cfg,
    ) = compute_updates(tab_key, show_right, _left_cfg, right_cfg)
    return right_group_update, right_astro_update, right_debug_update, new_right_cfg


initial_metadata = get_build_metadata()

with gr.Blocks(title="MDX→Astro 뷰어", css=DUAL_PANE_CSS) as ui:
    selected_tab_state = gr.State(DEFAULT_TAB_KEY)  # No persistence across refresh by design
    left_config_state = gr.State({"locale": "en"})
    right_config_state = gr.State(
        {"locale": "en", "astro_loaded": False, "last_dist_exists": DIST.exists()}
    )

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
            right_toggle = gr.Checkbox(label="Show right pane", value=False)
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
            with gr.Group(elem_id="right-pane-group", visible=False) as right_group:
                with gr.Column(elem_id="right-pane"):
                    right_astro = gr.HTML(
                        value="",
                        visible=False,
                        elem_id="right-pane-astro",
                    )
                    right_debug = gr.Markdown(
                        "",
                        visible=False,
                        elem_id="right-pane-debug",
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
            right_astro,
            right_debug,
            right_config_state,
        ],
    )

    right_toggle.change(
        handle_right_toggle,
        inputs=[right_toggle, selected_tab_state, left_config_state, right_config_state],
        outputs=[right_group, right_astro, right_debug, right_config_state],
    )

# Gradio는 /app 하위 경로에 마운트 (정적은 아래에서 루트에 마운트)
app = gr.mount_gradio_app(fastapi_app, ui, path="/app")

# Gradio 마운트 후에 Astro 정적 자산을 루트('/')로 마운트 (경로 우선순위 보장)
app.mount("/", StaticFiles(directory=str(DIST), html=True, check_dir=False), name="site")

