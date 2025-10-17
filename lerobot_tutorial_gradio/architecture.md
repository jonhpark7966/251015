# Architecture Overview

## System Goals
- Render the Robot Learning tutorial (maintained as LaTeX/MDX sources in the upstream Hugging Face Space) inside a local Gradio UI.
- Keep the content pipeline identical to the Space: LaTeX → MDX conversion → Astro static build, then expose the generated HTML locally without relying on Hugging Face infrastructure.

## Repository Layout
- `src_space/`: Direct clone of `huggingface.co/spaces/lerobot/robot-learning-tutorial`. Contains the MDX conversion scripts (`app/scripts/latex-importer/`) and the Astro site (`app/`).
- `src_space/app/dist/`: Astro build output (HTML, JS, CSS, assets). Generated via `npm run build` inside `src_space/app/`.
- `app.py`: FastAPI application that mounts both the Gradio UI and the static Astro build. Paths are anchored to `app.py` so the server can be launched from any working directory.
- `requirements.txt`: Python dependencies (`fastapi`, `gradio`, `uvicorn[standard]`).

## Content Pipeline
1. **LaTeX → MDX**: Run the existing importer under `src_space/app/scripts/latex-importer/`. This step populates `src_space/app/src/content/` with MDX files. (The repo keeps the Space tooling untouched so the original workflows still apply.)
2. **Astro Static Build**: Execute `npm install` (or `npm ci`) and `npm run build` inside `src_space/app/`. Astro, configured with MDX/KaTeX/citation plugins, produces a static site in `dist/`.
3. **Static Assets Ready**: The generated `dist/` folder is what the Python side serves. Whenever the content changes, rebuild to refresh the served assets. Astro no longer pre-compresses output; runtime gzip is handled by FastAPI middleware.

## Serving Architecture
- `FastAPI` owns the ASGI app lifecycle.
- `gradio.Blocks` defines a small UI with documentation text and an `<iframe>` pointed at the Astro site.
- `gr.mount_gradio_app(app, ui, path="/app")` attaches the Gradio interface at `/app`.
- `StaticFiles(directory=DIST, html=True, check_dir=False)` mounts `src_space/app/dist` at the root path `/`. This is prioritized after mounting the Gradio UI, so the iframe resolves to the static site.
- When run with `uvicorn app:app --host 0.0.0.0 --port 7860`, visiting `http://localhost:7860/` serves the Astro site, and `http://localhost:7860/app/` loads the Gradio wrapper that embeds it.

## Operational Notes
- Startup validation raises a clear error if `src_space/app/dist` is missing, preventing silent iframe failures.
- Static files are served directly by FastAPI; gzip compression is provided by `GZipMiddleware` and immutable cache headers are added automatically for hashed Astro assets.
- Cross-origin iframe usage is future-proofed with a permissive `CORSMiddleware` setup.
- `GET /health` exposes a lightweight health endpoint, reporting whether the Astro build artifacts are present.
- Because the repository mirrors the Hugging Face Space, syncing updates or rerunning the build pipeline keeps local rendering aligned with production behavior.
