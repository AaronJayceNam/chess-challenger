"use strict";

// --------------------------------------------------------------------------- //
// helpers
// --------------------------------------------------------------------------- //
async function api(path, body) {
  const res = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body || {}),
  });
  if (!res.ok) {
    let msg = res.statusText;
    try { msg = (await res.json()).detail || msg; } catch (e) {}
    throw new Error(msg);
  }
  return res.json();
}
const $ = (id) => document.getElementById(id);
const GLYPH = { k: "♚", q: "♛", r: "♜", b: "♝", n: "♞", p: "♟" };

// Slide the piece that just moved from its origin square to its destination,
// so moves look smooth even though the board is re-rendered from scratch.
function animateMove(boardEl, fromSq, toSq, orient) {
  if (!boardEl || !fromSq || !toSq) return;
  const files = orient === "w" ? "abcdefgh" : "hgfedcba";
  const ranks = orient === "w" ? [8, 7, 6, 5, 4, 3, 2, 1] : [1, 2, 3, 4, 5, 6, 7, 8];
  const fc = files.indexOf(fromSq[0]), fr = ranks.indexOf(+fromSq[1]);
  const tc = files.indexOf(toSq[0]), tr = ranks.indexOf(+toSq[1]);
  if (fc < 0 || tc < 0 || fr < 0 || tr < 0) return;
  const cell = (boardEl.clientWidth || 440) / 8;
  const dx = (fc - tc) * cell, dy = (fr - tr) * cell;
  const sqDiv = boardEl.children[tr * 8 + tc];
  const pc = sqDiv && sqDiv.querySelector(".pc");
  if (!pc) return;
  // start at the origin square, then transition to 0 (forced reflow so the
  // start position registers — more reliable than requestAnimationFrame).
  pc.style.transition = "none";
  pc.style.transform = `translate(${dx}px, ${dy}px)`;
  pc.style.zIndex = "12";
  void pc.offsetWidth;
  pc.style.transition = "transform .22s cubic-bezier(.22,.61,.36,1)";
  pc.style.transform = "translate(0, 0)";
}

function overlay(show, msg) {
  $("overlay").classList.toggle("hidden", !show);
  if (msg) $("overlayMsg").textContent = msg;
}
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

// --------------------------------------------------------------------------- //
// user settings (persisted)
// --------------------------------------------------------------------------- //
const SETTINGS = {
  showDots: localStorage.getItem("cc_showdots") !== "0",   // legal-move grey circles
};

// --------------------------------------------------------------------------- //
// drag-to-move (works alongside click-to-move on every game board)
// --------------------------------------------------------------------------- //
let _dragJustMoved = false;   // suppress the click that follows a drag-drop

// cfg: { movable():bool, legal():{sq:[dests]}, commit(from,to) }  — commit plays
// the move (handling promotion). Attach ONCE per board element; survives the
// board's innerHTML re-renders because the listener lives on the board itself.
function enableBoardDrag(boardEl, cfg) {
  let d = null;
  const clearTargets = () => boardEl.querySelectorAll(".dnd-target").forEach((el) => el.classList.remove("dnd-target"));

  boardEl.addEventListener("pointerdown", (e) => {
    if (!cfg.movable()) return;
    const pc = e.target.closest(".pc");
    const sqEl = pc && pc.closest(".sq");
    const from = sqEl && sqEl.dataset.sq;
    if (!from) return;                 // must grab an actual piece
    // ANY piece can be picked up; only a legal target completes a move. A piece
    // with no legal moves just lifts and snaps back.
    // no preventDefault: touch-action:pan-y (CSS) lets a vertical swipe scroll the
    // page, while letting the native click through keeps tap-to-move working on touch.
    d = { from, pc, sx: e.clientX, sy: e.clientY, moved: false, clone: null, legal: cfg.legal() || {}, cell: boardEl.getBoundingClientRect().width / 8 };
    try { boardEl.setPointerCapture(e.pointerId); } catch (err) {}
  });

  boardEl.addEventListener("pointermove", (e) => {
    if (!d) return;
    if (!d.moved && Math.hypot(e.clientX - d.sx, e.clientY - d.sy) < 6) return;
    if (!d.moved) {
      d.moved = true;
      const c = d.pc.cloneNode(true);
      c.className = d.pc.className + " dragging";
      c.style.cssText = `position:fixed;width:${d.cell}px;height:${d.cell}px;display:flex;` +
        `align-items:center;justify-content:center;font-size:${getComputedStyle(d.pc).fontSize};` +
        `pointer-events:none;z-index:70;`;
      document.body.appendChild(c);
      d.clone = c;
      d.pc.style.opacity = "0";   // hide the original so the piece itself appears to move
      if (d.pc.parentElement) d.pc.parentElement.classList.add("dnd-from");   // highlight origin square
      if (SETTINGS.showDots) (d.legal[d.from] || []).forEach((t) => { const el = boardEl.querySelector(`.sq[data-sq="${t}"]`); if (el) el.classList.add("dnd-target"); });
    }
    d.clone.style.left = (e.clientX - d.cell / 2) + "px";
    d.clone.style.top = (e.clientY - d.cell / 2) + "px";
  });

  const cleanup = () => {
    if (!d) return null;
    const cur = d; d = null;
    clearTargets();
    boardEl.querySelectorAll(".dnd-from").forEach((el) => el.classList.remove("dnd-from"));
    if (cur.clone) cur.clone.remove();
    if (cur.pc) cur.pc.style.opacity = "";
    return cur;
  };
  const finish = (e) => {
    const cur = cleanup();
    if (!cur || !cur.moved) return;   // a tap, not a drag → let the click handler run
    const el = document.elementFromPoint(e.clientX, e.clientY);
    const sqEl = el && el.closest(".sq");
    const to = sqEl && sqEl.dataset.sq;
    if (to && to !== cur.from && cur.legal[cur.from] && cur.legal[cur.from].includes(to)) {
      _dragJustMoved = true; setTimeout(() => { _dragJustMoved = false; }, 0);
      cfg.commit(cur.from, to);
    }
  };
  boardEl.addEventListener("pointerup", finish);
  // pointercancel = the browser took the gesture for scrolling → abort, never move
  boardEl.addEventListener("pointercancel", () => { cleanup(); });
}

// Keep the active move visible by scrolling ONLY the list container — never the
// page (element.scrollIntoView scrolls the whole window, which on phones makes
// the screen jump/scroll down on every move).
function scrollListToActive(list) {
  if (!list) return;
  const act = list.querySelector(".mv.active");
  if (!act) return;
  const lr = list.getBoundingClientRect(), ar = act.getBoundingClientRect();
  if (ar.top < lr.top) list.scrollTop -= (lr.top - ar.top) + 6;
  else if (ar.bottom > lr.bottom) list.scrollTop += (ar.bottom - lr.bottom) + 6;
}

// --------------------------------------------------------------------------- //
// tabs
// --------------------------------------------------------------------------- //
// Both the desktop top-tabs and the mobile bottom-nav use [data-tab] buttons.
document.querySelectorAll("[data-tab]").forEach((b) => {
  b.onclick = () => switchTab(b.dataset.tab);
});
function switchTab(name) {
  document.body.classList.remove("ingame");   // leaving into a browse tab always exits immersive
  document.querySelectorAll("[data-tab]").forEach((b) =>
    b.classList.toggle("active", b.dataset.tab === name));
  document.querySelectorAll(".tab").forEach((t) =>
    t.classList.toggle("active", t.id === "tab-" + name));
  window.scrollTo(0, 0);
  if (name === "online") {
    if (typeof loadLeaderboard === "function") loadLeaderboard();
    if (typeof updateOgAuthGate === "function") updateOgAuthGate();
  }
  if (name === "growth" && typeof renderGrowth === "function") renderGrowth();
  if (name === "ai" && typeof refreshDashboard === "function") refreshDashboard();
}
// empty-state "go analyze" buttons
document.querySelectorAll("[data-goto]").forEach((b) => {
  b.onclick = () => switchTab(b.dataset.goto);
});

// --------------------------------------------------------------------------- //
// health
// --------------------------------------------------------------------------- //
(async () => {
  try {
    const h = await (await fetch("/api/health")).json();
    const el = $("sfStatus");
    if (h.stockfish) {
      el.innerHTML = "엔진: <b>Stockfish 연결됨</b>" +
        (h.coaching ? " · LLM 코칭 가능" : " · LLM 코칭 비활성(키 없음)");
    } else {
      el.className = "sf bad";
      el.innerHTML = "엔진: <b>Stockfish 없음</b> — STOCKFISH_PATH 설정 필요";
    }
  } catch (e) { $("sfStatus").textContent = "상태 확인 실패: " + e.message; }
})();

// =========================================================================== //
// Shared board helpers
// =========================================================================== //
function parseFen(fen) {
  const rows = fen.split(" ")[0].split("/");
  const map = {};
  for (let r = 0; r < 8; r++) {
    let file = 0;
    for (const ch of rows[r]) {
      if (/\d/.test(ch)) file += +ch;
      else { map["abcdefgh"[file] + (8 - r)] = ch; file++; }
    }
  }
  return map;
}

function promoChooser(boardEl, isWhite, cb) {
  closePromo();
  const picker = document.createElement("div");
  picker.className = "promo"; picker.id = "promoPicker";
  ["q", "r", "b", "n"].forEach((p) => {
    const d = document.createElement("div");
    d.className = "pc " + (isWhite ? "w" : "b");
    d.textContent = GLYPH[p]; d.style.color = "#111";
    d.onclick = () => { closePromo(); cb(p); };
    picker.appendChild(d);
  });
  const wrap = boardEl.getBoundingClientRect();
  picker.style.left = (wrap.left + wrap.width / 2 - 30) + "px";
  picker.style.top = (wrap.top + wrap.height / 2 - 80) + "px";
  document.body.appendChild(picker);
}
function closePromo() { const p = $("promoPicker"); if (p) p.remove(); }

function download(name, text, type) {
  const b = new Blob([text], { type });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(b); a.download = name; a.click();
}

function setStatus(id, msg, err) {
  const el = $(id);
  el.textContent = msg || "";
  el.className = "status" + (err ? " err" : "");
}

// "Failed to fetch" = the request never reached the server (server not running).
function isOffline(e) {
  return /failed to fetch|networkerror|load failed|connection refused/i.test((e && e.message) || "");
}
const OFFLINE_MSG = "서버에 연결할 수 없습니다. 바탕화면의 'Chess Challenger' 아이콘을 다시 한 번 실행한 뒤, 이 페이지를 새로고침(F5)하세요.";

// =========================================================================== //
// RATING + GAME HISTORY — per device (localStorage).
// The rating changes ONLY through online matches; AI games are logged in the
// history but never move the rating.
//
// Scale: starts at 400, can never drop below 0; 2000 ≈ pro. The higher you
// are, the LESS a win gives and the MORE a loss costs. Gains/losses also depend
// on the OPPONENT's rating (standard Elo expected score: beating someone
// stronger pays more, losing to someone weaker costs more). Equal-opponent
// amounts:
//   win : +68 at 400, +50 at 1000, +20 at 2000 (floor +16)
//   loss: -18 at 400, -30 at 1000, -50 at 2000 (cap -60)
// =========================================================================== //
const RATING_START = 400;

// New storage key: values from earlier scales would be wrong here.
function myRating() {
  const v = localStorage.getItem("cc_rating3");
  return v === null ? RATING_START : Math.max(0, +v);
}
function setMyRating(r) { localStorage.setItem("cc_rating3", String(Math.max(0, Math.round(r)))); updateRatingChip(); authSchedulePush(); }
function kWin(r) { return Math.max(32, 160 - r * 0.06); }
function kLoss(r) { return Math.min(120, 20 + r * 0.04); }
function eloDelta(mine, opp, score) {
  const expected = 1 / (1 + Math.pow(10, (opp - mine) / 400));
  const raw = score - expected;
  const k = raw >= 0 ? kWin(mine) : kLoss(mine);
  return Math.round(k * raw);
}
// Rating tiers — a chess-piece symbol next to the number, ascending by piece
// value as the rating climbs. Same brackets everywhere the rating shows.
function ratingTier(r) {
  if (r >= 2300) return { sym: "♔", name: "마스터", cls: "t-king" };
  if (r >= 1900) return { sym: "♕", name: "퀸", cls: "t-queen" };
  if (r >= 1500) return { sym: "♖", name: "룩", cls: "t-rook" };
  if (r >= 1100) return { sym: "♗", name: "비숍", cls: "t-bishop" };
  if (r >= 700) return { sym: "♘", name: "나이트", cls: "t-knight" };
  return { sym: "♙", name: "폰", cls: "t-pawn" };
}
// HTML: colored tier symbol + number (e.g. for chips/badges/leaderboard)
function ratingHTML(r) {
  const t = ratingTier(r);
  return `<span class="tier ${t.cls}" title="${t.name}">${t.sym}</span>${r}`;
}
// plain text: symbol + number (for textContent contexts)
function ratingText(r) { return `${ratingTier(r).sym} ${r}`; }

