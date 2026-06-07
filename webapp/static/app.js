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

function overlay(show, msg) {
  $("overlay").classList.toggle("hidden", !show);
  if (msg) $("overlayMsg").textContent = msg;
}

// --------------------------------------------------------------------------- //
// tabs
// --------------------------------------------------------------------------- //
document.querySelectorAll(".tabs button[data-tab]").forEach((b) => {
  b.onclick = () => switchTab(b.dataset.tab);
});
function switchTab(name) {
  document.querySelectorAll(".tabs button[data-tab]").forEach((b) =>
    b.classList.toggle("active", b.dataset.tab === name));
  document.querySelectorAll(".tab").forEach((t) =>
    t.classList.toggle("active", t.id === "tab-" + name));
}

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
// RECORD MODE
// =========================================================================== //
const REC = { moves: [], state: null, sel: null, orient: "w" };

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

function renderRecBoard() {
  const board = $("recBoard");
  board.innerHTML = "";
  if (!REC.state) return;
  const map = parseFen(REC.state.fen);
  const files = REC.orient === "w" ? [..."abcdefgh"] : [..."hgfedcba"];
  const ranks = REC.orient === "w" ? [8, 7, 6, 5, 4, 3, 2, 1] : [1, 2, 3, 4, 5, 6, 7, 8];
  const lastUci = REC.moves.length ? REC.moves[REC.moves.length - 1] : null;
  const lastFrom = lastUci ? lastUci.slice(0, 2) : null;
  const lastTo = lastUci ? lastUci.slice(2, 4) : null;
  const kingChar = REC.state.turn === "w" ? "K" : "k";
  let kingSq = null;
  for (const sq in map) if (map[sq] === kingChar) kingSq = sq;
  const legal = REC.state.legal || {};

  for (const rank of ranks) {
    for (const f of files) {
      const sq = f + rank;
      const fi = "abcdefgh".indexOf(f);
      const light = (fi + rank) % 2 === 0;
      const div = document.createElement("div");
      div.className = "sq " + (light ? "light" : "dark");
      if (sq === lastFrom || sq === lastTo) div.classList.add("last");
      if (REC.sel === sq) div.classList.add("sel");
      if (REC.state.check && sq === kingSq) div.classList.add("check");
      div.dataset.sq = sq;

      const p = map[sq];
      if (p) {
        const span = document.createElement("span");
        span.className = "pc " + (p === p.toUpperCase() ? "w" : "b");
        span.textContent = GLYPH[p.toLowerCase()];
        div.appendChild(span);
      }
      // legal-move dot
      if (REC.sel && legal[REC.sel] && legal[REC.sel].includes(sq)) {
        const dot = document.createElement("div");
        dot.className = "dot" + (map[sq] ? " cap" : "");
        div.appendChild(dot);
      }
      div.onclick = () => onRecClick(sq);
      board.appendChild(div);
    }
  }
}

function onRecClick(sq) {
  if (REC.state.gameOver) return;
  const map = parseFen(REC.state.fen);
  const legal = REC.state.legal || {};
  if (REC.sel) {
    if (legal[REC.sel] && legal[REC.sel].includes(sq)) {
      tryMove(REC.sel, sq, map[REC.sel]);
      return;
    }
    if (legal[sq]) { REC.sel = sq; renderRecBoard(); return; }
    REC.sel = null; renderRecBoard(); return;
  }
  if (legal[sq]) { REC.sel = sq; renderRecBoard(); }
}

function tryMove(from, to, pieceChar) {
  const toRank = +to[1];
  const isPawn = pieceChar && pieceChar.toLowerCase() === "p";
  if (isPawn && (toRank === 8 || toRank === 1)) {
    showPromo(from, to, pieceChar === "P");
  } else {
    commitMove(from + to);
  }
}

function showPromo(from, to, isWhite) {
  closePromo();
  const picker = document.createElement("div");
  picker.className = "promo";
  picker.id = "promoPicker";
  ["q", "r", "b", "n"].forEach((p) => {
    const d = document.createElement("div");
    d.className = "pc " + (isWhite ? "w" : "b");
    d.textContent = GLYPH[p];
    d.style.color = isWhite ? "#111" : "#111";
    d.onclick = () => { closePromo(); commitMove(from + to + p); };
    picker.appendChild(d);
  });
  // center over the board
  const wrap = $("recBoard").getBoundingClientRect();
  picker.style.left = (wrap.left + wrap.width / 2 - 30) + "px";
  picker.style.top = (wrap.top + wrap.height / 2 - 80) + "px";
  document.body.appendChild(picker);
}
function closePromo() { const p = $("promoPicker"); if (p) p.remove(); }

