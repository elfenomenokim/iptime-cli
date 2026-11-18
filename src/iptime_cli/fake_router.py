"""A tiny fake of the ipTIME admin API with made-up data, to try the CLI without a router.

    python -m iptime_cli.fake_router --port 8080
    IPTIME_PASSWORD=secret iptime --host 127.0.0.1:8080 clients

Not a router: it only knows the methods the CLI uses.  Login is ``admin`` / ``secret``.
Modes for testing error paths: ``--old-ui`` (no /ui/ page), ``--captcha`` (every login asks for a
captcha), ``--lockout`` (every login is blocked).  Writes change the in-memory data only.
"""
from __future__ import annotations

import argparse
import copy
import json
import secrets
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PASSWORD = "secret"


def fresh_state() -> dict:
    stations = [
        ("AA:BB:CC:00:00:01", "192.168.0.10", "desktop", "wired", {"port": "lan2", "link": 1000, "down_bytes": 52428800, "up_bytes": 10485760}, "static"),
        ("AA:BB:CC:00:00:02", "192.168.0.11", "nas", "wired", {"port": "lan4", "link": 1000, "down_bytes": 9437184000, "up_bytes": 2147483648}, "dhcp"),
        ("AA:BB:CC:00:00:03", "192.168.0.20", "laptop", "wireless", {"bss": "5g.1", "duration": 3600, "rssi": -48, "normal_power": 100, "down_speed": 866, "up_speed": 780, "down_bytes": 734003200, "up_bytes": 104857600}, "dhcp"),
        ("AA:BB:CC:00:00:04", "192.168.0.21", "phone", "wireless", {"bss": "5g.1", "duration": 1200, "rssi": -61, "normal_power": 100, "down_speed": 433, "up_speed": 390, "down_bytes": 31457280, "up_bytes": 5242880}, "dhcp"),
        ("AA:BB:CC:00:00:05", "192.168.0.30", "smart-plug", "wireless", {"bss": "2g.1", "duration": 86400, "rssi": -70, "normal_power": 100, "down_speed": 72, "up_speed": 72, "down_bytes": 1048576, "up_bytes": 524288}, "dhcp"),
    ]
    return {
        "stations": [{"mac": m, "info": {"ip": ip, "type": t, "name": n, "product_id": "", "product_name": "", "ptype": "normal", "icon": ""},
                      "connection": {"type": k, "upstream_mac": "AA:BB:CC:00:10:01", k: d}} for m, ip, n, k, d, t in stations],
        "leases": [{"mac": "AA:BB:CC:00:00:02", "ip": "192.168.0.11", "remaining": 80000, "desc": "nas"},
                   {"mac": "AA:BB:CC:00:00:03", "ip": "192.168.0.20", "remaining": 6400, "desc": "laptop"},
                   {"mac": "AA:BB:CC:00:00:04", "ip": "192.168.0.21", "remaining": 3200, "desc": "phone"},
                   {"mac": "AA:BB:CC:00:00:05", "ip": "192.168.0.30", "remaining": 70000, "desc": "smart-plug"}],
        "reserved": [{"mac": "AA:BB:CC:00:00:02", "ip": "192.168.0.11", "desc": "NAS"}],
        "forwards": [{"name": "Web server", "active": True, "protocol": "tcp", "target": "192.168.0.10", "priority": 1, "fixed": False,
                      "src": {"start": 8080}, "dst": {"start": 80}},
                     {"name": "Game range", "active": False, "protocol": "udp", "target": "192.168.0.20", "priority": 2, "fixed": False,
                      "src": {"start": 27000, "end": 27010}, "dst": {"start": 27000, "end": 27010}}],
        "upnp": [{"name": "example-portmap_udp_40001", "active": True, "protocol": "udp", "target": "192.168.0.21", "priority": 3, "fixed": False,
                  "src": {"start": 40001}, "dst": {"start": 40001}}],
        "http": {"mode": "HTTP", "http_port": 80, "remotehttp_flag": False, "remotehttp_port": 8080,
                 "https_port": 443, "remotehttps_flag": False, "remotehttps_port": 8443},
        "rebooted": False,
        "fw": "16.000", "up_stage": None, "down_until": 0.0, "outage": 3.0, "drop_sessions": False,
    }


def ok(result):
    return {"result": result}


def err(code, message):
    return {"result": None, "error": {"code": code, "message": message}}