function updateRatingChip() {
  const el = $("ratingChip");
  const loggedIn = !!(typeof AUTH !== "undefined" && AUTH && AUTH.token);
  if (el) {
    el.classList.toggle("hidden", !loggedIn);   // no rating shown when logged out
    if (loggedIn) el.innerHTML = `레이팅 <b>${ratingHTML(myRating())}</b>`;
  }
  const og = $("ogRating"); if (og && loggedIn) og.innerHTML = ratingHTML(myRating());
  if (typeof refreshDashboard === "function") refreshDashboard();
}

function gameHistory() {
  try { return JSON.parse(localStorage.getItem("cc_history") || "[]"); }
  catch (e) { return []; }
}
function addHistory(entry) {
  const h = gameHistory();
  h.unshift({ ...entry, date: new Date().toISOString().slice(0, 10) });
  localStorage.setItem("cc_history", JSON.stringify(h.slice(0, 50)));
  renderHistory();
  authSchedulePush();
}
function renderHistory() {
  const el = $("ogHistory"); if (!el) return;
  const h = gameHistory();
  if (!h.length) { el.innerHTML = '<div class="hist-empty">아직 기록된 대국이 없습니다.</div>'; return; }
  el.innerHTML = h.slice(0, 12).map((g) => {
    const res = g.result === "win" ? '<b class="w">승</b>' : g.result === "loss" ? '<b class="l">패</b>' : '<b class="d">무</b>';
    const delta = (g.ratingDelta === null || g.ratingDelta === undefined) ? '<span class="dim">—</span>'
      : (g.ratingDelta >= 0 ? `<span class="up">+${g.ratingDelta}</span>` : `<span class="down">${g.ratingDelta}</span>`);
    const mode = g.mode === "online" ? "🌐" : "🤖";
    return `<div class="hist-row"><span class="dim">${(g.date || "").slice(5)}</span>` +
      `<span>${mode} ${escapeHtml(g.opponent || "")}</span>${res}${delta}</div>`;
  }).join("");
}

// =========================================================================== //
// ANALYZE -> REVIEW
// =========================================================================== //
let LAST_REQ = null;

async function runAnalyze(req, statusId = "aiStatus") {
  LAST_REQ = req;
  overlay(true, "엔진이 모든 수를 평가하고 있습니다… (보통 5~15초)");
  try {
    const view = await api("/api/analyze", req);
    loadReview(view);
    switchTab("review");
  } catch (e) {
    overlay(false);
    setStatus(statusId, isOffline(e) ? OFFLINE_MSG : "분석 실패: " + e.message, true);
    return;
  }
  overlay(false);
}

const RV = { view: null, idx: 0, N: 0 };

function clsColor(c) {
  return ({ Best: "#2e7d32", Excellent: "#2e7d32", Good: "#9e9e9e",
    Inaccuracy: "#c9a227", Mistake: "#e07a1f", Blunder: "#c62828" })[c] || "#ddd";
}
function clsLabel(c) {
  return ({ Best: "최선", Excellent: "훌륭함", Good: "무난", Inaccuracy: "부정확",
    Mistake: "실수", Blunder: "블런더" })[c] || c;
}

function loadReview(view) {
  RV.view = view; RV.N = view.svgs.length - 1; RV.idx = 0;
  $("rvEmpty").classList.add("hidden");      // hide the "analyze first" prompt
  $("rvContent").classList.remove("hidden"); // reveal the review

  $("rvSummary").innerHTML =
    `<b>${view.title}</b> &nbsp; <span style="color:#9aa0a6">${view.opening || ""}</span><br>` +
    `정확도(둔 수가 최선에 얼마나 가까웠는지) — ` +
    `<b>백 ${view.white.accuracy.toFixed(1)}%</b> &nbsp;·&nbsp; <b>흑 ${view.black.accuracy.toFixed(1)}%</b>`;

  // movelist
  let html = "";
  view.moves.forEach((m) => {
    if (m.color === "white") html += `<span class="num">${m.moveNumber}.</span>`;
    html += `<span class="mv" data-idx="${m.ply}" style="color:${m.clsColor}" ` +
      `title="${clsLabel(m.classification)} — ${(m.explain || "").replace(/"/g, "'")}">` +
      `${m.san}${m.symbol}</span> `;
  });
  $("rvMoves").innerHTML = html;
  $("rvMoves").querySelectorAll(".mv").forEach((el) =>
    el.onclick = () => rvGo(+el.dataset.idx));

  renderCoach(view.coach);
  rvRender();
}

function rvDetail() {
  if (RV.idx === 0) {
    $("rvDetail").innerHTML = '<div class="r">시작 포지션입니다. ▶ 또는 → 키로 진행하세요.</div>';
    return;
  }
  const m = RV.view.moves[RV.idx - 1];
  const turn = m.color === "white" ? "백" : "흑";
  const tag = m.isBest
    ? '<span class="tag" style="background:#2e7d32;color:#fff">최선</span>'
    : `<span class="tag" style="background:${m.clsColor}">${clsLabel(m.classification)} ${m.symbol}</span>`;
  const missed = m.missedWin ? ' <b style="color:#c62828">· 승리 놓침</b>' : "";
  const explain = m.explain
    ? `<div class="aiexplain">🤖 ${escapeHtml(m.explain)}</div>` : "";
  const pv = (m.pv || []).slice(0, 8).join(" ");
  const pvRow = pv ? `<div class="r">예상 진행 수순: <span class="pv">${pv}</span></div>` : "";
  $("rvDetail").innerHTML =
    `<div><b style="font-size:16px">${m.moveNumber}${m.color === "white" ? "." : "..."} ${turn} ${m.san}${m.symbol}</b> &nbsp; ${tag}${missed}</div>` +
    explain +
    pvRow;
}

function rvGraph() {
  const g = $("rvGraph");
  const w = g.clientWidth || 480, h = 90;
  g.setAttribute("viewBox", `0 0 ${w} ${h}`);
  const ww = RV.view.whiteWin;
  const xs = (i) => (RV.N === 0 ? 0 : (i / RV.N) * w);
  const ys = (v) => h - (v / 100) * h;
  const pts = ww.map((v, i) => `${xs(i).toFixed(1)},${ys(v).toFixed(1)}`).join(" ");
  const area = `0,${h} ${pts} ${w},${h}`;
  const cx = xs(RV.idx);
  g.innerHTML =
    `<line x1="0" y1="${h / 2}" x2="${w}" y2="${h / 2}" stroke="#555" stroke-dasharray="3 3"/>` +
    `<polygon points="${area}" fill="#3b82f622"/>` +
    `<polyline points="${pts}" fill="none" stroke="#9ecbff" stroke-width="1.5"/>` +
    `<line x1="${cx}" y1="0" x2="${cx}" y2="${h}" stroke="#fff" stroke-width="1.5"/>`;
}

function rvRender() {
  $("rvBoard").innerHTML = RV.view.svgs[RV.idx];
  $("rvBar").style.height = RV.view.whiteWin[RV.idx] + "%";
  $("rvBarLbl").textContent = RV.view.evalLabels[RV.idx];
  $("rvSlider").max = RV.N; $("rvSlider").value = RV.idx;
  document.querySelectorAll("#rvMoves .mv").forEach((el) =>
    el.classList.toggle("active", +el.dataset.idx === RV.idx));
  scrollListToActive($("rvMoves"));
  rvDetail(); rvGraph();
}
function rvGo(i) { RV.idx = Math.max(0, Math.min(RV.N, i)); rvRender(); }

$("rvFirst").onclick = () => rvGo(0);
$("rvPrev").onclick = () => rvGo(RV.idx - 1);
$("rvNext").onclick = () => rvGo(RV.idx + 1);
$("rvLast").onclick = () => rvGo(RV.N);
$("rvSlider").oninput = (e) => rvGo(+e.target.value);
$("rvGraph").addEventListener("click", (e) => {
  const r = e.currentTarget.getBoundingClientRect();
  rvGo(Math.round(((e.clientX - r.left) / r.width) * RV.N));
});
document.addEventListener("keydown", (e) => {
  if (!document.getElementById("tab-review").classList.contains("active")) return;
  if (e.key === "ArrowLeft") { rvGo(RV.idx - 1); e.preventDefault(); }
  if (e.key === "ArrowRight") { rvGo(RV.idx + 1); e.preventDefault(); }
  if (e.key === "Home") rvGo(0);
  if (e.key === "End") rvGo(RV.N);
});
window.addEventListener("resize", () => { if (RV.view) rvGraph(); });

// ---- coach ----
function renderCoach(coach) {
  const el = $("rvCoach");
  if (!coach) { el.textContent = ""; return; }
  if (coach.available && coach.text) {
    el.innerHTML = `<div style="white-space:pre-wrap; font-size:14px; line-height:1.6">${escapeHtml(coach.text)}</div>`;
  } else if (coach.available) {
    el.innerHTML = `<div style="color:#9aa0a6; font-size:14px">LLM 코칭을 생성하려면 아래 버튼을 누르세요.</div>` +
      `<button class="ghost" id="coachBtn" style="margin-top:8px">🧠 코치 평 생성</button>`;
    $("coachBtn").onclick = genCoach;
  } else {
    el.innerHTML = `<div style="color:#9aa0a6; font-size:14px">${escapeHtml(coach.message || "LLM 코칭 비활성화됨.")}</div>`;
  }
}
async function genCoach() {
  if (!LAST_REQ) return;
  overlay(true, "코치가 리포트를 작성 중입니다…");
  try {
    const view = await api("/api/analyze", { ...LAST_REQ, coach: true });
    RV.view.coach = view.coach;
    renderCoach(view.coach);
  } catch (e) { renderCoach({ available: false, message: "코칭 오류: " + e.message }); }
  overlay(false);
}
function escapeHtml(s) {
  return s.replace(/[&<>]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c]));
}

// ---- review players / title / shapes for export ----
function reviewMeta() {
  const v = RV.view;
  const [white, black] = (v.title || "White vs Black").split(" vs ");
  return { v, white: white || "White", black: black || "Black" };
}

// AI explanations keyed by position index (ply). Each move's explanation describes
// the move that REACHED that position, so it attaches to index = ply.
function aiCommentsByIndex() {
  const c = {};
  RV.view.moves.forEach((m) => { if (m.explain) c[String(m.ply)] = m.explain; });
  return c;
}

// ---- export annotated PGN (with AI explanations) ----
$("rvExport").onclick = () => {
  const { v, white, black } = reviewMeta();
  let txt = `[Event "Chess Coach Studio"]\n[White "${white}"]\n[Black "${black}"]\n[Result "${v.result}"]\n\n`;
  let body = "";
  v.moves.forEach((m) => {
    if (m.color === "white") body += `${m.moveNumber}. `;
    body += `${m.san}${m.symbol} `;
    if (m.explain) body += `{ ${m.explain} } `;
  });
  txt += body + v.result + "\n";
  download("annotated.pgn", txt, "application/x-chess-pgn");
  setStatus("rvShareStatus", "AI 해설이 담긴 주석 PGN을 저장했습니다.");
};

// ---- share: standalone HTML study with AI explanations + arrows ----
$("rvShare").onclick = async () => {
  const { v, white, black } = reviewMeta();
  setStatus("rvShareStatus", "AI 해설 공유본 생성 중…");
  try {
    const res = await fetch("/api/study_html", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        moves: v.moves.map((m) => m.uci),
        comments: aiCommentsByIndex(),
        shapes: {},
        white, black, title: v.title || "체스 AI 해설",
      }),
    });
    if (!res.ok) throw new Error(await res.text());
    const html = await res.text();
    const name = (v.title || "study").replace(/[^\w가-힣 -]/g, "").trim() + ".html";
    download(name || "study.html", html, "text/html");
    setStatus("rvShareStatus", "저장 완료! 이 파일은 인터넷 없이 열립니다. 사람들에게 그대로 보내세요.");
  } catch (e) { setStatus("rvShareStatus", "생성 실패: " + e.message, true); }
};

