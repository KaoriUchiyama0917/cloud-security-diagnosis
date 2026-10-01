/**
 * report.js — 顧客向けレポート画面のデータ取得・描画ロジック
 */

"use strict";

// ============================================================
// 初期化
// ============================================================

document.addEventListener("DOMContentLoaded", () => {
  init();
});

async function init() {
  try {
    const res = await fetch(`/api/report/${PAGE_TIMESTAMP}`);
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      showError(err.detail || "レポートデータの取得に失敗しました。");
      return;
    }
    const data = await res.json();
    render(data);
  } catch (e) {
    showError("通信エラーが発生しました: " + e.message);
  }
}

// ============================================================
// メイン描画
// ============================================================

function render(data) {
  const summary  = data.summary  || {};
  const findings = data.findings || [];

  renderCover(summary);
  renderSummaryStats(summary, findings);
  renderSystemInfo(summary);
  renderFindings(findings);
  renderHearing(summary);
  renderFooter(summary);

  // 戻るリンク
  document.getElementById("backToResult").href = `/result/${PAGE_TIMESTAMP}`;

  // 表示切替
  document.getElementById("loadingState").classList.add("hidden");
  document.getElementById("reportBody").classList.remove("hidden");
}

// ============================================================
// 表紙ヘッダー
// ============================================================

function renderCover(summary) {
  const systemName = summary.system_name || "（システム名未設定）";
  const datetime   = summary.diagnosis_datetime || summary.diagnosed_at || "";
  const accountId  = summary.account_id || "";

  document.getElementById("coverSystemName").textContent = systemName;
  document.getElementById("coverDatetime").textContent   = datetime ? `診断日時：${datetime}` : "";
  document.getElementById("coverAccountId").textContent  = accountId ? `AWSアカウントID：${accountId}` : "";
}

// ============================================================
// セクション1: 診断結果サマリー
// ============================================================

function renderSummaryStats(summary, findings) {
  const total = summary.total      || summary.total_count || 0;
  const pass  = summary.pass_count || 0;
  const fail  = summary.fail_count || 0;

  document.getElementById("statTotal").textContent = total;
  document.getElementById("statPass").textContent  = pass;
  document.getElementById("statFail").textContent  = fail;

  // リスクレベル別件数を findings から算出
  const riskOrder = { HIGH: 4, MEDIUM: 3, LOW: 2, NONE: 1 };
  const riskCounts = { HIGH: 0, MEDIUM: 0, LOW: 0, NONE: 0 };
  let maxRisk = "NONE";
  for (const f of findings) {
    const risk = getRisk(f);
    const key = riskCounts.hasOwnProperty(risk) ? risk : "NONE";
    riskCounts[key]++;
    if ((riskOrder[risk] || 0) > (riskOrder[maxRisk] || 0)) {
      maxRisk = risk;
    }
  }

  const riskEl = document.getElementById("statMaxRisk");
  riskEl.textContent = maxRisk;

  const riskWrap = document.getElementById("statRiskWrap");
  riskWrap.classList.remove("report-stat-high", "report-stat-medium", "report-stat-low", "report-stat-none");
  if (maxRisk === "HIGH")   riskWrap.classList.add("report-stat-high");
  if (maxRisk === "MEDIUM") riskWrap.classList.add("report-stat-medium");
  if (maxRisk === "LOW")    riskWrap.classList.add("report-stat-low");
  if (maxRisk === "NONE")   riskWrap.classList.add("report-stat-none");

  // リスク別件数バーを描画
  const riskCountsEl = document.getElementById("riskCounts");
  if (riskCountsEl) {
    const items = [
      { key: "HIGH",   label: "HIGH（高リスク）",   cls: "report-risk-count-high" },
      { key: "MEDIUM", label: "MEDIUM（中リスク）", cls: "report-risk-count-medium" },
      { key: "LOW",    label: "LOW（低リスク）",    cls: "report-risk-count-low" },
    ];
    riskCountsEl.innerHTML = items.map(({ key, label, cls }) => `
      <div class="report-risk-count-item ${cls}">
        <span class="report-risk-count-label">${label}</span>
        <span class="report-risk-count-value">${riskCounts[key]}件</span>
      </div>
    `).join("");
  }
}

