"""HTTP client and typed helpers for the ipTIME JSON API (new admin UI, firmware 16.x)."""
from __future__ import annotations

import http.client
import http.cookiejar
import json
import re
import ssl
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass, field
from typing import Any, Optional

from .catalog import classify

MAC_RE = re.compile(r"^[0-9A-Fa-f]{2}([:-][0-9A-Fa-f]{2}){5}$")


class IptimeError(Exception):
    """Base class for every error this package raises."""


class ConnectError(IptimeError):
    """The router could not be reached."""


class OldUiError(IptimeError):
    """The router serves the old admin UI, which this package does not support yet."""


class LoginError(IptimeError):
    """The router refused the login."""


class CaptchaError(LoginError):
    """The router wants a captcha before it accepts another login."""


class LockoutError(LoginError):
    """The router temporarily blocks logins (too many failures)."""


class UpgradeError(IptimeError):
    """The firmware upgrade failed, timed out or never started."""


class ApiError(IptimeError):
    """The router answered a call with an error object."""

    def __init__(self, method: str, code: Any, message: str):
        super().__init__(f"{method}: {message} (code {code})")
        self.method, self.code, self.message = method, code, message


def normalize_host(host: str) -> str:
    """``192.168.0.1``, ``192.168.0.1:8080`` or a full URL -> ``http://host[:port]``."""
    host = (host or "").strip().rstrip("/")
    if not host:
        raise IptimeError("no router address: pass --host or set IPTIME_HOST")
    if "://" not in host:
        host = "http://" + host
    if host.endswith("/ui"):
        host = host[:-3]
    return host


def normalize_mac(mac: str) -> str:
    if not MAC_RE.match(mac or ""):
        raise IptimeError(f"not a MAC address: {mac!r} (expected AA:BB:CC:00:00:01)")
    return mac.replace("-", ":").upper()


def parse_ports(text: str) -> dict:
    """``8080`` -> {"start": 8080};  ``8000-8010`` -> {"start": 8000, "end": 8010}."""
    m = re.fullmatch(r"\s*(\d{1,5})(?:\s*-\s*(\d{1,5}))?\s*", str(text))
    if not m:
        raise IptimeError(f"not a port or port range: {text!r}")
    start = int(m.group(1))
    out = {"start": start}
    if m.group(2):
        end = int(m.group(2))
        if end < start:
            raise IptimeError(f"port range ends before it starts: {text!r}")
        out["end"] = end
    for value in out.values():
        if not 1 <= value <= 65535:
            raise IptimeError(f"port out of range 1-65535: {text!r}")
    return out


@dataclass
class Station:
    """One device the router sees (wired or Wi-Fi)."""
    mac: str
    ip: str = ""
    name: str = ""
    link: str = ""          # "wired" or "wireless"
    where: str = ""         # LAN port ("lan2") or BSS ("5g.1")
    rssi: Optional[int] = None
    down_mbps: Optional[int] = None
    up_mbps: Optional[int] = None
    down_bytes: Optional[int] = None
    up_bytes: Optional[int] = None
    addressing: str = ""    # "dhcp" or "static"
    lease_remaining: Optional[int] = None
    reserved: bool = False

    def as_dict(self) -> dict:
        return asdict(self)


@dataclass
class Lease:
    mac: str
    ip: str
    remaining: int = 0
    name: str = ""


@dataclass
class Reservation:
    mac: str
    ip: str
    name: str = ""


@dataclass
class PortForward:
    name: str
    protocol: str
    target: str
    external: dict = field(default_factory=dict)   # "src" in the API
    internal: dict = field(default_factory=dict)   # "dst" in the API
    active: bool = True
    fixed: bool = False

    @staticmethod
    def span(ports: dict) -> str:
        if not ports:
            return ""
        if "end" in ports and ports["end"] != ports["start"]:
            return f"{ports['start']}-{ports['end']}"
        return str(ports["start"])

    def as_dict(self) -> dict:
        d = asdict(self)
        d["external"], d["internal"] = self.span(self.external), self.span(self.internal)
        return d


