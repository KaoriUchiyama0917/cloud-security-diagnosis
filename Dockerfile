# ============================================================
# Dockerfile
# AWSクラウドセキュリティ診断ツール - FastAPI アプリケーション
#
# ビルド:
#   docker compose up -d --build
#
# 注意:
#   Prowler は別の Docker コンテナとして起動する（Docker-outside-of-Docker）。
#   そのため /var/run/docker.sock を compose.yaml でマウントする。
# ============================================================

FROM python:3.12-slim

# Docker-outside-of-Docker で使用する Docker CLI をインストール
RUN apt-get update \
    && apt-get install -y docker.io \
    && rm -rf /var/lib/apt/lists/*

# 作業ディレクトリ
WORKDIR /app

# 依存ライブラリをインストール（レイヤーキャッシュ活用のため先にコピー）
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# アプリケーションコードをコピー
COPY . .

# output / uploads ディレクトリを作成（ボリュームマウント前に存在させる）
RUN mkdir -p output uploads frontend/static frontend/views

# uvicorn でアプリを起動
# ポートはコンテナ内 8000 番（compose.yaml で 8800 にマッピング）
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]