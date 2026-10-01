# ファイル依存関係マップ

> 各ファイルが「何をして」「どこに影響するか」を一覧化したドキュメントです。  
> GitHub 管理後もコードの全体像を素早く把握できるよう作成しています。

---

## プロジェクト全体構成

```
cloud-security-diagnosis/
├── app.py                          ← Web アプリ エントリーポイント（FastAPI）
├── diagnosis_runner.py             ← 診断処理コア（バックグラウンド実行）
├── main.py                         ← CLI 実行用エントリーポイント（旧版・開発用）
│
├── backend/
│   ├── input/
│   │   ├── hearing_reader.py       ← Excel ヒアリングシート読み込み
│   │   └── hearing_validator.py    ← ヒアリングシート入力チェック
│   ├── aws/
│   │   └── aws_connector.py        ← AWS 認証・AssumeRole
│   └── ai/
│       ├── ai_input_builder.py     ← AI へ渡すデータ整形
│       └── bedrock_evaluator.py    ← Amazon Bedrock 呼び出し・料金計算
│
├── frontend/
│   ├── views/
│   │   ├── pre_diagnosis.html      ← 診断開始画面（Jinja2 テンプレート）
│   │   ├── result.html             ← 診断結果画面（Jinja2 テンプレート）
│   │   └── history.html            ← 履歴一覧画面（Jinja2 テンプレート）
│   └── static/
│       ├── css/style.css           ← 全画面共通スタイル
│       ├── js/pre_diagnosis.js     ← 診断開始画面のロジック
│       ├── js/result.js            ← 診断結果画面のロジック
│       └── js/history.js           ← 履歴画面のロジック
│
├── templates/
│   ├── hearing_template_v2.xlsx    ← ヒアリングシート（顧客配布用テンプレート）
│   └── customer_diagnosis_role.yaml← 診断用 IAM Role の CloudFormation テンプレート
│
├── output/                         ← 診断結果保存先（タイムスタンプ別フォルダ）
├── uploads/                        ← アップロードされたヒアリングシート一時保存
│
├── Dockerfile                      ← FastAPI アプリ用コンテナ定義
├── compose.yaml                    ← Docker Compose 設定（DooD 構成）
├── requirements.txt                ← Python 依存パッケージ
├── .env                            ← AWS 認証情報・Bedrock 設定（Git 管理外）
└── .gitignore                      ← Git 除外設定
```

---

## ファイル別 詳細マップ

### エントリーポイント

| ファイル | 役割 | 呼び出し先 | 影響範囲 |
|---|---|---|---|
| [`app.py`](app.py) | FastAPI アプリ本体。ルーティング・API エンドポイント定義 | `diagnosis_runner.py`、`backend/input/*` | 全 API・全画面 |
| [`diagnosis_runner.py`](diagnosis_runner.py) | 診断処理をバックグラウンドスレッドで実行。進捗管理・結果保存 | `backend/input/*`、`backend/aws/*`、`backend/ai/*` | 診断フロー全体 |
| [`main.py`](main.py) | CLI から直接診断を実行する旧エントリーポイント（開発・デバッグ用） | `backend/input/*`、`backend/aws/*`、`backend/ai/*` | CLI 実行時のみ |

---

### backend/input（入力処理）

| ファイル | 役割 | 呼び出し元 | 出力 |
|---|---|---|---|
| [`backend/input/hearing_reader.py`](backend/input/hearing_reader.py) | Excel ヒアリングシートを読み込み、辞書形式に変換する | `app.py`、`diagnosis_runner.py`、`main.py` | `{"基本情報": {...}, "権限系": {"MFA": {...}}}` |
| [`backend/input/hearing_validator.py`](backend/input/hearing_validator.py) | ヒアリングシートの必須項目・形式チェック（ARN・アカウントID等） | `app.py`、`diagnosis_runner.py`、`main.py` | エラーメッセージリスト |

**データフロー:**
```
hearing_template_v2.xlsx
    → hearing_reader.py（読み込み）
    → hearing_validator.py（バリデーション）
    → diagnosis_runner.py / app.py（診断処理へ）
```

---

### backend/aws（AWS 接続）