class Router:
    """Talk to one router.  Logs in lazily on the first call.

    ``dry_run=True`` makes every call that is not a read return the request instead of sending it.
    Logging in may end an admin session that is open in a browser.
    """

    def __init__(self, host: str, user: str = "admin", password: str = "", *, timeout: float = 15,
                 verify_tls: bool = True, dry_run: bool = False):
        self.base = normalize_host(host)
        self.user, self.password = user, password
        self.timeout, self.dry_run = timeout, dry_run
        self.logged_in = False
        self.sent: list = []          # every request that went to /cgi/service.cgi (without secrets)
        handlers: list = [urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar())]
        if self.base.startswith("https") and not verify_tls:
            ctx = ssl.create_default_context()
            ctx.check_hostname, ctx.verify_mode = False, ssl.CERT_NONE
            handlers.append(urllib.request.HTTPSHandler(context=ctx))
        self._opener = urllib.request.build_opener(*handlers)

    # -- plumbing ---------------------------------------------------------------------------
    def __enter__(self) -> "Router":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def close(self) -> None:
        """Log out (best effort)."""
        if self.logged_in:
            try:
                self._post({"method": "session/logout"})
            except IptimeError:
                pass
            self.logged_in = False

    def _open(self, req):
        try:
            return self._opener.open(req, timeout=self.timeout)
        except urllib.error.HTTPError as exc:
            return exc
        except (urllib.error.URLError, OSError, http.client.HTTPException) as exc:
            raise ConnectError(f"cannot reach {self.base}: {getattr(exc, 'reason', exc)}") from exc

    def _post(self, body: dict) -> dict:
        req = urllib.request.Request(
            self.base + "/cgi/service.cgi", json.dumps(body).encode(),
            {"Content-Type": "application/json; charset=utf-8", "Cache-Control": "no-store",
             "Origin": self.base, "Referer": self.base + "/ui/"})
        resp = self._open(req)
        raw = resp.read()
        try:
            data = json.loads(raw)
        except ValueError:
            raise OldUiError(
                "old admin UI not supported yet: /cgi/service.cgi did not answer JSON "
                f"(HTTP {getattr(resp, 'status', '?')}). Only the new admin UI (firmware 16.x, "
                "served at /ui/) is supported.") from None
        if not isinstance(data, dict):
            raise IptimeError(f"unexpected answer from the router: {raw[:80]!r}")
        return data

    def request_for(self, method: str, params: Any = None) -> dict:
        body: dict = {"method": method}
        if params is not None:
            body["params"] = params
        return body

    def connect(self) -> None:
        """Fetch the admin UI once (sets the cookie) and refuse the old admin UI."""
        resp = self._open(urllib.request.Request(self.base + "/ui/"))
        page = resp.read(65536).decode("utf-8", "replace")
        status = getattr(resp, "status", 200)
        if status != 200 or "flutter" not in page.lower():
            raise OldUiError(
                "old admin UI not supported yet: no new admin UI at "
                f"{self.base}/ui/ (HTTP {status}). This package needs firmware 16.x.")

    def login(self) -> None:
        if self.logged_in:
            return
        if not self.password:
            raise LoginError("no password given")
        self.connect()
        data = self._post({"method": "session/login",
                           "params": {"id": self.user, "pw": self.password}})
        if data.get("result") == "done":
            self.logged_in = True
            return
        text = json.dumps(data, ensure_ascii=False)
        low = text.lower()
        if "captcha" in low:
            raise CaptchaError(f"the router asks for a captcha before the next login: {text}")
        if any(w in low for w in ("lock", "block", "too many", "wait")):
            raise LockoutError(f"the router blocks logins for now: {text}")
        hint = " (wrong user or password?)" if (data.get("error") or {}).get("code") == -31996 else ""
        raise LoginError(f"login failed{hint}: {text}")

    # -- calls ------------------------------------------------------------------------------
    def call_raw(self, method: str, params: Any = None) -> dict:
        """Send one call and return the whole answer ({"result": ..., "error": ...})."""
        body = self.request_for(method, params)
        if self.dry_run and classify(method, params) in ("write", "danger"):
            return {"dry_run": True, "would_send": {"POST": self.base + "/cgi/service.cgi",
                                                    "body": body}}
        self.login()
        data = self._post(body)
        if (data.get("error") or {}).get("message") == "Unauthenticated" and method != "session/login":
            self.logged_in = False           # session expired: log in once more and retry
            self.login()
            data = self._post(body)
        self.sent.append(body)
        return data

    def call(self, method: str, params: Any = None) -> Any:
        """Send one call and return ``result``; raise :class:`ApiError` on an error object."""
        data = self.call_raw(method, params)
        if data.get("dry_run"):
            return data
        err = data.get("error")
        if err:
            raise ApiError(method, err.get("code"), err.get("message", "error"))
        return data.get("result")

    def has_method(self, method: str) -> bool:
        return bool(self.call("api/has", method))

    # -- reads ------------------------------------------------------------------------------
    def session(self) -> dict:
        return self.call("session/info")

    def product(self) -> dict:
        return self.call("product/info")

    def firmware(self) -> dict:
        info = self.call("firmware/info")
        try:
            latest = self.call("firmware/version/latest")
        except ApiError:
            latest = None
        info["latest"] = latest
        info["update_available"] = bool(latest) and _version_key(str(latest)) > _version_key(
            str(info.get("version", "0")))
        return info

    def system(self, secrets: bool = False) -> dict:
        data = self.call("system/info")
        if not secrets:
            data = _mask(data)
        return data

    def wan(self) -> dict:
        info = self.call("network/interface/wan1/info")
        info["dns"] = _try(self, "network/dns/info")
        for port in _try(self, "port/link/status") or []:
            if port.get("type") == "wan":
                info["link_speed"] = port.get("link")
        for stat in _try(self, "port/stat/get") or []:
            if stat.get("type") == "wan":
                info["rx_bytes"] = stat.get("rx", {}).get("byte")
                info["tx_bytes"] = stat.get("tx", {}).get("byte")
        return info

    def lan(self) -> dict:
        info = self.call("network/interface/lan/info")
        info["dhcp"] = _try(self, "dhcpd/config/get", "lan")
        return info

    def leases(self) -> list:
        return [Lease(x["mac"].upper(), x.get("ip", ""), x.get("remaining", 0), x.get("desc", ""))
                for x in self.call("dhcpd/lease/show", "lan") or []]

    def reservations(self) -> list:
        return [Reservation(x["mac"].upper(), x.get("ip", ""), x.get("desc", ""))
                for x in self.call("dhcpd/reservedaddr/show", "lan") or []]

    def stations(self) -> list:
        """All devices the router sees, merged with DHCP leases and reservations."""
        leases = {x.mac: x for x in self.leases()}
        reserved = {x.mac for x in self.reservations()}
        out = []
        for item in self.call("network/interface/lan/stations") or []:
            info, conn = item.get("info") or {}, item.get("connection") or {}
            mac = item["mac"].upper()
            kind = conn.get("type", "")
            detail = conn.get(kind) or {}
            st = Station(mac=mac, ip=info.get("ip", ""), name=info.get("name", ""), link=kind,
                         where=detail.get("bss") or detail.get("port") or "",
                         rssi=detail.get("rssi"), down_mbps=detail.get("down_speed"),
                         up_mbps=detail.get("up_speed"), down_bytes=detail.get("down_bytes"),
                         up_bytes=detail.get("up_bytes"), addressing=info.get("type", ""))
            lease = leases.pop(mac, None)
            if lease:
                st.lease_remaining = lease.remaining
                st.name = st.name or lease.name
            st.reserved = mac in reserved
            out.append(st)
        return out

    def wifi(self, secrets: bool = False) -> list:
        """One row per SSID, with band and running state."""
        bands = {b["band"]: b for b in self.call("wireless/band/show") or []}
        band_info = {b["band"]: b for b in self.call("wireless/band/info") or []}
        running = {b["bss"]: b for b in self.call("wireless/bss/info") or []}
        counts: dict = {}
        for st in self.stations():
            if st.link == "wireless":
                counts[st.where] = counts.get(st.where, 0) + 1
        rows = []
        for bss in self.call("wireless/bss/show") or []:
            band = bss["bss"].split(".")[0]
            row = {"bss": bss["bss"], "band": band, "ssid": bss.get("ssid", ""),
                   "enabled": bss.get("enable"), "running": (running.get(bss["bss"]) or {}).get("run"),
                   "hidden": bss.get("hide"), "security": bss.get("authenc", ""),
                   "channel": (band_info.get(band) or {}).get("channel") or (bands.get(band) or {}).get("channel"),
                   "width": (bands.get(band) or {}).get("width"),
                   "mode": (bands.get(band) or {}).get("mode"),
                   "clients": counts.get(bss["bss"], 0)}
            if secrets:
                row["password"] = bss.get("password", "")
            rows.append(row)
        return rows

    def port_forwards(self, kind: str = "user") -> list:
        out = []
        for x in self.call("portforward/get", kind) or []:
            out.append(PortForward(x["name"], x.get("protocol", ""), x.get("target", ""),
                                   x.get("src", {}), x.get("dst", {}), bool(x.get("active", True)),
                                   bool(x.get("fixed", False))))
        return out

    def remote_admin(self) -> dict:
        return self.call("http/config")

    # -- writes (never called unless you call them; honour dry_run) ----------------------------
    def add_port_forward(self, name: str, target: str, protocol: str, external: str,
                         internal: Optional[str] = None, active: bool = True):
        if protocol not in ("tcp", "udp", "tcpudp"):
            raise IptimeError("protocol must be tcp, udp or tcpudp")
        params = {"name": name, "active": active, "protocol": protocol, "target": target,
                  "src": parse_ports(external), "dst": parse_ports(internal or external)}
        return self.call("portforward/add", params)

    def del_port_forward(self, names: list, kind: str = "user"):
        return self.call("portforward/del", {"type": kind, "list": list(names)})

    def reserve(self, mac: str, ip: str, name: str = ""):
        return self.call("dhcpd/reservedaddr/add",
                         {"ntag": "lan", "mac": normalize_mac(mac), "ip": ip, "desc": name})

    def unreserve(self, mac: str):
        return self.call("dhcpd/reservedaddr/del", {"ntag": "lan", "mac": [normalize_mac(mac)]})

    def set_remote_admin(self, enabled: bool, port: Optional[int] = None):
        """Turn remote (WAN) HTTP admin on or off.  ``on`` exposes the admin page to the internet;
        ``off`` closes both the HTTP and the HTTPS remote admin endpoints."""
        current = self.remote_admin()
        params = {"remotehttp_flag": bool(enabled),
                  "remotehttp_port": int(port or current.get("remotehttp_port") or 8080),
                  "commit": True}
        if not enabled:
            # switching remote admin off must close the HTTPS admin endpoint too,
            # not leave it exposed on the WAN
            params["remotehttps_flag"] = False
        return self.call("http/config", params)

    def upgrade_firmware(self, wait_timeout: float = 1800, poll: float = 10, progress=None,
                         sleep=time.sleep, clock=time.monotonic) -> dict:
        """Run the router's own online firmware upgrade and wait until it is back on the new version.

        Sends ``firmware/upgrade/prepare {"method": "auto"}`` then ``firmware/upgrade/online`` (the
        two calls the admin page's "upgrade now" makes), polls ``firmware/upgrade/status``, rides
        out the reboot (the router is unreachable for a few minutes), logs in again and compares
        ``firmware/info``.  Nothing is uploaded; the router downloads the image itself.
        ``progress(message)`` is called on each stage change.  ``dry_run`` returns the two requests.
        """
        say = progress or (lambda _msg: None)
        before = self.firmware()
        old, latest = str(before.get("version")), before.get("latest")
        if not before["update_available"]:
            return {"upgraded": False, "reason": "already up to date", "from": old, "latest": latest}
        if self.dry_run:
            sent = [self.call_raw(m, p)["would_send"] for m, p in _UPGRADE_CALLS]
            return {"dry_run": True, "upgraded": False, "from": old, "latest": latest, "would_send": sent}
        started = clock()
        for method, params in _UPGRADE_CALLS:
            self.call(method, params)
        say(f"upgrade requested: {old} -> {latest}")
        active_seen, last_stage = False, None
        while True:
            if clock() - started > wait_timeout:
                raise UpgradeError(f"gave up after {int(wait_timeout)}s waiting for the router "
                                   f"(still on {old}?); it may still be rebooting")
            status = None
            try:
                status = self.call("firmware/upgrade/status")
            except LoginError:
                # reauthentication was refused (wrong password, captcha, lockout):
                # stop at once instead of hammering the router with logins until
                # the timeout, and let the real error reach the caller
                raise
            except IptimeError:             # router rebooting: no answer, or the session is gone
                self.logged_in = False
                if last_stage != "unreachable":
                    say("router is rebooting (unreachable)")
                last_stage, active_seen = "unreachable", True
            if status:
                stage = status.get("stage")
                if stage == "failed":
                    raise UpgradeError(f"the router reports the upgrade failed: {status.get('failed') or 'unknown reason'}")
                if stage != last_stage:
                    say(f"stage: {stage}")
                    last_stage = stage
                if stage not in ("idle", None):
                    active_seen = True
                if stage in ("idle", "succeeded") and active_seen:
                    try:
                        now = str(self.call("firmware/info").get("version"))
                    except IptimeError:
                        now = old
                    if now != old:
                        return {"upgraded": True, "from": old, "to": now, "latest": latest,
                                "seconds": int(clock() - started)}
                elif stage == "idle" and clock() - started > 180:
                    raise UpgradeError("the router never started the upgrade (stage stayed idle)")
            sleep(poll)

    def reboot(self):
        """Reboot the router now.  The connection drops for a minute or two."""
        return self.call("reboot/now")


_UPGRADE_CALLS = (("firmware/upgrade/prepare", {"method": "auto"}), ("firmware/upgrade/online", None))


def _version_key(text: str) -> tuple:
    return tuple(int(p) if p.isdigit() else 0 for p in re.split(r"[.\-]", text))


def _try(router: Router, method: str, params: Any = None):
    try:
        return router.call(method, params)
    except ApiError:
        return None


def _mask(value: Any) -> Any:
    """Replace every ``password`` value with ``********`` (the router returns Wi-Fi keys in clear)."""
    if isinstance(value, dict):
        return {k: ("********" if k == "password" and v else _mask(v)) for k, v in value.items()}
    if isinstance(value, list):
        return [_mask(v) for v in value]
    return value