// =========================================================================== //
// PLAY vs AI (levels 1-10) -> auto-evaluate when the game ends
// =========================================================================== //
const AIG = { moves: [], state: null, sel: null, orient: "w", level: 3, human: "w", over: false, thinking: false, started: false, style: "default" };

// Progress: the highest level beaten (persisted in localStorage). Shown as a
// plain level number — no titles.
function bestLevel() { return +(localStorage.getItem("cc_best_level") || 0); }
function setBestLevel(n) { localStorage.setItem("cc_best_level", String(n)); authSchedulePush(); }
function updateRankBadge() {
  const b = bestLevel(), el = $("aiRank");
  if (!el) return;
  const rb = (typeof t === "function") ? t("rank_best") : "내 최고 기록";
  if (b > 0) { el.textContent = `${rb}: ${aiLevelWord()} ${b} · ${aiTitle(b)}`; el.classList.toggle("master", b >= 10); }
  else { el.textContent = (typeof t === "function") ? t("rank_none") : "아직 클리어한 레벨이 없습니다"; el.classList.remove("master"); }
}

// ---- big win/loss/draw result screen ----
function showResult(o) {
  const box = $("resultBox");
  box.className = "result-box " + o.kind;
  $("resultIcon").textContent = o.icon;
  $("resultTitle").textContent = o.title;
  $("resultSub").textContent = o.sub || "";
  const badge = $("resultBadge");
  if (o.badge) {
    badge.classList.remove("hidden");
    badge.classList.toggle("master", !!o.badge.master);
    badge.innerHTML = `<span class="small">${o.badge.small || "🎉 새 기록 달성"}</span>${o.badge.text}`;
  } else { badge.classList.add("hidden"); }
  const act = $("resultActions"); act.innerHTML = "";
  (o.actions || []).forEach((a) => {
    const btn = document.createElement("button");
    btn.className = a.primary ? "primary" : "ghost";
    btn.textContent = a.label;
    btn.onclick = () => { hideResult(); if (a.onClick) a.onClick(); };
    act.appendChild(btn);
  });
  const conf = $("confetti"); conf.innerHTML = "";
  if (o.kind === "win") {
    const colors = ["#f5b301", "#6d5cff", "#3fb950", "#ff7a00", "#9ecbff", "#ff5c7a"];
    for (let i = 0; i < 44; i++) {
      const p = document.createElement("i");
      p.style.left = Math.round(Math.random() * 100) + "%";
      p.style.background = colors[i % colors.length];
      p.style.animationDuration = (1.4 + Math.random() * 1.5) + "s";
      p.style.animationDelay = (Math.random() * 0.5) + "s";
      conf.appendChild(p);
    }
  }
  $("resultOverlay").classList.remove("hidden");
}
function hideResult() { $("resultOverlay").classList.add("hidden"); }

function renderAiBoard() {
  const board = $("aiBoard"); board.innerHTML = "";
  const st = AIG.state; if (!st) return;
  const map = parseFen(st.fen);
  const files = AIG.orient === "w" ? [..."abcdefgh"] : [..."hgfedcba"];
  const ranks = AIG.orient === "w" ? [8, 7, 6, 5, 4, 3, 2, 1] : [1, 2, 3, 4, 5, 6, 7, 8];
  const lastUci = AIG.moves.length ? AIG.moves[AIG.moves.length - 1] : null;
  const lf = lastUci ? lastUci.slice(0, 2) : null, lt = lastUci ? lastUci.slice(2, 4) : null;
  const kingChar = st.turn === "w" ? "K" : "k";
  let kingSq = null;
  for (const s in map) if (map[s] === kingChar) kingSq = s;
  const canMove = !AIG.over && !AIG.thinking && st.turn === AIG.human;
  const legal = canMove ? (st.legal || {}) : {};
  for (const rank of ranks) {
    for (const f of files) {
      const sq = f + rank, fi = "abcdefgh".indexOf(f);
      const div = document.createElement("div");
      div.className = "sq " + ((fi + rank) % 2 === 0 ? "light" : "dark");
      if (sq === lf || sq === lt) div.classList.add("last");
      if (AIG.sel === sq) div.classList.add("sel");
      if (st.check && sq === kingSq) div.classList.add("check");
      const p = map[sq];
      if (p) {
        const s = document.createElement("span");
        s.className = "pc " + (p === p.toUpperCase() ? "w" : "b");
        s.textContent = GLYPH[p.toLowerCase()];
        div.appendChild(s);
      }
      if (SETTINGS.showDots && AIG.sel && legal[AIG.sel] && legal[AIG.sel].includes(sq)) {
        const d = document.createElement("div"); d.className = "dot" + (map[sq] ? " cap" : "");
        div.appendChild(d);
      }
      div.dataset.sq = sq;
      div.onclick = () => onAiClick(sq);
      board.appendChild(div);
    }
  }
}

function onAiClick(sq) {
  if (_dragJustMoved) return;
  const st = AIG.state;
  if (!AIG.started || AIG.over || AIG.thinking || !st || st.turn !== AIG.human) return;
  const map = parseFen(st.fen), legal = st.legal || {};
  if (AIG.sel) {
    if (legal[AIG.sel] && legal[AIG.sel].includes(sq)) {
      const from = AIG.sel, piece = map[from], r = +sq[1];
      AIG.sel = null;
      if (piece && piece.toLowerCase() === "p" && (r === 8 || r === 1)) {
        promoChooser($("aiBoard"), piece === "P", (pp) => aiHumanMove(from + sq + pp));
      } else {
        aiHumanMove(from + sq);
      }
      return;
    }
    if (legal[sq]) { AIG.sel = sq; renderAiBoard(); return; }
    AIG.sel = null; renderAiBoard(); return;
  }
  if (legal[sq]) { AIG.sel = sq; renderAiBoard(); }
}

// ---- AI opponent identity for the player bar (name + rating) ----
const AI_STYLE_LABEL = { tal: "탈", fischer: "피셔", carlsen: "카를센", petrosian: "페트로시안" };
// 10-level ladder: title (호칭) per level + a friendly display rating that
// shows the widening gap. Titles are translated via i18n (lvl_1..lvl_10).
const AI_LEVEL_RATING = [0, 250, 450, 650, 850, 1050, 1300, 1550, 1850, 2200, 2850];
function aiTitle(n) { n = Math.max(1, Math.min(10, +n || 1)); return (typeof t === "function") ? t("lvl_" + n) : String(n); }
function aiLevelWord() { return (typeof t === "function") ? t("word_level") : "레벨"; }
function aiLevelText(n) { return `${aiLevelWord()} ${n} · ${aiTitle(n)}`; }
function aiOppInfo() {
  if (AIG.style && AIG.style !== "default")
    return { name: `${AI_STYLE_LABEL[AIG.style] || "AI"} AI`, rating: "최강" };
  const lv = AIG.level;
  return { name: `AI · ${aiTitle(lv)}`, rating: AI_LEVEL_RATING[lv] || 2850 };
}
function renderAiPbars() {
  const top = $("aiTopBar"), bottom = $("aiBottomBar");
  if (!top || !bottom) return;
  if (!AIG.started || !AIG.state) { top.classList.add("hidden"); bottom.classList.add("hidden"); return; }
  top.classList.remove("hidden"); bottom.classList.remove("hidden");
  const mine = AIG.human, theirs = mine === "w" ? "b" : "w";
  const turnOf = (c) => AIG.started && !AIG.over && AIG.state.turn === c;
  const html = (name, rating, isMe, active) =>
    `<span class="pv-ava ${isMe ? "me" : ""}">${escapeHtml(String(name).charAt(0).toUpperCase())}</span>` +
    `<span class="pv-name">${escapeHtml(name)}</span>` +
    `<span class="pv-rating">${typeof rating === "number" ? ratingHTML(rating) : escapeHtml(rating)}</span>` +
    `<span class="pv-turn ${active ? "active" : ""}"></span>`;
  const opp = aiOppInfo();
  top.innerHTML = html(opp.name, opp.rating, false, turnOf(theirs));
  bottom.innerHTML = html(AUTH.id || "나", myRating(), true, turnOf(mine));
}

function updateAiTurn() {
  renderAiPbars();
  const t = $("aiTurn"), st = AIG.state;
  if (!st || !AIG.started) { t.innerHTML = '<span class="pill"></span>난이도와 색을 고르고 “새 대국 시작”을 누르세요.'; return; }
  if (AIG.over) { t.innerHTML = "<b>대국 종료</b>"; return; }
  if (AIG.thinking) { t.innerHTML = '<span class="pill b"></span>AI가 생각 중…'; return; }
  const w = st.turn === "w", mine = st.turn === AIG.human;
  t.innerHTML = `<span class="pill ${w ? "" : "b"}"></span>${w ? "백" : "흑"} 차례` +
    (mine ? " (당신)" : " (AI)") + (st.check ? " · <b style='color:#ff8a80'>체크!</b>" : "");
}

function renderAiMoves() {
  const el = $("aiMoves");
  const san = (AIG.state && AIG.state.san) ? AIG.state.san : [];
  if (!san.length) { el.innerHTML = '<span class="num">대국을 시작하면 여기에 기보가 쌓입니다.</span>'; return; }
  let html = "";
  san.forEach((s, i) => {
    if (i % 2 === 0) html += `<span class="num">${i / 2 + 1}.</span>`;
    html += `<span class="mv" style="cursor:default">${s}</span> `;
  });
  el.innerHTML = html; el.scrollTop = el.scrollHeight;
}

async function aiHumanMove(uci) {
  const moves = [...AIG.moves, uci];
  let st;
  try { st = await api("/api/legal", { moves }); }
  catch (e) { setStatus("aiStatus", isOffline(e) ? OFFLINE_MSG : "수 처리 오류: " + e.message, true); return; }
  AIG.moves = moves; AIG.state = st; AIG.sel = null;
  renderAiBoard(); renderAiMoves(); updateAiTurn();
  animateMove($("aiBoard"), uci.slice(0, 2), uci.slice(2, 4), AIG.orient);
  if (st.gameOver) { aiEndGame(); return; }
  await sleep(150);   // let the player's piece finish sliding before the AI replies
  await aiReply();
}

async function aiReply() {
  // NOTE: do not re-render the board here — that would wipe the player's
  // in-flight slide animation. Input is already gated by AIG.thinking.
  AIG.thinking = true; updateAiTurn();
  let res;
  try { res = await api("/api/ai_move", { moves: AIG.moves, level: AIG.level, style: AIG.style }); }
  catch (e) { AIG.thinking = false; updateAiTurn(); setStatus("aiStatus", isOffline(e) ? OFFLINE_MSG : "AI 응수 오류: " + e.message, true); return; }
  AIG.thinking = false;
  if (res.move) AIG.moves.push(res.move);
  AIG.state = res;
  renderAiBoard(); renderAiMoves(); updateAiTurn();
  if (res.move) animateMove($("aiBoard"), res.move.slice(0, 2), res.move.slice(2, 4), AIG.orient);
  if (res.gameOver) aiEndGame();
}

function aiPlayerNames() {
  const lv = AIG.level;
  const ai = `AI ${aiTitle(lv)}`;
  return AIG.human === "w"
    ? { white: "나(You)", black: ai }
    : { white: ai, black: "나(You)" };
}

function aiEndGame() {
  AIG.over = true; document.body.classList.remove("ingame"); renderAiBoard(); updateAiTurn();
  const r = AIG.state.result, lv = AIG.level;
  let kind = "draw";
  if (r === "1-0") kind = AIG.human === "w" ? "win" : "loss";
  else if (r === "0-1") kind = AIG.human === "b" ? "win" : "loss";

  // Beating this level grants its title (if it's a new personal best).
  let badge = null;
  if (kind === "win" && lv > bestLevel()) {
    setBestLevel(lv); updateRankBadge();
    badge = { text: `${aiLevelText(lv)} 클리어!`, master: lv >= 10 };
  }
  // AI games go into the history but never move the rating (online-only).
  addHistory({ mode: "ai", opponent: `AI ${aiTitle(lv)}`, result: kind, ratingDelta: null });
  setStatus("aiStatus", `대국 종료 (${r}).`);
  $("aiAnalyze").classList.remove("hidden");

  const { white, black } = aiPlayerNames();
  const actions = [
    { label: "🤖 AI 평가 보기", primary: true,
      onClick: () => runAnalyze({ moves: AIG.moves, white, black, movetime: 350 }) },
    { label: "🔄 새 대국", onClick: () => switchTab("ai") },
  ];
  const aiName = `AI ${aiTitle(lv)}`;
  const opts = kind === "win"
    ? { kind, icon: "🏆", title: "승리!", sub: `${aiName}를 이겼습니다`, badge, actions }
    : kind === "loss"
      ? { kind, icon: "😢", title: "패배", sub: `${aiName}에게 졌습니다. 다시 도전!`, actions }
      : { kind, icon: "🤝", title: "무승부", sub: `${aiName}와 비겼습니다`, actions };
  setTimeout(() => showResult(opts), 500);   // let the final move finish sliding
}

