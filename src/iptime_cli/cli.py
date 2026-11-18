"""``iptime`` command line."""
from __future__ import annotations

import argparse
import json
import sys
import time

from . import __version__, config
from .catalog import all_methods, classify
from .client import IptimeError, PortForward, Router, normalize_mac
from .render import human_bytes, human_duration, pairs, table

EPILOG = """\
Write commands (port add/rm, dhcp reserve/unreserve, remote-admin on|off, reboot) change the router.
Add --dry-run to print the request instead of sending it.  Logging in may end an admin session that
is open in a browser.  Unofficial; not affiliated with EFM Networks."""


def build_parser() -> argparse.ArgumentParser:
    def make_common(sub: bool) -> argparse.ArgumentParser:
        """Connection/output flags; accepted before and after the command."""
        S = argparse.SUPPRESS

        def d(value):
            return S if sub else value

        c = argparse.ArgumentParser(add_help=False)
        g = c.add_argument_group("connection")
        g.add_argument("--host", default=d(None), help="router address (default: IPTIME_HOST or 192.168.0.1)")
        g.add_argument("--user", default=d(None), help="admin user (default: IPTIME_USER or admin)")
        g.add_argument("--config", metavar="FILE", default=d(None), help="config file (default ~/.config/iptime-cli/config)")
        g.add_argument("--timeout", type=float, default=d(15), help="seconds per request (default 15)")
        g.add_argument("--insecure", action="store_true", default=d(False), help="do not verify a self-signed https certificate")
        o = c.add_argument_group("output")
        o.add_argument("--json", action="store_true", default=d(False), help="print JSON instead of a table")
        o.add_argument("--show-secrets", action="store_true", default=d(False), help="show Wi-Fi passwords (hidden by default)")
        w = c.add_argument_group("writes")
        w.add_argument("--dry-run", action="store_true", default=d(False), help="print the request instead of sending a write")
        w.add_argument("-y", "--yes", action="store_true", default=d(False), help="do not ask before a write")
        return c

    common = make_common(True)

    p = argparse.ArgumentParser(prog="iptime", description="Unofficial command line for ipTIME routers with the new admin UI (firmware 16.x).",
                                epilog=EPILOG, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--version", action="version", version=f"iptime-cli {__version__}")
    for action in make_common(False)._actions:
        if action.dest != "help":
            p._add_action(action)
    sub = p.add_subparsers(dest="command", required=True, metavar="COMMAND")

    def add(name, help, **kw):
        return sub.add_parser(name, help=help, parents=[common], description=help, **kw)

    add("info", "model, firmware (and whether a newer one exists), uptime, LAN/WAN summary")
    c = add("clients", "every device the router sees: wired and Wi-Fi, with DHCP lease info")
    c.add_argument("--wireless", action="store_true", help="only Wi-Fi devices")
    c.add_argument("--wired", action="store_true", help="only wired devices")
    add("wan", "WAN link: type, IP, gateway, DNS, link speed, traffic")
    add("wifi", "SSIDs, bands, channels and security")

    pt = add("port", "port forwarding rules")
    ps = pt.add_subparsers(dest="action", required=True, metavar="ACTION")

    def padd(name, help):
        return ps.add_parser(name, help=help, parents=[common], description=help)

    pl = padd("list", "list rules")
    pl.add_argument("--upnp", action="store_true", help="show rules added by UPnP instead")
    pa = padd("add", "add a rule")
    pa.add_argument("name")
    pa.add_argument("--target", required=True, metavar="IP", help="LAN address to forward to")
    pa.add_argument("--proto", default="tcp", choices=["tcp", "udp", "tcpudp"])
    pa.add_argument("--ext", required=True, metavar="PORT[-END]", help="external (WAN) port or range")
    pa.add_argument("--int", dest="internal", metavar="PORT[-END]", help="internal port or range (default: same as --ext)")
    pa.add_argument("--disabled", action="store_true", help="add the rule switched off")
    pr = padd("rm", "remove rules by name")
    pr.add_argument("names", nargs="+")

    dh = add("dhcp", "DHCP leases and static reservations")
    ds = dh.add_subparsers(dest="action", required=True, metavar="ACTION")

    def dadd(name, help):
        return ds.add_parser(name, help=help, parents=[common], description=help)

    dadd("list", "leases and reservations")
    dr = dadd("reserve", "reserve an address for a MAC")
    dr.add_argument("mac")
    dr.add_argument("ip")
    dr.add_argument("--name", default="iptime-cli", help="description shown in the admin UI")
    du = dadd("unreserve", "remove the reservation of a MAC")
    du.add_argument("mac")

    ra = add("remote-admin", "show, or switch, admin access from the internet (WAN)")
    ra.add_argument("state", nargs="?", choices=["on", "off"], help="omit to just show the state")
    ra.add_argument("--port", type=int, help="WAN admin port when switching on (default: the stored one)")

    fw = add("firmware", "check for, or install, a newer firmware (the router's own online upgrade)")
    fs = fw.add_subparsers(dest="action", required=True, metavar="ACTION")

    def fadd(name, help):
        return fs.add_parser(name, help=help, parents=[common], description=help)

    fadd("check", "running firmware vs the newest one the router knows of")
    fu = fadd("upgrade", "install the newest firmware; the router reboots and the network drops for a few minutes")
    fu.add_argument("--if-available", action="store_true", help="do nothing, quietly, when already up to date")
    fu.add_argument("--wait-timeout", type=float, default=1800, metavar="SECONDS",
                    help="how long to wait for the router to come back on the new version (default 1800)")
    fu.add_argument("--poll", type=float, default=10, metavar="SECONDS", help="status poll interval (default 10)")

    add("reboot", "reboot the router now (asks first; connection drops for a minute or two)")

    ca = add("call", "send one raw API call (escape hatch)")
    ca.add_argument("method")
    ca.add_argument("params", nargs="?", help='JSON, e.g. \'"user"\' or \'{"ntag":"lan"}\'')
    ca.add_argument("--write", action="store_true", help="allow a method that is not a read")

    m = sub.add_parser("methods", help="list the API methods found in the admin UI", parents=[common],
                       description="List the API methods found in the admin UI bundle (no router needed).")
    m.add_argument("--kind", choices=["read", "write", "danger", "session"])
    m.add_argument("--seen", action="store_true", help="only methods called on real hardware")
    return p


def emit(args, data, text: str) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2) if args.json else text)


