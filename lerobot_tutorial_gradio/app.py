from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
import gradio as gr
from pathlib import Path

DIST = Path("src_space/app/dist").resolve()

app = FastAPI()

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
app = gr.mount_gradio_app(app, ui, path="/app")

# Gradio 마운트 후에 Astro 정적 자산을 루트('/')로 마운트 (경로 우선순위 보장)
if DIST.exists():
    app.mount("/", StaticFiles(directory=str(DIST), html=True), name="site")
