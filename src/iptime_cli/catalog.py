"""Catalog of JSON-API methods the ipTIME admin UI (Flutter, firmware 16.x) calls.

Every request is ``POST /cgi/service.cgi {"method": ..., "params": ...}``.  The list below was
extracted from the admin bundle the router serves (``/ui/main.dart.js``, build 16.00.0).  A
method is only marked ``ok`` when it was actually called against a real router and answered.

status values:
  ok      called on real hardware (read-only), answered
  absent  called on real hardware, the model answered "Method not found" or "Config error"
  used    write method that an earlier hand-written script sent to real hardware.  This package's
          own write code has only been exercised against the bundled fake router.
  bundle  present in the admin bundle, never called by us
"""
from __future__ import annotations

FIRMWARE = "16.00.0"

# last path segments that only read
_READ_SEGMENTS = {
    "get", "show", "info", "status", "list", "max", "stations", "stalist", "chart", "spec", "state",
    "count", "supported_fs", "support", "support_func", "name", "num", "role", "running", "latest",
    "is_set", "has", "read", "progressing", "params", "pcount", "storage", "temperature", "auth",
    "account", "profile", "services", "original", "all", "agent", "online", "user_count", "changed",
    "backup", "expire", "port", "portcfg", "relay", "rssi", "min", "range",
}
# last segments that change state or trigger an action
_WRITE_SEGMENTS = {
    "add", "set", "del", "remove", "clear", "start", "stop", "update", "new", "enroll", "cancel",
    "connect", "disconnect", "reset", "restore", "gen", "flush", "suspend", "resume", "apply",
    "upgrade", "prepare", "now", "timer", "beep", "convert", "scrub", "mount", "umount", "download",
    "send", "scan", "signal", "operation", "enable", "modify", "delall", "online_upgrade", "ctrl",
    "report_on_error", "redirect_on_error", "mode", "policy", "delete", "change",
}
# explicitly dangerous: loses config, drops the connection or flashes firmware
DANGER = {
    "reboot/now", "reboot/timer", "config/reset", "config/restore", "default/admin",
    "firmware/upgrade/online", "firmware/upgrade/prepare", "network/interface/wan1/suspend",
    "network/interface/wan1/resume", "network/arp/flush", "partition/add", "partition/del",
    "btrfs/subvol/convert", "usb/umount", "https/cert/del", "https/cert/gen", "admin/account",
    "wireless/band/set",
}
# "<name>/config" style methods read without params and write with params
_CONFIG_LIKE = ("config", "config/get", "get")

SESSION = {"session/login", "session/logout", "session/update", "session/info"}


def classify(method: str, params=None) -> str:
    """Return ``read``, ``write``, ``danger`` or ``session``.

    Unknown names that do not look like a read are reported as ``write`` so that guards stay on
    the safe side.
    """
    if method in SESSION:
        return "session"
    if method in DANGER:
        return "danger"
    last = method.rsplit("/", 1)[-1]
    if last == "config" or method.endswith("/config/original"):
        return "read" if params is None else "write"
    if last in _WRITE_SEGMENTS:
        return "write"
    if last in _READ_SEGMENTS:
        return "read"
    return "write"