def confirm(args, what: str) -> bool:
    if args.dry_run or args.yes:
        return True
    if not sys.stdin.isatty():
        raise IptimeError(f"refusing to {what} without --yes (no terminal to ask on); "
                          "use --dry-run to see the request")
    try:
        return input(f"{what}? [y/N] ").strip().lower() in ("y", "yes")
    except EOFError:
        return False


def rules_table(rules: list) -> str:
    return table(["NAME", "PROTO", "EXTERNAL", "TARGET", "INTERNAL", "ON"],
                 [[x["name"], x.get("protocol"), PortForward.span(x.get("src", {})), x.get("target"),
                   PortForward.span(x.get("dst", {})), "yes" if x.get("active") else "no"] for x in rules])


def show_write(args, result) -> None:
    if isinstance(result, list) and not args.json and all(isinstance(x, dict) and "src" in x for x in result):
        print("ok, rules now:\n" + rules_table(result))
    elif isinstance(result, dict) and result.get("dry_run"):
        sent = result["would_send"]
        emit(args, result, f"dry run, nothing sent:\nPOST {sent['POST']}\n"
                           f"{json.dumps(sent['body'], ensure_ascii=False)}")
    else:
        emit(args, {"ok": True, "result": result}, f"ok: {json.dumps(result, ensure_ascii=False)}")


def _ipkey(ip: str) -> tuple:
    return tuple(int(p) if p.isdigit() else 0 for p in ip.split("."))


def cmd_info(args, r: Router):
    prod, fw, sys_ = r.product(), r.firmware(), r.system()
    lan, wan = r.lan(), r.wan()
    data = {"product": prod, "firmware": fw, "system": {k: v for k, v in sys_.items() if k != "wireless"},
            "lan": lan, "wan": wan}
    latest = fw.get("latest")
    note = f"{latest}  (update available)" if fw.get("update_available") else f"{latest}  (up to date)" if latest else "unknown"
    dhcp = lan.get("dhcp") or {}
    emit(args, data, pairs([
        ("Model", prod.get("name")),
        ("Firmware", f"{fw.get('version')}  (built {fw.get('build_date')})"),
        ("Latest firmware", note),
        ("Uptime", human_duration(sys_.get("uptime"))),
        ("LAN", f"{lan.get('ip')} / {lan.get('mask')}"),
        ("DHCP pool", f"{dhcp.get('min_ip')} - {dhcp.get('max_ip')}" if dhcp else ""),
        ("WAN", f"{wan.get('type')} {wan.get('ip')}  gateway {wan.get('gateway')}  {wan.get('status')}"),
        ("WAN link", wan.get("link_speed")),
    ]))