async function aiStart() {
  AIG.level = +$("aiLevel").value;
  AIG.human = $("aiColor").value;
  AIG.style = $("aiStyle") ? $("aiStyle").value : "default";
  AIG.orient = AIG.human;
  AIG.moves = []; AIG.sel = null; AIG.over = false; AIG.thinking = false; AIG.started = true;
  $("aiAnalyze").classList.add("hidden");
  try { AIG.state = await api("/api/legal", { moves: [] }); }
  catch (e) { AIG.started = false; setStatus("aiStatus", isOffline(e) ? OFFLINE_MSG : "시작 오류: " + e.message, true); return; }
  const styleNames = { tal: "탈 스타일 ⚔️", fischer: "피셔 스타일 🎯", carlsen: "카를센 스타일 ♟️", petrosian: "페트로시안 스타일 🛡️" };
  setStatus("aiStatus", AIG.style !== "default"
    ? `${styleNames[AIG.style]} AI와 대국 시작! 당신은 ${AIG.human === "w" ? "백" : "흑"}입니다.`
    : `${aiLevelText(AIG.level)} AI와 대국 시작! 당신은 ${AIG.human === "w" ? "백" : "흑"}입니다.`);
  document.body.classList.add("ingame");     // immersive: board + opponent only
  renderAiBoard(); renderAiMoves(); updateAiTurn();
  if (AIG.human === "b") await aiReply();   // AI (white) moves first
}

$("aiLevel").oninput = (e) => {
  $("aiLevelLabel").textContent = aiLevelText(+e.target.value);
};
$("aiStyle").onchange = (e) => {
  const styled = e.target.value !== "default";
  $("aiStyleNote").style.display = styled ? "block" : "none";
  $("aiLevel").disabled = styled;
  $("aiLevelLabel").style.opacity = styled ? "0.4" : "1";
};
$("aiStart").onclick = aiStart;
$("aiFlip").onclick = () => { AIG.orient = AIG.orient === "w" ? "b" : "w"; renderAiBoard(); };
$("aiResign").onclick = () => {
  if (!AIG.moves.length) { setStatus("aiStatus", "먼저 대국을 시작하고 한 수 이상 두세요.", true); return; }
  AIG.over = true; document.body.classList.remove("ingame"); updateAiTurn();
  const { white, black } = aiPlayerNames();
  setStatus("aiStatus", "기권했습니다. 둔 수들을 평가합니다…");
  runAnalyze({ moves: AIG.moves, white, black, movetime: 350 });
};
$("aiAnalyze").onclick = () => {
  if (!AIG.moves.length) return;
  const { white, black } = aiPlayerNames();
  runAnalyze({ moves: AIG.moves, white, black, movetime: 350 });
};

// =========================================================================== //
// CHECKMATE PUZZLES
// =========================================================================== //
const PZ = { list: [], idx: 0, cat: 0, baseFen: null, fen: null, mateIn: 0, movesLeft: 0,
  sel: null, legal: {}, lastUci: null, hintSq: null, busy: false, locked: false, solved: pzLoadSolved() };
function pzUnlocked(level) { return level === 1 || PZ.solved.has(level - 1); }

function pzLoadSolved() {
  try { return new Set(JSON.parse(localStorage.getItem("cc_puzzles_solved") || "[]")); }
  catch (e) { return new Set(); }
}
function pzSaveSolved() { localStorage.setItem("cc_puzzles_solved", JSON.stringify([...PZ.solved])); authSchedulePush(); }

async function loadPuzzles() {
  try { PZ.list = await (await fetch("/static/puzzles.json")).json(); }
  catch (e) { PZ.list = []; }
  if (PZ.list.length) {
    renderPzGrid();
    let idx = PZ.list.findIndex((p) => !PZ.solved.has(p.level));  // resume at first unsolved
    if (idx < 0) idx = 0;
    loadPuzzle(idx);
  } else { $("pzPrompt").textContent = "퍼즐을 불러오지 못했습니다."; }
}

function renderPzGrid() {
  const grid = $("pzGrid"); grid.innerHTML = "";
  const start = PZ.cat * 25;
  for (let i = 0; i < 25; i++) {
    const idx = start + i, lvl = idx + 1;
    const unlocked = pzUnlocked(lvl);
    const b = document.createElement("button");
    b.textContent = unlocked ? lvl : "";
    if (idx === PZ.idx) b.classList.add("cur");
    if (PZ.solved.has(lvl)) b.classList.add("solved");
    if (!unlocked) b.classList.add("locked");
    b.onclick = () => loadPuzzle(idx);
    grid.appendChild(b);
  }
  const solvedCount = PZ.list.filter((p) => PZ.solved.has(p.level)).length;
  $("pzProgress").textContent = `(푼 문제 ${solvedCount}/${PZ.list.length})`;
}

async function loadPuzzle(idx) {
  if (idx < 0 || idx >= PZ.list.length) return;
  PZ.idx = idx; PZ.cat = Math.floor(idx / 25);
  document.querySelectorAll("#pzCats button").forEach((b) =>
    b.classList.toggle("active", +b.dataset.cat === PZ.cat));
  const p = PZ.list[idx];
  renderPzGrid();
  if (!pzUnlocked(p.level)) {       // sequential lock — must beat the previous level first
    PZ.locked = true; PZ.fen = p.fen; PZ.sel = null; PZ.lastUci = null; PZ.hintSq = null; PZ.busy = false;
    PZ.legal = { legal: {} };
    $("pzPrompt").innerHTML = `🔒 #${p.level} 잠김 — 앞 단계 #${p.level - 1}을(를) 먼저 깨야 합니다.`;
    setStatus("pzFeedback", "이전 단계를 먼저 해결하세요.", true);
    renderPzBoard();
    return;
  }
  PZ.locked = false;
  PZ.baseFen = p.fen; PZ.fen = p.fen; PZ.mateIn = p.mateIn; PZ.movesLeft = p.mateIn;
  PZ.sel = null; PZ.lastUci = null; PZ.hintSq = null; PZ.busy = false;
  $("pzPrompt").innerHTML = `#${p.level} — 백이 두어 <b>${p.mateIn}수</b> 만에 체크메이트! (백 차례)`;
  $("pzFeedback").textContent = ""; $("pzFeedback").className = "status";
  try { PZ.legal = await api("/api/legal_fen", { fen: PZ.fen }); }
  catch (e) { PZ.legal = { legal: {} }; }
  renderPzBoard();
}

function renderPzBoard() {
  const board = $("pzBoard"); board.innerHTML = "";
  if (!PZ.fen) return;
  const map = parseFen(PZ.fen);
  const files = [..."abcdefgh"], ranks = [8, 7, 6, 5, 4, 3, 2, 1];
  const lf = PZ.lastUci ? PZ.lastUci.slice(0, 2) : null, lt = PZ.lastUci ? PZ.lastUci.slice(2, 4) : null;
  const legal = (PZ.busy ? {} : (PZ.legal.legal || {}));
  let kingSq = null;
  if (PZ.legal.check) { const kc = PZ.legal.turn === "w" ? "K" : "k"; for (const s in map) if (map[s] === kc) kingSq = s; }
  for (const rank of ranks) {
    for (const f of files) {
      const sq = f + rank, fi = "abcdefgh".indexOf(f);
      const div = document.createElement("div");
      div.className = "sq " + ((fi + rank) % 2 === 0 ? "light" : "dark");
      if (sq === lf || sq === lt) div.classList.add("last");
      if (PZ.sel === sq) div.classList.add("sel");
      if (PZ.hintSq === sq) div.classList.add("sel");
      if (sq === kingSq) div.classList.add("check");
      const p = map[sq];
      if (p) {
        const s = document.createElement("span");
        s.className = "pc " + (p === p.toUpperCase() ? "w" : "b");
        s.textContent = GLYPH[p.toLowerCase()];
        div.appendChild(s);
      }
      if (SETTINGS.showDots && PZ.sel && legal[PZ.sel] && legal[PZ.sel].includes(sq)) {
        const d = document.createElement("div"); d.className = "dot" + (map[sq] ? " cap" : "");
        div.appendChild(d);
      }
      div.dataset.sq = sq;
      div.onclick = () => onPzClick(sq);
      board.appendChild(div);
    }
  }
}

function onPzClick(sq) {
  if (_dragJustMoved || PZ.busy || PZ.locked) return;
  PZ.hintSq = null;
  const legal = PZ.legal.legal || {};
  if (PZ.sel) {
    if (legal[PZ.sel] && legal[PZ.sel].includes(sq)) { pzUserMove(PZ.sel + sq); return; }
    if (legal[sq]) { PZ.sel = sq; renderPzBoard(); return; }
    PZ.sel = null; renderPzBoard(); return;
  }
  if (legal[sq]) { PZ.sel = sq; renderPzBoard(); }
}

function pzWrongEffect() {
  const stack = $("pzStack"), flash = $("pzFlash");
  stack.classList.remove("shake"); void stack.offsetWidth; stack.classList.add("shake");
  flash.classList.remove("show"); void flash.offsetWidth; flash.classList.add("show");
}

async function pzUserMove(uci) {
  PZ.busy = true; PZ.sel = null; renderPzBoard();
  const prevFen = PZ.fen, prevLast = PZ.lastUci;
  let res;
  try { res = await api("/api/puzzle_move", { fen: PZ.fen, move: uci, mateIn: PZ.movesLeft }); }
  catch (e) { PZ.busy = false; setStatus("pzFeedback", isOffline(e) ? OFFLINE_MSG : "오류: " + e.message, true); renderPzBoard(); return; }

  if (!res.correct) {
    // play the move, then shake the board + flash a big "오답!", then revert
    PZ.fen = res.userFen; PZ.lastUci = uci;
    renderPzBoard();
    animateMove($("pzBoard"), uci.slice(0, 2), uci.slice(2, 4), "w");
    await sleep(260);
    pzWrongEffect();
    await sleep(760);
    PZ.fen = prevFen; PZ.lastUci = prevLast;
    PZ.busy = false; renderPzBoard();
    return;
  }
  // show the user's move
  PZ.fen = res.userFen; PZ.lastUci = uci;
  renderPzBoard();
  animateMove($("pzBoard"), uci.slice(0, 2), uci.slice(2, 4), "w");

  if (res.solved) {
    PZ.busy = false; PZ.legal = { legal: {} };
    await sleep(300);   // let the final piece finish sliding before the result shows
    pzSolved();
    return;
  }

  // defender replies after a short beat
  await sleep(260);
  PZ.fen = res.fen; PZ.lastUci = res.replyUci; PZ.movesLeft = res.mateIn;
  renderPzBoard();
  if (res.replyUci) animateMove($("pzBoard"), res.replyUci.slice(0, 2), res.replyUci.slice(2, 4), "w");
  setStatus("pzFeedback", `✅ 좋아요! 메이트까지 ${res.mateIn}수 남았습니다.`, false);
  $("pzFeedback").style.color = "#7bd88f";
  try { PZ.legal = await api("/api/legal_fen", { fen: PZ.fen }); } catch (e) { PZ.legal = { legal: {} }; }
  PZ.busy = false;
  renderPzBoard();
}

function pzSolved() {
  const p = PZ.list[PZ.idx];
  PZ.solved.add(p.level); pzSaveSolved(); renderPzGrid();
  showResult({
    kind: "win", icon: "🏆", title: "정답!", sub: `퍼즐 #${p.level} · ${p.mateIn}수 메이트 성공!`,
    actions: [
      { label: "다음 퍼즐 ▶", primary: true, onClick: () => loadPuzzle(Math.min(PZ.list.length - 1, PZ.idx + 1)) },
      { label: "이 퍼즐 다시", onClick: () => loadPuzzle(PZ.idx) },
    ],
  });
}

