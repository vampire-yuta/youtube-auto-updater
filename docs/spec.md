# YouTube Auto Uploader 仕様書

## 概要

ブラウザから動画をアップロードすると、BGM合成・サムネイル生成・YouTube公開予約を自動実行するWebアプリケーション。Kubernetes（kind/minikube）上で動作する。

## システム構成

```
[ブラウザ]
  動画ファイル選択 + タイトル・サムネ文字入力 → 送信

[Kubernetes (kind/minikube)]
  FastAPI Pod
    → 動画受信
    → FFmpegでBGM合成
    → サムネイル生成（フレーム切り出し + テキスト合成）
    → YouTube Data API v3で非公開アップロード（1時間後に公開予約）
    → 一時ファイル削除
```

## Web UI

シンプルなHTMLフォーム。1ページ完結。

- タイトル（テキスト入力）
- サムネイル文字（テキスト入力）
- 動画ファイル（ファイル選択）
- アップロードボタン

送信後、処理結果（成功/失敗、YouTube URL）を表示。

## 処理フロー

### 1. 動画受信

- FastAPIでmultipart/form-dataとして受信
- 一時ディレクトリに保存

### 2. BGM合成

- FFmpegを使用
- BGMファイル: コンテナ内 `/app/assets/bgm.mp3`（固定）
- BGMは動画の長さに合わせてループ再生
- BGM音量: 元音量の10%程度（自分の声が主）
- 動画の音声トラック（自分の声）はそのまま維持

### 3. サムネイル生成

- FFmpegで動画の中間地点のフレームを1枚切り出し
- Pillowでテキストを合成
  - スタイル: 白文字、黒縁取り、画像下部に大きく配置
  - フォント: コンテナ内 `/app/assets/font.ttf`

### 4. YouTubeアップロード

- YouTube Data API v3を使用
- OAuth2認証（トークンはK8s Secretから読み込み）
- アップロード設定:
  - タイトル: フォーム入力値
  - 説明文: テンプレート固定
  - サムネイル: 生成した画像
  - 公開設定: 非公開 → 1時間後に公開予約（publishAt）
  - カテゴリ: People & Blogs (22)

### 5. 後処理

- 一時ファイル（アップロード動画、BGM合成済み動画、サムネイル画像）を削除
- 処理結果をレスポンスとして返す

## ディレクトリ構成

```
youtube-auto-uploader/
├── docs/
│   └── spec.md                # この仕様書
├── src/
│   ├── app.py                 # FastAPIアプリケーション
│   ├── audio.py               # FFmpegによるBGM合成
│   ├── thumbnail.py           # サムネイル生成
│   └── uploader.py            # YouTubeアップロード
├── templates/
│   └── index.html             # アップロードフォーム
├── config/
│   └── description.txt        # 説明文テンプレート
├── assets/
│   ├── bgm.mp3               # BGMファイル（手動配置）
│   └── font.ttf              # サムネ用フォント（手動配置）
├── helm/
│   └── youtube-auto-uploader/
│       ├── Chart.yaml
│       ├── values.yaml
│       └── templates/
│           ├── deployment.yaml
│           ├── service.yaml
│           ├── secret.yaml
│           └── configmap.yaml
├── Dockerfile
└── requirements.txt
```

## Kubernetes構成

### コンテナイメージ

- ベース: python:3.12-slim + FFmpeg
- ローカルビルド → `kind load docker-image` or `minikube image load`

### Helmリソース

| リソース | 内容 |
|---|---|
| Deployment | FastAPIアプリ（1 replica） |
| Service | NodePort or port-forward でアクセス |
| Secret | YouTube OAuth2認証情報（client_secret.json, token.json） |
| ConfigMap | 説明文テンプレート |

### Secret に格納するもの

- `client_secret.json` — Google OAuth2クライアントID
- `token.json` — 認証済みトークン（初回認証後に取得）

## 依存関係

### システム

- Python 3.12+
- FFmpeg

### Pythonパッケージ

- fastapi — Webフレームワーク
- uvicorn — ASGIサーバ
- python-multipart — ファイルアップロード
- jinja2 — HTMLテンプレート
- google-api-python-client — YouTube Data API
- google-auth-oauthlib — OAuth2認証
- Pillow — 画像処理（テキスト合成）

## 実行方法

### ローカルビルド & デプロイ

```bash
# イメージビルド
docker build -t youtube-auto-uploader:latest .

# kindの場合
kind load docker-image youtube-auto-uploader:latest

# minikubeの場合
minikube image load youtube-auto-uploader:latest

# Helmデプロイ
helm install youtube-uploader helm/youtube-auto-uploader

# アクセス
kubectl port-forward svc/youtube-uploader 8080:8080
# → http://localhost:8080
```

## 初回セットアップ

1. YouTube Data API v3を有効化（Google Cloud Console）
2. OAuth2クライアントIDを作成
3. ローカルで初回認証を実行してtoken.jsonを取得
4. K8s Secretに認証情報を登録
5. `assets/bgm.mp3` と `assets/font.ttf` を配置
6. Dockerイメージをビルド & デプロイ
