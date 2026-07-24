"""Render a GameAnalysis into a single self-contained HTML file.

No Node, no CDN, no internet: python-chess renders one SVG board per position
(with last-move highlight + engine best-move arrow), and a small amount of inline
JavaScript handles move navigation, the eval bar, the eval graph, and the
annotated move list. Open the file in any browser.
"""
from __future__ import annotations

import json

import chess
import chess.svg
import chess.pgn

from .analyze import GameAnalysis
from .explain import explain_move

BOARD_SIZE = 440

# classification -> colour (move list + detail panel)
_COLOR = {
    "Brilliant": "#1aa7a0",
    "Great": "#3f7fd6",
    "Best": "#2e7d32",
    "Excellent": "#2e7d32",
    "Good": "#9e9e9e",
    "Inaccuracy": "#c9a227",
    "Mistake": "#e07a1f",
    "Blunder": "#c62828",
}
_ARROW_BEST = "#15781b"   # green: engine's best move from the shown position


def _fmt_eval(cp, mate) -> str:
    if mate is not None:
        if mate == 0:
            return "#"
        return f"#{mate:+d}"
    if cp is None:
        return "—"
    return f"{cp/100:+.2f}"


def _build_svgs_and_series(game: chess.pgn.Game, ga: GameAnalysis):
    """Return (svgs, white_win, eval_labels) — one entry per displayed position.

    Index 0 is the starting position; index k is the position after ply k.
    """
    board = game.board()
    moves = list(game.mainline_moves())

    svgs = [chess.svg.board(board, size=BOARD_SIZE, coordinates=True)]

    # White-POV win% / eval label per position (for the bar + graph).
    m0 = ga.moves[0]
    w0 = m0.win_prob_before if m0.color == "white" else 100.0 - m0.win_prob_before
    white_win = [round(w0, 1)]
    eval_labels = ["start"]

    for k, mv in enumerate(moves):
        board.push(mv)

        arrows = []
        # Best move available to whoever is on move in THIS position = next ply's best.
        if k + 1 < len(ga.moves):
            bu = ga.moves[k + 1].best_move_uci
            if bu:
                arrows.append(chess.svg.Arrow(
                    chess.parse_square(bu[0:2]),
                    chess.parse_square(bu[2:4]),
                    color=_ARROW_BEST,
                ))
        svgs.append(chess.svg.board(
            board, size=BOARD_SIZE, lastmove=mv, arrows=arrows, coordinates=True,
        ))

        m = ga.moves[k]
        wa = m.win_prob_after if m.color == "white" else 100.0 - m.win_prob_after
        white_win.append(round(wa, 1))
        eval_labels.append(_fmt_eval(m.eval_cp, m.eval_mate))

    return svgs, white_win, eval_labels


def _movelist_html(ga: GameAnalysis) -> str:
    parts: list[str] = []
    for m in ga.moves:
        if m.color == "white":
            parts.append(f'<span class="num">{m.move_number}.</span>')
        color = _COLOR.get(m.classification, "#ddd")
        tip = (f"{m.classification}  |  CPL {m.cpl}  |  "
               f"win {m.win_prob_before:.0f}%→{m.win_prob_after:.0f}%")
        parts.append(
            f'<span class="mv" data-idx="{m.ply}" style="color:{color}" '
            f'title="{tip}">{m.san}{m.symbol}</span>'
        )
    return "\n".join(parts)


