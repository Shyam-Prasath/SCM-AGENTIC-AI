from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

LOG_DIR = Path(__file__).resolve().parent / "logs"
LOG_DIR.mkdir(exist_ok=True)
TEXT_LOG = LOG_DIR / "scm_agent.log"
JSONL_LOG = LOG_DIR / "scm_runs.jsonl"

logger = logging.getLogger("hexashop_scm")
logger.setLevel(logging.INFO)
if not logger.handlers:
    handler = logging.FileHandler(TEXT_LOG, encoding="utf-8")
    formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)


def _safe(value: Any):
    try:
        json.dumps(value)
        return value
    except TypeError:
        return str(value)


def log_event(event_type: str, payload: Dict[str, Any]):
    record = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "event_type": event_type,
        **{k: _safe(v) for k, v in payload.items()},
    }
    logger.info(json.dumps(record, ensure_ascii=False))
    with open(JSONL_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def read_recent_logs(limit: int = 50):
    if not JSONL_LOG.exists():
        return []
    lines = JSONL_LOG.read_text(encoding="utf-8").splitlines()[-limit:]
    records = []
    for line in lines:
        try:
            records.append(json.loads(line))
        except Exception:
            records.append({"raw": line})
    return records
