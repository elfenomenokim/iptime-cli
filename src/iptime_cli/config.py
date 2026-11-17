"""Settings: flags > environment > config file > defaults."""
from __future__ import annotations

import os
import stat
import sys
from dataclasses import dataclass

DEFAULT_HOST = "192.168.0.1"     # ipTIME factory default
DEFAULT_USER = "admin"

_KEYS = {
    "host": ("host", "url", "iptime_host", "iptime_admin_url"),
    "user": ("user", "username", "iptime_user", "iptime_admin_user"),
    "password": ("password", "pass", "iptime_password", "iptime_admin_password"),
}
_ENV = {
    "host": ("IPTIME_HOST", "IPTIME_ADMIN_URL"),
    "user": ("IPTIME_USER", "IPTIME_ADMIN_USER"),
    "password": ("IPTIME_PASSWORD", "IPTIME_ADMIN_PASSWORD"),
}


@dataclass
class Settings:
    host: str
    user: str
    password: str
    config_path: str = ""


def default_config_path() -> str:
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    return os.path.join(base, "iptime-cli", "config")


def read_file(path: str, warn=True) -> dict:
    """Parse ``key = value`` lines (also ``IPTIME_HOST=...`` and ``export`` forms)."""
    out: dict = {}
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#") or ("=" not in line and ":" not in line):
                continue
            if line.startswith("export "):
                line = line[7:]
            key, _, value = line.partition("=") if "=" in line else line.partition(":")
            key, value = key.strip().lower(), value.strip().strip("'\"")
            for name, aliases in _KEYS.items():
                if key in aliases:
                    out[name] = value
    if warn and out.get("password"):
        mode = stat.S_IMODE(os.stat(path).st_mode)
        if mode & 0o077:
            print(f"warning: {path} holds a password but is readable by others "
                  f"(mode {mode:04o}); run: chmod 600 {path}", file=sys.stderr)
    return out


def resolve(host=None, user=None, config=None, prompt=True) -> Settings:
    path = config or os.environ.get("IPTIME_CONFIG") or default_config_path()
    values: dict = {}
    if os.path.exists(path):
        values = read_file(path)
    elif config:
        raise SystemExit(f"config file not found: {config}")

    def pick(name, flag):
        if flag:
            return flag
        for var in _ENV[name]:
            if os.environ.get(var):
                return os.environ[var]
        return values.get(name, "")

    settings = Settings(pick("host", host) or DEFAULT_HOST, pick("user", user) or DEFAULT_USER,
                        pick("password", None), path if values else "")
    if not settings.password and prompt:
        if sys.stdin.isatty():
            import getpass
            settings.password = getpass.getpass(f"password for {settings.user}@{settings.host}: ")
        else:
            raise SystemExit("error: no password. Set IPTIME_PASSWORD, put it in "
                             f"{default_config_path()}, or run in a terminal to be asked.")
    return settings