document.querySelectorAll("#pzCats button").forEach((b) => {
  b.onclick = () => { PZ.cat = +b.dataset.cat; loadPuzzle(PZ.cat * 25); };
});
$("pzPrev").onclick = () => loadPuzzle(PZ.idx - 1);
$("pzNext").onclick = () => loadPuzzle(PZ.idx + 1);
$("pzReset").onclick = () => loadPuzzle(PZ.idx);
$("pzHint").onclick = async () => {
  const p = PZ.list[PZ.idx];
  if (PZ.fen !== PZ.baseFen) await loadPuzzle(PZ.idx);   // hint from the start
  PZ.hintSq = (p.solution[0] || "").slice(0, 2);
  renderPzBoard();
  setStatus("pzFeedback", "💡 표시된 칸의 기물을 움직여 보세요.", false);
};
$("pzSolution").onclick = () => {
  const p = PZ.list[PZ.idx];
  setStatus("pzFeedback", "정답: " + (p.solutionSan || []).join(" "), false);
};

async function aiBoot() {
  loadPuzzles();
  updateRatingChip();
  renderHistory();
  updateRankBadge();
  $("aiLevelLabel").textContent = aiLevelText($("aiLevel").value);
  try { AIG.state = await api("/api/legal", { moves: [] }); renderAiBoard(); updateAiTurn(); }
  catch (e) { /* board stays empty until 새 대국 시작 */ }
}

// =========================================================================== //
// LEARN CHESS BASICS — visualize how each piece moves + the rules
// =========================================================================== //
function _sq(fx, fy) { return "abcdefgh"[fx] + (fy + 1); }
function _inb(x, y) { return x >= 0 && x < 8 && y >= 0 && y < 8; }
function _slide(fx, fy, dirs) {
  const out = [];
  for (const [dx, dy] of dirs) {
    let x = fx + dx, y = fy + dy;
    while (_inb(x, y)) { out.push(_sq(x, y)); x += dx; y += dy; }
  }
  return out;
}
function _steps(fx, fy, offs) {
  return offs.filter(([dx, dy]) => _inb(fx + dx, fy + dy)).map(([dx, dy]) => _sq(fx + dx, fy + dy));
}
const _DIAG = [[1, 1], [1, -1], [-1, 1], [-1, -1]];
const _ORTHO = [[1, 0], [-1, 0], [0, 1], [0, -1]];
const _KNIGHT = [[1, 2], [2, 1], [-1, 2], [-2, 1], [1, -2], [2, -1], [-1, -2], [-2, -1]];
const _ALL8 = [..._DIAG, ..._ORTHO];

function learnTopic(topic) {
  // d4 = fx 3, fy 3
  switch (topic) {
    case "pawn": return {
      title: "폰 (Pawn) ♟", pieces: { e2: "P", d3: "p", f3: "p" },
      moves: ["e3", "e4"], captures: ["d3", "f3"],
      desc: "폰은 <b>앞으로 한 칸</b> 전진합니다. 단, 그 폰의 <b>첫 이동</b>에 한해 두 칸까지 갈 수 있어요(e2→e4).<br>" +
        "잡을 때는 <b>대각선 앞</b>으로만 잡습니다(빨간 표시). <b>뒤로는 절대 못 가고</b>, 앞이 막히면 못 움직입니다.<br>" +
        "끝 줄(8랭크)에 도달하면 <b>승격</b>합니다. → '승격' 버튼 참고",
    };
    case "knight": return {
      title: "나이트 (Knight) ♞", pieces: { d4: "N" }, moves: _steps(3, 3, _KNIGHT), captures: [],
      desc: "나이트는 <b>'ㄴ'(L)자</b>로 움직입니다 — 한 방향 두 칸 + 직각으로 한 칸.<br>" +
        "체스에서 <b>유일하게 다른 기물을 뛰어넘을 수 있는</b> 기물입니다(앞이 막혀 있어도 OK).",
    };
    case "bishop": return {
      title: "비숍 (Bishop) ♝", pieces: { d4: "B" }, moves: _slide(3, 3, _DIAG), captures: [],
      desc: "비숍은 <b>대각선</b>으로 막힐 때까지 원하는 만큼 이동합니다.<br>" +
        "한 비숍은 <b>한 가지 색의 칸</b>에만 머뭅니다(흰칸 비숍/검은칸 비숍).",
    };
    case "rook": return {
      title: "룩 (Rook) ♜", pieces: { d4: "R" }, moves: _slide(3, 3, _ORTHO), captures: [],
      desc: "룩은 <b>가로·세로</b>로 막힐 때까지 원하는 만큼 이동합니다. 캐슬링에도 쓰입니다.",
    };
    case "queen": return {
      title: "퀸 (Queen) ♛", pieces: { d4: "Q" }, moves: _slide(3, 3, _ALL8), captures: [],
      desc: "퀸은 <b>가로·세로·대각선 모두</b> 원하는 만큼 이동합니다. <b>가장 강력한</b> 기물(룩+비숍).",
    };
    case "king": return {
      title: "킹 (King) ♚", pieces: { d4: "K" }, moves: _steps(3, 3, _ALL8), captures: [],
      desc: "킹은 <b>모든 방향으로 한 칸씩</b> 이동합니다. 가장 중요한 기물 — <b>잡히면(체크메이트) 패배</b>.<br>" +
        "상대가 공격하는 칸으로는 갈 수 없습니다.",
    };
    case "castle": return {
      title: "캐슬링 (Castling)", pieces: { e1: "K", h1: "R", a1: "R" }, moves: ["g1", "f1", "c1", "d1"], captures: [],
      desc: "킹과 룩을 <b>한 번에</b> 움직이는 특수 수입니다.<br>" +
        "• 킹사이드: 킹 e1→g1, 룩 h1→f1<br>• 퀸사이드: 킹 e1→c1, 룩 a1→d1<br>" +
        "조건: 킹과 그 룩이 <b>아직 안 움직였고</b>, 사이가 <b>비어 있고</b>, 킹이 <b>체크가 아니며</b> 지나는 칸도 공격받지 않을 때.",
    };
    case "enpassant": return {
      title: "앙파상 (En passant)", pieces: { e5: "P", d5: "p" }, moves: [], captures: ["d6"],
      desc: "상대 폰이 <b>두 칸 전진</b>해 내 폰 바로 옆에 나란히 섰을 때(d7→d5), <b>바로 다음 수에 한해</b> " +
        "마치 한 칸만 온 것처럼 <b>대각선 뒤(d6)로 잡는</b> 특수 규칙입니다. 잡힌 상대 폰(d5)은 사라집니다.",
    };
    case "promotion": return {
      title: "승격 (Promotion)", pieces: { e7: "P" }, moves: ["e8"], captures: [],
      desc: "폰이 <b>끝 줄(8랭크)</b>에 도달하면 <b>퀸·룩·비숍·나이트</b> 중 하나로 변신합니다.<br>" +
        "거의 항상 가장 강한 <b>퀸</b>으로 승격합니다(언더프로모션은 특수한 경우).",
    };
    default: return learnTopic("pawn");
  }
}

function renderLearnBoard(cfg) {
  const board = $("learnBoard"); board.innerHTML = "";
  const files = [..."abcdefgh"], ranks = [8, 7, 6, 5, 4, 3, 2, 1];
  const moves = new Set(cfg.moves || []), caps = new Set(cfg.captures || []);
  for (const rank of ranks) {
    for (const f of files) {
      const sq = f + rank, fi = "abcdefgh".indexOf(f);
      const div = document.createElement("div");
      div.className = "sq " + ((fi + rank) % 2 === 0 ? "light" : "dark");
      const p = (cfg.pieces || {})[sq];
      if (p) {
        const s = document.createElement("span");
        s.className = "pc " + (p === p.toUpperCase() ? "w" : "b");
        s.textContent = GLYPH[p.toLowerCase()];
        div.appendChild(s);
      }
      if (moves.has(sq)) { const d = document.createElement("div"); d.className = "lmove"; div.appendChild(d); }
      if (caps.has(sq)) { const d = document.createElement("div"); d.className = "lcap"; div.appendChild(d); }
      board.appendChild(div);
    }
  }
}

function showLearn(topic) {
  const cfg = learnTopic(topic);
  renderLearnBoard(cfg);
  $("learnTitle").textContent = cfg.title;
  $("learnDesc").innerHTML = cfg.desc;
}
document.querySelectorAll("#learnSel button").forEach((b) => {
  b.onclick = () => {
    document.querySelectorAll("#learnSel button").forEach((x) => x.classList.toggle("active", x === b));
    showLearn(b.dataset.topic);
  };
});
showLearn("pawn");

// =========================================================================== //
// ONLINE MULTIPLAYER — WebSocket matchmaking + play. The server validates all
// moves and broadcasts state; this client only renders and sends intents.
// =========================================================================== //
const OG = {
  ws: null, started: false, over: false, color: null, opponent: null,
  state: null, moves: [], sel: null, orient: "w", lastUci: null, pingTimer: null,
  oppRating: RATING_START, ratingApplied: false,
  clock: { w: 600, b: 600 }, clockSyncedAt: 0,
};

// ---- chess clock (server-authoritative; we only tick the display) ----
function ogSyncClock(state) {
  if (typeof state.clockW === "number") OG.clock = { w: state.clockW, b: state.clockB };
  OG.clockSyncedAt = performance.now();
}
function ogClockNow(color) {
  let v = color === "w" ? OG.clock.w : OG.clock.b;
  // only the side to move's clock runs
  if (OG.started && !OG.over && OG.state && OG.state.turn === color) {
    v -= (performance.now() - OG.clockSyncedAt) / 1000;
  }
  return Math.max(0, v);
}
function fmtClock(s) {
  s = Math.max(0, Math.ceil(s));
  return String(Math.floor(s / 60)).padStart(2, "0") + ":" + String(s % 60).padStart(2, "0");
}

// ---- captured material from the FEN (points: P1 N3 B3 R5 Q9) ----
const PIECE_PTS = { p: 1, n: 3, b: 3, r: 5, q: 9 };
function materialInfo(fen) {
  const cnt = {};
  for (const c of "PNBRQpnbrq") cnt[c] = 0;
  for (const ch of fen.split(" ")[0]) if (cnt[ch] !== undefined) cnt[ch]++;
  const start = { p: 8, n: 2, b: 2, r: 2, q: 1 };
  const capByWhite = [], capByBlack = [];
  let wPts = 0, bPts = 0;
  for (const t of ["q", "r", "b", "n", "p"]) {
    for (let i = 0; i < Math.max(0, start[t] - cnt[t]); i++) { capByWhite.push(t); wPts += PIECE_PTS[t]; }
    for (let i = 0; i < Math.max(0, start[t] - cnt[t.toUpperCase()]); i++) { capByBlack.push(t); bPts += PIECE_PTS[t]; }
  }
  return { capByWhite, capByBlack, wLead: wPts - bPts };
}

// ---- player bars: [profile] [name + timer side by side] ... [captured +pts] ----
function renderPbars() {
  const top = $("ogTopBar"), bottom = $("ogBottomBar");
  if (!OG.started || !OG.state) { top.classList.add("hidden"); bottom.classList.add("hidden"); return; }
  top.classList.remove("hidden"); bottom.classList.remove("hidden");
  const mat = materialInfo(OG.state.fen);
  const mine = OG.color, theirs = mine === "w" ? "b" : "w";
  const bar = (el, color, name, rating, isMe) => {
    const caps = color === "w" ? mat.capByWhite : mat.capByBlack;
    const lead = color === "w" ? mat.wLead : -mat.wLead;
    const active = OG.started && !OG.over && OG.state.turn === color;
    const t = ogClockNow(color);
    el.innerHTML =
      `<span class="pv-ava ${isMe ? "me" : ""}">${escapeHtml((name || "?").charAt(0).toUpperCase())}</span>` +
      `<span class="pv-name">${escapeHtml(name || "")}</span>` +
      `<span class="pv-rating">${ratingHTML(rating)}</span>` +
      `<span class="pv-clock ${active ? "active" : ""} ${t < 60 ? "low" : ""}">⏱ ${fmtClock(t)}</span>` +
      `<span class="pv-caps">${caps.map((c) => GLYPH[c]).join("")}` +
      `${lead > 0 ? `<b class="pv-lead">+${lead}</b>` : ""}</span>`;
  };
  bar(top, theirs, OG.opponent || "상대", OG.oppRating, false);
  bar(bottom, mine, ogName(), myRating(), true);
}
setInterval(() => { if (OG.started) renderPbars(); }, 250);

function ogSend(payload) {
  if (OG.ws && OG.ws.readyState === WebSocket.OPEN) OG.ws.send(JSON.stringify(payload));
}