def cmd_clients(args, r: Router):
    rows = r.stations()
    if args.wireless:
        rows = [x for x in rows if x.link == "wireless"]
    if args.wired:
        rows = [x for x in rows if x.link == "wired"]
    rows.sort(key=lambda x: _ipkey(x.ip))
    if args.json:
        print(json.dumps([x.as_dict() for x in rows], ensure_ascii=False, indent=2))
        return
    body = []
    for x in rows:
        link = f"{x.where} {x.rssi} dBm" if x.link == "wireless" else f"{x.where} wired"
        lease = human_duration(x.lease_remaining) if x.lease_remaining is not None else ("static" if x.addressing == "static" else "")
        body.append([x.ip, x.mac, x.name, link, lease, "yes" if x.reserved else ""])
    print(table(["IP", "MAC", "NAME", "LINK", "LEASE LEFT", "RESERVED"], body))


def cmd_wan(args, r: Router):
    w = r.wan()
    emit(args, w, pairs([
        ("Type", w.get("type")), ("Status", f"{w.get('status')} ({w.get('protocol_status')})"),
        ("IP", w.get("ip")), ("Mask", w.get("mask")), ("Gateway", w.get("gateway")),
        ("DNS", ", ".join(w.get("dns") or [])), ("MAC", w.get("mac")), ("MTU", w.get("mtu")),
        ("Link speed", w.get("link_speed")), ("Connected for", human_duration(w.get("connected_period"))),
        ("Received", human_bytes(w.get("rx_bytes"))), ("Sent", human_bytes(w.get("tx_bytes"))),
    ]))


def cmd_wifi(args, r: Router):
    rows = r.wifi(secrets=args.show_secrets)
    if args.json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        return
    head = ["BSS", "SSID", "BAND", "CH", "SECURITY", "ON", "HIDDEN", "CLIENTS"]
    if args.show_secrets:
        head.append("PASSWORD")
    body = []
    for x in rows:
        row = [x["bss"], x["ssid"], f"{x['band']} {x['mode']}/{x['width']}MHz", x["channel"], x["security"],
               "yes" if x["running"] else "no", "yes" if x["hidden"] else "", x["clients"]]
        if args.show_secrets:
            row.append(x.get("password", ""))
        body.append(row)
    print(table(head, body))


def cmd_port(args, r: Router):
    if args.action == "list":
        rules = r.port_forwards("upnp" if args.upnp else "user")
        if args.json:
            print(json.dumps([x.as_dict() for x in rules], ensure_ascii=False, indent=2))
            return
        print(table(["NAME", "PROTO", "EXTERNAL", "TARGET", "INTERNAL", "ON"],
                    [[x.name, x.protocol, PortForward.span(x.external), x.target,
                      PortForward.span(x.internal), "yes" if x.active else "no"] for x in rules]))
    elif args.action == "add":
        if not confirm(args, f"add port forward {args.name!r} {args.ext} -> {args.target}"):
            return
        show_write(args, r.add_port_forward(args.name, args.target, args.proto, args.ext,
                                               args.internal, not args.disabled))
    elif args.action == "rm":
        if not confirm(args, f"remove port forward {', '.join(args.names)}"):
            return
        show_write(args, r.del_port_forward(args.names))


def cmd_dhcp(args, r: Router):
    if args.action == "list":
        reserved = {x.mac: x for x in r.reservations()}
        leases = {x.mac: x for x in r.leases()}
        rows = []
        for mac in sorted(set(reserved) | set(leases), key=lambda m: _ipkey((reserved.get(m) or leases[m]).ip)):
            res, lease = reserved.get(mac), leases.get(mac)
            state = "reserved+leased" if res and lease else "reserved" if res else "leased"
            rows.append({"ip": (res or lease).ip, "mac": mac, "name": (res.name if res and res.name else lease.name if lease else ""),
                         "state": state, "lease_remaining": lease.remaining if lease else None})
        if args.json:
            print(json.dumps(rows, ensure_ascii=False, indent=2))
            return
        print(table(["IP", "MAC", "NAME", "STATE", "LEASE LEFT"],
                    [[x["ip"], x["mac"], x["name"], x["state"],
                      human_duration(x["lease_remaining"]) if x["lease_remaining"] is not None else ""] for x in rows]))
    elif args.action == "reserve":
        if not confirm(args, f"reserve {args.ip} for {normalize_mac(args.mac)}"):
            return
        show_write(args, r.reserve(args.mac, args.ip, args.name))
    elif args.action == "unreserve":
        if not confirm(args, f"remove the reservation of {normalize_mac(args.mac)}"):
            return
        show_write(args, r.unreserve(args.mac))


