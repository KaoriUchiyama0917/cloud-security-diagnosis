/**
 * pre_diagnosis.js
 * 事前画面（ステップ形式）
 *
 * STEP 1: ヒアリングシート選択・読み込み
 * STEP 2: 読込結果確認（自動表示）
 * STEP 3: AIモデル選択
 * STEP 4: MFAコード入力
 * STEP 5: 診断開始ボタン
 * STEP 6: 診断進捗（SSE）
 */

"use strict";

// ============================================================
// 状態
// ============================================================

let selectedFile  = null;
let uploadId      = null;
let selectedModel = null;  // "haiku" | "sonnet"
let diagnosisId   = null;
let sseSource     = null;
let elapsedTimer  = null;
let elapsedSeconds = 0;

// モデルID → Bedrock モデル識別子のマッピング
// ※ 実際の Bedrock モデル ID または Inference Profile ID に合わせて変更してください
const MODEL_ID_MAP = {
  haiku:  "anthropic.claude-3-haiku-20240307-v1:0",
  sonnet: "anthropic.claude-3-5-sonnet-20241022-v2:0",
};

// ============================================================
// DOM 参照
// ============================================================

const fileInput        = document.getElementById("fileInput");
const uploadArea       = document.getElementById("uploadArea");
const uploadFilename   = document.getElementById("uploadFilename");
const loadBtn          = document.getElementById("loadBtn");
const loadSpinner      = document.getElementById("loadSpinner");
const errorBox         = document.getElementById("errorBox");
const errorList        = document.getElementById("errorList");

const step2Card        = document.getElementById("step2Card");
const step3Card        = document.getElementById("step3Card");
const step4Card        = document.getElementById("step4Card");
const step5Card        = document.getElementById("step5Card");
const step6Card        = document.getElementById("step6Card");

const modelGrid        = document.getElementById("modelGrid");
const modelErrorBox    = document.getElementById("modelErrorBox");

const mfaCodeInput     = document.getElementById("mfaCodeInput");
const mfaErrorBox      = document.getElementById("mfaErrorBox");
const mfaErrorMsg      = document.getElementById("mfaErrorMsg");

// MFA入力欄：半角数字以外をリアルタイムで除去
mfaCodeInput.addEventListener("input", () => {
  mfaCodeInput.value = mfaCodeInput.value.replace(/[^\d]/g, "");
});

const startBtn         = document.getElementById("startBtn");
const progressSteps    = document.getElementById("progressSteps");
const elapsedTime      = document.getElementById("elapsedTime");
const progressError    = document.getElementById("progressError");
const progressErrorMsg = document.getElementById("progressErrorMsg");
const retryBtn         = document.getElementById("retryBtn");

// ============================================================
// STEP 1: ファイル選択
// ============================================================

fileInput.addEventListener("change", () => {
  const file = fileInput.files[0];
  if (file) setFile(file);
});

function setFile(file) {
  selectedFile = file;
  uploadFilename.textContent = `📎 ${file.name}`;
  uploadFilename.classList.remove("hidden");
  uploadArea.classList.add("has-file");
  loadBtn.disabled = false;

  // 前回の結果をリセット
  hideElement(errorBox);
  hideElement(step2Card);
  hideElement(step3Card);
  hideElement(step4Card);
  hideElement(step5Card);
  uploadId = null;
  selectedModel = null;
  uncheckAllModels();
}

// ドラッグ＆ドロップ
function handleDragOver(e) {
  e.preventDefault();
  uploadArea.classList.add("drag-over");
}
function handleDragLeave(e) {
  uploadArea.classList.remove("drag-over");
}
function handleDrop(e) {
  e.preventDefault();
  uploadArea.classList.remove("drag-over");
  const file = e.dataTransfer.files[0];
  if (file) {
    fileInput.files = e.dataTransfer.files;
    setFile(file);
  }
}