| ファイル | 役割 | 呼び出し元 | 出力 |
|---|---|---|---|
| [`backend/aws/aws_connector.py`](backend/aws/aws_connector.py) | MFA 認証 → STS GetSessionToken → AssumeRole の一連の AWS 認証フロー | `diagnosis_runner.py`、`main.py` | `(boto3.Session, role_credentials)` |

**認証フロー:**
```
.env（AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY）
    → boto3.Session（ベースセッション）
    → iam.get_user() → MFA デバイス取得
    → sts.get_session_token(mfa_code)  ← フロントから受け取った6桁コード
    → boto3.Session（MFA 認証済みセッション）
    → sts.assume_role(role_arn)
    → role_session, role_credentials（Prowler・Bedrock へ渡す）
```

---

### backend/ai（AI 評価）

| ファイル | 役割 | 呼び出し元 | 出力 |
|---|---|---|---|
| [`backend/ai/ai_input_builder.py`](backend/ai/ai_input_builder.py) | Prowler の OCSF JSON から FAIL Finding だけ抽出し、AI へ渡す最小データを組み立てる | `diagnosis_runner.py`、`main.py` | `[{"finding": {...}, "hearing": {...}}]` |
| [`backend/ai/bedrock_evaluator.py`](backend/ai/bedrock_evaluator.py) | Amazon Bedrock（Claude Haiku）を呼び出し、MFA 設定の評価結果と利用料金を返す | `diagnosis_runner.py`、`main.py` | `{"decision": ..., "risk": ..., "reason": ..., "cost_usd": ...}` |

**AI 評価フロー:**
```
output/{timestamp}/*.ocsf.json（Prowler 結果）
    → ai_input_builder.py（FAIL のみ抽出・整形）
    → bedrock_evaluator.py（Bedrock Converse API 呼び出し）
    → {"decision", "risk", "reason", "security_risk", "missing_information", "cost_usd"}
    → output/{timestamp}/mfa_ai_evaluation.json（保存）
```

**AI へ渡す情報（プライバシー制御）:**
- ✅ 渡す: 対象種別（ROOT / IAM_USER）、対象名、MFA 判定、ヒアリング回答
- ❌ 渡さない: AWSアカウントID、ARN全体、Role情報、認証情報

---

### frontend（画面）

| ファイル | 役割 | 対応 API | 対応 JS |
|---|---|---|---|
| [`frontend/views/pre_diagnosis.html`](frontend/views/pre_diagnosis.html) | 診断開始画面。ファイルアップロード・MFA入力・診断実行・進捗表示 | `POST /api/hearing/upload`、`POST /api/diagnosis/start`、`GET /api/diagnosis/{id}/progress` | `pre_diagnosis.js` |
| [`frontend/views/result.html`](frontend/views/result.html) | 診断結果画面。サマリー・Finding 一覧・AI 評価結果表示 | `GET /api/result/{timestamp}` | `result.js` |
| [`frontend/views/history.html`](frontend/views/history.html) | 過去の診断履歴一覧 | `GET /api/history` | `history.js` |
| [`frontend/static/css/style.css`](frontend/static/css/style.css) | 全画面共通スタイル | - | - |
| [`frontend/static/js/pre_diagnosis.js`](frontend/static/js/pre_diagnosis.js) | ファイルアップロード・バリデーション表示・SSE 進捗受信 | `app.py` | - |
| [`frontend/static/js/result.js`](frontend/static/js/result.js) | 診断結果 JSON の取得・レンダリング | `app.py` | - |
| [`frontend/static/js/history.js`](frontend/static/js/history.js) | 履歴一覧の取得・レンダリング | `app.py` | - |

---

### インフラ・設定ファイル

| ファイル | 役割 | 影響範囲 |
|---|---|---|
| [`Dockerfile`](Dockerfile) | FastAPI アプリのコンテナイメージ定義 | Docker 環境での起動全体 |
| [`compose.yaml`](compose.yaml) | Docker Compose 設定。DooD（Docker-outside-of-Docker）構成で Prowler を起動 | Docker 環境での起動全体 |
| [`requirements.txt`](requirements.txt) | Python 依存パッケージ（FastAPI / boto3 / openpyxl 等） | アプリ全体 |
| [`.env`](`.env`) | AWS 認証情報・Bedrock 設定（**Git 管理外**） | `aws_connector.py`、`bedrock_evaluator.py`、`diagnosis_runner.py` |
| [`.gitignore`](.gitignore) | Git 除外設定（`.env`、`output/`、`uploads/` 等） | Git 管理範囲 |

