"""Run the server windowless (launched via pythonw.exe, no console).

pythonw.exe has no valid stdout/stderr, so uvicorn's logging would crash the
process the first time it writes a line. We point stdout/stderr at a log file
*before* uvicorn configures logging, so the server runs reliably with no window
and we still get logs for troubleshooting.

Launch:  pythonw.exe -m webapp.run_bg   (run with the project root as cwd)
"""
import os
import sys

LOG_PATH = os.path.join(os.path.expanduser("~"), ".chess_coach_server.log")
try:
    _log = open(LOG_PATH, "a", buffering=1, encoding="utf-8")
    sys.stdout = _log
    sys.stderr = _log
except Exception:
    pass

import uvicorn  # noqa: E402

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run("webapp.server:app", host="127.0.0.1", port=port, log_level="info")