def build_view_data(game: chess.pgn.Game, ga: GameAnalysis) -> dict:
    """Everything the front-end needs to render an analysed game.

    Shared by the static HTML generator (`render_html`) and the web API, so the
    board/eval/movelist rendering is identical in both.
    """
    svgs, white_win, eval_labels = _build_svgs_and_series(game, ga)

    # Korean piece name → language-neutral code, so the client can build a
    # localized causal "why" (the Korean `explain` text is shown only to ko users).
    _K2C = {"폰": "pawn", "나이트": "knight", "비숍": "bishop", "룩": "rook", "퀸": "queen", "킹": "king"}
    moves_payload = [{
        "ply": m.ply,
        "moveNumber": m.move_number,
        "san": m.san,
        "uci": m.uci,
        "symbol": m.symbol,
        "color": m.color,
        "classification": m.classification,
        "cpl": m.cpl,
        "winBefore": m.win_prob_before,
        "winAfter": m.win_prob_after,
        "accuracy": m.accuracy,
        "best": m.best_move_san,
        "pv": m.pv,
        "isBest": m.is_best,
        "missedWin": m.missed_win,
        "explain": explain_move(m),
        "clsColor": _COLOR.get(m.classification, "#ddd"),
        # ---- language-neutral causal facts (for the localized "why" coach) ----
        "replySan": m.reply_san,
        "replyCapType": _K2C.get(m.reply_captures),
        "capturedType": _K2C.get(m.captured_piece),
        "movedType": _K2C.get(m.piece_moved),
        "bestIsCapture": m.best_is_capture,
        "isCapture": m.is_capture,
        "isCastle": m.is_castle,
        "givesCheck": m.gives_check,
        "develops": m.develops,
        "onlyMove": m.only_move,
        "isMate": m.is_mate,
    } for m in ga.moves]

    h = ga.headers
    eng = ga.engine
    budget = (f"depth {eng['depth']}" if eng.get("depth") and not eng.get("movetime_ms")
              else f"movetime {eng['movetime_ms']}ms")

    return {
        "title": f"{h.get('White','White')} vs {h.get('Black','Black')}",
        "sub": f"{h.get('Event','')} {h.get('Date','')}  •  {ga.result}".strip(),
        "opening": f"{h.get('ECO','')} {h.get('Opening','')}".strip(),
        "engLine": f"Stockfish • {budget} • threads {eng['threads']} • hash {eng['hash_mb']}MB",
        "result": ga.result,
        "white": {"accuracy": ga.white.accuracy, "acpl": ga.white.acpl,
                  "counts": ga.white.counts},
        "black": {"accuracy": ga.black.accuracy, "acpl": ga.black.acpl,
                  "counts": ga.black.counts},
        "svgs": svgs,
        "whiteWin": white_win,
        "evalLabels": eval_labels,
        "moves": moves_payload,
    }


def render_html(game: chess.pgn.Game, ga: GameAnalysis) -> str:
    view = build_view_data(game, ga)
    data = {k: view[k] for k in ("svgs", "whiteWin", "evalLabels", "moves")}
    summary = (
        f"<b>White</b> {view['white']['accuracy']:.1f}% (ACPL {view['white']['acpl']:.0f}) "
        f"&nbsp;·&nbsp; <b>Black</b> {view['black']['accuracy']:.1f}% "
        f"(ACPL {view['black']['acpl']:.0f})"
    )
    return _TEMPLATE.format(
        title=view["title"],
        sub=view["sub"],
        opening=view["opening"],
        eng_line=view["engLine"],
        summary=summary,
        movelist=_movelist_html(ga),
        board_size=BOARD_SIZE,
        data_json=json.dumps(data, ensure_ascii=False),
    )