---

### テンプレート・テストデータ

| ファイル | 役割 |
|---|---|
| [`templates/hearing_template_v2.xlsx`](templates/hearing_template_v2.xlsx) | 顧客へ配布するヒアリングシートのテンプレート |
| [`templates/customer_diagnosis_role.yaml`](templates/customer_diagnosis_role.yaml) | 顧客 AWS アカウントに作成する診断用 IAM Role の CloudFormation テンプレート |
| [`testdata/mfa_fail_dummy.ocsf.json`](testdata/mfa_fail_dummy.ocsf.json) | AI 評価テスト用のダミー Prowler 出力（OCSF 形式） |

---

## 診断フロー全体図

```
[ブラウザ]
    │
    │ 1. Excel アップロード
    ▼
[app.py] POST /api/hearing/upload
    │
    ├─→ hearing_reader.py（Excel 読み込み）
    └─→ hearing_validator.py（バリデーション）
    │
    │ 2. 診断開始（MFAコード + モデルID）
    ▼
[app.py] POST /api/diagnosis/start
    │
    └─→ diagnosis_runner.run_diagnosis()（別スレッド）
            │
            ├─ aws_connector.assume_role()
            │       └─ .env の認証情報 + フロントの MFA コード
            │
            ├─ docker run prowlercloud/prowler（subprocess）
            │       └─ output/{timestamp}/*.ocsf.json 生成
            │
            ├─ ai_input_builder.build_mfa_ai_inputs()
            │       └─ FAIL Finding のみ抽出
            │
            ├─ bedrock_evaluator.evaluate_mfa()
            │       └─ Bedrock Converse API → 評価 JSON
            │
            └─ output/{timestamp}/diagnosis_result.json 保存
    │
    │ 3. 進捗確認（SSE）
    ▼
[app.py] GET /api/diagnosis/{id}/progress
    │
    └─→ diagnosis_runner.get_diagnosis_progress()
    │
    │ 4. 結果表示
    ▼
[app.py] GET /api/result/{timestamp}
    │
    └─→ diagnosis_runner.load_result()
            └─ output/{timestamp}/diagnosis_result.json 読み込み
```

---

## 出力ファイル構造

```
output/{timestamp}/
├── prowler-output-{account_id}-{timestamp}.ocsf.json  ← Prowler 診断結果（OCSF 形式）
├── prowler-output-{account_id}-{timestamp}.csv        ← Prowler 診断結果（CSV）
├── prowler-output-{account_id}-{timestamp}.html       ← Prowler 診断結果（HTML レポート）
├── prowler.log                                         ← Prowler 実行ログ
├── mfa_ai_evaluation.json                              ← AI 評価結果（FAIL のみ）
└── diagnosis_result.json                               ← サマリー + Finding 統合結果（履歴用）
```

---

## .env に必要な環境変数

| 変数名 | 用途 | 参照ファイル |
|---|---|---|
| `AWS_ACCESS_KEY_ID` | AWS 認証（ベースユーザー） | `aws_connector.py` |
| `AWS_SECRET_ACCESS_KEY` | AWS 認証（ベースユーザー） | `aws_connector.py` |
| `BEDROCK_INFERENCE_PROFILE_ID` | Bedrock 推論プロファイル ARN | `diagnosis_runner.py`、`main.py` |
| `BEDROCK_REGION` | Bedrock リージョン（デフォルト: `ap-northeast-1`） | `diagnosis_runner.py`、`main.py` |
| `USD_TO_JPY` | AI 料金の円換算レート（デフォルト: `155`） | `diagnosis_runner.py`、`main.py` |
| `HOST_OUTPUT_DIR` | Docker DooD 構成時のホスト側 output パス | `diagnosis_runner.py`、`compose.yaml` |
