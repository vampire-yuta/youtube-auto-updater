"""YouTube Data API v3 によるアップロード"""

from datetime import datetime, timedelta, timezone

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

import json
from pathlib import Path

SCOPES = ["https://www.googleapis.com/auth/youtube"]


def get_authenticated_service(client_secret_file: str, token_file: str):
    """YouTube APIの認証済みサービスを返す。

    初回はブラウザ認証。以降はトークンファイルを再利用。
    """
    creds = None
    token_path = Path(token_file)

    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(client_secret_file, SCOPES)
            creds = flow.run_local_server(port=0)

        token_path.parent.mkdir(parents=True, exist_ok=True)
        token_path.write_text(creds.to_json())

    return build("youtube", "v3", credentials=creds)


def upload_video(
    service,
    video_path: str,
    title: str,
    description: str,
    category_id: str = "22",
    publish_delay_minutes: int = 60,
) -> str:
    """動画をYouTubeに非公開アップロードし、公開予約を設定する。

    Args:
        service: YouTube APIサービス
        video_path: アップロードする動画ファイルパス
        title: 動画タイトル
        description: 動画の説明文
        category_id: YouTubeカテゴリID
        publish_delay_minutes: アップロードから公開までの待ち時間（分）

    Returns:
        アップロードされた動画のID
    """
    publish_at = datetime.now(timezone.utc) + timedelta(minutes=publish_delay_minutes)

    body = {
        "snippet": {
            "title": title,
            "description": description,
            "categoryId": category_id,
        },
        "status": {
            "privacyStatus": "private",
            "publishAt": publish_at.isoformat(),
            "selfDeclaredMadeForKids": False,
        },
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


def _resumable_upload(request):
    """リジューム可能なアップロードを実行する。"""
    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            print(f"  アップロード進捗: {int(status.progress() * 100)}%")
    return response
