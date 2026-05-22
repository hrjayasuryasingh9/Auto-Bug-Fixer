import logging
import sys
import os

LOG_FILE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "logs", "app.log"))

_FMT = "%(asctime)s [%(levelname)s] %(message)s"
_DATE = "%Y-%m-%d %H:%M:%S"


class _FlushHandler(logging.StreamHandler):
    """Flushes immediately so logs appear in real-time."""
    def emit(self, record):
        super().emit(record)
        self.flush()


class _FlushFileHandler(logging.FileHandler):
    def emit(self, record):
        super().emit(record)
        self.flush()


def _setup_logger() -> logging.Logger:
    log = logging.getLogger("ai-error-fixer")
    log.setLevel(logging.DEBUG)

    if log.handlers:
        return log

    fmt = logging.Formatter(_FMT, datefmt=_DATE)

    console = _FlushHandler(sys.stdout)
    console.setLevel(logging.DEBUG)
    console.setFormatter(fmt)
    log.addHandler(console)

    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    fh = _FlushFileHandler(LOG_FILE, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(fmt)
    log.addHandler(fh)

    log.propagate = False
    return log


logger = _setup_logger()
