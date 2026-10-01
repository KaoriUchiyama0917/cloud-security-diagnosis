/**
 * history.js
 * 履歴画面（過去の診断結果一覧表示・結果画面への遷移）
 */

"use strict";

// ============================================================
// DOM 参照
// ============================================================

const loadingState    = document.getElementById("loadingState");
const errorState      = document.getElementById("errorState");
const errorMsg        = document.getElementById("errorMsg");
const historyBody     = document.getElementById("historyBody");
const emptyState      = document.getElementById("emptyState");
const historyTableCard = document.getElementById("historyTableCard");
const historyTableBody = document.getElementById("historyTableBody");

// ============================================================
// 初期化
// ============================================================

async function init() {
  try {
    const res = await fetch("/api/history");
    if (!res.ok) {
      const data = await res.json();
      showError(data.error || "履歴の取得に失敗しました。");
      return;
    }
    const history = await res.json();

    hide(loadingState);
    show(historyBody);

    if (history.length === 0) {
      show(emptyState);
      hide(historyTableCard);
    } else {
      hide(emptyState);
      show(historyTableCard);
      renderHistory(history);
    }
  } catch (err) {
    showError(`通信エラー: ${err.message}`);
  }
}

// ============================================================
// 履歴テーブル描画
// ============================================================

function renderHistory(history) {
  historyTableBody.innerHTML = "";

  history.forEach(item => {
    const tr = document.createElement("tr");
    tr.style.cursor = "pointer";
    tr.addEventListener("click", () => {
      window.location.href = `/result/${item.timestamp}`;
    });

    // 診断対象
    const tdSystem = document.createElement("td");
    tdSystem.style.fontWeight = "600";
    tdSystem.textContent = item.system_name || "（名称なし）";

    // 診断日時
    const tdDate = document.createElement("td");
    tdDate.textContent = item.diagnosis_datetime || item.timestamp || "-";

    // 最大リスク
    const tdRisk = document.createElement("td");
    if (item.max_risk) {
      tdRisk.appendChild(makeRiskBadge(item.max_risk));
    } else {
      const span = document.createElement("span");
      span.className = "badge badge-none";
      span.textContent = "-";
      tdRisk.appendChild(span);
    }

    // リスク別件数（シンプルテキスト）
    const tdRiskCounts = document.createElement("td");
    tdRiskCounts.style.fontSize = "12px";
    tdRiskCounts.style.fontFamily = "monospace";
    tdRiskCounts.style.whiteSpace = "nowrap";
    const rc = item.risk_counts || {};
    if (rc.HIGH !== undefined) {
      tdRiskCounts.textContent = `HIGH:${rc.HIGH || 0}  MEDIUM:${rc.MEDIUM || 0}  LOW:${rc.LOW || 0}  NONE:${rc.NONE || 0}`;
    } else {
      tdRiskCounts.textContent = "-";
    }

    // 診断件数
    const tdTotal = document.createElement("td");
    tdTotal.textContent = item.total ?? "-";

    // AI 料金
    const tdCost = document.createElement("td");
    const cost = item.cost || {};
    if (cost.usd_str) {
      tdCost.innerHTML = `
        <span class="font-mono" style="font-size:13px;">${cost.usd_str}</span>
        <span class="text-muted text-sm"> (約 ${cost.jpy_str})</span>
      `;
    } else {
      tdCost.textContent = "-";
    }

    tr.appendChild(tdSystem);
    tr.appendChild(tdDate);
    tr.appendChild(tdRisk);
    tr.appendChild(tdRiskCounts);
    tr.appendChild(tdTotal);
    tr.appendChild(tdCost);
    historyTableBody.appendChild(tr);
  });
}

// ============================================================
// バッジ生成
// ============================================================

function makeRiskBadge(risk) {
  const map = {
    "HIGH":   ["🔴 HIGH",   "high"],
    "MEDIUM": ["🟡 MEDIUM", "medium"],
    "LOW":    ["🟢 LOW",    "low"],
  };
  const [text, type] = map[risk] || [risk || "-", "none"];
  const span = document.createElement("span");
  span.className = `badge badge-${type}`;
  span.textContent = text;
  return span;
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
