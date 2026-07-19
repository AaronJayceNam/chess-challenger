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
  navs_growth: { ko: "성장", en: "Progress", ja: "成長", zh: "成长", es: "Progreso" },
  navs_learn:  { ko: "배우기", en: "Learn", ja: "学ぶ", zh: "学习", es: "Aprender" },
  navs_review: { ko: "리뷰", en: "Review", ja: "レビュー", zh: "复盘", es: "Análisis" },
  // ----- heros -----
  hero_ai_t: { ko: "AI와 대국", en: "Play the Computer", ja: "AIと対局", zh: "与电脑对弈", es: "Juega contra la IA" },
  hero_ai_p: {
    ko: "난이도 1~10, 유명 선수 스타일까지 — 스톡피시 엔진과 겨뤄보세요. 대국이 끝나면 AI 복기도 볼 수 있어요.",
    en: "Levels 1–10 plus famous-player styles — take on the Stockfish engine. After the game you can get an AI review of every move.",
    ja: "レベル1〜10、名選手のスタイルまで — Stockfishエンジンと対戦。対局後はAIのレビューも見られます。",
    zh: "1–10 级，还有名家风格——挑战 Stockfish 引擎。对局结束后还可查看 AI 复盘。",
    es: "Niveles 1–10 y estilos de grandes maestros: enfréntate al motor Stockfish. Al terminar, puedes ver el análisis de la IA de cada jugada.",
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
  set_sound_label:{ ko: "효과음", en: "Sound effects", ja: "効果音", zh: "音效", es: "Efectos de sonido" },
  set_sound_desc: { ko: "수를 두거나 잡을 때, 체크·승패 시 소리를 재생합니다.", en: "Play sounds on moves, captures, checks, and results.", ja: "着手・駒取り・チェック・勝敗時に音を鳴らします。", zh: "在走子、吃子、将军和胜负时播放声音。", es: "Reproduce sonidos al mover, capturar, dar jaque y al terminar." },
  set_coords_label:{ ko: "보드 좌표 표시", en: "Board coordinates", ja: "盤の座標", zh: "棋盘坐标", es: "Coordenadas" },
  set_coords_desc:{ ko: "보드에 a–h, 1–8 좌표를 표시합니다.", en: "Show a–h and 1–8 labels on the board.", ja: "盤に a–h・1–8 の座標を表示します。", zh: "在棋盘上显示 a–h、1–8 坐标。", es: "Muestra las coordenadas a–h y 1–8 en el tablero." },
  set_board_label:{ ko: "체스판 스타일", en: "Board style", ja: "盤のスタイル", zh: "棋盘样式", es: "Estilo del tablero" },
  set_board_desc: { ko: "보드의 색 테마를 선택합니다.", en: "Choose the board color theme.", ja: "盤の色テーマを選びます。", zh: "选择棋盘配色主题。", es: "Elige el tema de color del tablero." },
  board_green: { ko: "그린", en: "Green", ja: "グリーン", zh: "绿色", es: "Verde" },
  board_wood:  { ko: "우드", en: "Wood", ja: "ウッド", zh: "木纹", es: "Madera" },
  board_blue:  { ko: "블루", en: "Blue", ja: "ブルー", zh: "蓝色", es: "Azul" },
  board_gray:  { ko: "그레이", en: "Gray", ja: "グレー", zh: "灰色", es: "Gris" },
  board_coral: { ko: "산호", en: "Coral", ja: "コーラル", zh: "珊瑚", es: "Coral" },
  set_privacy:    { ko: "개인정보 처리방침", en: "Privacy Policy", ja: "プライバシーポリシー", zh: "隐私政策", es: "Política de privacidad" },
  sync_btn:       { ko: "🔄 동기화 · 최신으로 새로고침", en: "🔄 Sync & update", ja: "🔄 同期して最新に更新", zh: "🔄 同步并更新", es: "🔄 Sincronizar y actualizar" },
  sync_desc:      { ko: "진행상황을 계정에 저장하고, 앱을 최신 버전으로 새로고침합니다.", en: "Saves your progress to your account and reloads the app to the latest version.", ja: "進行状況をアカウントに保存し、アプリを最新版に更新します。", zh: "将进度保存到账号，并把应用刷新到最新版本。", es: "Guarda tu progreso en tu cuenta y actualiza la app a la última versión." },
  sync_running:   { ko: "동기화 중…", en: "Syncing…", ja: "同期中…", zh: "同步中…", es: "Sincronizando…" },
  update_avail:   { ko: "새 버전이 있어요.", en: "A new version is available.", ja: "新しいバージョンがあります。", zh: "有新版本可用。", es: "Hay una nueva versión disponible." },
  update_btn:     { ko: "🔄 업데이트", en: "🔄 Update", ja: "🔄 更新", zh: "🔄 更新", es: "🔄 Actualizar" },
  // ----- primary controls / card titles (home) -----
  h_newgame:     { ko: "새 대국 설정", en: "New game setup", ja: "新規対局の設定", zh: "新对局设置", es: "Configurar partida" },
  h_moves:       { ko: "기보", en: "Moves", ja: "棋譜", zh: "棋谱", es: "Jugadas" },
  h_after:       { ko: "경기 종료 후", en: "After the game", ja: "対局終了後", zh: "对局结束后", es: "Tras la partida" },
  lbl_difficulty:{ ko: "난이도 — 1(왕초보) ~ 10(그랜드마스터)", en: "Difficulty — 1 (Novice) to 10 (Grandmaster)", ja: "難易度 — 1(超初心者)〜10(グランドマスター)", zh: "难度 — 1(新手)到 10(特级大师)", es: "Dificultad — 1 (Principiante) a 10 (Gran Maestro)" },
  word_level:    { ko: "레벨", en: "Level", ja: "レベル", zh: "等级", es: "Nivel" },
  word_cleared:  { ko: "클리어", en: "cleared", ja: "クリア", zh: "通关", es: "superado" },
  rank_none:     { ko: "아직 클리어한 레벨이 없습니다", en: "No level cleared yet", ja: "まだクリアしたレベルはありません", zh: "还没有通关任何等级", es: "Aún no has superado ningún nivel" },
  rank_best:     { ko: "내 최고 기록", en: "Best cleared", ja: "自己ベスト", zh: "最佳纪录", es: "Mejor marca" },
  // AI level titles (호칭) — aligned to the target-rating ladder
  lvl_1:  { ko: "왕초보", en: "Novice", ja: "超初心者", zh: "新手", es: "Principiante" },
  lvl_2:  { ko: "중수", en: "Beginner", ja: "初級者", zh: "入门", es: "Aprendiz" },
  lvl_3:  { ko: "아마추어", en: "Amateur", ja: "アマチュア", zh: "业余", es: "Aficionado" },
  lvl_4:  { ko: "전술가", en: "Tactician", ja: "戦術家", zh: "战术家", es: "Táctico" },
  lvl_5:  { ko: "클럽 플레이어", en: "Club player", ja: "クラブ級", zh: "俱乐部级", es: "Jugador de club" },
  lvl_6:  { ko: "상급자", en: "Advanced", ja: "上級者", zh: "高级", es: "Avanzado" },
  lvl_7:  { ko: "토너먼트 플레이어", en: "Tournament", ja: "トーナメント級", zh: "锦标赛级", es: "De torneo" },
  lvl_8:  { ko: "전문가", en: "Expert", ja: "エキスパート", zh: "专家", es: "Experto" },
  lvl_9:  { ko: "마스터", en: "Master", ja: "マスター", zh: "大师", es: "Maestro" },
  lvl_10: { ko: "그랜드마스터", en: "Grandmaster", ja: "グランドマスター", zh: "特级大师", es: "Gran Maestro" },
  // game records window + full-screen exit
  hist_title:  { ko: "📋 게임 기록", en: "📋 Game records", ja: "📋 対局履歴", zh: "📋 对局记录", es: "📋 Historial" },
  hist_empty:  { ko: "아직 기록된 대국이 없습니다.", en: "No games recorded yet.", ja: "まだ記録された対局はありません。", zh: "还没有对局记录。", es: "Aún no hay partidas registradas." },
  hist_review: { ko: "🔍 리뷰", en: "🔍 Review", ja: "🔍 レビュー", zh: "🔍 复盘", es: "🔍 Analizar" },
  hist_norec:  { ko: "기보 없음", en: "No moves", ja: "棋譜なし", zh: "无棋谱", es: "Sin registro" },
  exit_btn:    { ko: "🚪 나가기", en: "🚪 Exit", ja: "🚪 退出", zh: "🚪 退出", es: "🚪 Salir" },
  // loss-result gate (see the last move before the defeat screen)
  gate_msg: { ko: "상대가 마지막 수를 두었습니다. 체스판을 확인한 뒤 결과를 보세요.", en: "Your opponent played their last move. Review the board, then see the result.", ja: "相手が最後の一手を指しました。盤面を確認してから結果を見ましょう。", zh: "对手已走出最后一步。查看棋盘后再看结果。", es: "Tu rival hizo su última jugada. Revisa el tablero y luego ve el resultado." },
  gate_btn: { ko: "결과 보기 ▶", en: "See result ▶", ja: "結果を見る ▶", zh: "查看结果 ▶", es: "Ver resultado ▶" },
  lbl_style:     { ko: "AI 스타일 (유명 선수처럼 두기)", en: "AI style (play like a famous player)", ja: "AIスタイル(名選手のように指す)", zh: "AI 风格(模仿名家)", es: "Estilo de IA (juega como un maestro)" },
  lbl_color:     { ko: "내 색", en: "My color", ja: "自分の色", zh: "我的执棋", es: "Mi color" },
  btn_newgame:   { ko: "▶ 새 대국 시작", en: "▶ New game", ja: "▶ 新しい対局", zh: "▶ 开始新对局", es: "▶ Nueva partida" },
  btn_resign_ai: { ko: "🏳️ 기권하고 평가받기", en: "🏳️ Resign & review", ja: "🏳️ 投了して評価", zh: "🏳️ 认输并复盘", es: "🏳️ Rendirse y analizar" },
  btn_flip:      { ko: "⇅ 보드 뒤집기", en: "⇅ Flip board", ja: "⇅ 盤を反転", zh: "⇅ 翻转棋盘", es: "⇅ Girar tablero" },

  // ----- account deletion (settings) -----
  set_del_label: { ko: "계정 삭제", en: "Delete account", ja: "アカウント削除", zh: "删除账号", es: "Eliminar cuenta" },
  set_del_desc:  { ko: "계정과 서버에 저장된 모든 데이터(레이팅·기록·퍼즐)를 영구 삭제합니다. 되돌릴 수 없습니다.", en: "Permanently delete your account and all server-stored data (rating, history, puzzles). This cannot be undone.", ja: "アカウントとサーバー上の全データ(レート・履歴・パズル)を完全に削除します。取り消せません。", zh: "永久删除您的账号及服务器上的所有数据(等级分·记录·谜题)，不可恢复。", es: "Elimina permanentemente tu cuenta y todos los datos del servidor (rating, historial, puzzles). No se puede deshacer." },
  set_del_btn:   { ko: "계정 삭제", en: "Delete", ja: "削除", zh: "删除", es: "Eliminar" },
  del_confirm:   { ko: "정말 계정을 삭제할까요? 서버에 저장된 레이팅·기록·퍼즐이 모두 사라지며 되돌릴 수 없습니다.", en: "Really delete your account? Your rating, history, and puzzles on the server will be gone permanently.", ja: "本当にアカウントを削除しますか? サーバー上のレート・履歴・パズルは完全に消え、元に戻せません。", zh: "确定要删除账号吗？服务器上的等级分、记录和谜题将永久消失，无法恢复。", es: "¿Seguro que quieres eliminar tu cuenta? Tu rating, historial y puzzles del servidor se perderán para siempre." },
  del_done:      { ko: "계정이 삭제되었습니다.", en: "Your account has been deleted.", ja: "アカウントを削除しました。", zh: "账号已删除。", es: "Tu cuenta ha sido eliminada." },

  // ----- auth modal -----
  auth_title:    { ko: "👤 로그인 / 회원가입", en: "👤 Sign in / Sign up", ja: "👤 ログイン / 登録", zh: "👤 登录 / 注册", es: "👤 Iniciar sesión / Registrarse" },
  auth_id_label: { ko: "아이디 (2~20자, 한글/영문/숫자)", en: "Username (2–20 chars)", ja: "ユーザー名(2〜20文字)", zh: "用户名(2–20个字符)", es: "Usuario (2–20 caracteres)" },
  auth_pw_label: { ko: "비밀번호 (4자 이상)", en: "Password (4+ chars)", ja: "パスワード(4文字以上)", zh: "密码(4位以上)", es: "Contraseña (4+ caracteres)" },
  auth_login:    { ko: "로그인", en: "Sign in", ja: "ログイン", zh: "登录", es: "Iniciar sesión" },
  auth_register: { ko: "회원가입", en: "Sign up", ja: "登録", zh: "注册", es: "Registrarse" },
  auth_open:     { ko: "👤 로그인", en: "👤 Sign in", ja: "👤 ログイン", zh: "👤 登录", es: "👤 Entrar" },
  auth_logout:   { ko: "로그아웃", en: "Sign out", ja: "ログアウト", zh: "退出", es: "Salir" },
  auth_hint:     { ko: "회원가입하면 지금까지의 진행상황(레이팅·대국 기록·퍼즐)이 계정에 저장되고, 다른 기기에서 로그인해도 이어집니다.", en: "Sign up to save your progress (rating, game history, puzzles) to your account and continue on any device.", ja: "登録すると進行状況(レート・対局履歴・パズル)がアカウントに保存され、別の端末でも続けられます。", zh: "注册后，您的进度(等级分、对局记录、谜题)会保存到账号，在任何设备登录都能继续。", es: "Regístrate para guardar tu progreso (rating, historial, puzzles) en tu cuenta y seguir en cualquier dispositivo." },
  auth_forgot:   { ko: "비밀번호를 잊으셨나요?", en: "Forgot your password?", ja: "パスワードをお忘れですか?", zh: "忘记密码?", es: "¿Olvidaste tu contraseña?" },
  recovery_saved:{ ko: "🔑 복구 코드를 안전한 곳에 저장하세요! 비밀번호를 잊으면 이 코드로만 재설정할 수 있어요:", en: "🔑 Save this recovery code somewhere safe! It's the only way to reset your password if you forget it:", ja: "🔑 この復旧コードを安全な場所に保存してください! パスワードを忘れた場合、これでのみ再設定できます:", zh: "🔑 请把这个恢复码保存在安全的地方! 忘记密码时只能用它来重置:", es: "🔑 ¡Guarda este código de recuperación en un lugar seguro! Es la única forma de restablecer tu contraseña si la olvidas:" },
  reset_id:      { ko: "아이디를 입력하세요", en: "Enter your username", ja: "ユーザー名を入力", zh: "输入用户名", es: "Introduce tu usuario" },
  reset_code:    { ko: "복구 코드를 입력하세요 (가입 때 받은 코드)", en: "Enter your recovery code (from sign-up)", ja: "復旧コードを入力(登録時のコード)", zh: "输入恢复码(注册时获得)", es: "Introduce tu código de recuperación (del registro)" },
  reset_newpw:   { ko: "새 비밀번호를 입력하세요 (4자 이상)", en: "Enter a new password (4+ chars)", ja: "新しいパスワードを入力(4文字以上)", zh: "输入新密码(4位以上)", es: "Introduce una nueva contraseña (4+ caracteres)" },
  reset_done:    { ko: "비밀번호가 재설정되었습니다.", en: "Your password has been reset.", ja: "パスワードを再設定しました。", zh: "密码已重置。", es: "Tu contraseña ha sido restablecida." },
  auth_email_label:{ ko: "이메일 (선택 · 비밀번호 찾기용)", en: "Email (optional · for password recovery)", ja: "メール(任意・パスワード復旧用)", zh: "邮箱(可选 · 用于找回密码)", es: "Correo (opcional · para recuperar contraseña)" },
  reset_email_prompt:{ ko: "이메일로 보낸 6자리 코드를 입력하세요 (받은 편지함을 확인하세요)", en: "Enter the 6-digit code we emailed you (check your inbox)", ja: "メールに送った6桁のコードを入力してください(受信箱を確認)", zh: "请输入我们邮件发送的6位验证码(请查收邮箱)", es: "Introduce el código de 6 dígitos que te enviamos por correo (revisa tu bandeja)" },
  reset_sending: { ko: "확인 중…", en: "Checking…", ja: "確認中…", zh: "确认中…", es: "Comprobando…" },

  // ----- online tab -----
  og_match_title:{ ko: "온라인 매치", en: "Online match", ja: "オンライン対戦", zh: "在线对战", es: "Partida en línea" },
  og_login_req:  { ko: "🔒 로그인이 필요합니다", en: "🔒 Sign-in required", ja: "🔒 ログインが必要です", zh: "🔒 需要登录", es: "🔒 Inicio de sesión requerido" },
  og_login_desc: { ko: "온라인 레이팅 대국은 로그인한 계정만 이용할 수 있습니다. 레이팅과 전적이 계정에 저장됩니다.", en: "Online rated games require a signed-in account. Your rating and record are saved to it.", ja: "オンラインのレート対局はログイン済みアカウントのみ利用できます。レートと戦績が保存されます。", zh: "在线等级分对局需要登录账号。您的等级分和战绩将被保存。", es: "Las partidas clasificatorias requieren una cuenta. Tu rating y récord se guardan en ella." },
  og_rating_label:{ ko: "내 레이팅", en: "My rating", ja: "マイレート", zh: "我的等级分", es: "Mi rating" },
  og_nick_label: { ko: "닉네임 (계정 아이디)", en: "Nickname (account id)", ja: "ニックネーム(アカウントID)", zh: "昵称(账号ID)", es: "Apodo (id de cuenta)" },
  og_quick:      { ko: "⚡ 빠른 매치 찾기", en: "⚡ Find a match", ja: "⚡ クイックマッチ", zh: "⚡ 快速匹配", es: "⚡ Buscar partida" },
  og_cancel:     { ko: "매칭 취소", en: "Cancel", ja: "マッチング取消", zh: "取消匹配", es: "Cancelar" },
  og_friend_title:{ ko: "친구와 하기 (초대 코드)", en: "Play a friend (invite code)", ja: "友達と対戦(招待コード)", zh: "和好友对战(邀请码)", es: "Jugar con un amigo (código)" },
  og_create:     { ko: "🔗 초대 코드 만들기", en: "🔗 Create invite code", ja: "🔗 招待コード作成", zh: "🔗 创建邀请码", es: "🔗 Crear código" },
  og_join_label: { ko: "친구가 준 코드 입력", en: "Enter a friend's code", ja: "友達のコードを入力", zh: "输入好友的邀请码", es: "Introduce el código de un amigo" },
  og_join:       { ko: "참가", en: "Join", ja: "参加", zh: "加入", es: "Unirse" },
  og_gameinfo:   { ko: "대국 정보", en: "Game info", ja: "対局情報", zh: "对局信息", es: "Info de la partida" },
  og_lb_hint:    { ko: "로그인한 플레이어만 순위에 올라갑니다.", en: "Only signed-in players appear on the leaderboard.", ja: "ログイン済みのプレイヤーのみランキングに載ります。", zh: "只有已登录的玩家才会出现在排行榜上。", es: "Solo los jugadores con sesión aparecen en la clasificación." },
  h_leaderboard: { ko: "🏆 리더보드", en: "🏆 Leaderboard", ja: "🏆 ランキング", zh: "🏆 排行榜", es: "🏆 Clasificación" },
  h_history:     { ko: "대국 기록", en: "Game history", ja: "対局履歴", zh: "对局记录", es: "Historial" },
  og_resign:     { ko: "🏳️ 기권", en: "🏳️ Resign", ja: "🏳️ 投了", zh: "🏳️ 认输", es: "🏳️ Rendirse" },
  og_draw:       { ko: "🤝 무승부 제안", en: "🤝 Offer draw", ja: "🤝 引き分け提案", zh: "🤝 提议和棋", es: "🤝 Ofrecer tablas" },
  og_chat_btn:   { ko: "💬 채팅", en: "💬 Chat", ja: "💬 チャット", zh: "💬 聊天", es: "💬 Chat" },
  og_send:       { ko: "보내기", en: "Send", ja: "送信", zh: "发送", es: "Enviar" },

  // ----- puzzle tab -----
  pz_desc:       { ko: "백이 두어 정해진 수 안에 체크메이트를 만드세요. 상대는 가장 오래 버티는 수로 응수합니다.", en: "Play White and force checkmate within the given moves. Black defends as long as possible.", ja: "白番で、指定手数以内にチェックメイトを。相手は最も長く粘る手で応じます。", zh: "执白在规定步数内将杀。黑方以最顽强的方式抵抗。", es: "Juega con blancas y da mate en las jugadas indicadas. Las negras resisten lo máximo posible." },
  pz_c1:         { ko: "1수 (1–25)", en: "Mate in 1 (1–25)", ja: "1手詰 (1–25)", zh: "1步杀 (1–25)", es: "Mate en 1 (1–25)" },
  pz_c2:         { ko: "2수 (26–50)", en: "Mate in 2 (26–50)", ja: "2手詰 (26–50)", zh: "2步杀 (26–50)", es: "Mate en 2 (26–50)" },
  pz_c3:         { ko: "3수 (51–75)", en: "Mate in 3 (51–75)", ja: "3手詰 (51–75)", zh: "3步杀 (51–75)", es: "Mate en 3 (51–75)" },
  pz_c4:         { ko: "4수 (76–100)", en: "Mate in 4 (76–100)", ja: "4手詰 (76–100)", zh: "4步杀 (76–100)", es: "Mate en 4 (76–100)" },
  pz_prev:       { ko: "◀ 이전", en: "◀ Prev", ja: "◀ 前へ", zh: "◀ 上一题", es: "◀ Anterior" },
  pz_reset:      { ko: "⟲ 다시 풀기", en: "⟲ Retry", ja: "⟲ やり直し", zh: "⟲ 重做", es: "⟲ Reintentar" },
  pz_hint:       { ko: "💡 힌트", en: "💡 Hint", ja: "💡 ヒント", zh: "💡 提示", es: "💡 Pista" },
  pz_solution:   { ko: "정답 보기", en: "Solution", ja: "解答を見る", zh: "查看答案", es: "Solución" },
  pz_next:       { ko: "다음 ▶", en: "Next ▶", ja: "次へ ▶", zh: "下一题 ▶", es: "Siguiente ▶" },

  // ----- growth tab -----
  gr_goal:       { ko: "🎯 이번 주 목표", en: "🎯 This week's goal", ja: "🎯 今週の目標", zh: "🎯 本周目标", es: "🎯 Meta semanal" },
  gr_reco:       { ko: "오늘의 추천", en: "Today's suggestion", ja: "今日のおすすめ", zh: "今日推荐", es: "Sugerencia de hoy" },
  gr_chart:      { ko: "레이팅 성장 그래프", en: "Rating growth chart", ja: "レーティング推移グラフ", zh: "等级分成长图", es: "Gráfico de rating" },
  gr_proj:       { ko: "미래 레이팅 예측", en: "Rating forecast", ja: "将来のレート予測", zh: "未来等级分预测", es: "Previsión de rating" },
  gr_proj_note:  { ko: "최근 온라인 대국 추세를 단순 연장한 추정치입니다 — 참고용이에요.", en: "A rough estimate extending your recent online trend — for reference only.", ja: "最近のオンライン対局の傾向を単純に延ばした推定値です(参考用)。", zh: "根据近期在线对局趋势的简单推算，仅供参考。", es: "Una estimación aproximada de tu tendencia reciente: solo de referencia." },

  // ----- review tab -----
  rv_empty_t:    { ko: "아직 평가한 게임이 없어요", en: "No reviewed games yet", ja: "まだ評価した対局がありません", zh: "还没有已复盘的对局", es: "Aún no hay partidas analizadas" },
  rv_empty_p:    { ko: "먼저 AI에게 분석을 맡기세요. 경기를 두고 평가하면 여기에 결과가 나타납니다.", en: "Have the AI analyze a game first — play and review, and the results appear here.", ja: "まずAIに分析させましょう。対局して評価すると、ここに結果が表示されます。", zh: "先让 AI 分析一局。下棋并复盘后，结果会显示在这里。", es: "Deja que la IA analice una partida: juega y analiza, y los resultados aparecerán aquí." },
  rv_goto_ai:    { ko: "🤖 AI와 대국하러 가기", en: "🤖 Play the computer", ja: "🤖 AIと対局へ", zh: "🤖 去人机对弈", es: "🤖 Jugar contra la IA" },
  rv_goto_online:{ ko: "🌐 온라인 대국하기", en: "🌐 Play online", ja: "🌐 オンライン対局", zh: "🌐 在线对弈", es: "🌐 Jugar en línea" },
  rv_share_title:{ ko: "공유 / 내보내기", en: "Share / Export", ja: "共有 / 書き出し", zh: "分享 / 导出", es: "Compartir / Exportar" },
  rv_coach_title:{ ko: "코치 평 (LLM, 선택)", en: "Coach comment (LLM, optional)", ja: "コーチの講評(LLM・任意)", zh: "教练点评(LLM，可选)", es: "Comentario del entrenador (LLM, opcional)" },

  // ----- learn tab -----
  learn_rules_title:{ ko: "체스의 기본 규칙", en: "Basic chess rules", ja: "チェスの基本ルール", zh: "国际象棋基本规则", es: "Reglas básicas del ajedrez" },
  pc_pawn:   { ko: "♟ 폰", en: "♟ Pawn", ja: "♟ ポーン", zh: "♟ 兵", es: "♟ Peón" },
  pc_knight: { ko: "♞ 나이트", en: "♞ Knight", ja: "♞ ナイト", zh: "♞ 马", es: "♞ Caballo" },
  pc_bishop: { ko: "♝ 비숍", en: "♝ Bishop", ja: "♝ ビショップ", zh: "♝ 象", es: "♝ Alfil" },
  pc_rook:   { ko: "♜ 룩", en: "♜ Rook", ja: "♜ ルーク", zh: "♜ 车", es: "♜ Torre" },
  pc_queen:  { ko: "♛ 퀸", en: "♛ Queen", ja: "♛ クイーン", zh: "♛ 后", es: "♛ Dama" },
  pc_king:   { ko: "♚ 킹", en: "♚ King", ja: "♚ キング", zh: "♚ 王", es: "♚ Rey" },
  pc_castle: { ko: "캐슬링", en: "Castling", ja: "キャスリング", zh: "王车易位", es: "Enroque" },
  pc_enp:    { ko: "앙파상", en: "En passant", ja: "アンパッサン", zh: "吃过路兵", es: "Al paso" },
  pc_promo:  { ko: "승격", en: "Promotion", ja: "プロモーション", zh: "升变", es: "Coronación" },

  // ----- in-game dynamic (turn indicator / result) -----
  turn_white:  { ko: "백 차례", en: "White to move", ja: "白番", zh: "白方走", es: "Juegan las blancas" },
  turn_black:  { ko: "흑 차례", en: "Black to move", ja: "黒番", zh: "黑方走", es: "Juegan las negras" },
  turn_you:    { ko: "(당신)", en: "(you)", ja: "(あなた)", zh: "(你)", es: "(tú)" },
  turn_ai:     { ko: "(AI)", en: "(AI)", ja: "(AI)", zh: "(AI)", es: "(IA)" },
  turn_check:  { ko: "체크!", en: "Check!", ja: "チェック!", zh: "将军!", es: "¡Jaque!" },
  turn_thinking:{ ko: "AI가 생각 중…", en: "AI is thinking…", ja: "AIが考え中…", zh: "AI 思考中…", es: "La IA está pensando…" },
  turn_start:  { ko: "새 대국을 시작하세요.", en: "Start a new game.", ja: "新しい対局を始めましょう。", zh: "开始新对局。", es: "Empieza una partida nueva." },
  turn_over:   { ko: "대국 종료", en: "Game over", ja: "対局終了", zh: "对局结束", es: "Partida terminada" },
  res_win:     { ko: "승리하셨습니다", en: "You won", ja: "勝ちました", zh: "你赢了", es: "Has ganado" },
  res_loss:    { ko: "패배하셨습니다", en: "You lost", ja: "負けました", zh: "你输了", es: "Has perdido" },
  res_draw:    { ko: "무승부입니다", en: "It's a draw", ja: "引き分けです", zh: "和棋", es: "Empate" },
  og_turn_wait:{ ko: "매치를 시작하면 보드가 열립니다.", en: "Start a match to open the board.", ja: "マッチを開始すると盤が開きます。", zh: "开始对局后棋盘会打开。", es: "Empieza una partida para abrir el tablero." },
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
