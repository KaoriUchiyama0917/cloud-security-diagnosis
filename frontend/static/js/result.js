/**
 * result.js
 * 結果出力画面（Finding一覧・詳細パネル・サマリー表示）
 * 現在診断・過去診断共通で使用する
 */

"use strict";

// PAGE_TIMESTAMP は result.html の <script> で定義済み

// ============================================================
// DOM 参照
// ============================================================

const loadingState     = document.getElementById("loadingState");
const errorState       = document.getElementById("errorState");
const errorMsg         = document.getElementById("errorMsg");
const resultBody       = document.getElementById("resultBody");

// サマリー
const summarySystemName = document.getElementById("summarySystemName");
const summaryDatetime   = document.getElementById("summaryDatetime");
const summaryCost       = document.getElementById("summaryCost");
const statTotal         = document.getElementById("statTotal");
const statPass          = document.getElementById("statPass");
const statFail          = document.getElementById("statFail");
const statAi            = document.getElementById("statAi");

// Finding テーブル
const findingTableBody  = document.getElementById("findingTableBody");

// 詳細パネル
const detailPanel       = document.getElementById("detailPanel");
const detailCloseBtn    = document.getElementById("detailCloseBtn");
const detailMeta        = document.getElementById("detailMeta");
const detailMessage     = document.getElementById("detailMessage");
const detailAiSection   = document.getElementById("detailAiSection");
const detailReason      = document.getElementById("detailReason");
const detailRiskSection = document.getElementById("detailRiskSection");
const detailSecurityRisk = document.getElementById("detailSecurityRisk");
const detailHearingSection = document.getElementById("detailHearingSection");
const detailHearing     = document.getElementById("detailHearing");
const detailMissingSection = document.getElementById("detailMissingSection");
const detailMissingList = document.getElementById("detailMissingList");

// 診断員レビュー
const detailReviewSection   = document.getElementById("detailReviewSection");
const reviewStatusBadge     = document.getElementById("reviewStatusBadge");
const reviewResult          = document.getElementById("reviewResult");
const reviewSeverity        = document.getElementById("reviewSeverity");
const reviewReason          = document.getElementById("reviewReason");
const reviewSecurityRisk    = document.getElementById("reviewSecurityRisk");
const reviewRecommendation  = document.getElementById("reviewRecommendation");
const reviewNote            = document.getElementById("reviewNote");
const reviewIncludeInReport = document.getElementById("reviewIncludeInReport");
const reviewSaveBtn         = document.getElementById("reviewSaveBtn");
const reviewSaveMsg         = document.getElementById("reviewSaveMsg");

// ============================================================
// 初期化
// ============================================================

let allFindings = [];
let resultSummary = {};
let currentFindingIdx = null;  // 現在開いている Finding のインデックス

async function init() {
  try {
    const res = await fetch(`/api/result/${PAGE_TIMESTAMP}`);
    if (!res.ok) {
      const data = await res.json();
      showError(data.error || "診断結果の取得に失敗しました。");
      return;
    }
    const data = await res.json();
    allFindings = data.findings || [];
    resultSummary = data.summary || {};
    renderAll(resultSummary, allFindings);
    hide(loadingState);
    show(resultBody);
  } catch (err) {
    showError(`通信エラー: ${err.message}`);
  }
}

// ============================================================
// 全体描画
// ============================================================

function renderAll(summary, findings) {
  renderSummary(summary);
  renderFindingTable(findings);
  updateReportButton(findings);
}

