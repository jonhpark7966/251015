from pathlib import Path

import gradio as gr
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware

BASE_DIR = Path(__file__).resolve().parent
DIST = BASE_DIR / "src_space/app/dist"


class CacheControlMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):  # type: ignore[override]
        response = await call_next(request)
        path = request.url.path
        if path.startswith("/_astro/"):
            response.headers.setdefault(
                "Cache-Control", "public, max-age=31536000, immutable"
            )
        return response


fastapi_app = FastAPI()
fastapi_app.add_middleware(GZipMiddleware, minimum_size=1000)
fastapi_app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)
fastapi_app.add_middleware(CacheControlMiddleware)


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


with gr.Blocks(title="MDX→Astro 뷰어") as ui:
    gr.Markdown("### Astro로 빌드된 MDX 문서를 아래에 임베드합니다. (정식 경로는 '/').")
    if DIST.exists():
        # 루트 경로에 정적 사이트가 있으므로 그대로 임베드
        gr.HTML("<iframe src='/' style='width:100%; height:85vh; border:0' title='Astro Site'></iframe>")
    else:
        gr.Markdown(
            ":warning: 빌드 산출물(dist)이 없습니다. 'src_space/app'에서 'npm install && npm run build'를 먼저 실행하세요."
        )

# Gradio는 /app 하위 경로에 마운트 (정적은 아래에서 루트에 마운트)
app = gr.mount_gradio_app(fastapi_app, ui, path="/app")

# Gradio 마운트 후에 Astro 정적 자산을 루트('/')로 마운트 (경로 우선순위 보장)
app.mount("/", StaticFiles(directory=str(DIST), html=True, check_dir=False), name="site")
