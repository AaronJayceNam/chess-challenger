// =========================================================================== //
// i18n.js — language switching for the app chrome (nav, screen titles, home
// stats, sidebar, settings, primary controls). Loaded BEFORE app.js so the
// global t()/CC_LANG are available to the app's renderers.
//
// Static text is translated by tagging elements with data-i18n="key" (their
// textContent is replaced) or data-i18n-ph="key" (placeholder). Dynamic text
// built in JS calls t("key"). Adding a language = add its code to LANGS and a
// value under each key below.
// =========================================================================== //
var LANGS = ["ko", "en", "ja", "zh", "es"];
var CC_LANG = (function () { try { return localStorage.getItem("cc_lang") || "ko"; } catch (e) { return "ko"; } })();
if (LANGS.indexOf(CC_LANG) < 0) CC_LANG = "ko";

var I18N = {
  // ----- sidebar navigation -----
  nav_ai:     { ko: "AI 대국", en: "vs Computer", ja: "AI対局", zh: "人机对弈", es: "vs. IA" },
  nav_online: { ko: "온라인 대국", en: "Online", ja: "オンライン対局", zh: "在线对弈", es: "En línea" },
  nav_puzzle: { ko: "퍼즐", en: "Puzzles", ja: "パズル", zh: "谜题", es: "Puzzles" },
  nav_learn:  { ko: "체스 배우기", en: "Learn", ja: "チェスを学ぶ", zh: "学习", es: "Aprender" },
  nav_growth: { ko: "성장", en: "Progress", ja: "成長", zh: "成长", es: "Progreso" },
  nav_review: { ko: "리뷰", en: "Review", ja: "レビュー", zh: "复盘", es: "Análisis" },
  // ----- bottom nav (short) -----
  navs_ai:     { ko: "AI", en: "AI", ja: "AI", zh: "人机", es: "IA" },
  navs_online: { ko: "온라인", en: "Online", ja: "対戦", zh: "在线", es: "Online" },
  navs_puzzle: { ko: "퍼즐", en: "Puzzle", ja: "パズル", zh: "谜题", es: "Puzzle" },
  navs_growth: { ko: "성장", en: "Progress", ja: "成長", zh: "成长", es: "Nivel" },
  navs_learn:  { ko: "배우기", en: "Learn", ja: "学ぶ", zh: "学习", es: "Aprender" },
  navs_review: { ko: "리뷰", en: "Review", ja: "レビュー", zh: "复盘", es: "Análisis" },
  // ----- heros -----
  hero_ai_t: { ko: "AI와 대국", en: "Play the Computer", ja: "AIと対局", zh: "与电脑对弈", es: "Juega contra la IA" },
  hero_ai_p: {
    ko: "난이도 1~15, 유명 선수 스타일까지 — 스톡피시 엔진과 겨뤄보세요. 대국이 끝나면 자동으로 AI가 복기해줍니다.",
    en: "Levels 1–15 plus famous-player styles — take on the Stockfish engine. When the game ends, the AI reviews every move automatically.",
    ja: "レベル1〜15、名選手のスタイルまで — Stockfishエンジンと対戦。対局後はAIが自動で振り返ります。",
    zh: "1–15 级，还有名家风格——挑战 Stockfish 引擎。对局结束后 AI 会自动复盘每一步。",
    es: "Niveles 1–15 y estilos de grandes maestros: enfréntate al motor Stockfish. Al terminar, la IA analiza cada jugada.",
  },
  hero_online_t: { ko: "온라인 대국", en: "Online Games", ja: "オンライン対局", zh: "在线对弈", es: "Partidas en línea" },
  hero_online_p: {
    ko: "전 세계 플레이어와 실시간 레이팅 대국. 10분 대국 · 초대 코드로 친구와도.",
    en: "Real-time rated games with players worldwide. 10-minute games · play friends with an invite code.",
    ja: "世界中のプレイヤーとリアルタイムのレート対局。10分切れ負け・招待コードで友達とも。",
    zh: "与全球玩家进行实时等级分对局。10 分钟对局 · 用邀请码和好友对战。",
    es: "Partidas clasificatorias en tiempo real con jugadores de todo el mundo. 10 min · juega con amigos por código.",
  },
  hero_puzzle_t: { ko: "체크메이트 퍼즐", en: "Checkmate Puzzles", ja: "チェックメイトパズル", zh: "将杀谜题", es: "Puzzles de mate" },
  hero_puzzle_p: {
    ko: "1수부터 4수까지 100개. 정해진 수 안에 체크메이트를 완성하세요.",
    en: "100 puzzles, mate in 1 to 4. Deliver checkmate within the given number of moves.",
    ja: "1手詰から4手詰まで100問。指定手数以内にチェックメイトを決めましょう。",
    zh: "从 1 步到 4 步共 100 题。在规定步数内完成将杀。",
    es: "100 puzzles, mate en 1 a 4. Da jaque mate en las jugadas indicadas.",
  },
  hero_learn_t: { ko: "체스 배우기", en: "Learn Chess", ja: "チェスを学ぶ", zh: "学习国际象棋", es: "Aprende ajedrez" },
  hero_learn_p: {
    ko: "기물별 움직임과 특수 규칙을 보드에서 직접 눌러보며 익히세요.",
    en: "Learn how each piece moves and the special rules by trying them on the board.",
    ja: "各駒の動きと特殊ルールを、盤上で実際に触れながら覚えましょう。",
    zh: "在棋盘上亲手尝试，掌握每种棋子的走法和特殊规则。",
    es: "Aprende cómo se mueve cada pieza y las reglas especiales probándolas en el tablero.",
  },
  hero_growth_t: { ko: "성장 리포트", en: "Progress Report", ja: "成長レポート", zh: "成长报告", es: "Informe de progreso" },
  hero_growth_p: {
    ko: "레이팅 추이·미래 예측·주간 목표로 실력이 어떻게 늘고 있는지 한눈에.",
    en: "See how you're improving at a glance — rating trend, forecast, and weekly goals.",
    ja: "レーティング推移・将来予測・週間目標で、上達の様子をひと目で。",
    zh: "通过等级分走势、未来预测和每周目标，一眼看清你的进步。",
    es: "Ve tu progreso de un vistazo: evolución del rating, previsión y metas semanales.",
  },
  // ----- home stats -----
  stat_rating:  { ko: "레이팅", en: "Rating", ja: "レート", zh: "等级分", es: "Rating" },
  stat_best:    { ko: "최고 레벨", en: "Best level", ja: "最高レベル", zh: "最高等级", es: "Mejor nivel" },
  stat_puzzles: { ko: "푼 퍼즐", en: "Puzzles", ja: "解いたパズル", zh: "已解谜题", es: "Puzzles" },
  stat_winrate: { ko: "승률", en: "Win rate", ja: "勝率", zh: "胜率", es: "Victorias" },
  stat_games:   { ko: "총 대국", en: "Games", ja: "総対局", zh: "总对局", es: "Partidas" },
  // ----- sidebar profile + tip -----
  sp_guest:     { ko: "게스트", en: "Guest", ja: "ゲスト", zh: "访客", es: "Invitado" },
  sp_notlogged: { ko: "로그인 전 · 게스트", en: "Not signed in · Guest", ja: "未ログイン・ゲスト", zh: "未登录 · 访客", es: "Sin sesión · Invitado" },
  sp_best:      { ko: "최고레벨", en: "Best lv", ja: "最高Lv", zh: "最高级", es: "Nivel máx" },
  sp_puzzles:   { ko: "푼 퍼즐", en: "Puzzles", ja: "パズル", zh: "谜题", es: "Puzzles" },
  tip_title: { ko: "💡 오늘의 팁", en: "💡 Tip of the day", ja: "💡 今日のヒント", zh: "💡 今日提示", es: "💡 Consejo del día" },
  tip_body: {
    ko: "기물을 잃지 않으려면 매 수마다 “상대가 나를 잡을 수 있나?”를 먼저 확인하세요.",
    en: "To avoid losing pieces, each move ask yourself first: “Can my opponent capture this?”",
    ja: "駒を失わないために、毎手「相手に取られないか?」をまず確認しましょう。",
    zh: "为了不丢子，每一步先想一想：“对手能吃我吗?”",
    es: "Para no perder piezas, en cada jugada pregúntate primero: «¿Puede capturarla el rival?»",
  },
  // ----- settings modal -----
  set_title:      { ko: "⚙️ 설정", en: "⚙️ Settings", ja: "⚙️ 設定", zh: "⚙️ 设置", es: "⚙️ Ajustes" },
  set_lang_label: { ko: "언어", en: "Language", ja: "言語", zh: "语言", es: "Idioma" },
  set_lang_desc:  { ko: "앱 화면의 표시 언어를 선택합니다.", en: "Choose the display language for the app.", ja: "アプリの表示言語を選びます。", zh: "选择应用界面的显示语言。", es: "Elige el idioma de la interfaz." },
  set_dots_label: { ko: "이동 가능 칸 표시", en: "Show move hints", ja: "移動可能マスを表示", zh: "显示可走格子", es: "Mostrar movimientos" },
  set_dots_desc:  { ko: "말을 선택·드래그할 때 갈 수 있는 칸에 회색 원을 표시합니다.", en: "Show grey dots on the squares a selected or dragged piece can move to.", ja: "駒を選択・ドラッグしたとき、移動できるマスに灰色の丸を表示します。", zh: "选中或拖动棋子时，在可走的格子上显示灰点。", es: "Muestra puntos grises en las casillas a las que puede ir la pieza seleccionada." },
  set_close:      { ko: "닫기", en: "Close", ja: "閉じる", zh: "关闭", es: "Cerrar" },
  // ----- primary controls / card titles (home) -----
  h_newgame:     { ko: "새 대국 설정", en: "New game setup", ja: "新規対局の設定", zh: "新对局设置", es: "Configurar partida" },
  h_moves:       { ko: "기보", en: "Moves", ja: "棋譜", zh: "棋谱", es: "Jugadas" },
  h_after:       { ko: "경기 종료 후", en: "After the game", ja: "対局終了後", zh: "对局结束后", es: "Tras la partida" },
  lbl_difficulty:{ ko: "난이도 — 1(왕초보) ~ 10(그랜드마스터)", en: "Difficulty — 1 (Novice) to 10 (Grandmaster)", ja: "難易度 — 1(超初心者)〜10(グランドマスター)", zh: "难度 — 1(新手)到 10(特级大师)", es: "Dificultad — 1 (Principiante) a 10 (Gran Maestro)" },
  word_level:    { ko: "레벨", en: "Level", ja: "レベル", zh: "等级", es: "Nivel" },
  word_cleared:  { ko: "클리어", en: "cleared", ja: "クリア", zh: "通关", es: "superado" },
  rank_none:     { ko: "아직 클리어한 레벨이 없습니다", en: "No level cleared yet", ja: "まだクリアしたレベルはありません", zh: "还没有通关任何等级", es: "Aún no has superado ningún nivel" },
  rank_best:     { ko: "내 최고 기록", en: "Best cleared", ja: "自己ベスト", zh: "最佳纪录", es: "Mejor marca" },
  // AI level titles (호칭)
  lvl_1:  { ko: "왕초보", en: "Novice", ja: "超初心者", zh: "新手", es: "Principiante" },
  lvl_2:  { ko: "초보", en: "Beginner", ja: "初心者", zh: "入门", es: "Aprendiz" },
  lvl_3:  { ko: "입문", en: "Rookie", ja: "見習い", zh: "初级", es: "Iniciado" },
  lvl_4:  { ko: "아마추어", en: "Amateur", ja: "アマチュア", zh: "业余", es: "Amateur" },
  lvl_5:  { ko: "중급", en: "Intermediate", ja: "中級者", zh: "中级", es: "Intermedio" },
  lvl_6:  { ko: "상급", en: "Advanced", ja: "上級者", zh: "高级", es: "Avanzado" },
  lvl_7:  { ko: "숙련자", en: "Skilled", ja: "熟練者", zh: "熟练", es: "Hábil" },
  lvl_8:  { ko: "전문가", en: "Expert", ja: "エキスパート", zh: "专家", es: "Experto" },
  lvl_9:  { ko: "마스터", en: "Master", ja: "マスター", zh: "大师", es: "Maestro" },
  lvl_10: { ko: "그랜드마스터", en: "Grandmaster", ja: "グランドマスター", zh: "特级大师", es: "Gran Maestro" },
  lbl_style:     { ko: "AI 스타일 (유명 선수처럼 두기)", en: "AI style (play like a famous player)", ja: "AIスタイル(名選手のように指す)", zh: "AI 风格(模仿名家)", es: "Estilo de IA (juega como un maestro)" },
  lbl_color:     { ko: "내 색", en: "My color", ja: "自分の色", zh: "我的执棋", es: "Mi color" },
  btn_newgame:   { ko: "▶ 새 대국 시작", en: "▶ New game", ja: "▶ 新しい対局", zh: "▶ 开始新对局", es: "▶ Nueva partida" },
  btn_resign_ai: { ko: "🏳️ 기권하고 평가받기", en: "🏳️ Resign & review", ja: "🏳️ 投了して評価", zh: "🏳️ 认输并复盘", es: "🏳️ Rendirse y analizar" },
  btn_flip:      { ko: "⇅ 보드 뒤집기", en: "⇅ Flip board", ja: "⇅ 盤を反転", zh: "⇅ 翻转棋盘", es: "⇅ Girar tablero" },
};

function t(key) {
  var d = I18N[key];
  if (!d) return key;
  return (d[CC_LANG] != null) ? d[CC_LANG] : d.ko;
}

function applyLang(lang) {
  if (LANGS.indexOf(lang) < 0) lang = "ko";
  CC_LANG = lang;
  try { localStorage.setItem("cc_lang", lang); } catch (e) {}
  document.documentElement.lang = lang;
  document.querySelectorAll("[data-i18n]").forEach(function (el) {
    var v = t(el.getAttribute("data-i18n"));
    if (v != null) el.textContent = v;
  });
  document.querySelectorAll("[data-i18n-ph]").forEach(function (el) {
    el.setAttribute("placeholder", t(el.getAttribute("data-i18n-ph")));
  });
  var sel = document.getElementById("setLang");
  if (sel) sel.value = lang;
  // re-render dynamic bits that build their own text via t()
  if (typeof refreshDashboard === "function") { try { refreshDashboard(); } catch (e) {} }
}

// wire the settings language selector (this script runs after the modal exists)
(function () {
  var s = document.getElementById("setLang");
  if (s) { s.value = CC_LANG; s.addEventListener("change", function (e) { applyLang(e.target.value); }); }
})();