function updateReportButton(findings) {
  const reportBtn = document.getElementById("reportBtn");
  const reportBlockMsg = document.getElementById("reportBlockMsg");

  if (!reportBtn) return;

  // FAIL かつ未レビューの Finding を取得
  const unreviewed = (findings || []).filter(f => {
    if (f.cspm_status !== "FAIL") return false;

    const review = f.review || {};

    return review.status !== "approved";
  });

  if (unreviewed.length > 0) {
    // 未レビューがある間はレポート作成不可
    reportBtn.removeAttribute("href");
    reportBtn.style.opacity = "0.4";
    reportBtn.style.cursor = "not-allowed";
    reportBtn.style.pointerEvents = "none";

    if (reportBlockMsg) {
      reportBlockMsg.textContent =
        `未レビューの項目が ${unreviewed.length} 件あります。すべてのレビューを確定してください。`;

      reportBlockMsg.classList.remove("hidden");
    }

  } else {
    // 全FAILのレビューが完了したら有効化
    reportBtn.href = `/report/${PAGE_TIMESTAMP}`;
    reportBtn.style.opacity = "";
    reportBtn.style.cursor = "";
    reportBtn.style.pointerEvents = "";

    if (reportBlockMsg) {
      reportBlockMsg.classList.add("hidden");
    }
  }
}
// ============================================================
// サマリー描画
// ============================================================

function renderSummary(s) {
  summarySystemName.textContent = s.system_name || "（システム名なし）";
  summaryDatetime.textContent   = `診断日時: ${s.diagnosis_datetime || ""}`;

  statTotal.textContent = s.total ?? "-";
  statPass.textContent  = s.pass_count ?? "-";
  statFail.textContent  = s.fail_count ?? "-";
  statAi.textContent    = s.ai_count ?? "-";

  // AI 料金
  const cost = s.cost || {};
  if (cost.usd_str) {
    summaryCost.innerHTML =
      `<strong>AI Cost:</strong> ${cost.usd_str} <span style="color:var(--color-text-muted)">(約 ${cost.jpy_str})</span>`;
  }
}

// ============================================================
// Finding テーブル描画
// ============================================================

function renderFindingTable(findings) {
  findingTableBody.innerHTML = "";

  if (findings.length === 0) {
    const tr = document.createElement("tr");
    tr.innerHTML = `<td colspan="5" class="text-center text-muted" style="padding:32px;">
      診断結果がありません。
    </td>`;
    findingTableBody.appendChild(tr);
    return;
  }

  findings.forEach((f, idx) => {
    const tr = document.createElement("tr");
    tr.dataset.idx = idx;
    tr.addEventListener("click", () => openDetail(idx, tr));

    // 診断項目
    const tdTitle = document.createElement("td");
    tdTitle.textContent = f.check_title || f.check_id;

    // 対象
    const tdTarget = document.createElement("td");
    tdTarget.style.fontFamily = "monospace";
    tdTarget.textContent = f.target || "-";

    // CSPM 判定
    const tdCspm = document.createElement("td");
    tdCspm.appendChild(makeCspmBadge(f.cspm_status));

    // AI 判定
    const tdAi = document.createElement("td");
    if (f.cspm_status === "PASS") {
      tdAi.appendChild(makeBadge("-", "none"));
    } else if (f.ai_result) {
      tdAi.appendChild(makeAiBadge(f.ai_result.decision));
    } else {
      tdAi.appendChild(makeBadge("評価中", "none"));
    }

    // リスク
    const tdRisk = document.createElement("td");
    if (f.cspm_status === "PASS") {
      tdRisk.appendChild(makeRiskBadge("NONE"));

    } else if (f.ai_result && f.ai_result.risk) {
      tdRisk.appendChild(makeRiskBadge(f.ai_result.risk));

    } else {
      tdRisk.appendChild(makeRiskBadge("NONE"));
    }
    tr.appendChild(tdTitle);
    tr.appendChild(tdTarget);
    tr.appendChild(tdCspm);
    tr.appendChild(tdAi);
    tr.appendChild(tdRisk);
    findingTableBody.appendChild(tr);
  });
}

// ============================================================
// Finding 詳細パネル
// ============================================================

let selectedRow = null;

