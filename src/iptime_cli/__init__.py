"""Unofficial CLI and library for ipTIME routers with the new admin UI (firmware 16.x)."""
from .client import (ApiError, CaptchaError, ConnectError, IptimeError, Lease, LockoutError,
                     LoginError, OldUiError, PortForward, Reservation, Router, Station, UpgradeError)

__version__ = "0.1.2"
__all__ = ["Router", "Station", "Lease", "Reservation", "PortForward", "IptimeError", "ApiError",
           "LoginError", "CaptchaError", "LockoutError", "OldUiError", "ConnectError", "UpgradeError"]