_TEMPLATE = r"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title} — Matevio</title>
<style>
  :root {{ --bg:#1e1f22; --panel:#2b2d31; --ink:#e6e6e6; --muted:#9aa0a6; }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; background:var(--bg); color:var(--ink);
    font-family:'Segoe UI',system-ui,Arial,sans-serif; }}
  header {{ padding:14px 20px; border-bottom:1px solid #000; }}
  header h1 {{ font-size:18px; margin:0; }}
  header .meta {{ color:var(--muted); font-size:13px; margin-top:3px; }}
  header .summary {{ margin-top:6px; font-size:14px; }}
  .wrap {{ display:flex; gap:18px; padding:18px; align-items:flex-start;
    flex-wrap:wrap; }}
  .left {{ display:flex; gap:10px; }}
  .evalbar {{ width:18px; height:{board_size}px; background:#111; border-radius:4px;
    overflow:hidden; position:relative; border:1px solid #000; }}
  .evalbar .white {{ position:absolute; bottom:0; left:0; right:0; background:#e9e9e9;
    transition:height .15s ease; }}
  .evalbar .lbl {{ position:absolute; left:0; right:0; text-align:center; font-size:10px;
    color:#111; bottom:2px; font-weight:700; mix-blend-mode:difference; color:#fff; }}
  .board {{ width:{board_size}px; height:{board_size}px; }}
  .controls {{ margin-top:10px; display:flex; gap:6px; align-items:center; }}
  button {{ background:var(--panel); color:var(--ink); border:1px solid #000;
    border-radius:6px; padding:6px 11px; font-size:15px; cursor:pointer; }}
  button:hover {{ background:#3a3d43; }}
  input[type=range] {{ flex:1; }}
  .right {{ flex:1; min-width:320px; max-width:520px; }}
  .card {{ background:var(--panel); border-radius:8px; padding:12px 14px;
    margin-bottom:14px; }}
  .graph {{ width:100%; height:90px; display:block; cursor:pointer; }}
  .moves {{ line-height:2.0; font-size:15px; max-height:300px; overflow:auto; }}
  .moves .num {{ color:var(--muted); margin:0 4px 0 10px; }}
  .moves .mv {{ cursor:pointer; padding:1px 4px; border-radius:4px; }}
  .moves .mv:hover {{ background:#3a3d43; }}
  .moves .mv.active {{ background:#4b5563; color:#fff !important; }}
  .detail .tag {{ display:inline-block; padding:2px 9px; border-radius:10px;
    font-size:12px; font-weight:700; color:#111; }}
  .detail .row {{ margin-top:8px; font-size:14px; color:var(--muted); }}
  .detail .row b {{ color:var(--ink); }}
  .pv {{ font-family:'Consolas',monospace; color:#cbd5e1; }}
  .legend {{ font-size:12px; color:var(--muted); }}
  .legend span {{ margin-right:10px; }}
</style>
</head>
<body>
<header>
  <h1>{title}</h1>
  <div class="meta">{sub} &nbsp;·&nbsp; {opening} &nbsp;·&nbsp; {eng_line}</div>
  <div class="summary">{summary}</div>
</header>

<div class="wrap">
  <div>
    <div class="left">
      <div class="evalbar"><div class="white" id="ebar"></div><div class="lbl" id="elbl"></div></div>
      <div class="board" id="board"></div>
    </div>
    <div class="controls">
      <button id="bFirst" title="처음">⏮</button>
      <button id="bPrev"  title="이전 (←)">◀</button>
      <button id="bNext"  title="다음 (→)">▶</button>
      <button id="bLast"  title="끝">⏭</button>
      <input type="range" id="slider" min="0" value="0">
    </div>
    <div class="legend" style="margin-top:8px">
      <span style="color:#15781b">▮ 엔진 추천(녹색 화살표)</span>
      <span style="color:#2e7d32">● Best/Excellent</span>
      <span style="color:#c9a227">● Inaccuracy ?!</span>
      <span style="color:#e07a1f">● Mistake ?</span>
      <span style="color:#c62828">● Blunder ??</span>
    </div>
  </div>

  <div class="right">
    <div class="card">
      <svg class="graph" id="graph" preserveAspectRatio="none"></svg>
    </div>
    <div class="card detail" id="detail"></div>
    <div class="card">
      <div class="moves" id="moves">{movelist}</div>
    </div>
  </div>
</div>

<script id="data" type="application/json">{data_json}</script>
<script>
const DATA = JSON.parse(document.getElementById('data').textContent);
const N = DATA.svgs.length - 1;          // number of plies
let idx = 0;                              // 0..N  (0 = start position)

const board = document.getElementById('board');
const ebar  = document.getElementById('ebar');
const elbl  = document.getElementById('elbl');
const slider= document.getElementById('slider');
const detail= document.getElementById('detail');
const graph = document.getElementById('graph');
slider.max = N;

function evalColor(cls) {{
  return ({{Best:'#2e7d32',Excellent:'#2e7d32',Good:'#9e9e9e',
    Inaccuracy:'#c9a227',Mistake:'#e07a1f',Blunder:'#c62828'}})[cls] || '#ddd';
}}

function renderDetail() {{
  if (idx === 0) {{
    detail.innerHTML = '<div class="row">시작 포지션입니다. ▶ 또는 → 키로 진행하세요.</div>';
    return;
  }}
  const m = DATA.moves[idx-1];
  const turn = m.color === 'white' ? '백' : '흑';
  const tag = m.isBest
    ? '<span class="tag" style="background:#2e7d32;color:#fff">Best</span>'
    : `<span class="tag" style="background:${{m.clsColor}}">${{m.classification}} ${{m.symbol}}</span>`;
  const missed = m.missedWin ? ' <b style="color:#c62828">· 승리 놓침</b>' : '';
  const bestRow = m.isBest ? '' :
    `<div class="row">엔진 최선: <b>${{m.best||'—'}}</b></div>`;
  detail.innerHTML =
    `<div><b style="font-size:16px">${{m.ply}}. ${{turn}} ${{m.san}}${{m.symbol}}</b> &nbsp; ${{tag}}${{missed}}</div>` +
    `<div class="row">CPL <b>${{m.cpl}}</b> · 승률 <b>${{m.winBefore.toFixed(0)}}%→${{m.winAfter.toFixed(0)}}%</b> · 정확도 <b>${{m.accuracy.toFixed(0)}}</b></div>` +
    bestRow +
    `<div class="row">주 변화(PV): <span class="pv">${{(m.pv||[]).slice(0,8).join(' ')}}</span></div>`;
}}

function renderGraph() {{
  const w = graph.clientWidth || 480, h = 90;
  graph.setAttribute('viewBox', `0 0 ${{w}} ${{h}}`);
  const ww = DATA.whiteWin;            // 0..100 per position (0..N)
  const xs = i => (N === 0 ? 0 : i / N * w);
  const ys = v => h - (v/100)*h;
  let pts = ww.map((v,i)=>`${{xs(i).toFixed(1)}},${{ys(v).toFixed(1)}}`).join(' ');
  let area = `0,${{h}} ` + pts + ` ${{w}},${{h}}`;
  const cx = xs(idx);
  graph.innerHTML =
    `<line x1="0" y1="${{h/2}}" x2="${{w}}" y2="${{h/2}}" stroke="#555" stroke-dasharray="3 3"/>` +
    `<polygon points="${{area}}" fill="#3b82f622"/>` +
    `<polyline points="${{pts}}" fill="none" stroke="#9ecbff" stroke-width="1.5"/>` +
    `<line x1="${{cx}}" y1="0" x2="${{cx}}" y2="${{h}}" stroke="#fff" stroke-width="1.5"/>`;
}}

function render() {{
  board.innerHTML = DATA.svgs[idx];
  const w = DATA.whiteWin[idx];
  ebar.style.height = w + '%';
  elbl.textContent = DATA.evalLabels[idx];
  slider.value = idx;
  document.querySelectorAll('.mv').forEach(el => {{
    el.classList.toggle('active', +el.dataset.idx === idx);
  }});
  const act = document.querySelector('.mv.active');
  if (act) act.scrollIntoView({{block:'nearest'}});
  renderDetail();
  renderGraph();
}}

function go(i) {{ idx = Math.max(0, Math.min(N, i)); render(); }}

document.getElementById('bFirst').onclick = () => go(0);
document.getElementById('bPrev').onclick  = () => go(idx-1);
document.getElementById('bNext').onclick  = () => go(idx+1);
document.getElementById('bLast').onclick  = () => go(N);
slider.oninput = e => go(+e.target.value);
document.getElementById('moves').addEventListener('click', e => {{
  const mv = e.target.closest('.mv'); if (mv) go(+mv.dataset.idx);
}});
graph.addEventListener('click', e => {{
  const r = graph.getBoundingClientRect();
  go(Math.round((e.clientX - r.left)/r.width * N));
}});
document.addEventListener('keydown', e => {{
  if (e.key === 'ArrowLeft')  {{ go(idx-1); e.preventDefault(); }}
  if (e.key === 'ArrowRight') {{ go(idx+1); e.preventDefault(); }}
  if (e.key === 'Home') go(0);
  if (e.key === 'End')  go(N);
}});
window.addEventListener('resize', renderGraph);

render();
</script>
</body>
</html>
"""


# =========================================================================== #
# Shareable "study": user-annotated line (no engine) with arrows/highlights and
# per-move explanations, baked into a single standalone HTML file.
# =========================================================================== #
_SHAPE_ARROW = "#e0413f"     # red arrow (teaching)
_SHAPE_CIRCLE = "#15781b66"  # translucent green square highlight


def _study_svg(board: chess.Board, lastmove, shape: dict) -> str:
    arrows = []
    for pair in (shape.get("arrows") or []):
        try:
            arrows.append(chess.svg.Arrow(
                chess.parse_square(pair[0]), chess.parse_square(pair[1]),
                color=_SHAPE_ARROW))
        except Exception:
            pass
    fill = {}
    for sq in (shape.get("circles") or []):
        try:
            fill[chess.parse_square(sq)] = _SHAPE_CIRCLE
        except Exception:
            pass
    return chess.svg.board(board, size=BOARD_SIZE, lastmove=lastmove,
                           arrows=arrows, fill=fill, coordinates=True)


def render_study_html(*, moves: list[str], comments: dict, shapes: dict,
                      white: str, black: str, title: str) -> str:
    board = chess.Board()
    items = [{
        "svg": _study_svg(board, None, shapes.get("0", {})),
        "comment": comments.get("0", ""),
        "label": "시작 포지션",
    }]
    replay = chess.Board()
    for k, u in enumerate(moves):
        mv = chess.Move.from_uci(u)
        san = replay.san(mv)
        replay.push(mv)
        board.push(mv)
        num = (k // 2) + 1
        label = f"{num}.{'' if k % 2 == 0 else '..'} {san}"
        items.append({
            "svg": _study_svg(board, mv, shapes.get(str(k + 1), {})),
            "comment": comments.get(str(k + 1), ""),
            "label": label,
        })

    data_json = json.dumps(items, ensure_ascii=False)
    return _STUDY_TEMPLATE.format(
        title=title or "Chess Study",
        white=white or "White",
        black=black or "Black",
        board_size=BOARD_SIZE,
        data_json=data_json,
    )


_STUDY_TEMPLATE = r"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
  :root {{ --bg:#1e1f22; --panel:#2b2d31; --ink:#e6e6e6; --muted:#9aa0a6; }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; background:var(--bg); color:var(--ink);
    font-family:'Segoe UI',system-ui,Arial,sans-serif; }}
  header {{ padding:14px 20px; border-bottom:1px solid #000; }}
  header h1 {{ font-size:18px; margin:0; }}
  header .meta {{ color:var(--muted); font-size:13px; margin-top:3px; }}
  .wrap {{ display:flex; gap:18px; padding:18px; align-items:flex-start; flex-wrap:wrap; }}
  .board {{ width:{board_size}px; height:{board_size}px; }}
  .controls {{ margin-top:10px; display:flex; gap:6px; align-items:center; }}
  button {{ background:var(--panel); color:var(--ink); border:1px solid #000;
    border-radius:6px; padding:6px 11px; font-size:15px; cursor:pointer; }}
  button:hover {{ background:#3a3d43; }}
  input[type=range] {{ flex:1; }}
  .right {{ flex:1; min-width:300px; max-width:480px; }}
  .card {{ background:var(--panel); border-radius:8px; padding:14px 16px; margin-bottom:14px; }}
  .label {{ font-size:16px; font-weight:700; margin-bottom:8px; }}
  .comment {{ font-size:15px; line-height:1.65; white-space:pre-wrap; }}
  .comment.empty {{ color:var(--muted); }}
  .moves {{ line-height:2.0; font-size:15px; max-height:260px; overflow:auto; }}
  .moves .num {{ color:var(--muted); margin:0 4px 0 8px; }}
  .moves .mv {{ cursor:pointer; padding:1px 4px; border-radius:4px; }}
  .moves .mv:hover {{ background:#3a3d43; }}
  .moves .mv.active {{ background:#4b5563; color:#fff; }}
  .moves .has {{ color:#7bd88f; }}
</style>
</head>
<body>
<header>
  <h1>{title}</h1>
  <div class="meta">{white} (백) vs {black} (흑) — 화살표·강조와 설명으로 보는 해설</div>
</header>
<div class="wrap">
  <div>
    <div class="board" id="board"></div>
    <div class="controls">
      <button id="bFirst">⏮</button><button id="bPrev">◀</button>
      <button id="bNext">▶</button><button id="bLast">⏭</button>
      <input type="range" id="slider" min="0" value="0">
    </div>
  </div>
  <div class="right">
    <div class="card">
      <div class="label" id="label"></div>
      <div class="comment" id="comment"></div>
    </div>
    <div class="card"><div class="moves" id="moves"></div></div>
  </div>
</div>
<script id="data" type="application/json">{data_json}</script>
<script>
const ITEMS = JSON.parse(document.getElementById('data').textContent);
const N = ITEMS.length - 1;
let idx = 0;
const board = document.getElementById('board'), slider = document.getElementById('slider');
const label = document.getElementById('label'), comment = document.getElementById('comment');
slider.max = N;

let html = '';
ITEMS.forEach((it, i) => {{
  if (i === 0) return;
  if (i % 2 === 1) html += `<span class="num">${{(i-1)/2+1}}.</span>`;
  const has = it.comment ? ' has' : '';
  const lab = it.label.replace(/^\d+\.(\.\.)?\s*/, '');
  html += `<span class="mv${{has}}" data-i="${{i}}">${{lab}}${{it.comment?' 💬':''}}</span> `;
}});
document.getElementById('moves').innerHTML = html;
document.getElementById('moves').addEventListener('click', e => {{
  const m = e.target.closest('.mv'); if (m) go(+m.dataset.i);
}});

function render() {{
  const it = ITEMS[idx];
  board.innerHTML = it.svg;
  label.textContent = it.label;
  comment.textContent = it.comment || '(이 수에는 설명이 없습니다)';
  comment.className = 'comment' + (it.comment ? '' : ' empty');
  slider.value = idx;
  document.querySelectorAll('.mv').forEach(el =>
    el.classList.toggle('active', +el.dataset.i === idx));
  const a = document.querySelector('.mv.active'); if (a) a.scrollIntoView({{block:'nearest'}});
}}
function go(i) {{ idx = Math.max(0, Math.min(N, i)); render(); }}
document.getElementById('bFirst').onclick = () => go(0);
document.getElementById('bPrev').onclick = () => go(idx-1);
document.getElementById('bNext').onclick = () => go(idx+1);
document.getElementById('bLast').onclick = () => go(N);
slider.oninput = e => go(+e.target.value);
document.addEventListener('keydown', e => {{
  if (e.key === 'ArrowLeft') {{ go(idx-1); e.preventDefault(); }}
  if (e.key === 'ArrowRight') {{ go(idx+1); e.preventDefault(); }}
}});
render();
</script>
</body>
</html>
"""
