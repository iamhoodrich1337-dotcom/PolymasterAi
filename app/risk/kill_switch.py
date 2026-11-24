import json
from pathlib import Path
from app.core.logging import get_logger

logger = get_logger(__name__)
KILL_SWITCH_FILE = Path("kill_switch.json")

class KillSwitch:
    def __init__(self) -> None:
        self._engaged = False
        self._reason = ""
        self._load()
    def _load(self) -> None:
        if KILL_SWITCH_FILE.exists():
            try:
                data = json.loads(KILL_SWITCH_FILE.read_text())
                self._engaged = bool(data.get("engaged", False))
                self._reason = str(data.get("reason", ""))
            except Exception:
                logger.exception("Failed to load kill switch state")
    def _persist(self) -> None:
        KILL_SWITCH_FILE.write_text(json.dumps({"engaged": self._engaged, "reason": self._reason}))
    @property
    def engaged(self) -> bool:
        return self._engaged
    @property
    def reason(self) -> str:
        return self._reason
    def engage(self, reason: str) -> None:
        self._engaged = True
        self._reason = reason
        self._persist()
        logger.critical("Kill switch engaged: %s", reason)
    def disengage(self, reason: str = "manual reset") -> None:
        self._engaged = False
        self._reason = reason
        self._persist()
        logger.warning("Kill switch disengaged: %s", reason)