# method | params | note | status
_OBSERVED = """
session/info||who am I: ip, mac, location, idle timeout, level|ok
admin/auth/info||login policy: auth mode, session timeout, captcha use/tolerance|ok
product/info||model, id, board, MACs, vendor, mesh support|ok
product/name||model name string|ok
system/info||version, uptime, WAN link speed, DHCP range, SSIDs (incl. Wi-Fi passwords in clear)|ok
system/name||device name|ok
system/temperature|"cpu"|CPU temperature; this model answers "Config error"|absent
firmware/info||running firmware: version, build date, snapshot id|ok
firmware/version/latest||newest firmware version the router knows of|ok
firmware/upgrade/status||stage idle, starting, checking, downloading, waiting, writing, succeeded or failed (plus a downloading percent and a failed reason: download, format, version, internal)|ok
network/interface/wan1/info||WAN type, link, status, IP, mask, gateway, MAC, MTU, connected seconds|ok
network/interface/wan1/config||WAN configuration (type, DHCP/PPPoE/static options)|ok
network/interface/lan/info||LAN bridge: IP, mask, MAC, MTU|ok
network/interface/lan/config||LAN configuration|ok
network/interface/lan/stations||every device the router sees: MAC, IP, name, wired port or Wi-Fi BSS/RSSI/speeds|ok
network/dns/info||DNS servers in use|ok
network/dns/config||manual DNS settings|ok
conn/info||connection-tracking totals per LAN host|ok
dhcpd/status|"lan"|DHCP server running or suspended|ok
dhcpd/config/get|"lan"|DHCP pool, mask, gateway, DNS, lease time|ok
dhcpd/lease/show|"lan"|current leases: MAC, IP, remaining seconds, hostname|ok
dhcpd/reservedaddr/show|"lan"|static DHCP reservations|ok
wireless/info||per band: supported modes, widths, authentication, country|ok
wireless/band/info||per band: activated, channel, bandwidth, DFS state|ok
wireless/band/show||per band settings: channel, mode, width, TX power, streams|ok
wireless/bss/info||per SSID: running, MAC, interface|ok
wireless/bss/show||per SSID settings: SSID, hidden, authentication, password (in clear), max stations|ok
wireless/client/info||repeater/client-mode link state per band|ok
wireless/client/show||repeater/client-mode settings per band|ok
wireless/mac/show||Wi-Fi MAC filter policy and list per SSID|ok
wireless/wps/info||WPS state per band|ok
wireless/mlo/info||Wi-Fi 7 multi-link operation; this model answers "Method not found"|absent
port/num||{"wan": 1, "lan": 4}|ok
port/link/info||per port: supported speeds|ok
port/link/status||per port: negotiated link speed|ok
port/stat/get||per port rx/tx packet and byte counters|ok
port/role||switch port role; this model answers "Method not found"|absent
power/status||this model answers "Method not found"|absent
fan/running||this model answers "Method not found"|absent
led/status||LED on or off|ok
tethering/status||USB tethering state|ok
upnp/config||UPnP enabled flag|ok
nat/config||NAT enabled flag|ok
dmz/config||DMZ mode, host MAC, lease|ok
http/config|none to read; {"remotehttp_flag","remotehttp_port","commit":true} to write|admin ports and remote (WAN) admin flags; the write body is from the admin bundle, never sent by us|ok
time/config||time server, time zone, DST|ok
portforward/get|"user" or "upnp"|port-forward rules: name, active, protocol, target, src (external) and dst (internal) ports|ok
portforward/max||maximum number of rules|ok
wol/show||Wake-on-LAN list|ok
route/static/show||static routes|ok
qos/rule/show||QoS rules|ok
firewall/get||firewall rules|ok
easymesh/info||EasyMesh active flag and role|ok
usb/show||USB devices and partitions|ok
wan/heartbeat||WAN heartbeat (keep-alive) settings|ok
ui/lang/config||admin UI language|ok
session/login|{"id","pw"}|log in; answers {"result": "done"}; sets the session cookie|used
session/logout||log out|ok
portforward/add|{"name","active","protocol","target","src":{"start"[,"end"]},"dst":{...}}|add a rule|used
portforward/set||change a rule|used
portforward/del|{"type":"user","list":[names]}|delete rules by name; answers the new list|used
dhcpd/reservedaddr/add|{"ntag":"lan","mac","ip","desc"}|one reservation per call|used
dhcpd/reservedaddr/del|{"ntag":"lan","mac":[macs]}|delete reservations|used
firmware/upgrade/prepare|{"method":"auto"}|step 1 of "upgrade now" (online upgrade); never sent to real hardware by us|bundle
firmware/upgrade/online||step 2: the router downloads and flashes the latest image itself, then reboots; an error answer means nothing to upgrade; never sent to real hardware by us|bundle
reboot/now||reboot the router immediately; never called by us|bundle
"""


def _parse():
    out = {}
    for line in _OBSERVED.strip().splitlines():
        name, params, note, status = line.split("|")
        out[name] = {"params": params, "note": note, "status": status}
    return out


OBSERVED = _parse()

