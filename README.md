## 使用技術

- Python
- FastAPI
- Docker / Docker Compose
- boto3
- Prowler
- AI API
- HTML / CSS / JavaScript

## ディレクトリ構成

```text
cloud-security-diagnosis/
├── app.py
├── main.py
├── diagnosis_runner.py
├── requirements.txt
├── Dockerfile
├── compose.yaml
│
├── backend/          # バックエンド処理
├── frontend/         # Web画面
├── templates/        # ヒアリングシート等
├── testdata/         # テスト用データ
│
├── uploads/          # アップロードファイル
├── findings/         # Finding
├── output/           # 診断結果
└── logs/             # ログ
```

※ `uploads/`、`findings/`、`output/`、`logs/` はGit管理対象外です。

## 環境設定

`.env` に実行に必要な環境変数を設定します。

`.env` には認証情報やAPIキーなどの機密情報が含まれるため、GitHubにはコミットしないでください。

## 起動方法

### 1. コンテナをビルド・起動

```shell
docker compose up -d --build
```

### 2. ログを確認

```shell
docker compose logs -f
```

### 3. Web画面へアクセス

ブラウザから以下へアクセスします。

```text
http://localhost:8800/
```

## AWS診断用Role

診断対象AWSアカウントに診断用IAM Roleを作成します。

例：

```text
CloudSecurityAssessmentRole
```

診断に必要なAWS設定を参照できる読み取り権限を付与し、ツールから `AssumeRole` して診断を実行します。

## 診断結果

診断によって取得したAWS設定からFindingを生成します。

その後、AIを使用して以下のような観点から評価します。

- リスクレベル
- 設定上の問題
- 誤検知の可能性
- 判断理由
- 推奨される対応

## セキュリティ上の注意

以下の情報はGitHubへコミットしないでください。

- `.env`
- AWS認証情報
- APIキー
- 顧客の実データ
- 診断結果
- アップロードされたヒアリングシート

これらは `.gitignore` でGit管理対象から除外します。