async function commitMove(uci) {
  const next = [...REC.moves, uci];
  try {
    const st = await api("/api/legal", { moves: next });
    REC.moves = next; REC.state = st; REC.sel = null;
    renderRecBoard(); renderRecMoves(st.san); updateTurn();
  } catch (e) { setStatus("recStatus", "수 처리 오류: " + e.message, true); }
}

function renderRecMoves(san) {
  const el = $("recMoves");
  if (!san || !san.length) {
    el.innerHTML = '<span class="num">아직 둔 수가 없습니다. 보드에서 수를 두세요.</span>';
    return;
  }
  let html = "";
  san.forEach((s, i) => {
    if (i % 2 === 0) html += `<span class="num">${i / 2 + 1}.</span>`;
    html += `<span class="mv">${s}</span> `;
  });
  el.innerHTML = html;
  el.scrollTop = el.scrollHeight;
}

function updateTurn() {
  const t = $("recTurn");
  if (REC.state.gameOver) {
    t.innerHTML = `<b>대국 종료 — 결과 ${REC.state.result}</b>`;
    return;
  }
  const w = REC.state.turn === "w";
  t.innerHTML = `<span class="pill ${w ? "" : "b"}"></span>${w ? "백(White)" : "흑(Black)"} 차례` +
    (REC.state.check ? "  · <b style='color:#ff8a80'>체크!</b>" : "");
}

async function recInit() {
  const st = await api("/api/legal", { moves: [] });
  REC.moves = []; REC.state = st; REC.sel = null;
  renderRecBoard(); renderRecMoves([]); updateTurn();
}
$("recUndo").onclick = async () => {
  if (!REC.moves.length) return;
  const next = REC.moves.slice(0, -1);
  const st = await api("/api/legal", { moves: next });
  REC.moves = next; REC.state = st; REC.sel = null;
  renderRecBoard(); renderRecMoves(st.san); updateTurn();
};
$("recReset").onclick = recInit;
$("recFlip").onclick = () => { REC.orient = REC.orient === "w" ? "b" : "w"; renderRecBoard(); };

$("recAnalyze").onclick = async () => {
  if (!REC.moves.length) { setStatus("recStatus", "먼저 수를 두세요.", true); return; }
  await runAnalyze({
    moves: REC.moves,
    white: $("recWhite").value || "White",
    black: $("recBlack").value || "Black",
    depth: +$("recDepth").value,
  });
};

// =========================================================================== //
// UPLOAD MODE
// =========================================================================== //
const SAMPLE_PGN = `[Event "Paris"]
[White "Paul Morphy"]
[Black "Duke Karl / Count Isouard"]
[Result "1-0"]
[ECO "C41"]
[Opening "Philidor Defense"]

1. e4 e5 2. Nf3 d6 3. d4 Bg4 4. dxe5 Bxf3 5. Qxf3 dxe5 6. Bc4 Nf6 7. Qb3 Qe7
8. Nc3 c6 9. Bg5 b5 10. Nxb5 cxb5 11. Bxb5+ Nbd7 12. O-O-O Rd8 13. Rxd7 Rxd7
14. Rd1 Qe6 15. Bxd7+ Nxd7 16. Qb8+ Nxb8 17. Rd8# 1-0`;

$("pgnFile").onchange = (e) => {
  const f = e.target.files[0]; if (!f) return;
  const r = new FileReader();
  r.onload = () => { $("pgnText").value = r.result; };
  r.readAsText(f);
};
$("upSample").onclick = () => { $("pgnText").value = SAMPLE_PGN; setStatus("upStatus", "샘플 게임을 불러왔습니다. 평가하기를 누르세요."); };
$("upAnalyze").onclick = async () => {
  const pgn = $("pgnText").value.trim();
  if (!pgn) { setStatus("upStatus", "PGN을 붙여넣거나 파일을 선택하세요.", true); return; }
  await runAnalyze({ pgn, depth: +$("upDepth").value });
};