// ============================================================
// セクション2: システム情報
// ============================================================

function renderSystemInfo(summary) {
  const tbody = document.getElementById("systemInfoTable");

  const rows = [
    ["システム名",       summary.system_name        || "—"],
    ["AWSアカウントID",  summary.account_id          || "—"],
    ["診断日時",         summary.diagnosis_datetime  || summary.diagnosed_at || "—"],
    ["対象リージョン",   summary.region              || "—"],
    ["ロールARN",        summary.role_arn            || "—"],
    ["クラウド",         summary.cloud               || "AWS"],
  ];

  tbody.innerHTML = rows.map(([label, value]) => `
    <tr>
      <th class="report-info-th">${escHtml(label)}</th>
      <td class="report-info-td">${escHtml(String(value))}</td>
    </tr>
  `).join("");
}

// ============================================================
// セクション3: 検出された問題と対応方針
// ============================================================

function renderFindings(findings) {
  const container = document.getElementById("findingCards");
  const noMsg     = document.getElementById("noFindingsMsg");

  if (!findings || findings.length === 0) {
    noMsg.classList.remove("hidden");
    return;
  }

  // リスクレベル順にソート（HIGH → MEDIUM → LOW → NONE）
  const riskOrder = { HIGH: 0, MEDIUM: 1, LOW: 2, NONE: 3 };
  const sorted = [...findings].sort((a, b) => {
    return (riskOrder[getRisk(a)] ?? 9) - (riskOrder[getRisk(b)] ?? 9);
  });

  container.innerHTML = sorted.map((f, i) => buildFindingCard(f, i + 1)).join("");
}

function buildFindingCard(f, num) {
  const review   = f.review   || {};
  // const aiResult = f.ai_result || {};

  // 表示値の決定（レビュー済み優先、なければAI判定）
  const title       = f.check_title || f.check_id || "（項目名不明）";
  const target      = f.target      || "—";
  const risk        = getRisk(f);
  const message   = f.message || "—";
  const reason    = review.reason || "—";
  const secRisk   = review.security_risk || "—";
  const recommend = review.recommendation || "—";
  const riskClass = {
    HIGH:   "report-risk-badge-high",
    MEDIUM: "report-risk-badge-medium",
    LOW:    "report-risk-badge-low",
    NONE:   "report-risk-badge-none",
  }[risk] || "report-risk-badge-none";

const reviewedBadge =
  `<span class="report-reviewed-badge">✓ 診断員確認済み</span>`;
  
  return `
    <div class="report-finding-card">
      <div class="report-finding-header">
        <div class="report-finding-num">${num}</div>
        <div class="report-finding-title">${escHtml(title)}</div>
        <span class="report-risk-badge ${riskClass}">${risk}</span>
        ${reviewedBadge}
      </div>
      <div class="report-finding-target">
        <span class="report-finding-target-label">対象リソース</span>
        <span class="report-finding-target-value">${escHtml(target)}</span>
      </div>
      <div class="report-finding-body">
        <div class="report-finding-field">
          <div class="report-finding-field-label">検出内容</div>
          <div class="report-finding-field-value">${escHtml(message)}</div>
        </div>
        <div class="report-finding-field">
          <div class="report-finding-field-label">判定理由</div>
          <div class="report-finding-field-value">${escHtml(reason)}</div>
        </div>
        <div class="report-finding-field">
          <div class="report-finding-field-label">セキュリティリスク</div>
          <div class="report-finding-field-value">${escHtml(secRisk)}</div>
        </div>
        <div class="report-finding-field">
          <div class="report-finding-field-label"> 推奨対応</div>
          <div class="report-finding-field-value">${escHtml(recommend)}</div>
        </div>
      </div>
    </div>
  `;
}

