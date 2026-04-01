"""YouTube Auto Uploader — FastAPI Webアプリケーション"""

import logging
import os
import tempfile
from pathlib import Path

from fastapi import FastAPI, File, Form, UploadFile, Request
from fastapi.responses import HTMLResponse
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
PUBLISH_DELAY = int(os.getenv("PUBLISH_DELAY_MINUTES", "60"))


def load_description() -> str:
    with open(DESCRIPTION_FILE) as f:
        return f.read().strip()


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/upload", response_class=HTMLResponse)
async def upload(
    request: Request,
    title: str = Form(...),
    thumbnail_text: str = Form(...),
    video: UploadFile = File(...),
):
    tmp_dir = tempfile.mkdtemp()
    video_path = os.path.join(tmp_dir, video.filename)
    mixed_path = None
    thumb_path = None

    try:
        # 動画を一時保存
        log.info(f"動画受信: {video.filename}")
        with open(video_path, "wb") as f:
            while chunk := await video.read(1024 * 1024):
                f.write(chunk)

        # BGM合成
        log.info("BGM合成中...")
        mixed_path = mix_bgm(video_path, str(BGM_FILE), BGM_VOLUME)
        log.info("BGM合成完了")

        # サムネイル生成
        log.info("サムネイル生成中...")
        thumb_path = generate_thumbnail(
            video_path,
            thumbnail_text,
            font_file=str(FONT_FILE),
            font_size=FONT_SIZE,
        )
        log.info("サムネイル生成完了")

        # YouTubeアップロード
        log.info("YouTubeアップロード中...")
        description = load_description()
        service = get_authenticated_service(CLIENT_SECRET_FILE, TOKEN_FILE)
        video_id = upload_video(
            service,
            mixed_path,
            title=title,
            description=description,
            category_id=CATEGORY_ID,
            publish_delay_minutes=PUBLISH_DELAY,
        )
        log.info(f"アップロード完了: {video_id}")

        # サムネイル設定
        log.info("サムネイル設定中...")
        set_thumbnail(service, video_id, thumb_path)
        log.info("サムネイル設定完了")

        youtube_url = f"https://youtu.be/{video_id}"
        return templates.TemplateResponse("index.html", {
            "request": request,
            "success": True,
            "youtube_url": youtube_url,
            "title": title,
        })

    except Exception as e:
        log.error(f"処理失敗: {e}", exc_info=True)
        return templates.TemplateResponse("index.html", {
            "request": request,
            "error": str(e),
        })

    finally:
        # 一時ファイル削除
        for path in [video_path, mixed_path, thumb_path]:
            if path and os.path.exists(path):
                os.unlink(path)
        if os.path.exists(tmp_dir):
            os.rmdir(tmp_dir)
