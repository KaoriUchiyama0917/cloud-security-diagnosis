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

const findingAccountId      = document.getElementById("findingAccountId");
const findingRoleName       = document.getElementById("findingRoleName");

const findingGroups         = document.getElementById("findingGroups");

// ============================================================
// Finding 一覧：表示列定義
// ============================================================

const FINDING_COLUMNS = [
  {
    key: "category",
    label: "診断項目",
    render: (f) => f.category || "-"
  },
  {
    key: "check_title",
    label: "診断内容",
    render: (f) => f.check_title || f.check_id || "-"
  },
  {
    key: "target_type",
    label: "対象種別",
    render: (f) => f.target_type || "-"
  },
  {
    key: "target",
    label: "対象",
    render: (f) => f.target || "-"
  },
  {
  key: "cspm_status",
  label: "CSPM判定",
  render: (f) => {

    // Permission Boundaryだけ表示名を変更
    if (f.category === "Permission Boundary") {
      if (f.cspm_status === "PASS") {
        return makeBadge("設定あり", "pass");
      }
      if (f.cspm_status === "FAIL") {
        return makeBadge("設定なし", "fail");
      }
    }
    // その他の診断項目は通常のPASS / FAIL
    return makeCspmBadge(f.cspm_status);
  }
},
  {
    key: "severity",
    label: "Severity",
    render: (f) => f.severity || "-"
  },
  {
    key: "ai_decision",
    label: "AI判定",
    render: (f) => {
      if (f.cspm_status === "PASS") {
        return makeBadge("-", "none");
      }

      if (f.ai_result) {
        return makeAiBadge(f.ai_result.decision);
      }

      return makeBadge("未評価", "none");
    }
  },
  {
    key: "risk",
    label: "リスク",
    render: (f) => {
      if (f.cspm_status === "PASS") {
        return makeRiskBadge("NONE");
      }

      return makeRiskBadge(
        f.ai_result?.risk || "NONE"
      );
    }
  }
];

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
  renderAccountInfo(summary);
  renderFindingGroups(findings);
  updateReportButton(findings);
}

// ============================================================
// Account情報描画
// ============================================================

function renderAccountInfo(summary) {
  findingAccountId.textContent =
    summary.account_id || "-";

  const roleArn = summary.role_arn || "";

  findingRoleName.textContent =
    roleArn
      ? roleArn.split("/").pop()
      : "-";
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
function renderFindingGroups(findings) {
  findingGroups.innerHTML = "";

  if (!findings || findings.length === 0) {
    findingGroups.innerHTML = `
      <div class="text-center text-muted" style="padding:32px;">
        診断結果がありません。
      </div>
    `;
    return;
  }

  // ==========================================================
  // category ごとに Finding をまとめる
  // ==========================================================

  const grouped = {};

  findings.forEach((finding, idx) => {
    const category = finding.category || "その他";

    if (!grouped[category]) {
      grouped[category] = [];
    }

    grouped[category].push({
      finding,
      originalIndex: idx
    });
  });


  // ==========================================================
  // category ごとに折りたたみブロックを作成
  // ==========================================================

  Object.entries(grouped).forEach(
    ([category, items], categoryIndex) => {

      const passCount = items.filter(
        item => item.finding.cspm_status === "PASS"
      ).length;

      const failCount = items.filter(
        item => item.finding.cspm_status === "FAIL"
      ).length;


      // details を使うことで開閉処理を自前実装しなくてよい
      const details = document.createElement("details");

      details.className = "finding-group";

      // 最初のカテゴリだけ最初から開く
      if (categoryIndex === 0) {
        details.open = true;
      }


      // ======================================================
      // 見出し
      // ======================================================

      const summary = document.createElement("summary");
      summary.className = "finding-group-header";

      const title = document.createElement("span");
      title.className = "finding-group-title";
      title.textContent = category;

      const counts = document.createElement("span");
      counts.className = "finding-group-counts";

      counts.appendChild(
        makeBadge(`PASS ${passCount}`, "pass")
      );

      counts.appendChild(
        makeBadge(`FAIL ${failCount}`, failCount > 0 ? "fail" : "none")
      );

      summary.appendChild(title);
      summary.appendChild(counts);

      details.appendChild(summary);


      // ======================================================
      // テーブル
      // ======================================================

      const tableWrap = document.createElement("div");
      tableWrap.className = "table-wrap findings-table-wrap";

      const table = document.createElement("table");
      table.className = "findings-table";


      // ヘッダー
      const thead = document.createElement("thead");
      const headRow = document.createElement("tr");

      FINDING_COLUMNS.forEach(column => {
        // category は見出し側に出ているため表から除外
        if (column.key === "category") {
          return;
        }

        const th = document.createElement("th");
        th.textContent = column.label;

        headRow.appendChild(th);
      });

      thead.appendChild(headRow);
      table.appendChild(thead);


      // ======================================================
      // Finding
      // ======================================================

      const tbody = document.createElement("tbody");

      items.forEach(({ finding, originalIndex }) => {

        const tr = document.createElement("tr");

        tr.dataset.idx = originalIndex;

        // FAILのFindingは行全体を強調表示
        if (finding.cspm_status === "FAIL") {
          tr.classList.add("finding-row-fail");
        }

        tr.addEventListener(
          "click",
          () => openDetail(originalIndex, tr)
        );


        FINDING_COLUMNS.forEach(column => {

          // categoryはグループ名で表示済み
          if (column.key === "category") {
            return;
          }

          const td = document.createElement("td");
          const value = column.render(finding);

          if (value instanceof Node) {
            td.appendChild(value);
          } else {
            td.textContent = value ?? "-";
          }

          tr.appendChild(td);
        });


        tbody.appendChild(tr);
      });


      table.appendChild(tbody);
      tableWrap.appendChild(table);
      details.appendChild(tableWrap);

      findingGroups.appendChild(details);
    }
  );
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