function setStatus(id, msg, err) {
  const el = $(id);
  el.textContent = msg || "";
  el.className = "status" + (err ? " err" : "");
}

// =========================================================================== //
// ANALYZE -> REVIEW
// =========================================================================== //
let LAST_REQ = null;

async function runAnalyze(req) {
  LAST_REQ = req;
  overlay(true, "엔진이 둔 수를 평가 중입니다…");
  try {
    const view = await api("/api/analyze", req);
    loadReview(view);
    switchTab("review");
  } catch (e) {
    overlay(false);
    const id = req.pgn ? "upStatus" : "recStatus";
    setStatus(id, "분석 실패: " + e.message, true);
    return;
  }
  overlay(false);
}

const RV = { view: null, idx: 0, N: 0 };

function clsColor(c) {
  return ({ Best: "#2e7d32", Excellent: "#2e7d32", Good: "#9e9e9e",
    Inaccuracy: "#c9a227", Mistake: "#e07a1f", Blunder: "#c62828" })[c] || "#ddd";
}

function loadReview(view) {
  RV.view = view; RV.N = view.svgs.length - 1; RV.idx = 0;
  $("tabReview").disabled = false;

  $("rvSummary").innerHTML =
    `<b>${view.title}</b> &nbsp; <span style="color:#9aa0a6">${view.opening || ""} · ${view.engLine}</span><br>` +
    `정확도 — <b>백 ${view.white.accuracy.toFixed(1)}%</b> (ACPL ${view.white.acpl.toFixed(0)}) ` +
    `&nbsp;·&nbsp; <b>흑 ${view.black.accuracy.toFixed(1)}%</b> (ACPL ${view.black.acpl.toFixed(0)})`;

  // movelist
  let html = "";
  view.moves.forEach((m) => {
    if (m.color === "white") html += `<span class="num">${m.moveNumber}.</span>`;
    html += `<span class="mv" data-idx="${m.ply}" style="color:${m.clsColor}" ` +
      `title="${m.classification} | CPL ${m.cpl} | 승률 ${m.winBefore.toFixed(0)}%→${m.winAfter.toFixed(0)}%">` +
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
    ? '<span class="tag" style="background:#2e7d32;color:#fff">Best</span>'
    : `<span class="tag" style="background:${m.clsColor}">${m.classification} ${m.symbol}</span>`;
  const missed = m.missedWin ? ' <b style="color:#c62828">· 승리 놓침</b>' : "";
  const bestRow = m.isBest ? "" : `<div class="r">엔진 최선: <b>${m.best || "—"}</b></div>`;
  $("rvDetail").innerHTML =
    `<div><b style="font-size:16px">${m.moveNumber}${m.color === "white" ? "." : "..."} ${turn} ${m.san}${m.symbol}</b> &nbsp; ${tag}${missed}</div>` +
    `<div class="r">CPL <b>${m.cpl}</b> · 승률 <b>${m.winBefore.toFixed(0)}%→${m.winAfter.toFixed(0)}%</b> · 정확도 <b>${m.accuracy.toFixed(0)}</b></div>` +
    bestRow +
    `<div class="r">주 변화(PV): <span class="pv">${(m.pv || []).slice(0, 8).join(" ")}</span></div>`;
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
  const act = document.querySelector("#rvMoves .mv.active");
  if (act) act.scrollIntoView({ block: "nearest" });
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

// ---- export annotated PGN ----
$("rvExport").onclick = () => {
  const v = RV.view;
  const [white, black] = (v.title || "White vs Black").split(" vs ");
  let txt = `[Event "Chess Coach Studio"]\n[White "${white || "White"}"]\n[Black "${black || "Black"}"]\n[Result "${v.result}"]\n\n`;
  let body = "";
  v.moves.forEach((m) => {
    if (m.color === "white") body += `${m.moveNumber}. `;
    body += `${m.san}${m.symbol} `;
    if (!m.isBest && m.best) body += `{ ${m.classification}, CPL ${m.cpl}, 최선 ${m.best} } `;
  });
  txt += body + v.result + "\n";
  const blob = new Blob([txt], { type: "application/x-chess-pgn" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = "annotated.pgn";
  a.click();
};

// boot
recInit().catch((e) => setStatus("recStatus", "초기화 오류: " + e.message, true));