function ogConnect(then) {
  if (OG.ws && OG.ws.readyState === WebSocket.OPEN) { then && then(); return; }
  const proto = location.protocol === "https:" ? "wss" : "ws";
  const ws = new WebSocket(`${proto}://${location.host}/ws`);
  OG.ws = ws;
  ws.onopen = () => {
    if (OG.pingTimer) clearInterval(OG.pingTimer);
    OG.pingTimer = setInterval(() => ogSend({ type: "ping" }), 25000); // keep proxies from closing us
    then && then();
  };
  ws.onmessage = (e) => { try { ogHandle(JSON.parse(e.data)); } catch (err) {} };
  ws.onclose = () => {
    if (OG.pingTimer) { clearInterval(OG.pingTimer); OG.pingTimer = null; }
    if (OG.started && !OG.over) {
      OG.over = true; updateOgTurn();
      setStatus("ogStatus", "서버와 연결이 끊어졌습니다. 새로고침 후 다시 매치를 시작하세요.", true);
    }
    OG.ws = null;
  };
  ws.onerror = () => { setStatus("ogSetupStatus", "연결 오류 — 잠시 후 다시 시도하세요.", true); };
}

function ogName() { return ($("ogName").value || "플레이어").trim().slice(0, 20) || "플레이어"; }

// Matchmaking always starts on a FRESH socket: closing the old one makes the
// server clean up any stale queue/room/game state for us, so the user can
// never get stuck in "이미 대국 중입니다".
function ogFresh(then) {
  if (OG.ws) {
    try { OG.ws.onclose = null; OG.ws.close(); } catch (e) {}
    OG.ws = null;
  }
  OG.started = false; OG.over = false;
  ogConnect(then);
}

function ogHandle(msg) {
  switch (msg.type) {
    case "waiting":
      setStatus("ogSetupStatus", "상대를 찾는 중… 다른 사람이 '빠른 매치'를 누르면 연결됩니다.");
      $("ogCancel").classList.remove("hidden");
      break;
    case "room":
      $("ogCodeBox").classList.remove("hidden");
      $("ogCode").textContent = msg.code;
      setStatus("ogSetupStatus", "친구가 코드를 입력하면 대국이 시작됩니다.");
      $("ogCancel").classList.remove("hidden");
      break;
    case "cancelled":
      setStatus("ogSetupStatus", "매칭을 취소했습니다.");
      $("ogCancel").classList.add("hidden");
      $("ogCodeBox").classList.add("hidden");
      break;
    case "start":
      OG.started = true; OG.over = false; OG.ratingApplied = false;
      OG.oppRating = +(msg.opponentRating || RATING_START);
      OG.color = msg.color; OG.orient = msg.color;
      OG.opponent = msg.opponent || "상대";
      OG.state = msg.state; OG.moves = msg.state.moves || []; OG.sel = null; OG.lastUci = null;
      ogSyncClock(msg.state);
      $("ogSetup").classList.add("hidden");
      $("ogGameInfo").classList.remove("hidden");
      $("ogCancel").classList.add("hidden"); $("ogCodeBox").classList.add("hidden");
      $("ogVs").innerHTML = `${escapeHtml(ogName())} (${ratingHTML(myRating())}) vs ${escapeHtml(OG.opponent)} (${ratingHTML(OG.oppRating)})`;
      $("ogColorInfo").textContent = `당신은 ${OG.color === "w" ? "백(선공)" : "흑(후공)"}입니다.`;
      setStatus("ogStatus", "대국 시작! 행운을 빕니다 🍀");
      setStatus("ogSetupStatus", "");
      ogEnterGame();
      renderOgBoard(); renderOgMoves(); updateOgTurn(); renderPbars();
      break;
    case "state":
      OG.state = msg.state; OG.moves = msg.state.moves || []; OG.sel = null;
      OG.lastUci = msg.lastUci || null;
      ogSyncClock(msg.state);
      $("ogDrawPrompt").classList.add("hidden");   // a move voids any pending draw offer
      renderOgBoard(); renderOgMoves(); updateOgTurn(); renderPbars();
      if (OG.lastUci) animateMove($("ogBoard"), OG.lastUci.slice(0, 2), OG.lastUci.slice(2, 4), OG.orient);
      break;
    case "draw_offered":
      $("ogDrawPrompt").classList.remove("hidden");
      break;
    case "draw_declined":
      setStatus("ogStatus", "상대가 무승부 제안을 거절했습니다.", true);
      break;
    case "chat":
      ogAppendChat(OG.opponent || "상대", msg.text || "", false);
      break;
    case "end":
      ogEnd(msg.result, msg.reason);
      break;
    case "error":
      setStatus(OG.started ? "ogStatus" : "ogSetupStatus", msg.message || "오류", true);
      break;
  }
}

function renderOgBoard() {
  const board = $("ogBoard"); board.innerHTML = "";
  const st = OG.state; if (!st) return;
  const map = parseFen(st.fen);
  const files = OG.orient === "w" ? [..."abcdefgh"] : [..."hgfedcba"];
  const ranks = OG.orient === "w" ? [8, 7, 6, 5, 4, 3, 2, 1] : [1, 2, 3, 4, 5, 6, 7, 8];
  const lf = OG.lastUci ? OG.lastUci.slice(0, 2) : null, lt = OG.lastUci ? OG.lastUci.slice(2, 4) : null;
  const myTurn = OG.started && !OG.over && st.turn === OG.color;
  const legal = myTurn ? (st.legal || {}) : {};
  let kingSq = null;
  if (st.check) { const kc = st.turn === "w" ? "K" : "k"; for (const s in map) if (map[s] === kc) kingSq = s; }
  for (const rank of ranks) {
    for (const f of files) {
      const sq = f + rank, fi = "abcdefgh".indexOf(f);
      const div = document.createElement("div");
      div.className = "sq " + ((fi + rank) % 2 === 0 ? "light" : "dark");
      if (sq === lf || sq === lt) div.classList.add("last");
      if (OG.sel === sq) div.classList.add("sel");
      if (sq === kingSq) div.classList.add("check");
      const p = map[sq];
      if (p) {
        const s = document.createElement("span");
        s.className = "pc " + (p === p.toUpperCase() ? "w" : "b");
        s.textContent = GLYPH[p.toLowerCase()];
        div.appendChild(s);
      }
      if (SETTINGS.showDots && OG.sel && legal[OG.sel] && legal[OG.sel].includes(sq)) {
        const d = document.createElement("div"); d.className = "dot" + (map[sq] ? " cap" : "");
        div.appendChild(d);
      }
      div.dataset.sq = sq;
      div.onclick = () => onOgClick(sq);
      board.appendChild(div);
    }
  }
}

function onOgClick(sq) {
  if (_dragJustMoved) return;
  const st = OG.state;
  if (!OG.started || OG.over || !st || st.turn !== OG.color) return;
  const map = parseFen(st.fen), legal = st.legal || {};
  if (OG.sel) {
    if (legal[OG.sel] && legal[OG.sel].includes(sq)) {
      const from = OG.sel, piece = map[from], r = +sq[1];
      OG.sel = null;
      if (piece && piece.toLowerCase() === "p" && (r === 8 || r === 1)) {
        promoChooser($("ogBoard"), piece === "P", (pp) => ogSend({ type: "move", uci: from + sq + pp }));
      } else {
        ogSend({ type: "move", uci: from + sq });
      }
      renderOgBoard();
      return;
    }
    if (legal[sq]) { OG.sel = sq; renderOgBoard(); return; }
    OG.sel = null; renderOgBoard(); return;
  }
  if (legal[sq]) { OG.sel = sq; renderOgBoard(); }
}

function renderOgMoves() {
  const el = $("ogMoves");
  const san = (OG.state && OG.state.san) ? OG.state.san : [];
  if (!san.length) { el.innerHTML = '<span class="num">매치가 시작되면 기보가 여기에 쌓입니다.</span>'; return; }
  let html = "";
  san.forEach((s, i) => {
    if (i % 2 === 0) html += `<span class="num">${i / 2 + 1}.</span>`;
    html += `<span class="mv" style="cursor:default">${s}</span> `;
  });
  el.innerHTML = html; el.scrollTop = el.scrollHeight;
}

function updateOgTurn() {
  const t = $("ogTurn"), st = OG.state;
  if (!OG.started || !st) { t.innerHTML = '<span class="pill"></span>매치를 시작하면 보드가 열립니다.'; return; }
  if (OG.over) { t.innerHTML = "<b>대국 종료</b>"; return; }
  const w = st.turn === "w", mine = st.turn === OG.color;
  t.innerHTML = `<span class="pill ${w ? "" : "b"}"></span>${w ? "백" : "흑"} 차례` +
    (mine ? " (당신)" : ` (${OG.opponent || "상대"})`) +
    (st.check ? " · <b style='color:#ff8a80'>체크!</b>" : "");
}

function ogEnd(result, reason) {
  OG.over = true; ogExitGame(); renderOgBoard(); updateOgTurn();
  let kind = "draw";
  if (result === "1-0") kind = OG.color === "w" ? "win" : "loss";
  else if (result === "0-1") kind = OG.color === "b" ? "win" : "loss";
  const reasonTxt = { checkmate: "체크메이트", resign: "기권", forfeit: "상대가 나갔습니다", timeout: "시간 초과", agreement: "합의 무승부", draw: "무승부" }[reason] || "";
  const me = ogName();
  const white = OG.color === "w" ? me : (OG.opponent || "상대");
  const black = OG.color === "b" ? me : (OG.opponent || "상대");
  const movesCopy = [...OG.moves];
  const actions = [];
  if (movesCopy.length) {
    actions.push({ label: "🤖 AI 평가 보기", primary: true,
      onClick: () => runAnalyze({ moves: movesCopy, white, black, movetime: 350 }, "ogStatus") });
  }
  actions.push({ label: "🔄 새 매치", onClick: ogReset });

  // Rating changes ONLY here — an online match result. Apply exactly once.
  let badge = null;
  if (!OG.ratingApplied) {
    OG.ratingApplied = true;
    const before = myRating();
    const score = kind === "win" ? 1 : kind === "loss" ? 0 : 0.5;
    const newRating = Math.max(0, before + eloDelta(before, OG.oppRating, score));
    const applied = newRating - before;   // what actually changed (0-floor aware)
    setMyRating(newRating);
    addHistory({ mode: "online", opponent: OG.opponent || "상대", result: kind, ratingDelta: applied });
    badge = { small: "⚡ 레이팅 변동", text: `${applied >= 0 ? "+" + applied : applied} → ${ratingHTML(newRating)}` };
    setTimeout(loadLeaderboard, 1600);   // after the debounced progress push lands
  }

  const opts = kind === "win"
    ? { kind, icon: "🏆", title: "승리!", sub: `${OG.opponent}님을 이겼습니다 (${reasonTxt})`, badge, actions }
    : kind === "loss"
      ? { kind, icon: "😢", title: "패배", sub: `${OG.opponent}님에게 졌습니다 (${reasonTxt})`, badge, actions }
      : { kind, icon: "🤝", title: "무승부", sub: `${OG.opponent}님과 비겼습니다`, badge, actions };
  setStatus("ogStatus", `대국 종료 (${result}) — ${reasonTxt}`);
  setTimeout(() => showResult(opts), 450);
}

function ogReset() {
  OG.started = false; OG.over = false; OG.color = null; OG.opponent = null;
  OG.state = null; OG.moves = []; OG.sel = null; OG.lastUci = null;
  $("ogSetup").classList.remove("hidden");
  $("ogGameInfo").classList.add("hidden");
  $("ogCodeBox").classList.add("hidden");
  $("ogCancel").classList.add("hidden");
  $("ogTopBar").classList.add("hidden");
  $("ogBottomBar").classList.add("hidden");
  $("ogDrawPrompt").classList.add("hidden");
  ogExitGame();
  updateOgAuthGate();
  setStatus("ogStatus", ""); setStatus("ogSetupStatus", "");
  renderOgBoard(); renderOgMoves(); updateOgTurn();
  switchTab("online");
}