class Handler(BaseHTTPRequestHandler):
    server_version = "FakeIptime/0"

    def log_message(self, *_):
        pass

    def _send(self, code, body, ctype="application/json", headers=None):
        raw = body if isinstance(body, bytes) else json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(raw)))
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(raw)

    def _down(self) -> bool:
        """During the simulated reboot the router answers nothing: drop the connection."""
        if time.time() < self.server.state["down_until"]:
            self.close_connection = True
            return True
        return False

    def do_GET(self):
        if self._down():
            return
        if self.path.startswith("/ui") and not self.server.old_ui:
            self._send(200, b"<html><script src='flutter_bootstrap.js'></script></html>", "text/html")
        else:
            self._send(404 if self.server.old_ui and self.path.startswith("/ui") else 200,
                       b"<html>old ipTIME login page</html>", "text/html")

    def do_POST(self):
        if self._down():
            return
        if self.server.old_ui or self.path != "/cgi/service.cgi":
            return self._send(200, b"<html>old ipTIME login page</html>", "text/html")
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
        host = self.headers.get("Host", "")
        if self.headers.get("Origin") != f"http://{host}":
            return self._send(200, err(-32000, "Unauthenticated"))
        method, params = body.get("method", ""), body.get("params")
        srv = self.server
        cookie = self.headers.get("Cookie", "")
        if method == "session/login":
            if srv.captcha:
                return self._send(200, {"result": "captcha", "error": {"code": -1, "message": "captcha required"}})
            if srv.lockout:
                return self._send(200, {"result": "locked", "error": {"code": -2, "message": "too many failures, wait 60 seconds"}})
            if params == {"id": "admin", "pw": PASSWORD}:
                sid = secrets.token_hex(8)
                srv.sessions.add(sid)
                return self._send(200, ok("done"), headers={"Set-Cookie": f"sid={sid}; Path=/"})
            return self._send(200, {"result": "fail", "error": {"code": -3, "message": "wrong id or password"}})
        sid = cookie.split("sid=")[-1].split(";")[0] if "sid=" in cookie else ""
        if sid not in srv.sessions:
            return self._send(200, err(-32000, "Unauthenticated"))
        if method == "session/logout":
            srv.sessions.discard(sid)
            return self._send(200, ok("done"))
        srv.calls.append(body)
        answer = self.dispatch(srv.state, method, params)
        if srv.state["drop_sessions"]:
            srv.sessions.clear()
            srv.state["drop_sessions"] = False
        self._send(200, answer)

    @staticmethod
    def dispatch(st, method, params):
        if method == "session/info":
            return ok({"type": "session", "ip": "192.168.0.50", "location": "lan", "mac": "AA:BB:CC:00:00:50", "timeout": 1800, "level": "auth"})
        if method == "product/info":
            return ok({"name": "ipTIME FAKE-1000", "id": "fake1000", "company": "EFM Networks", "type": "wireless_router",
                       "mac": "AA:BB:CC:00:10:01", "version": "16.00.0", "wan_mac": "AA:BB:CC:00:10:02", "vendor": "efm"})
        if method == "firmware/info":
            return ok({"version": st["fw"], "build_date": "2026.01.01 00:00:00", "snapshot": "0000000"})
        if method == "firmware/version/latest":
            return ok("16.010")
        if method == "firmware/upgrade/prepare":
            return ok("done")
        if method == "firmware/upgrade/online":
            if st["fw"] == "16.010":
                return err(-1, "no need to upgrade")
            st["up_stage"] = 0
            return ok("done")
        if method == "firmware/upgrade/status":
            stages = [{"stage": "starting"}, {"stage": "checking"}, {"stage": "downloading", "downloading": 20},
                      {"stage": "downloading", "downloading": 70}, {"stage": "waiting"}, {"stage": "writing"}]
            i = st["up_stage"]
            if i is None:
                return ok({"stage": "idle"})
            if i >= len(stages):                       # flashing done: the router reboots
                st["fw"], st["up_stage"] = "16.010", None
                st["down_until"] = time.time() + st["outage"]
                st["drop_sessions"] = True
                return ok({"stage": "writing"})
            st["up_stage"] = i + 1
            return ok(stages[i])
        if method == "system/info":
            return ok({"version": "16.00.0", "uptime": 93784, "connected_period": 93700, "wan_link": "1000f",
                       "dhcpd": {"enable": True, "startip": "192.168.0.2", "endip": "192.168.0.254"},
                       "wireless": [{"band": "2g", "bss": [{"enable": True, "ssid": "example-2.4G", "password": "example-wifi-key"}]}]})
        if method == "network/interface/wan1/info":
            return ok({"type": "dhcp", "ifname": "eth3", "link": True, "status": "up", "protocol_status": "ok",
                       "mac": "AA:BB:CC:00:10:02", "ip": "203.0.113.7", "mask": "255.255.255.0", "gateway": "203.0.113.1",
                       "mtu": 1500, "device": "eth", "connected_period": 93700})
        if method == "network/interface/lan/info":
            return ok({"type": "static", "ifname": "br0", "link": True, "status": "up", "mac": "AA:BB:CC:00:10:01",
                       "ip": "192.168.0.1", "mask": "255.255.255.0", "gateway": "", "mtu": 1500})
        if method == "network/dns/info":
            return ok(["198.51.100.2", "198.51.100.3"])
        if method == "port/link/status":
            return ok([{"type": "wan", "port": 1, "link": "1000f"}, {"type": "lan", "port": 1, "link": "down"}])
        if method == "port/stat/get":
            return ok([{"type": "wan", "port": 1, "rx": {"byte": 3221225472000, "packet": 1}, "tx": {"byte": 322122547200, "packet": 1}}])
        if method == "dhcpd/config/get":
            return ok({"ntag": "lan", "enable": True, "min_ip": "192.168.0.2", "max_ip": "192.168.0.254", "mask": "255.255.255.0",
                       "gateway": "192.168.0.1", "dns": ["192.168.0.1"], "leasetime": 86400})
        if method == "dhcpd/lease/show":
            return ok(st["leases"])
        if method == "dhcpd/reservedaddr/show":
            return ok(st["reserved"])
        if method == "dhcpd/reservedaddr/add":
            st["reserved"].append({"mac": params["mac"], "ip": params["ip"], "desc": params["desc"]})
            return ok("done")
        if method == "dhcpd/reservedaddr/del":
            st["reserved"] = [x for x in st["reserved"] if x["mac"] not in params["mac"]]
            return ok("done")
        if method == "network/interface/lan/stations":
            return ok(st["stations"])
        if method == "wireless/band/show":
            return ok([{"band": "2g", "channel": "6", "mode": "11ax", "width": 40}, {"band": "5g", "channel": "36", "mode": "11ax", "width": 80}])
        if method == "wireless/band/info":
            return ok([{"band": "2g", "activated": True, "channel": "6"}, {"band": "5g", "activated": True, "channel": "36"}])
        if method == "wireless/bss/info":
            return ok([{"bss": "2g.1", "run": True}, {"bss": "5g.1", "run": True}])
        if method == "wireless/bss/show":
            return ok([{"bss": "2g.1", "enable": True, "ssid": "example-2.4G", "hide": False, "authenc": "wpa2psk_aes", "password": "example-wifi-key"},
                       {"bss": "5g.1", "enable": True, "ssid": "example-5G", "hide": False, "authenc": "wpa2psk_aes", "password": "example-wifi-key"}])
        if method == "portforward/get":
            return ok(st["forwards"] if params == "user" else st["upnp"])
        if method == "portforward/add":
            if any(x["name"] == params["name"] for x in st["forwards"]):
                return err(-100, "duplicate name")
            st["forwards"].append({**params, "priority": len(st["forwards"]) + 1, "fixed": False})
            return ok(st["forwards"])
        if method == "portforward/del":
            st["forwards"] = [x for x in st["forwards"] if x["name"] not in params["list"]]
            return ok(st["forwards"])
        if method == "http/config":
            if params is None:
                return ok(st["http"])
            st["http"]["remotehttp_flag"] = params["remotehttp_flag"]
            st["http"]["remotehttp_port"] = params["remotehttp_port"]
            if "remotehttps_flag" in params:
                st["http"]["remotehttps_flag"] = params["remotehttps_flag"]
            if "remotehttps_port" in params:
                st["http"]["remotehttps_port"] = params["remotehttps_port"]
            return ok("done")
        if method == "reboot/now":
            st["rebooted"] = True
            return ok("done")
        if method == "api/has":
            return ok(True)
        return err(-32601, "Method not found")


class FakeServer(ThreadingHTTPServer):
    def __init__(self, addr, old_ui=False, captcha=False, lockout=False):
        super().__init__(addr, Handler)
        self.old_ui, self.captcha, self.lockout = old_ui, captcha, lockout
        self.state, self.sessions, self.calls = fresh_state(), set(), []

    def snapshot(self) -> dict:
        return copy.deepcopy(self.state)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port", type=int, default=8080)
    ap.add_argument("--old-ui", action="store_true")
    ap.add_argument("--captcha", action="store_true")
    ap.add_argument("--lockout", action="store_true")
    ap.add_argument("--upgrade-outage", type=float, default=3.0, help="seconds the router is unreachable after flashing")
    a = ap.parse_args(argv)
    srv = FakeServer(("127.0.0.1", a.port), a.old_ui, a.captcha, a.lockout)
    srv.state["outage"] = a.upgrade_outage
    print(f"fake ipTIME router on http://127.0.0.1:{a.port}/  (admin / {PASSWORD})", flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
