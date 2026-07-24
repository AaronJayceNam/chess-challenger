/* Client-side Stockfish (asm.js) in a Web Worker.
 *
 * Why: the app server runs on a 0.1-CPU shared instance, so the ENGINE SEARCH
 * (AI moves, hints, analysis) is the real bottleneck. This runs that search on
 * the player's own machine instead. Move generation / legality stays on the
 * server (it's cheap); only the slow part moves here. Everything degrades
 * gracefully to the server endpoints if the engine can't load (old browser,
 * blocked worker, etc.).
 *
 * Public API (window.SF):
 *   SF.available            – boolean, Workers supported at all
 *   SF.warmup()             – Promise, kick off engine load early (optional)
 *   SF.ready()              – Promise<boolean>, resolves true once usable
 *   SF.newGame()            – clear the engine's hash between unrelated games
 *   SF.bestMove(fen, opts)  – Promise<{bestmove, cp, mate, pv}>
 *                             opts: {movetime, elo}  (elo null/omitted = full strength)
 */
(function () {
  "use strict";
  var ENGINE_URL = "/static/engine/stockfish.js?v=1";
  var worker = null, readyP = null, busy = false, curElo = "unset";
  var queue = [];

  function ensure() {
    if (readyP) return readyP;
    readyP = new Promise(function (resolve, reject) {
      try { worker = new Worker(ENGINE_URL); }
      catch (e) { reject(e); return; }
      var done = false;
      var to = setTimeout(function () { if (!done) reject(new Error("engine init timeout")); }, 25000);
      worker.onmessage = function (e) {
        var s = String(e.data);
        if (s.indexOf("uciok") >= 0) worker.postMessage("isready");
        else if (s.indexOf("readyok") >= 0) { done = true; clearTimeout(to); worker.onmessage = null; resolve(); }
      };
      worker.onerror = function () { clearTimeout(to); reject(new Error("engine worker error")); };
      worker.postMessage("uci");
    });
    return readyP;
  }

  // one blocking search; assumes the worker is idle
  function search(fen, opts) {
    return new Promise(function (resolve) {
      var cp = null, mate = null, pv = [];
      function onMsg(e) {
        var s = String(e.data);
        if (s.indexOf("info") === 0 && s.indexOf(" pv ") >= 0) {
          var mMate = s.match(/score mate (-?\d+)/), mCp = s.match(/score cp (-?\d+)/);
          if (mMate) { mate = +mMate[1]; cp = null; }
          else if (mCp) { cp = +mCp[1]; mate = null; }
          var mPv = s.match(/ pv (.+)$/); if (mPv) pv = mPv[1].trim().split(/\s+/);
        } else if (s.indexOf("bestmove") === 0) {
          worker.removeEventListener("message", onMsg);
          var bm = s.split(/\s+/)[1];
          resolve({ bestmove: (bm && bm !== "(none)") ? bm : null, cp: cp, mate: mate, pv: pv });
        }
      }
      worker.addEventListener("message", onMsg);
      // only reconfigure strength when it actually changes (avoids churn)
      var elo = (opts.elo == null) ? null : opts.elo;
      if (elo !== curElo) {
        if (elo == null) worker.postMessage("setoption name UCI_LimitStrength value false");
        else { worker.postMessage("setoption name UCI_LimitStrength value true"); worker.postMessage("setoption name UCI_Elo value " + elo); }
        curElo = elo;
      }
      if (opts.chess960) worker.postMessage("setoption name UCI_Chess960 value true");
      worker.postMessage("position fen " + fen);
      var mt = Math.max(40, Math.min(5000, opts.movetime || 500));
      worker.postMessage("go movetime " + mt);
    });
  }

  function pump() {
    if (busy || !queue.length) return;
    busy = true;
    var job = queue.shift();
    ensure()
      .then(function () { return search(job.fen, job.opts); })
      .then(function (r) { job.resolve(r); }, function (e) { job.reject(e); })
      .then(function () { busy = false; pump(); });
  }

  window.SF = {
    available: (typeof Worker !== "undefined"),
    warmup: function () { return ensure().then(function () { return true; }, function () { return false; }); },
    ready: function () { return ensure().then(function () { return true; }, function () { return false; }); },
    newGame: function () { if (worker) { try { worker.postMessage("ucinewgame"); } catch (e) {} } },
    bestMove: function (fen, opts) {
      return new Promise(function (resolve, reject) {
        if (!window.SF.available) { reject(new Error("no worker support")); return; }
        queue.push({ fen: fen, opts: opts || {}, resolve: resolve, reject: reject });
        pump();
      });
    },
  };
})();
