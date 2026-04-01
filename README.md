# YouTube Auto Uploader

ブラウザから動画をアップロードすると、BGM合成・サムネイル生成・YouTube公開予約を自動実行するWebアプリケーション。

## 機能

- BGMループ合成（固定BGM、音量自動調整）
- サムネイル自動生成（動画フレーム切り出し + 赤文字黒縁テキスト合成）
- YouTube Data API v3 によるアップロード・サムネイル設定・公開予約
- 公開タイミング選択（すぐ公開 / 1時間後 / 2時間後 / 明日18時）
- SSEによるリアルタイム進捗表示（ファイル送信パーセント含む）

## 技術スタック

- Python (FastAPI + uvicorn)
- FFmpeg（BGM合成・フレーム切り出し）
- Pillow（テキスト合成）
- google-api-python-client（YouTube API）
- Kubernetes (minikube / kind) + Helm

## ディレクトリ構成

```
youtube-auto-uploader/
├── src/
│   ├── app.py              # FastAPIアプリケーション（SSE進捗配信）
│   ├── audio.py            # FFmpegによるBGMループ合成
│   ├── thumbnail.py        # サムネイル生成（フレーム切り出し + テキスト合成）
│   └── uploader.py         # YouTube Data API アップロード
├── templates/
│   └── index.html          # Web UI
├── config/
│   ├── client_secret.json  # OAuth2クライアントID（手動配置）
│   ├── token.json          # OAuth2トークン（自動生成）
│   └── description.txt     # 説明文テンプレート
├── assets/
│   └── bgm.mp3             # BGMファイル（手動配置）
├── helm/youtube-auto-uploader/
│   ├── Chart.yaml
│   ├── values.yaml
│   └── templates/
│       ├── deployment.yaml
│       ├── service.yaml
│       └── configmap.yaml
├── Dockerfile
├── Makefile
└── requirements.txt
```

## セットアップ

### 1. OAuth2 クレデンシャルの取得

1. [Google Cloud Console](https://console.cloud.google.com/) にアクセスし、プロジェクトを作成
2. 「APIとサービス」→「ライブラリ」から **YouTube Data API v3** を有効化
3. 「APIとサービス」→「OAuth同意画面」を設定
   - ユーザータイプ: 外部
   - アプリ名: 任意（例: YouTube Auto Uploader）
   - スコープ: `youtube` を追加
   - テストユーザー: 自分のGoogleアカウントを追加
4. 「APIとサービス」→「認証情報」→「認証情報を作成」→「OAuthクライアントID」
   - アプリケーションの種類: デスクトップアプリ
   - JSONをダウンロード → `config/client_secret.json` として保存
5. 初回トークン取得（ローカルで実行）:
   ```bash
   python3 -m venv .venv && source .venv/bin/activate
   pip install google-api-python-client google-auth-oauthlib
   python3 -c "
   import sys; sys.path.insert(0, '.')
   from src.uploader import get_authenticated_service
   svc = get_authenticated_service('config/client_secret.json', 'config/token.json')
   print('認証成功')
   "
   ```
   ブラウザが開くのでGoogleアカウントで認証 → `config/token.json` が生成される

   ※ 「アクセスをブロック」と表示された場合は「詳細」→「安全でないページに移動」でスキップ

### 2. アセット配置

- `assets/bgm.mp3` — BGMファイルを配置

### 3. デプロイ (minikube)

```bash
# セットアップ（クラスタ作成→ビルド→デプロイ）
make setup RUNTIME=minikube

# Secret登録
make secret CLIENT_SECRET=config/client_secret.json TOKEN=config/token.json

# アクセス
make port-forward
# → http://localhost:8081
```

### 3. デプロイ (kind)

```bash
make setup
make secret CLIENT_SECRET=config/client_secret.json TOKEN=config/token.json
make port-forward
```

## Makefileコマンド

| コマンド | 内容 |
|---|---|
| `make setup` | クラスタ作成→ビルド→ロード→Helmインストール |
| `make setup RUNTIME=minikube` | minikubeで同上 |
| `make deploy` | ビルド→ロード→Helmアップグレード（コード変更後） |
| `make secret CLIENT_SECRET=... TOKEN=...` | OAuth2認証情報をK8s Secretに登録 |
| `make port-forward` | localhost:8081 でアクセス |
| `make logs` | Podログ確認 |
| `make status` | Pod状態確認 |
| `make clean` | Helm削除 + クラスタ削除 |

## トークンについて

- アクセストークンは約1時間で期限切れ
- リフレッシュトークンで自動更新されるため、通常は再認証不要
- パスワード変更やアクセス取り消し時のみ再認証が必要