// 読み込みボタン
loadBtn.addEventListener("click", async () => {
  if (!selectedFile) return;

  setLoading(true);
  hideElement(errorBox);
  hideElement(step2Card);
  hideElement(step3Card);
  hideElement(step4Card);
  hideElement(step5Card);

  const formData = new FormData();
  formData.append("file", selectedFile);

  try {
    const res = await fetch("/api/hearing/upload", {
      method: "POST",
      body: formData,
    });
    const data = await res.json();

    if (!res.ok || !data.ok) {
      showErrors(data.errors || ["読み込みに失敗しました。"]);
      return;
    }

    uploadId = data.upload_id;
    renderHearingResult(data.hearing);

    // STEP 2・3・4・5 を順番に表示
    showElement(step2Card);
    showElement(step3Card);
    showElement(step4Card);
    showElement(step5Card);

    // STEP 2 のヘッダーを「確認済み」スタイルに
    step2Card.querySelector(".step-number").textContent = "✓";
    step2Card.querySelector(".step-number").classList.add("step-number-done");

    // STEP 3 のヘッダー番号を更新
    step3Card.querySelector(".step-number").textContent = "2";
    step4Card.querySelector(".step-number").textContent = "3";
    step5Card.querySelector(".step-number").textContent = "4";

    // AIモデル選択へスクロール
    step3Card.scrollIntoView({ behavior: "smooth", block: "start" });

  } catch (err) {
    showErrors([`通信エラー: ${err.message}`]);
  } finally {
    setLoading(false);
  }
});

// ============================================================
// STEP 2: ヒアリング読込結果の表示
// ============================================================

function renderHearingResult(hearing) {
  // 基本情報
  const basicGrid = document.getElementById("basicInfoGrid");
  basicGrid.innerHTML = "";
  const basicItems = [
    { label: "診断対象名",       value: hearing.system_name },
    { label: "クラウド",         value: hearing.cloud },
    { label: "AWSアカウントID",  value: hearing.account_id },
    { label: "Role ARN",         value: hearing.role_arn },
    { label: "リージョン",       value: hearing.region },
  ];
  basicItems.forEach(({ label, value }) => {
    basicGrid.appendChild(createInfoItem(label, value));
  });

  // 診断内容
  const diagDiv = document.getElementById("diagnosisItems");
  diagDiv.innerHTML = "";
  (hearing.diagnosis_items || []).forEach(item => {
    const badge = document.createElement("span");
    badge.className = "badge badge-pass";
    badge.style.marginRight = "8px";
    badge.textContent = item;
    diagDiv.appendChild(badge);
  });

  // MFA ヒアリング
  const mfaGrid = document.getElementById("mfaHearingGrid");
  mfaGrid.innerHTML = "";
  const mfa = hearing.mfa_hearing || {};
  const mfaItems = [
    { label: "管理画面利用者の有無",   value: mfa.console_access },
    { label: "利用目的",               value: mfa.usage },
    { label: "SSO 等の別ログイン手段", value: mfa.alternative_login },
    { label: "MFA 未設定の理由",       value: mfa.mfa_exception_reason },
  ];
  mfaItems.forEach(({ label, value }) => {
    mfaGrid.appendChild(createInfoItem(label, value));
  });
}

function createInfoItem(label, value) {
  const div = document.createElement("div");
  div.className = "info-item";

  const labelEl = document.createElement("div");
  labelEl.className = "info-label";
  labelEl.textContent = label;

  const valueEl = document.createElement("div");
  if (value) {
    valueEl.className = "info-value";
    valueEl.textContent = value;
  } else {
    valueEl.className = "info-value empty";
    valueEl.textContent = "未回答";
  }

  div.appendChild(labelEl);
  div.appendChild(valueEl);
  return div;
}

// ============================================================
// STEP 3: AIモデル選択
// ============================================================

modelGrid.addEventListener("change", (e) => {
  if (e.target.name === "aiModel") {
    selectedModel = e.target.value;
    hideElement(modelErrorBox);

    // 選択されたカードをハイライト
    document.querySelectorAll(".model-card").forEach(card => {
      card.classList.toggle("selected", card.dataset.modelId === selectedModel);
    });
  }
});

function uncheckAllModels() {
  document.querySelectorAll(".model-radio").forEach(r => r.checked = false);
  document.querySelectorAll(".model-card").forEach(c => c.classList.remove("selected"));
}

// ============================================================
// STEP 5: 診断開始
// ============================================================