_BUNDLE_NAMES = """
acl/config acl/whitelist/add acl/whitelist/del admin/account admin/auth admin/auth/info
admin/changed admin/email admin/email/clear admin/email/is_set api/has assistance/config
assistance/icc/config assistance/icc/info btrfs/scrub btrfs/subvol/convert captcha/new
cert/remote config/backup config/reset config/restore conn/ctrl conn/defaults conn/info
cupsd/config cupsd/status cwmp/get cwmp/set cwmp/status ddns/config ddns/config/add
ddns/config/del ddns/status/clear ddns/status/get ddns/update default/admin dhcpd/config/get
dhcpd/config/set dhcpd/lease/show dhcpd/reservedaddr/add dhcpd/reservedaddr/del
dhcpd/reservedaddr/show dhcpd/status diffserv/config dmz/config dos/config easymesh/config
easymesh/info easymesh/show/agent fan/config fan/config/original fan/running firewall/add
firewall/del firewall/get firewall/max firewall/set firmware/info firmware/upgrade/online
firmware/upgrade/prepare firmware/upgrade/status firmware/version/latest fm/guest/account
fm/guest/account/delete fm/guest/online fm/list ftp/config ftp/port/add ftp/port/del
ftp/port/list geoip/blocked/pcount geoip/country/list geoip/db/download geoip/enable geoip/get
geoip/policy/remove geoip/policy/set geoip/white/list geoip/white/remove geoip/white/set
history/range/spec history/station/connection/state
history/station/count/chart history/station/count/max history/station/count/stalist
history/station/disconnection/count/chart history/station/disconnection/count/max
history/station/rssi/chart history/station/rssi/min historyd/clear historyd/config
historyd/storage hostscan/log/clear hostscan/log/read hostscan/params hostscan/progressing
hostscan/start hostscan/stop http/config httpd/direct/portcfg https/cert/config https/cert/del
https/cert/gen https/cert/get https/cert/info https/cert/set httpsd/port icc/cli/connect/status
icc/cli/enroll icc/cli/enroll/cancel icc/cli/enroll/info icc/cli/enroll/status icc/cli/profile
icc/cli/site_config/show id/device/user_count id/keyset/list id/keyset/remove_user iptv/config
iptv/mode iptv/public/port l2tp/server/config led/config led/status macvlan/add macvlan/del
macvlan/get media/config media/db/show media/db/update mudfish/config mudfish/status
nas/user/add nas/user/del nas/user/info nas/user/modify nas/user/show nas/user/show/online
nat/config network/arp/flush network/dns/config network/dns/info network/info
network/interface/lan/config network/interface/lan/info network/interface/lan/scan/apcp
network/interface/lan/scan/dhcp network/interface/lan/stations network/interface/wan1/config
network/interface/wan1/info network/interface/wan1/resume network/interface/wan1/scan
network/interface/wan1/suspend partition/add partition/del partition/supported_fs
port/link/config port/link/info port/link/status port/num port/role port/stat/clear
port/stat/get portforward/add portforward/config portforward/del portforward/get
portforward/max portforward/set power/beep power/report_on_error power/status ppp/user/add
ppp/user/del ppp/user/disconnect ppp/user/max ppp/user/set ppp/user/show pptp/server/config
product/info product/name product/support_func qos/config qos/rule/del qos/rule/set
qos/rule/show reboot/now reboot/timer route/static/add route/static/del route/static/max
route/static/set route/static/show routine/add routine/del routine/expire routine/get
routine/services routine/set routine/status samba/config session/info session/login
session/logout session/update si/net/profile si/net/profile/clear snapshot/config
snapshot/delall snapshot/new switch/jumbo_frame/config switch/mirror/config switch/mirror/port
switch/trunk/config switch/trunk/port syslog/active syslog/clear syslog/email/config
syslog/email/send syslog/max syslog/show system/info system/name system/temperature
tethering/config tethering/status time/config torrent/config ui/lang/config ui/lang/list
ui/redirect_on_error upnp/config upnp/relay url/config urlredir/config urlredir/freedevice/add
urlredir/freedevice/del urlredir/freedevice/show usb/event/count usb/mode usb/mount
usb/mount/list usb/service/apply usb/service/status usb/show usb/umount vpncli/connect
vpncli/disconnect vpncli/filter/list vpncli/filter/remove vpncli/filter/set vpncli/server/list
vpncli/server/remove vpncli/server/set vpncli/status/list vpncli/upload/config wan/heartbeat
wg/client/add wg/client/change wg/client/del wg/client/show wg/peer/add wg/peer/change
wg/peer/del wg/peer/show wg/server/clear wg/server/set wg/server/show wireless/band/info
wireless/band/set wireless/band/show wireless/band/support wireless/bss/clear wireless/bss/info
wireless/bss/set wireless/bss/show wireless/channel/list wireless/channel/scan
wireless/client/info wireless/client/set wireless/client/show wireless/info wireless/mac/add
wireless/mac/del wireless/mac/policy wireless/mac/show wireless/mlo/info wireless/scan
wireless/wps/info wireless/wps/start wireless/wps/stop wl/operation wol/add wol/del wol/show
wol/signal
""".split()


def all_methods():
    """Return ``[{method, kind, status, firmware, params, note}]`` sorted by name."""
    rows = []
    for name in sorted(set(_BUNDLE_NAMES) | set(OBSERVED)):
        info = OBSERVED.get(name, {"params": "", "note": "", "status": "bundle"})
        rows.append({
            "method": name, "kind": classify(name), "status": info["status"],
            "firmware": FIRMWARE, "params": info["params"], "note": info["note"],
        })
    return rows
