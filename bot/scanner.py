import os
import clamd
import logging

CLAMAV_HOST = os.getenv("CLAMAV_HOST", "clamav")
CLAMAV_PORT = int(os.getenv("CLAMAV_PORT", "3310"))

class ScanResult:
    def __init__(self, status: str, signature: str | None):
        self.status = status      # "clean" | "infected" | "error"
        self.signature = signature

def _client():
    return clamd.ClamdNetworkSocket(host=CLAMAV_HOST, port=CLAMAV_PORT, timeout=30)

def scan_path(path: str) -> ScanResult:
    try:
        cd = _client()
        # PING ensures daemon is ready; raises on failure
        cd.ping()
        # clamd returns dict: {"path": ("FOUND"/"OK"/"ERROR", "SigName" or None)}
        result = cd.scan(path)
        if not result or path not in result:
            return ScanResult("error", None)
        status, sig = result[path]
        if status == "OK":
            return ScanResult("clean", None)
        if status == "FOUND":
            return ScanResult("infected", sig)
        return ScanResult("error", sig)
    except Exception as e:
        logging.exception("ClamAV scan failed for %s", path)
        return ScanResult("error", None)