$("ogQuick").onclick = () => {
  if (!requireLogin()) return;
  setStatus("ogSetupStatus", "서버에 연결 중…");
  ogFresh(() => ogSend({ type: "quick", name: ogName(), rating: myRating() }));
};
$("ogCreate").onclick = () => {
  if (!requireLogin()) return;
  setStatus("ogSetupStatus", "서버에 연결 중…");
  ogFresh(() => ogSend({ type: "create", name: ogName(), rating: myRating() }));
};
$("ogJoin").onclick = () => {
  if (!requireLogin()) return;
  const code = ($("ogJoinCode").value || "").trim().toUpperCase();
  if (code.length !== 4) { setStatus("ogSetupStatus", "4글자 코드를 입력하세요.", true); return; }
  setStatus("ogSetupStatus", "방에 참가하는 중…");
  ogFresh(() => ogSend({ type: "join", code, name: ogName(), rating: myRating() }));
};
$("ogCancel").onclick = () => ogSend({ type: "cancel" });
$("ogResign").onclick = () => {
  if (!OG.started || OG.over) { setStatus("ogStatus", "진행 중인 대국이 없습니다.", true); return; }
  ogSend({ type: "resign" });
};
$("ogDraw").onclick = () => {
  if (!OG.started || OG.over) { setStatus("ogStatus", "진행 중인 대국이 없습니다.", true); return; }
  ogSend({ type: "draw_offer" });
  setStatus("ogStatus", "무승부를 제안했습니다. 상대의 응답을 기다립니다…");
};
$("ogDrawAccept").onclick = () => { ogSend({ type: "draw_accept" }); $("ogDrawPrompt").classList.add("hidden"); };
$("ogDrawDecline").onclick = () => { ogSend({ type: "draw_decline" }); $("ogDrawPrompt").classList.add("hidden"); };
$("ogFlip").onclick = () => { OG.orient = OG.orient === "w" ? "b" : "w"; renderOgBoard(); };

// ---- login gate: online rated play requires an account ----
function openAuth() { $("authModal").classList.remove("hidden"); setStatus("authStatus", ""); $("authId").focus(); }
function updateOgAuthGate() {
  const gate = $("ogLoginGate"), body = $("ogMatchBody");
  if (!gate || !body) return;
  const on = !!AUTH.token;
  gate.classList.toggle("hidden", on);
  body.classList.toggle("hidden", !on);
  if (on && $("ogName")) $("ogName").value = AUTH.id || "플레이어";
}
$("ogLoginBtn").onclick = openAuth;
function requireLogin() {
  if (AUTH.token) return true;
  setStatus("ogSetupStatus", "온라인 대국은 로그인 후 이용할 수 있습니다.", true);
  openAuth();
  return false;
}

// ---- immersive in-game mode (hide menus) ----
function ogEnterGame() {
  document.body.classList.add("ingame");
  $("ogChat").classList.add("hidden");   // minimal by default; opened via the 💬 toggle
  $("ogChatLog").innerHTML = "";
}
function ogExitGame() {
  document.body.classList.remove("ingame");
  $("ogChat").classList.add("hidden");
}
$("ogChatToggle").onclick = () => $("ogChat").classList.toggle("hidden");

// ---- in-game chat ----
function ogAppendChat(who, text, me) {
  const log = $("ogChatLog");
  const d = document.createElement("div");
  d.className = "chatmsg" + (me ? " me" : "");
  d.innerHTML = `<b>${escapeHtml(who)}</b> ${escapeHtml(text)}`;
  log.appendChild(d); log.scrollTop = log.scrollHeight;
}
function ogSendChat() {
  const inp = $("ogChatInput"), t = (inp.value || "").trim();
  if (!t || !OG.started || OG.over) return;
  ogSend({ type: "chat", text: t });
  ogAppendChat(AUTH.id || "나", t, true);
  inp.value = "";
}
$("ogChatSend").onclick = ogSendChat;
$("ogChatInput").addEventListener("keydown", (e) => { if (e.key === "Enter") { e.preventDefault(); ogSendChat(); } });

// =========================================================================== //
// ACCOUNTS — register/login with id+password; progress lives on the server.
// Register uploads this device's current progress; login pulls the account's
// progress down (overwriting local); while logged in every change is pushed
// (debounced) via authSchedulePush() calls in the setters above.
// =========================================================================== //
const AUTH = {
  token: localStorage.getItem("cc_token") || null,
  id: localStorage.getItem("cc_uid") || null,
  pushTimer: null,
};

function collectProgress() {
  return {
    rating: myRating(),
    history: gameHistory(),
    bestLevel: bestLevel(),
    puzzles: [...PZ.solved],
  };
}

function applyProgress(p) {
  p = p || {};
  if (typeof p.rating === "number") localStorage.setItem("cc_rating3", String(Math.max(0, Math.round(p.rating))));
  if (Array.isArray(p.history)) localStorage.setItem("cc_history", JSON.stringify(p.history));
  if (typeof p.bestLevel === "number") localStorage.setItem("cc_best_level", String(p.bestLevel));
  if (Array.isArray(p.puzzles)) {
    localStorage.setItem("cc_puzzles_solved", JSON.stringify(p.puzzles));
    PZ.solved = new Set(p.puzzles);
  }
  updateRatingChip(); renderHistory(); updateRankBadge();
  if (PZ.list.length) renderPzGrid();
}

function authSchedulePush() {
  if (!AUTH.token) return;
  clearTimeout(AUTH.pushTimer);
  AUTH.pushTimer = setTimeout(async () => {
    try { await api("/api/auth/save", { token: AUTH.token, progress: collectProgress() }); }
    catch (e) { if (/세션/.test(e.message || "")) authClearSession(); }
  }, 800);
}

function authClearSession() {
  AUTH.token = null; AUTH.id = null;
  localStorage.removeItem("cc_token"); localStorage.removeItem("cc_uid");
  renderAuthArea();
  updateRatingChip();
  if (typeof updateOgAuthGate === "function") updateOgAuthGate();
}

function authSetSession(id, token, progress) {
  AUTH.id = id; AUTH.token = token;
  localStorage.setItem("cc_token", token); localStorage.setItem("cc_uid", id);
  applyProgress(progress);
  const nick = $("ogName"); if (nick) nick.value = id;   // nickname = account id
  renderAuthArea();
  updateRatingChip();
  if (typeof updateOgAuthGate === "function") updateOgAuthGate();
}

function renderAuthArea() {
  const el = $("authArea"); if (!el) return;
  if (AUTH.token) {
    el.innerHTML = `<span class="user-chip">👤 <b>${escapeHtml(AUTH.id || "")}</b></span>` +
      `<button class="ghost" id="authLogout">로그아웃</button>`;
    $("authLogout").onclick = async () => {
      try { await api("/api/auth/logout", { token: AUTH.token }); } catch (e) {}
      authClearSession();
    };
  } else {
    el.innerHTML = `<button class="ghost" id="authOpen">👤 로그인</button>`;
    $("authOpen").onclick = () => {
      $("authModal").classList.remove("hidden");
      setStatus("authStatus", "");
      $("authId").focus();
    };
  }
}

async function authSubmit(mode) {
  const id = ($("authId").value || "").trim();
  const pw = $("authPw").value || "";
  if (!id || !pw) { setStatus("authStatus", "아이디와 비밀번호를 입력하세요.", true); return; }
  setStatus("authStatus", mode === "register" ? "계정을 만드는 중…" : "로그인 중…");
  try {
    const body = mode === "register" ? { id, pw, progress: collectProgress() } : { id, pw };
    const r = await api("/api/auth/" + mode, body);
    authSetSession(r.id, r.token, r.progress);
    $("authModal").classList.add("hidden");
    $("authPw").value = "";
  } catch (e) {
    setStatus("authStatus", isOffline(e) ? OFFLINE_MSG : e.message, true);
  }
}

$("authLoginBtn").onclick = () => authSubmit("login");
$("authRegisterBtn").onclick = () => authSubmit("register");
$("authCloseBtn").onclick = () => $("authModal").classList.add("hidden");
$("authPw").addEventListener("keydown", (e) => { if (e.key === "Enter") authSubmit("login"); });

// =========================================================================== //
// LEADERBOARD — top registered accounts by rating (server-computed)
// =========================================================================== //
async function loadLeaderboard() {
  const el = $("lbList"); if (!el) return;
  try {
    const r = await (await fetch("/api/leaderboard")).json();
    $("lbTotal").textContent = r.total ? `(플레이어 ${r.total}명)` : "";
    if (!r.top || !r.top.length) {
      el.innerHTML = '<div class="hist-empty">아직 등록된 플레이어가 없습니다. 첫 주인공이 되어보세요!</div>';
      return;
    }
    const medal = (i) => i === 0 ? "🥇" : i === 1 ? "🥈" : i === 2 ? "🥉" : `${i + 1}`;
    el.innerHTML = r.top.map((e, i) => {
      const me = AUTH.id && e.id === AUTH.id;
      return `<div class="lb-row ${me ? "me" : ""}">` +
        `<span class="lb-rank">${medal(i)}</span>` +
        `<span class="lb-name">${escapeHtml(e.id)}${me ? " (나)" : ""}</span>` +
        `<b class="lb-rating">${ratingHTML(e.rating)}</b></div>`;
    }).join("");
  } catch (e) {
    el.innerHTML = '<div class="hist-empty">리더보드를 불러오지 못했습니다.</div>';
  }
}

async function authBoot() {
  renderAuthArea();
  updateOgAuthGate();
  if (!AUTH.token) return;
  try {
    const r = await api("/api/auth/load", { token: AUTH.token });
    AUTH.id = r.id; localStorage.setItem("cc_uid", r.id);
    applyProgress(r.progress);
    const nick = $("ogName"); if (nick) nick.value = r.id;
    renderAuthArea();
    updateOgAuthGate();
  } catch (e) {
    if (!isOffline(e)) authClearSession();   // expired session; keep it if just offline
  }
}

// drag-to-move on each game board (click-to-move still works)
enableBoardDrag($("aiBoard"), {
  movable: () => AIG.started && !AIG.over && !AIG.thinking && AIG.state && AIG.state.turn === AIG.human,
  legal: () => (AIG.state && AIG.state.legal) || {},
  commit: (from, to) => {
    const p = parseFen(AIG.state.fen)[from], r = +to[1]; AIG.sel = null;
    if (p && p.toLowerCase() === "p" && (r === 8 || r === 1)) promoChooser($("aiBoard"), p === "P", (pp) => aiHumanMove(from + to + pp));
    else aiHumanMove(from + to);
  },
});
enableBoardDrag($("ogBoard"), {
  movable: () => OG.started && !OG.over && OG.state && OG.state.turn === OG.color,
  legal: () => (OG.state && OG.state.legal) || {},
  commit: (from, to) => {
    const p = parseFen(OG.state.fen)[from], r = +to[1]; OG.sel = null;
    if (p && p.toLowerCase() === "p" && (r === 8 || r === 1)) promoChooser($("ogBoard"), p === "P", (pp) => ogSend({ type: "move", uci: from + to + pp }));
    else ogSend({ type: "move", uci: from + to });
    renderOgBoard();
  },
});
enableBoardDrag($("pzBoard"), {
  movable: () => !PZ.busy && !PZ.locked && PZ.legal && PZ.legal.legal,
  legal: () => (PZ.legal && PZ.legal.legal) || {},
  commit: (from, to) => { PZ.hintSq = null; pzUserMove(from + to); },
});

// =========================================================================== //
// GROWTH REPORT — rating graph (⑨), future projection (⑪), adaptive rec (③)
// All from local history; no AI key needed. (Meta/coaching, so allowed anywhere.)
// =========================================================================== //
function ratingSeries() {
  // history is newest-first with per-online-game ratingDelta; reconstruct the
  // rating after each game working from the current rating backwards.
  const games = gameHistory().slice().reverse();   // oldest first
  const total = games.reduce((s, g) => s + (g.ratingDelta || 0), 0);
  let cur = Math.max(0, myRating() - total);
  const pts = [{ r: cur, date: null, label: "시작" }];
  for (const g of games) {
    cur = Math.max(0, cur + (g.ratingDelta || 0));
    pts.push({ r: cur, date: g.date || null, mode: g.mode, result: g.result });
  }
  return pts;
}

function currentStreak() {
  const h = gameHistory();
  if (!h.length) return { kind: null, n: 0 };
  const first = h[0].result;
  if (first === "draw") return { kind: "draw", n: 1 };
  let n = 0;
  for (const g of h) { if (g.result === first) n++; else break; }
  return { kind: first, n };
}

function renderGrowth() {
  renderGoal();
  renderGrowthAdapt();
  renderGrowthChart();
  renderGrowthProjection();
}

