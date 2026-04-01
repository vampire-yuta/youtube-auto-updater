"""YouTube Data API v3 によるアップロード"""

from datetime import datetime, timedelta, timezone

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

import json
import shutil
from pathlib import Path

SCOPES = ["https://www.googleapis.com/auth/youtube"]
WRITABLE_TOKEN_PATH = Path("/tmp/youtube-token.json")


def get_authenticated_service(client_secret_file: str, token_file: str):
    """YouTube APIの認証済みサービスを返す。

    K8s SecretはReadOnlyなので、トークンを書き込み可能な場所にコピーして使う。
    """
    creds = None
    token_path = Path(token_file)

    # 初回: Secretから書き込み可能な場所にコピー
    if not WRITABLE_TOKEN_PATH.exists() and token_path.exists():
        shutil.copy2(str(token_path), str(WRITABLE_TOKEN_PATH))

    if WRITABLE_TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(str(WRITABLE_TOKEN_PATH), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(client_secret_file, SCOPES)
            creds = flow.run_local_server(port=0)

        WRITABLE_TOKEN_PATH.write_text(creds.to_json())

    return build("youtube", "v3", credentials=creds)


def _calc_publish_at(publish_timing: str) -> datetime | None:
    """公開タイミングからpublishAt日時を計算する。Noneなら即公開。"""
    now = datetime.now(timezone.utc)
    jst = timezone(timedelta(hours=9))

    if publish_timing == "now":
        return None
    elif publish_timing == "1hour":
        return now + timedelta(hours=1)
    elif publish_timing == "2hour":
        return now + timedelta(hours=2)
    elif publish_timing == "tomorrow_18":
        tomorrow = (datetime.now(jst) + timedelta(days=1)).replace(
            hour=18, minute=0, second=0, microsecond=0
        )
        return tomorrow.astimezone(timezone.utc)
    else:
        return now + timedelta(hours=1)


def upload_video(
    service,
    video_path: str,
    title: str,
    description: str,
    category_id: str = "22",
    publish_timing: str = "1hour",
) -> str:
    """動画をYouTubeにアップロードする。

    Args:
        service: YouTube APIサービス
        video_path: アップロードする動画ファイルパス
        title: 動画タイトル
        description: 動画の説明文
        category_id: YouTubeカテゴリID
        publish_timing: 公開タイミング (now, 1hour, 2hour, tomorrow_18)

    Returns:
        アップロードされた動画のID
    """
    publish_at = _calc_publish_at(publish_timing)

    if publish_at is None:
        status = {
            "privacyStatus": "public",
            "selfDeclaredMadeForKids": False,
        }
    else:
        status = {
            "privacyStatus": "private",
            "publishAt": publish_at.isoformat(),
            "selfDeclaredMadeForKids": False,
        }

    body = {
        "snippet": {
            "title": title,
            "description": description,
            "categoryId": category_id,
        },
        "status": status,
    }

    media = MediaFileUpload(video_path, chunksize=10 * 1024 * 1024, resumable=True)

    request = service.videos().insert(
        part="snippet,status",
        body=body,
        media_body=media,
    )

    response = _resumable_upload(request)
    return response["id"]


def set_thumbnail(service, video_id: str, thumbnail_path: str):
    """動画のサムネイルを設定する。"""
    media = MediaFileUpload(thumbnail_path, mimetype="image/jpeg")
    service.thumbnails().set(
        videoId=video_id,
        media_body=media,
    ).execute()


def _resumable_upload(request, max_retries=5):
    """リジューム可能なアップロードを実行する。"""
    import time
    import httplib2

    response = None
    retry = 0
    while response is None:
        try:
            status, response = request.next_chunk(num_retries=3)
            if status:
                print(f"  アップロード進捗: {int(status.progress() * 100)}%")
        except httplib2.HttpLib2Error as e:
            retry += 1
            if retry > max_retries:
                raise RuntimeError(f"アップロード失敗（リトライ上限）: {e}")
            print(f"  通信エラー、リトライ {retry}/{max_retries}: {e}")
            time.sleep(2 ** retry)
    return response