startBtn.addEventListener("click", async () => {
  // バリデーション
  if (!selectedModel) {
    showElement(modelErrorBox);
    step3Card.scrollIntoView({ behavior: "smooth", block: "start" });
    return;
  }
  hideElement(modelErrorBox);

  const mfaCode = mfaCodeInput.value.trim();
  // MFAコードは任意。入力がある場合のみ形式チェック
  if (mfaCode && (mfaCode.length !== 6 || !/^\d{6}$/.test(mfaCode))) {
    mfaErrorMsg.textContent = "MFAコードは6桁の数字で入力してください。";
    showElement(mfaErrorBox);
    mfaCodeInput.focus();
    return;
  }
  hideElement(mfaErrorBox);

  // STEP 5 を非表示にして STEP 6（進捗）を表示
  hideElement(step5Card);
  showElement(step6Card);
  hideElement(progressError);

  // 進捗ステップ初期化
  renderProgressSteps([
    { step: "AWS認証",  status: "待機中" },
    { step: "Role切替", status: "待機中" },
    { step: "CSPM診断", status: "待機中" },
    { step: "AI評価",   status: "待機中" },
  ]);

  // 経過時間タイマー開始
  elapsedSeconds = 0;
  updateElapsedDisplay();
  elapsedTimer = setInterval(() => {
    elapsedSeconds++;
    updateElapsedDisplay();
  }, 1000);

  try {
    const res = await fetch("/api/diagnosis/start", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        upload_id: uploadId,
        mfa_code: mfaCode,
        model_id: MODEL_ID_MAP[selectedModel] || selectedModel,
      }),
    });
    const data = await res.json();

    if (!res.ok || data.detail) {
      stopTimer();
      showProgressError(data.detail || "診断開始に失敗しました。");
      return;
    }

    diagnosisId = data.diagnosis_id;
    startSSE(diagnosisId);

  } catch (err) {
    stopTimer();
    showProgressError(`通信エラー: ${err.message}`);
  }
});

// ============================================================
// STEP 6: SSE 進捗受信
// ============================================================

function startSSE(id) {
  if (sseSource) sseSource.close();

  sseSource = new EventSource(`/api/diagnosis/${id}/progress`);

  sseSource.onmessage = (e) => {
    const data = JSON.parse(e.data);

    if (data.status === "not_found") {
      sseSource.close();
      stopTimer();
      showProgressError("診断セッションが見つかりません。");
      return;
    }

    if (data.steps) {
      renderProgressSteps(data.steps);
    }

    if (data.elapsed !== undefined) {
      elapsedSeconds = data.elapsed;
      updateElapsedDisplay();
    }

    if (data.status === "done") {
      sseSource.close();
      stopTimer();
      if (data.timestamp) {
        window.location.href = `/result/${data.timestamp}`;
      }
    }

    if (data.status === "error") {
      sseSource.close();
      stopTimer();
      showProgressError(data.error || "診断中にエラーが発生しました。");
    }
  };

  sseSource.onerror = () => {
    sseSource.close();
    stopTimer();
    showProgressError("サーバーとの接続が切断されました。");
  };
}

// ============================================================
// 進捗ステップ描画
// ============================================================

const STEP_ICONS = {
  "AWS認証":  "🔑",
  "Role切替": "🔄",
  "CSPM診断": "🔍",
  "AI評価":   "🤖",
};

function renderProgressSteps(steps) {
  progressSteps.innerHTML = "";
  steps.forEach(({ step, status, message }) => {
    const div = document.createElement("div");
    div.className = `progress-step status-${status}`;

    const icon = document.createElement("div");
    icon.className = "step-icon";
    icon.textContent = STEP_ICONS[step] || "⚙️";

    const name = document.createElement("div");
    name.className = "step-name";
    name.textContent = step;

    const statusBadge = document.createElement("div");
    statusBadge.className = `step-status status-${status}`;
    if (status === "実行中") {
      statusBadge.innerHTML = `<span class="spinner"></span> ${status}`;
    } else {
      statusBadge.textContent = status;
    }

    div.appendChild(icon);
    div.appendChild(name);
    div.appendChild(statusBadge);
    progressSteps.appendChild(div);
  });
}

// ============================================================
// 経過時間表示
// ============================================================

function updateElapsedDisplay() {
  const m = Math.floor(elapsedSeconds / 60);
  const s = elapsedSeconds % 60;
  elapsedTime.textContent = `経過時間: ${m}分${String(s).padStart(2, "0")}秒`;
}

function stopTimer() {
  if (elapsedTimer) {
    clearInterval(elapsedTimer);
    elapsedTimer = null;
  }
}

// ============================================================
// やり直しボタン
// ============================================================

retryBtn.addEventListener("click", () => {
  window.location.reload();
});

// ============================================================
// ユーティリティ
// ============================================================

function setLoading(on) {
  loadBtn.disabled = on;
  loadSpinner.classList.toggle("hidden", !on);
}

function showErrors(errors) {
  errorList.innerHTML = "";
  errors.forEach(e => {
    const li = document.createElement("li");
    li.textContent = e;
    errorList.appendChild(li);
  });
  showElement(errorBox);
}

function showProgressError(msg) {
  progressErrorMsg.textContent = msg;
  showElement(progressError);
}

function showElement(el) {
  el.classList.remove("hidden");
}

function hideElement(el) {
  el.classList.add("hidden");
}
