# TODO — LaTeX→MDX(기존 스크립트) → Astro 빌드 → Gradio 임베드

정석 파이프라인: “LaTeX→MDX(기존 스크립트) → Astro 빌드 → Gradio에서 정적 산출물 임베드”.
원본 Space(lerobot/robot-learning-tutorial)에 이미 LaTeX→MDX 자동화와 Astro 설정이 준비되어 있으므로 그대로 활용합니다.

## 0) 준비(로컬/Spaces 공통)
- [ ] Node 20, npm 설치(필수)
- [ ] pandoc 설치(LaTeX→MD/MDX 변환 파이프라인에서 사용)
- [ ] Python 3.10+ 설치, `gradio`, `fastapi`, `uvicorn` 설치
  - 명령: `pip install gradio fastapi uvicorn`

## 1) 원본 Space 레포 클론
- [ ] Git LFS 활성화: `git lfs install`
- [ ] 원본 Space 클론: `git clone https://huggingface.co/spaces/lerobot/robot-learning-tutorial src_space`
- [ ] 구조 확인: `src_space/app/scripts/latex-importer/` 폴더 존재 확인

## 2) LaTeX 원본 배치
- [ ] LaTeX 프로젝트/문서를 `src_space/app/scripts/latex-importer/input/` 아래에 배치
  - 필요 시 README-latex-integration.md에 안내된 입력 경로/옵션을 참고

## 3) LaTeX → MDX 변환 (원본 스크립트 사용)
- [ ] `cd src_space/app && npm install` (lock 파일과 버전이 어긋나 있을 수 있어 `ci` 대신 `install` 권장)
- [ ] 변환 실행(둘 중 하나)
  - `npm run latex:convert`
  - `npm run latex-project-to-mdx`
- [ ] 변환 산출(MDX)이 지정된 출력 경로에 생성되었는지 확인

## 4) Astro 빌드(정적 HTML 산출)
- [ ] `cd src_space/app && npm run build`
- [ ] 빌드 결과 `src_space/app/dist/` 생성 및 `index.html` 포함 확인

## 5) Gradio 앱에서 정적 산출물 임베드(권장: FastAPI 정적 서빙 + iframe)
- [ ] 워크스페이스 루트에 `app.py` 생성(또는 기존 파일에 추가) — 내용 예시(정적 자산은 루트 `/`, Gradio는 `/app`):

```python
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
import gradio as gr
from pathlib import Path

DIST = Path("src_space/app/dist").resolve()

app = FastAPI()

with gr.Blocks(title="MDX→Astro 뷰어") as ui:
    gr.Markdown("### Astro로 빌드된 MDX 문서를 아래에 임베드합니다. (정식 경로는 '/').")
    if DIST.exists():
        gr.HTML("<iframe src='/' style='width:100%; height:85vh; border:0' title='Astro Site'></iframe>")
    else:
        gr.Markdown(
            ":warning: 빌드 산출물(dist)이 없습니다. 'src_space/app'에서 'npm install && npm run build'를 먼저 실행하세요."
        )

app = gr.mount_gradio_app(app, ui, path="/app")

if DIST.exists():
    app.mount("/", StaticFiles(directory=str(DIST), html=True), name="site")
```

- [ ] 로컬 실행(택1)
  - `uvicorn app:app --host 0.0.0.0 --port 7860`
  - `python -m uvicorn app:app --host 0.0.0.0 --port 7860`
- [ ] 브라우저에서 `http://localhost:7860` 접속 → Astro로 빌드된 페이지가 iframe으로 보이는지 확인

## 6) (선택) Hugging Face Space 자동 빌드/서빙 구성
- [ ] `pre_build.sh` 작성(Spaces에서 Node/pandoc 설치 및 빌드 자동화)

```bash
#!/usr/bin/env bash
set -euo pipefail

# Node 20 + pandoc 설치
curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
apt-get update && apt-get install -y nodejs pandoc git-lfs

# 원본 Space 클론
git lfs install
git clone https://huggingface.co/spaces/lerobot/robot-learning-tutorial src_space

# Astro 빌드
cd src_space/app
npm ci
npm run latex:convert   # 또는 npm run latex-project-to-mdx
npm run build           # dist/ 생성
```

- [ ] `requirements.txt`에 Python 의존성 명시: `gradio`, `fastapi`, `uvicorn`
- [ ] Space 런타임에서 `uvicorn app:app --host 0.0.0.0 --port 7860`로 기동되도록 설정(SDK: FastAPI 선택 시 자연스러움)

## 7) 검증 체크리스트
- [ ] 수식(KaTeX), 참고문헌, 코드 하이라이트, Mermaid 등이 정상 렌더링
- [ ] 내부 링크/이미지/자산이 `/_astro/...`, `/data/...` 등 루트 경로에서 정상 로딩
- [ ] 모바일/데스크톱 뷰에서 레이아웃 문제 없는지 확인

## 8) 대안(옵션) — 단일 HTML로 임베드
- [ ] Astro/Vite에 single-file 플러그인(예: `vite-plugin-singlefile`) 적용해 CSS/JS 인라인화
- [ ] `gr.HTML`의 `iframe srcdoc` 방식으로 단일 HTML 임베드(정적 자산 경로 문제 회피)

---

비고
- 위 파이프라인과 스크립트의 근거 및 예시는 `chat.txt`에 요약되어 있습니다.
- “MDX를 Gradio에서 직접 렌더링”은 불가하므로 반드시 Astro 등으로 **사전 빌드** 후 정적 임베드 방식으로 진행합니다.
