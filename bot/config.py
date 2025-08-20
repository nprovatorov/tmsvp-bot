import os

def _as_bool(v: str, default=False) -> bool:
    if v is None:
        return default
    return v.strip().lower() in {"1", "true", "yes", "on"}

PUBLIC_MODE = _as_bool(os.getenv("PUBLIC_MODE"), default=False)

# Comma-separated @usernames or numeric IDs
_raw_admins = os.getenv("ADMINS", "")
ADMINS = {a.strip() for a in _raw_admins.split(",") if a.strip()}