def cmd_remote_admin(args, r: Router):
    if args.state is None:
        c = r.remote_admin()
        emit(args, c, pairs([
            ("LAN admin", f"{c.get('mode')} port {c.get('http_port')}"),
            ("Remote HTTP", f"{'on' if c.get('remotehttp_flag') else 'off'}, port {c.get('remotehttp_port')}"),
            ("Remote HTTPS", f"{'on' if c.get('remotehttps_flag') else 'off'}, port {c.get('remotehttps_port')}")]))
        return
    on = args.state == "on"
    if on:
        print("warning: this opens the router's admin page to the internet.", file=sys.stderr)
    if not confirm(args, f"switch remote admin {args.state}"):
        return
    show_write(args, r.set_remote_admin(on, args.port))


def cmd_firmware(args, r: Router):
    fw = r.firmware()
    if args.action == "check":
        latest = fw.get("latest")
        state = "update available" if fw["update_available"] else "up to date" if latest else "unknown"
        emit(args, fw, pairs([("Running", f"{fw.get('version')}  (built {fw.get('build_date')})"),
                              ("Latest", latest), ("State", state)]))
        return
    if not fw["update_available"]:
        if not args.if_available:
            emit(args, {"upgraded": False, "from": fw.get("version"), "latest": fw.get("latest")},
                 f"firmware {fw.get('version')} is already the newest ({fw.get('latest')}); nothing to do")
        return
    if not confirm(args, f"upgrade firmware {fw.get('version')} -> {fw.get('latest')} "
                         "(the router reboots; the network drops for a few minutes)"):
        return
    log = (lambda m: print(f"[{time.strftime('%H:%M:%S')}] {m}", file=sys.stderr, flush=True))
    res = r.upgrade_firmware(args.wait_timeout, args.poll, progress=None if args.json else log)
    if res.get("dry_run"):
        print(f"dry run, nothing sent ({res['from']} -> {res['latest']}):" if not args.json else "", end="")
        if args.json:
            print(json.dumps(res, ensure_ascii=False, indent=2))
        else:
            print()
            for sent in res["would_send"]:
                print(f"POST {sent['POST']}\n{json.dumps(sent['body'], ensure_ascii=False)}")
        return
    emit(args, res, f"firmware upgraded {res['from']} -> {res['to']} in {human_duration(res['seconds'])}")


def cmd_reboot(args, r: Router):
    if not confirm(args, "reboot the router now"):
        return
    show_write(args, r.reboot())


def cmd_call(args, r: Router):
    params = None
    if args.params is not None:
        try:
            params = json.loads(args.params)
        except json.JSONDecodeError:
            params = args.params          # a bare word such as: call portforward/get user
    kind = classify(args.method, params)
    if kind in ("write", "danger") and not (args.write or args.dry_run):
        raise IptimeError(f"{args.method} is not a read ({kind}); add --write to send it, or --dry-run to see the request")
    if kind in ("write", "danger") and not confirm(args, f"send {args.method}"):
        return
    resp = r.call_raw(args.method, params)
    print(json.dumps(resp, ensure_ascii=False, indent=1))
    if resp.get("error"):
        raise SystemExit(1)


def cmd_methods(args):
    rows = all_methods()
    if args.kind:
        rows = [x for x in rows if x["kind"] == args.kind]
    if args.seen:
        rows = [x for x in rows if x["status"] != "bundle"]
    if args.json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        return
    print(table(["METHOD", "KIND", "STATUS", "FIRMWARE", "NOTE"],
                [[x["method"], x["kind"], x["status"], x["firmware"], x["note"]] for x in rows]))


HANDLERS = {"info": cmd_info, "clients": cmd_clients, "wan": cmd_wan, "wifi": cmd_wifi, "port": cmd_port,
            "dhcp": cmd_dhcp, "firmware": cmd_firmware, "remote-admin": cmd_remote_admin, "reboot": cmd_reboot, "call": cmd_call}


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "methods":
            cmd_methods(args)
            return 0
        s = config.resolve(args.host, args.user, args.config)
        with Router(s.host, s.user, s.password, timeout=args.timeout, verify_tls=not args.insecure,
                    dry_run=args.dry_run) as router:
            HANDLERS[args.command](args, router)
        return 0
    except IptimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except json.JSONDecodeError as exc:
        print(f"error: params are not valid JSON: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