// ============================================================
// セクション4: ヒアリング回答内容
// ============================================================

function renderHearing(summary) {
  const hearing = summary.hearing || {};
  const tbody   = document.getElementById("hearingTable");

  // hearing_display のキーラベルマッピング
  const HEARING_LABELS = {
    console_access:        "AWS管理画面にログインして操作する利用者はいますか？",
    usage:                 "AWS管理画面を利用する目的は何ですか？",
    alternative_login:     "SSOなどAWSへログインするための別の仕組みを利用していますか？",
    mfa_exception_reason:  "MFAを設定していない利用者がいる場合、理由はありますか？",
  };

  // null/undefined を除いた有効な回答のみ抽出
  const rows = Object.entries(hearing)
    .filter(([, val]) => val !== null && val !== undefined && val !== "")
    .map(([key, val]) => [HEARING_LABELS[key] || key, val]);

  if (rows.length === 0) {
    document.getElementById("hearingSection").classList.add("hidden");
    return;
  }

  tbody.innerHTML = rows.map(([label, value]) => `
    <tr>
      <th class="report-info-th">${escHtml(String(label))}</th>
      <td class="report-info-td">${escHtml(formatValue(value))}</td>
    </tr>
  `).join("");
}

// ============================================================
// フッター
// ============================================================

function renderFooter(summary) {
  const dt = summary.diagnosis_datetime || summary.diagnosed_at || "";
  const now = new Date().toLocaleString("ja-JP", { timeZone: "Asia/Tokyo" });
  document.getElementById("footerDatetime").textContent = `レポート生成日時：${now}`;
}

// ============================================================
// ユーティリティ
// ============================================================

/** Finding からリスクレベルを取得（レビュー優先） */
function getRisk(f) {
  const review = f.review || {};
  return (review.severity || "NONE").toUpperCase();
}
/** ISO日時を日本語表示に変換 */
function formatDatetime(isoStr) {
  if (!isoStr) return "";
  try {
    const d = new Date(isoStr.replace("_", "T").replace(/(\d{4})(\d{2})(\d{2})_(\d{2})(\d{2})(\d{2})/, "$1-$2-$3T$4:$5:$6"));
    if (isNaN(d.getTime())) {
      // タイムスタンプ形式 "20260929_042438" の場合
      const m = isoStr.match(/^(\d{4})(\d{2})(\d{2})_(\d{2})(\d{2})(\d{2})$/);
      if (m) {
        return `${m[1]}年${m[2]}月${m[3]}日 ${m[4]}:${m[5]}:${m[6]}`;
      }
      return isoStr;
    }
    return d.toLocaleString("ja-JP", {
      year: "numeric", month: "2-digit", day: "2-digit",
      hour: "2-digit", minute: "2-digit", second: "2-digit",
      timeZone: "Asia/Tokyo",
    });
  } catch {
    return isoStr;
  }
}

/** 値を文字列に変換 */
function formatValue(val) {
  if (val === null || val === undefined) return "—";
  if (typeof val === "boolean") return val ? "はい" : "いいえ";
  if (Array.isArray(val)) return val.join(", ");
  return String(val);
}

/** HTMLエスケープ */
function escHtml(str) {
  const AMP  = "&" + "amp;";
  const LT   = "&" + "lt;";
  const GT   = "&" + "gt;";
  const QUOT = "&" + "quot;";
  const BR   = "<" + "br>";
  return String(str)
    .replace(/&/g, AMP)
    .replace(/</g, LT)
    .replace(/>/g, GT)
    .replace(/"/g, QUOT)
    .replace(/\n/g, BR);
}

/** エラー表示 */
function showError(msg) {
  document.getElementById("loadingState").classList.add("hidden");
  document.getElementById("errorState").classList.remove("hidden");
  document.getElementById("errorMsg").textContent = msg;
}