function openDetail(idx, row) {
  const f = allFindings[idx];
  if (!f) return;

  currentFindingIdx = idx;

  // 選択行ハイライト
  if (selectedRow) selectedRow.classList.remove("selected");
  selectedRow = row;
  row.classList.add("selected");

  // メタ情報
  detailMeta.innerHTML = "";
  detailMeta.appendChild(makeBadge(f.check_title || f.check_id, "none"));
  detailMeta.appendChild(document.createTextNode(" "));

  const targetSpan = document.createElement("span");
  targetSpan.style.fontFamily = "monospace";
  targetSpan.style.fontSize = "13px";
  targetSpan.textContent = f.target || "-";
  detailMeta.appendChild(targetSpan);
  detailMeta.appendChild(document.createTextNode(" "));

  detailMeta.appendChild(makeCspmBadge(f.cspm_status));
  detailMeta.appendChild(document.createTextNode(" "));

  if (f.ai_result) {
    detailMeta.appendChild(makeAiBadge(f.ai_result.decision));
    detailMeta.appendChild(document.createTextNode(" "));
    detailMeta.appendChild(makeRiskBadge(f.ai_result.risk));
  }

  // 検出内容
  detailMessage.textContent = f.message || "（検出内容なし）";

  // AI 評価セクション
  if (f.ai_result) {
    detailReason.textContent = f.ai_result.reason || "（理由なし）";
    detailSecurityRisk.textContent = f.ai_result.security_risk || "（記載なし）";
    show(detailAiSection);
    show(detailRiskSection);

    // ヒアリング情報（AI が参照したもの）
    renderDetailHearing(resultSummary.hearing);
    show(detailHearingSection);

    // 追加確認事項
    const missing = f.ai_result.missing_information || [];
    if (missing.length > 0) {
      detailMissingList.innerHTML = "";
      missing.forEach(item => {
        const li = document.createElement("li");
        li.textContent = item;
        detailMissingList.appendChild(li);
      });
      show(detailMissingSection);
    } else {
      hide(detailMissingSection);
    }
  } else {
    hide(detailAiSection);
    hide(detailRiskSection);
    hide(detailHearingSection);
    hide(detailMissingSection);
  }

  // 診断員レビューセクション（FAIL のみ表示）
  if (f.cspm_status === "FAIL") {
    renderReviewSection(f);
    show(detailReviewSection);
  } else {
    hide(detailReviewSection);
  }

  show(detailPanel);

  // スクロール
  detailPanel.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

function renderDetailHearing(hearing) {
  detailHearing.innerHTML = "";
  if (!hearing) return;

  const items = [
    { label: "管理画面利用者の有無",   value: hearing.console_access },
    { label: "利用目的",               value: hearing.usage },
    { label: "SSO 等の別ログイン手段", value: hearing.alternative_login },
    { label: "MFA 未設定の理由",       value: hearing.mfa_exception_reason },
  ];

  items.forEach(({ label, value }) => {
    const labelEl = document.createElement("div");
    labelEl.className = "detail-hearing-label";
    labelEl.textContent = label;

    const valueEl = document.createElement("div");
    if (value) {
      valueEl.className = "detail-hearing-value";
      valueEl.textContent = value;
    } else {
      valueEl.className = "detail-hearing-value empty";
      valueEl.textContent = "未回答";
    }

    detailHearing.appendChild(labelEl);
    detailHearing.appendChild(valueEl);
  });
}

detailCloseBtn.addEventListener("click", () => {
  hide(detailPanel);
  if (selectedRow) {
    selectedRow.classList.remove("selected");
    selectedRow = null;
  }
  currentFindingIdx = null;
});

// ============================================================
// 診断員レビュー描画
// ============================================================

function renderReviewSection(f) {
  const review = f.review;
  const ai = f.ai_result;

  hide(reviewSaveMsg);

  if (review && review.status !== "unreviewed") {
    // レビュー済み → 保存済み内容を表示
    setSelectValue(reviewResult,   review.result   || "INCORRECT");
    setSelectValue(reviewSeverity, review.severity || "HIGH");
    reviewReason.value         = review.reason          || "";
    reviewSecurityRisk.value   = review.security_risk   || "";
    reviewRecommendation.value = review.recommendation  || "";
    reviewNote.value           = review.reviewer_note   || "";
    reviewIncludeInReport.checked = review.include_in_report !== false;

    reviewStatusBadge.textContent = "✓ レビュー済み";
    reviewStatusBadge.className   = "review-status-badge review-status-approved";
  } else {
    // 未レビュー → AI判定を初期値として表示
    setSelectValue(reviewResult,   ai ? ai.decision : "INCORRECT");
    setSelectValue(reviewSeverity, ai ? ai.risk     : "HIGH");
    reviewReason.value         = ai ? (ai.reason        || "") : "";
    reviewSecurityRisk.value   = ai ? (ai.security_risk || "") : "";
    reviewRecommendation.value = ai ? (ai.recommendation || "") : "";
    reviewNote.value           = "";
    reviewIncludeInReport.checked = true;

    reviewStatusBadge.textContent = "未レビュー";
    reviewStatusBadge.className   = "review-status-badge review-status-unreviewed";
  }
}

function setSelectValue(selectEl, value) {
  // 選択肢に存在する値のみセット（なければ先頭のまま）
  const opt = Array.from(selectEl.options).find(o => o.value === value);
  if (opt) selectEl.value = value;
}

// ============================================================
// レビュー保存
// ============================================================

reviewSaveBtn.addEventListener("click", async () => {
  if (currentFindingIdx === null) return;

  reviewSaveBtn.disabled = true;
  hide(reviewSaveMsg);

  const body = {
    result:            reviewResult.value,
    severity:          reviewSeverity.value,
    reason:            reviewReason.value.trim(),
    security_risk:     reviewSecurityRisk.value.trim(),
    recommendation:    reviewRecommendation.value.trim(),
    reviewer_note:     reviewNote.value.trim(),
    include_in_report: reviewIncludeInReport.checked,
  };

  try {
    const res = await fetch(
      `/api/result/${PAGE_TIMESTAMP}/review/${currentFindingIdx}`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      }
    );
    const data = await res.json();

    if (!res.ok || !data.ok) {
      showReviewMsg("保存に失敗しました。", false);
      return;
    }

    // ローカルの allFindings にも反映（再読み込みなしで表示更新）
    allFindings[currentFindingIdx].review = {
      status: "approved",
      ...body,
    };

    reviewStatusBadge.textContent = "✓ レビュー済み";
    reviewStatusBadge.className   = "review-status-badge review-status-approved";
    showReviewMsg("レビューを確定しました。", true);

    // レビュー保存後にレポート作成可否を再判定
    updateReportButton(allFindings);

  } catch (err) {
    showReviewMsg(`通信エラー: ${err.message}`, false);
  } finally {
    reviewSaveBtn.disabled = false;
  }
});