// ---- weekly goals (⑳) ----
function weekKey(d) {
  d = d || new Date();
  const t = new Date(d); t.setHours(0, 0, 0, 0);
  const day = (t.getDay() + 6) % 7;   // Mon=0
  t.setDate(t.getDate() - day);
  return t.toISOString().slice(0, 10);   // Monday's date = week id
}
const GOAL_TYPES = {
  onlinewin: { label: "온라인 승리", unit: "승", presets: [3, 5, 10] },
  games: { label: "대국 수", unit: "판", presets: [5, 10, 20] },
  rating: { label: "레이팅 상승", unit: "점", presets: [30, 60, 100] },
};
function goalGet() { try { return JSON.parse(localStorage.getItem("cc_goal") || "null"); } catch (e) { return null; } }
function goalSet(g) { localStorage.setItem("cc_goal", JSON.stringify(g)); renderGoal(); }
function goalProgress(g) {
  const wk = weekKey();
  const hist = gameHistory().filter((x) => x.date && weekKey(new Date(x.date)) === wk);
  if (g.type === "onlinewin") return hist.filter((x) => x.mode === "online" && x.result === "win").length;
  if (g.type === "games") return hist.length;
  if (g.type === "rating") return Math.max(0, hist.filter((x) => x.mode === "online").reduce((s, x) => s + (x.ratingDelta || 0), 0));
  return 0;
}
function renderGoal() {
  const el = $("grGoal"); if (!el) return;
  const g = goalGet();
  if (!g || g.week !== weekKey()) {
    // no active goal for this week — offer presets
    let html = `<p class="setdesc" style="margin:0 0 10px">이번 주 목표를 정해 꾸준함을 유지해 보세요.</p><div class="goal-presets">`;
    for (const [type, cfg] of Object.entries(GOAL_TYPES)) {
      cfg.presets.forEach((t) => {
        html += `<button class="ghost goal-set" data-type="${type}" data-target="${t}">${cfg.label} ${t}${cfg.unit}</button>`;
      });
    }
    html += `</div>`;
    el.innerHTML = html;
    el.querySelectorAll(".goal-set").forEach((b) => (b.onclick = () =>
      goalSet({ type: b.dataset.type, target: +b.dataset.target, week: weekKey() })));
    return;
  }
  const cfg = GOAL_TYPES[g.type], p = goalProgress(g), pct = Math.min(100, Math.round((p / g.target) * 100));
  const done = p >= g.target;
  el.innerHTML =
    `<div class="goal-head"><b>${cfg.label} ${g.target}${cfg.unit}</b>` +
    `<span>${done ? "🎉 달성!" : `${p} / ${g.target}${cfg.unit}`}</span></div>` +
    `<div class="goal-bar"><div class="goal-fill ${done ? "done" : ""}" style="width:${pct}%"></div></div>` +
    `<div style="margin-top:10px"><button class="ghost" id="goalReset">목표 바꾸기</button></div>`;
  $("goalReset").onclick = () => { localStorage.removeItem("cc_goal"); renderGoal(); };
}

function renderGrowthAdapt() {
  const el = $("grAdapt"); if (!el) return;
  const s = currentStreak();
  let html;
  if (s.kind === "loss" && s.n >= 3) {
    html = `<p class="grtip">😮‍💨 <b>${s.n}연패 중</b>이에요. 무리하게 이어가기보다 <b>쉬운 퍼즐</b>로 감을 되찾는 걸 추천해요.</p>` +
      `<button class="primary" data-goto="puzzle">🧩 쉬운 퍼즐 풀러 가기</button>`;
  } else if (s.kind === "win" && s.n >= 3) {
    html = `<p class="grtip">🔥 <b>${s.n}연승 중</b>! 실력이 오르는 신호예요. <b>더 높은 난이도 AI</b>에 도전해 성장 속도를 높여보세요.</p>` +
      `<button class="primary" id="grHarder">🤖 더 어려운 AI와 대국</button>`;
  } else {
    const r = myRating();
    html = `<p class="grtip">꾸준함이 실력을 만듭니다. 오늘도 한 판, 퍼즐 몇 개 어때요?</p>` +
      `<div style="display:flex;gap:8px;flex-wrap:wrap"><button class="ghost" data-goto="ai">🤖 AI 대국</button>` +
      `<button class="ghost" data-goto="puzzle">🧩 퍼즐</button>${AUTH.token ? '<button class="ghost" data-goto="online">🌐 온라인</button>' : ""}</div>`;
  }
  el.innerHTML = html;
  el.querySelectorAll("[data-goto]").forEach((b) => (b.onclick = () => switchTab(b.dataset.goto)));
  const harder = $("grHarder");
  if (harder) harder.onclick = () => {
    const lv = Math.min(10, (bestLevel() || 3) + 1);
    $("aiLevel").value = lv; $("aiLevel").dispatchEvent(new Event("input"));
    switchTab("ai");
  };
}

function renderGrowthChart() {
  const box = $("grChartBox"), stats = $("grStats");
  const pts = ratingSeries();
  const rated = gameHistory().filter((g) => g.mode === "online").length;
  if (pts.length < 2 || rated === 0) {
    box.innerHTML = '<div class="hist-empty">온라인 대국을 하면 레이팅 변화가 그래프로 그려집니다.</div>';
    stats.innerHTML = ""; return;
  }
  const vals = pts.map((p) => p.r);
  const min = Math.min(...vals), max = Math.max(...vals);
  const pad = Math.max(30, (max - min) * 0.15);
  const lo = Math.max(0, min - pad), hi = max + pad;
  const W = 320, H = 150, m = { l: 34, r: 8, t: 10, b: 16 };
  const x = (i) => m.l + (i / (pts.length - 1)) * (W - m.l - m.r);
  const y = (v) => m.t + (1 - (v - lo) / (hi - lo || 1)) * (H - m.t - m.b);
  const line = pts.map((p, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(p.r).toFixed(1)}`).join(" ");
  const area = line + ` L${x(pts.length - 1).toFixed(1)},${H - m.b} L${x(0).toFixed(1)},${H - m.b} Z`;
  const dots = pts.map((p, i) => `<circle cx="${x(i).toFixed(1)}" cy="${y(p.r).toFixed(1)}" r="2.4" fill="#57b97c"/>`).join("");
  const yl = [hi, (hi + lo) / 2, lo].map((v) =>
    `<text x="2" y="${(y(v) + 3).toFixed(1)}" font-size="9" fill="#8b93a1">${Math.round(v)}</text>`).join("");
  box.innerHTML =
    `<svg viewBox="0 0 ${W} ${H}" style="width:100%;height:auto;display:block">` +
    `<defs><linearGradient id="grg" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#57b97c" stop-opacity=".35"/><stop offset="1" stop-color="#57b97c" stop-opacity="0"/></linearGradient></defs>` +
    `<path d="${area}" fill="url(#grg)"/><path d="${line}" fill="none" stroke="#57b97c" stroke-width="2"/>${dots}${yl}</svg>`;
  const startR = pts[0].r, nowR = myRating(), delta = nowR - startR;
  const peak = Math.max(...vals);
  stats.innerHTML =
    `<span>현재 <b>${ratingHTML(nowR)}</b></span><span>최고 <b>${peak}</b></span>` +
    `<span>누적 <b class="${delta >= 0 ? "up" : "down"}">${delta >= 0 ? "+" + delta : delta}</b></span>` +
    `<span>온라인 <b>${rated}</b>판</span>`;
}

function renderGrowthProjection() {
  const el = $("grProjection");
  const online = gameHistory().filter((g) => g.mode === "online" && g.date);
  if (online.length < 4) {
    el.innerHTML = '<div class="hist-empty">온라인 대국이 4판 이상 쌓이면 예측이 표시됩니다.</div>'; return;
  }
  // rating change per day over the rated span
  const dates = online.map((g) => g.date).sort();
  const first = new Date(dates[0]), last = new Date(dates[dates.length - 1]);
  const days = Math.max(1, (last - first) / 86400000);
  const totalDelta = online.reduce((s, g) => s + (g.ratingDelta || 0), 0);
  const perDay = totalDelta / days;
  // clamp the 90-day change to a realistic band so short/steep samples don't
  // extrapolate to absurd numbers.
  const change = Math.max(-400, Math.min(400, perDay * 90));
  const proj90 = Math.max(0, Math.round(myRating() + change));
  const trend = perDay > 0.3 ? "상승세" : perDay < -0.3 ? "하락세" : "안정적";
  const arrow = perDay > 0.3 ? "📈" : perDay < -0.3 ? "📉" : "➖";
  el.innerHTML =
    `<div class="grproj">${arrow} 최근 추세는 <b>${trend}</b>입니다.<br>` +
    `지금처럼 계속하면 <b>3개월 뒤 약 ${ratingHTML(proj90)}</b> 정도가 예상돼요.</div>`;
}

// =========================================================================== //
// SETTINGS modal
// =========================================================================== //
function rerenderBoards() {
  if (AIG.state) renderAiBoard();
  if (OG.state) renderOgBoard();
  if (PZ.fen) renderPzBoard();
}
$("settingsBtn").onclick = () => {
  $("setShowDots").checked = SETTINGS.showDots;
  $("settingsModal").classList.remove("hidden");
};
$("settingsClose").onclick = () => $("settingsModal").classList.add("hidden");
$("settingsModal").onclick = (e) => { if (e.target === $("settingsModal")) $("settingsModal").classList.add("hidden"); };
$("setShowDots").onchange = (e) => {
  SETTINGS.showDots = e.target.checked;
  localStorage.setItem("cc_showdots", SETTINGS.showDots ? "1" : "0");
  rerenderBoards();
};

// boot
aiBoot();
authBoot();
loadLeaderboard();

// =========================================================================== //
// HOME DASHBOARD — packed stats strip + sidebar profile widget (v23).
// All values come from existing local state (rating, history, best level,
// solved puzzles); rendered on load, on tab switch, and on rating changes.
// =========================================================================== //
function renderHomeStats() {
  const el = document.getElementById("homeStats");
  if (!el) return;
  const hist = (typeof gameHistory === "function") ? gameHistory() : [];
  const wins = hist.filter((g) => g.result === "win").length;
  const losses = hist.filter((g) => g.result === "loss").length;
  const wr = (wins + losses) ? Math.round(wins / (wins + losses) * 100) : 0;
  const solved = (typeof PZ !== "undefined" && PZ.solved) ? PZ.solved.size : 0;
  const logged = !!(typeof AUTH !== "undefined" && AUTH.token);
  const T = (typeof t === "function") ? t : ((k) => k);
  const tiles = [
    { ic: "⭐", k: T("stat_rating"), v: logged ? ratingHTML(myRating()) : "—" },
    { ic: "🤖", k: T("stat_best"), v: (bestLevel() || "-") },
    { ic: "🧩", k: T("stat_puzzles"), v: solved + "<span style='font-size:13px;color:var(--muted)'>/100</span>" },
    { ic: "📈", k: T("stat_winrate"), v: wr + "<span style='font-size:13px;color:var(--muted)'>%</span>" },
    { ic: "♟", k: T("stat_games"), v: hist.length },
  ];
  el.innerHTML = tiles.map((t) =>
    `<div class="stat"><div class="ic">${t.ic}</div><div class="k">${t.k}</div><div class="v">${t.v}</div></div>`
  ).join("");
}

function renderSidebarProfile() {
  const el = document.getElementById("sideProfile");
  if (!el) return;
  const T = (typeof t === "function") ? t : ((k) => k);
  const logged = !!(typeof AUTH !== "undefined" && AUTH.token);
  const name = (logged && AUTH.id) ? AUTH.id : T("sp_guest");
  const solved = (typeof PZ !== "undefined" && PZ.solved) ? PZ.solved.size : 0;
  el.innerHTML =
    `<div class="sp-top">` +
      `<div class="sp-ava">${escapeHtml(name.charAt(0).toUpperCase())}</div>` +
      `<div style="min-width:0"><div class="sp-name">${escapeHtml(name)}</div>` +
      `<div class="sp-sub">${logged ? ratingHTML(myRating()) : T("sp_notlogged")}</div></div>` +
    `</div>` +
    `<div class="sp-stats">` +
      `<div class="sp-stat"><b>${bestLevel() || "-"}</b><span>${T("sp_best")}</span></div>` +
      `<div class="sp-stat"><b>${solved}</b><span>${T("sp_puzzles")}</span></div>` +
    `</div>`;
}

function refreshDashboard() {
  try {
    renderHomeStats(); renderSidebarProfile();
    if (typeof updateRankBadge === "function") updateRankBadge();
    const ll = document.getElementById("aiLevelLabel"), lv = document.getElementById("aiLevel");
    if (ll && lv && typeof aiLevelText === "function") ll.textContent = aiLevelText(lv.value);
  } catch (e) {}
}
refreshDashboard();

// Apply the saved language now that all renderers exist (translates static
// [data-i18n] text and re-renders the dynamic dashboard in the chosen tongue).
if (typeof applyLang === "function") applyLang(typeof CC_LANG !== "undefined" ? CC_LANG : "ko");
