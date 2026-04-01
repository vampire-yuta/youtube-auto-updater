"""YouTube Auto Uploader — FastAPI Webアプリケーション"""

import asyncio
import json
import logging
import os
import tempfile
import uuid
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

from fastapi import FastAPI, File, Form, UploadFile, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.templating import Jinja2Templates

from src.audio import mix_bgm
from src.thumbnail import generate_thumbnail
from src.uploader import get_authenticated_service, upload_video, set_thumbnail

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)

app = FastAPI(title="YouTube Auto Uploader")
templates = Jinja2Templates(directory="/app/templates")
executor = ThreadPoolExecutor(max_workers=2)

# 設定（環境変数 or デフォルト）
ASSETS_DIR = Path(os.getenv("ASSETS_DIR", "/app/assets"))
BGM_FILE = ASSETS_DIR / "bgm.mp3"
FONT_FILE = Path(os.getenv("FONT_FILE", "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"))
BGM_VOLUME = float(os.getenv("BGM_VOLUME", "0.1"))
FONT_SIZE = int(os.getenv("FONT_SIZE", "80"))
DESCRIPTION_FILE = Path(os.getenv("DESCRIPTION_FILE", "/app/config/description.txt"))
CLIENT_SECRET_FILE = os.getenv("CLIENT_SECRET_FILE", "/app/secrets/client_secret.json")
TOKEN_FILE = os.getenv("TOKEN_FILE", "/app/secrets/token.json")
CATEGORY_ID = os.getenv("YOUTUBE_CATEGORY_ID", "22")

# ジョブの進捗を保持
jobs: dict[str, list[dict]] = {}


def load_description() -> str:
    with open(DESCRIPTION_FILE) as f:
        return f.read().strip()


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


def _process_job(job_id: str, video_path: str, title: str, thumbnail_text: str, publish_timing: str):
    """バックグラウンドで動画処理を実行し、進捗をjobsに記録する"""
    mixed_path = None
    thumb_path = None

    def progress(step: str, status: str, detail: str = ""):
        jobs[job_id].append({"step": step, "status": status, "detail": detail})

    try:
        progress("bgm", "running", "BGM合成中...")

        mixed_path = mix_bgm(video_path, str(BGM_FILE), BGM_VOLUME)
        progress("bgm", "done", "BGM合成完了")

        progress("thumbnail", "running", "サムネイル生成中...")
        thumb_path = generate_thumbnail(
            video_path,
            thumbnail_text,
            font_file=str(FONT_FILE),
            font_size=FONT_SIZE,
        )
        progress("thumbnail", "done", "サムネイル生成完了")

        progress("auth", "running", "YouTube認証中...")
        description = load_description()
        service = get_authenticated_service(CLIENT_SECRET_FILE, TOKEN_FILE)
        progress("auth", "done", "YouTube認証完了")

        progress("upload", "running", "YouTubeアップロード中...")
        video_id = upload_video(
            service,
            mixed_path,
            title=title,
            description=description,
            category_id=CATEGORY_ID,
            publish_timing=publish_timing,
        )
        progress("upload", "done", f"アップロード完了")

        progress("thumbnail_set", "running", "サムネイル設定中...")
        set_thumbnail(service, video_id, thumb_path)
        progress("thumbnail_set", "done", "サムネイル設定完了")

        youtube_url = f"https://youtu.be/{video_id}"
        progress("complete", "done", youtube_url)

    except Exception as e:
        log.error(f"処理失敗: {e}", exc_info=True)
        progress("error", "error", str(e))

    finally:
        for path in [video_path, mixed_path, thumb_path]:
            if path and os.path.exists(path):
                os.unlink(path)
        tmp_dir = os.path.dirname(video_path)
        if os.path.exists(tmp_dir):
            try:
                os.rmdir(tmp_dir)
            except OSError:
                pass


@app.post("/upload")
async def upload(
    title: str = Form(...),
    thumbnail_text: str = Form(...),
    publish_timing: str = Form(...),
    video: UploadFile = File(...),
):
    # 動画を一時保存
    tmp_dir = tempfile.mkdtemp()
    video_path = os.path.join(tmp_dir, video.filename)
    log.info(f"動画受信: {video.filename}")
    with open(video_path, "wb") as f:
        while chunk := await video.read(1024 * 1024):
            f.write(chunk)

    # ジョブ開始
    job_id = str(uuid.uuid4())
    jobs[job_id] = [{"step": "receive", "status": "done", "detail": "動画受信完了"}]

    loop = asyncio.get_event_loop()
    loop.run_in_executor(executor, _process_job, job_id, video_path, title, thumbnail_text, publish_timing)

    return {"job_id": job_id}


@app.get("/progress/{job_id}")
async def progress(job_id: str):
    """SSEで進捗を配信する"""
    async def event_stream():
        sent = 0
        while True:
            if job_id not in jobs:
                yield f"data: {json.dumps({'step': 'error', 'status': 'error', 'detail': 'Job not found'})}\n\n"
                return

            events = jobs[job_id]
            while sent < len(events):
                event = events[sent]
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
                sent += 1

                if event["step"] in ("complete", "error"):
                    # クリーンアップ
                    del jobs[job_id]
                    return

            await asyncio.sleep(0.5)

    return StreamingResponse(event_stream(), media_type="text/event-stream")