function showReviewMsg(msg, ok) {
  reviewSaveMsg.textContent  = msg;
  reviewSaveMsg.className    = ok
    ? "review-save-msg review-save-ok"
    : "review-save-msg review-save-error";
  show(reviewSaveMsg);
}

// ============================================================
// バッジ生成ユーティリティ
// ============================================================

function makeBadge(text, type) {
  const span = document.createElement("span");
  span.className = `badge badge-${type}`;
  span.textContent = text;
  return span;
}

function makeCspmBadge(status) {
  if (status === "PASS") return makeBadge("✓ PASS", "pass");
  if (status === "FAIL") return makeBadge("✗ FAIL", "fail");
  return makeBadge(status || "-", "none");
}

function makeAiBadge(decision) {
  const map = {
    "CORRECT":      [" CORRECT",      "correct"],
    "INCORRECT":    [" INCORRECT",    "incorrect"],
    "NEEDS_REVIEW": [" NEEDS_REVIEW", "needs-review"],
  };
  const [text, type] = map[decision] || [decision || "-", "none"];
  return makeBadge(text, type);
}

function makeRiskBadge(risk) {
  const map = {
    "HIGH":   [" HIGH",   "high"],
    "MEDIUM": [" MEDIUM", "medium"],
    "LOW":    [" LOW",    "low"],
    "NONE":   [" NONE",   "none"],
  };
  const [text, type] = map[risk] || [risk || "-", "none"];
  return makeBadge(text, type);
}

// ============================================================
// ユーティリティ
// ============================================================

function show(el) { el.classList.remove("hidden"); }
function hide(el) { el.classList.add("hidden"); }

function showError(msg) {
  hide(loadingState);
  errorMsg.textContent = msg;
  show(errorState);
}

// ============================================================
// 起動
// ============================================================

init();
