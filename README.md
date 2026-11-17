# iptime-cli

[한국어](https://github.com/elfenomenokim/iptime-cli/blob/main/README.ko.md)

An unofficial command line and Python library for ipTIME routers that have the new admin UI (firmware 16.x). List connected devices, reserve DHCP addresses, manage port forwarding, check Wi-Fi and WAN, switch remote admin off — from a terminal, a script or an AI agent.

> Unofficial. Not affiliated with, endorsed by or supported by EFM Networks. ipTIME is their trademark.

```console
$ iptime clients
IP            MAC                NAME        LINK          LEASE LEFT  RESERVED
192.168.0.10  AA:BB:CC:00:00:01  desktop     lan2 wired    static
192.168.0.11  AA:BB:CC:00:00:02  nas         lan4 wired    22h 13m     yes
192.168.0.20  AA:BB:CC:00:00:03  laptop      5g.1 -48 dBm  1h 46m
192.168.0.21  AA:BB:CC:00:00:04  phone       5g.1 -61 dBm  53m 20s
192.168.0.30  AA:BB:CC:00:00:05  smart-plug  2g.1 -70 dBm  19h 26m
```

(Sample output from the bundled fake router, with made-up devices.)

ipTIME is the most common home router brand in Korea and it has no public API. Its new admin page (a Flutter app served at `/ui/`) talks to the router through one JSON endpoint, `POST /cgi/service.cgi {"method": ..., "params": ...}`. This tool speaks that same protocol. The only earlier public work we found is an npm package for the old UI on firmware 14.x.

## Why

- **Everything the admin page can read, one command away.** Clients, leases, reservations, port forwards, Wi-Fi, WAN, firmware (and whether a newer one exists).
- **Firmware check and one-command upgrade** using the router's own online upgrade, with a wait through the reboot.
- **Safe by default.** Reads never change anything. Every write asks first, supports `--dry-run`, and refuses to run without `--yes` when there is no terminal to ask on. Wi-Fi passwords, which the router returns in clear text, are hidden unless you pass `--show-secrets`.
- **A raw escape hatch.** `iptime call <method> [params]` sends any method; `iptime methods` lists the 290-odd methods found in the admin bundle, with the firmware they were seen on.
- **Standard library only.** No dependencies, Python 3.9+.
- **A library too.** `Router(host, user, password).call(method, params)` plus typed helpers.
- **A fake router to try it on.** `python -m iptime_cli.fake_router` serves made-up data, so you can run every example below without touching your router.

## Install

```console
$ pipx install iptime-cli     # recommended: isolated, on PATH
$ uvx iptime-cli --help       # or run without installing
$ pip install iptime-cli      # inside a project
```

## Configure

Settings are read in this order: command-line flag, environment variable, config file, default.

| Setting | Flag | Environment | Config file key | Default |
|---|---|---|---|---|
| Router address | `--host` | `IPTIME_HOST` | `host` | `192.168.0.1` |
| Admin user | `--user` | `IPTIME_USER` | `user` | `admin` |
| Admin password | — | `IPTIME_PASSWORD` | `password` | asked on the terminal |

The config file is `~/.config/iptime-cli/config` (or `--config FILE`, or `IPTIME_CONFIG`):

```ini
host = 192.168.0.1
user = admin
password = change-me
```

Keep it private: `chmod 600 ~/.config/iptime-cli/config`. The tool warns on stderr when a file with a password is readable by others. A file of `IPTIME_ADMIN_URL=`, `IPTIME_ADMIN_USER=`, `IPTIME_ADMIN_PASSWORD=` lines (or `IPTIME_HOST=` ...) works too. `--host` accepts `192.168.0.1`, `192.168.0.1:8080` or a full URL.

> **Logging in may end an open browser admin session.** The router allows few simultaneous admin sessions. The CLI logs out when it finishes.

## Usage

Global options go before or after the command. `--json` turns any read into JSON for scripts.

### Try it without a router

```console
$ python -m iptime_cli.fake_router --port 8080 &
$ export IPTIME_HOST=127.0.0.1:8080 IPTIME_PASSWORD=secret
```

### info

```console
$ iptime info
Model            ipTIME FAKE-1000
Firmware         16.000  (built 2026.01.01 00:00:00)
Latest firmware  16.010  (update available)
Uptime           1d 2h 3m
LAN              192.168.0.1 / 255.255.255.0
DHCP pool        192.168.0.2 - 192.168.0.254
WAN              dhcp 203.0.113.7  gateway 203.0.113.1  up
WAN link         1000f
```

`iptime firmware upgrade` installs it (see below).

### clients

Every device the router sees, wired and Wi-Fi, merged with DHCP lease and reservation data. `--wireless` and `--wired` filter.

```console
$ iptime clients --wireless
IP            MAC                NAME        LINK          LEASE LEFT  RESERVED
192.168.0.20  AA:BB:CC:00:00:03  laptop      5g.1 -48 dBm  1h 46m
192.168.0.21  AA:BB:CC:00:00:04  phone       5g.1 -61 dBm  53m 20s
192.168.0.30  AA:BB:CC:00:00:05  smart-plug  2g.1 -70 dBm  19h 26m
```

### wan and wifi

```console
$ iptime wan
Type           dhcp
Status         up (ok)
IP             203.0.113.7
Mask           255.255.255.0
Gateway        203.0.113.1
DNS            198.51.100.2, 198.51.100.3
MAC            AA:BB:CC:00:10:02
MTU            1500
Link speed     1000f
Connected for  1d 2h 1m
Received       2.9 TB
Sent           300.0 GB

$ iptime wifi
BSS   SSID          BAND           CH  SECURITY     ON   HIDDEN  CLIENTS
2g.1  example-2.4G  2g 11ax/40MHz  6   wpa2psk_aes  yes          1
5g.1  example-5G    5g 11ax/80MHz  36  wpa2psk_aes  yes          2
```

`iptime wifi --show-secrets` adds a PASSWORD column.

### port

```console
$ iptime port list
NAME        PROTO  EXTERNAL     TARGET        INTERNAL     ON
Web server  tcp    8080         192.168.0.10  80           yes
Game range  udp    27000-27010  192.168.0.20  27000-27010  no

$ iptime port add "Test rule" --target 192.168.0.10 --ext 9000-9005 --proto udp --dry-run
dry run, nothing sent:
POST http://127.0.0.1:8080/cgi/service.cgi
{"method": "portforward/add", "params": {"name": "Test rule", "active": true, "protocol": "udp", "target": "192.168.0.10", "src": {"start": 9000, "end": 9005}, "dst": {"start": 9000, "end": 9005}}}

$ iptime port add "Test rule" --target 192.168.0.10 --ext 9000 --int 90 --yes
ok, rules now:
NAME        PROTO  EXTERNAL     TARGET        INTERNAL     ON
Web server  tcp    8080         192.168.0.10  80           yes
Game range  udp    27000-27010  192.168.0.20  27000-27010  no
Test rule   tcp    9000         192.168.0.10  90           yes

$ iptime port rm "Test rule" --yes
ok, rules now:
NAME        PROTO  EXTERNAL     TARGET        INTERNAL     ON
Web server  tcp    8080         192.168.0.10  80           yes
Game range  udp    27000-27010  192.168.0.20  27000-27010  no
```

`--ext` is the port on the WAN side, `--int` the port on the target (default: same as `--ext`). `--proto` is `tcp`, `udp` or `tcpudp`. `iptime port list --upnp` shows the rules programs created through UPnP; `port rm` only removes your own rules.

### dhcp

```console
$ iptime dhcp list
IP            MAC                NAME        STATE            LEASE LEFT
192.168.0.11  AA:BB:CC:00:00:02  NAS         reserved+leased  22h 13m
192.168.0.20  AA:BB:CC:00:00:03  laptop      leased           1h 46m
192.168.0.21  AA:BB:CC:00:00:04  phone       leased           53m 20s
192.168.0.30  AA:BB:CC:00:00:05  smart-plug  leased           19h 26m

$ iptime dhcp reserve aa-bb-cc-00-00-09 192.168.0.40 --name printer --dry-run
dry run, nothing sent:
POST http://127.0.0.1:8080/cgi/service.cgi
{"method": "dhcpd/reservedaddr/add", "params": {"ntag": "lan", "mac": "AA:BB:CC:00:00:09", "ip": "192.168.0.40", "desc": "printer"}}

$ iptime dhcp unreserve AA:BB:CC:00:00:09 --yes
ok: "done"
```

MACs may be written with `:` or `-`, in any case.

### remote-admin

With no argument it shows the state; `on` and `off` change it.

```console
$ iptime remote-admin
LAN admin     HTTP port 80
Remote HTTP   off, port 8080
Remote HTTPS  off, port 8443

$ iptime remote-admin on --dry-run
warning: this opens the router's admin page to the internet.
dry run, nothing sent:
POST http://127.0.0.1:8080/cgi/service.cgi
{"method": "http/config", "params": {"remotehttp_flag": true, "remotehttp_port": 8080, "commit": true}}
```

`off` turns only remote (WAN) HTTP admin off; the admin page on the LAN stays reachable. `on` uses the stored remote port unless you pass `--port`.

### firmware

```console
$ iptime firmware check
Running  16.000  (built 2026.01.01 00:00:00)
Latest   16.010
State    update available

$ iptime firmware upgrade --dry-run
dry run, nothing sent (16.000 -> 16.010):
POST http://127.0.0.1:8080/cgi/service.cgi
{"method": "firmware/upgrade/prepare", "params": {"method": "auto"}}
POST http://127.0.0.1:8080/cgi/service.cgi
{"method": "firmware/upgrade/online"}

$ iptime firmware upgrade --yes
[17:31:34] upgrade requested: 16.000 -> 16.010
[17:31:34] stage: starting
[17:31:35] stage: checking
[17:31:36] stage: downloading
[17:31:38] stage: waiting
[17:31:39] stage: writing
[17:31:42] router is rebooting (unreachable)
[17:31:45] stage: idle
firmware upgraded 16.000 -> 16.010 in 11s
```

`check` compares the running version with the newest one the router itself reports. `upgrade` uses only the vendor's own online upgrade: the router downloads the image itself (nothing is uploaded from your machine), flashes it and reboots. It sends the two calls the admin page's "upgrade now" button makes, polls the upgrade status, waits through the outage, logs in again and prints old -> new.

- **Expect an outage.** The router reboots; the network drops for a few minutes (the router reports about four minutes of flashing). Run it by hand at a quiet time, not while someone depends on the connection.
- `upgrade` asks first; `--yes` skips the question, `--dry-run` prints the two requests and sends nothing.
- `--if-available` exits 0 and prints nothing when the router is already current.
- `--wait-timeout SECONDS` (default 1800) is how long to wait for the router to come back on a new version; `--poll SECONDS` (default 10) is the status interval. If the router never comes back in time the command exits 1 and says so; check the router yourself.
- The progress lines go to stderr; with `--json` only the final result is printed.
- If the router reports a failed upgrade (`download`, `format`, `version` or `internal`), the command stops with that reason.

### reboot

`iptime reboot` asks, then reboots the router; the connection drops for a minute or two. `--dry-run` shows the request.

### call and methods

```console
$ iptime call dhcpd/reservedaddr/show lan
{
 "result": [
  {
   "mac": "AA:BB:CC:00:00:02",
   "ip": "192.168.0.11",
   "desc": "NAS"
  }
 ]
}

$ iptime methods --seen
METHOD                          KIND     STATUS  FIRMWARE  NOTE
admin/auth/info                 read     ok      16.00.0   login policy: auth mode, session timeout, captcha use/tolerance
conn/info                       read     ok      16.00.0   connection-tracking totals per LAN host
...
```

`call` prints the router's whole answer (`{"result": ...}` or `{"error": ...}`) and exits 1 on an error object. Params are JSON; a bare word such as `lan` is sent as a string. A method that is not a read needs `--write` (or `--dry-run`). `iptime methods` needs no router; `--kind read|write|danger|session` and `--seen` filter. STATUS means `ok` (called on real hardware, read-only), `absent` (the model answered "Method not found" or "Config error"), `used` (a write method that an earlier hand-written script sent to real hardware) or `bundle` (named in the admin bundle, never called by us).

### Library

```python
from iptime_cli import Router

with Router("192.168.0.1", "admin", "change-me") as router:     # logs out on exit
    for st in router.stations():                                # typed: Station
        print(st.ip, st.mac, st.name, st.link)
    print(router.call("firmware/version/latest"))               # any method; returns "result"
```

```text
192.168.0.10 AA:BB:CC:00:00:01 desktop wired
192.168.0.11 AA:BB:CC:00:00:02 nas wired
192.168.0.20 AA:BB:CC:00:00:03 laptop wireless
192.168.0.21 AA:BB:CC:00:00:04 phone wireless
192.168.0.30 AA:BB:CC:00:00:05 smart-plug wireless
16.010
```

Helpers: `product()`, `firmware()`, `system()`, `wan()`, `lan()`, `stations()`, `leases()`, `reservations()`, `wifi()`, `port_forwards()`, `remote_admin()`; writes `add_port_forward()`, `del_port_forward()`, `reserve()`, `unreserve()`, `set_remote_admin()`, `upgrade_firmware()`, `reboot()`. `call()` returns the `result` and raises `ApiError` on an error object; `call_raw()` returns the whole answer. Errors derive from `IptimeError`: `ConnectError`, `OldUiError`, `LoginError` (`CaptchaError`, `LockoutError`), `ApiError`, `UpgradeError`. `Router(..., dry_run=True)` makes every non-read call return the request instead of sending it.

## Options

| Option | Meaning |
|---|---|
| `--host`, `--user`, `--config FILE` | connection settings (see Configure) |
| `--timeout SECONDS` | per-request timeout, default 15 |
| `--insecure` | do not verify a self-signed https certificate |
| `--json` | print JSON instead of a table |
| `--show-secrets` | show Wi-Fi passwords (hidden by default) |
| `--dry-run` | for writes: print the request, send nothing |
| `-y`, `--yes` | do not ask before a write |

Exit codes: `0` ok, `1` error (router, login, API), `2` bad usage or bad params JSON.

## Errors

| You see | Meaning |
|---|---|
| `old admin UI not supported yet` | the router has no `/ui/` page or does not answer JSON; it runs the old admin UI (firmware 14.x and earlier) |
| `login failed (wrong user or password?)` | the router refused the login |
| `the router asks for a captcha` / `the router blocks logins for now` | the router wants a captcha or has blocked logins after failures; wait, or log in once in a browser |
| `cannot reach ...` | wrong address, router off, or this machine is not allowed to reach the LAN |

## Safety notes for writes

- Every write command asks first. Without a terminal it refuses unless `--yes` is given; `--dry-run` never sends.
- Read a write with `--dry-run` first, then run it.
- `remote-admin on` exposes the admin page to the internet. Use a strong password, or do not.
- `port rm` deletes by name; names are exact. `dhcp reserve` takes one MAC and one IP per call.
- `firmware upgrade` reboots the router and drops the network for a few minutes; run it by hand at a quiet time, when nobody needs the connection. Only the router's own online upgrade is used.
- Wi-Fi settings are read-only in this version.
- `iptime call` accepts a method it does not know only with `--write`.

## Tested

| What | Result |
|---|---|
| Router | one ipTIME A5004NS-M, firmware 16.00.0 (build 2026.09.16) |
| Read commands (`info`, `clients`, `wan`, `wifi`, `dhcp list`, `port list`, `remote-admin`, `firmware check`, `call`) and `firmware upgrade --dry-run` | run against that router |
| Write commands (`port add/rm`, `dhcp reserve/unreserve`, `remote-admin on/off`, `reboot`, `firmware upgrade`) | **only against the bundled fake router**, never against a real one by this package. The request bodies follow what the admin page sends. An earlier hand-written script sent the same port-forward and DHCP-reservation bodies to a real router and they worked; `remote-admin off`, `remote-admin on`, `reboot` and the two firmware-upgrade calls and their status stages were read from the admin bundle and never reached real hardware |
| Login failures | one wrong login against real hardware: the router answered `{"error": {"code": -31996, "message": "Config error"}}`. Captcha and lockout messages were not observed; those paths are only exercised by the fake router, so their wording is a guess |
| OS | macOS, Python 3.12 |
| Not tested | Linux and Windows, other models, other 16.x builds, https admin, old admin UI (refused with an error), Wi-Fi 7 / mesh models |

Other models may differ: on the tested model `system/temperature`, `wireless/mlo/info`, `port/role`, `power/status` and `fan/running` are absent.

## For AI agents

See [AGENTS.md](https://github.com/elfenomenokim/iptime-cli/blob/main/AGENTS.md). A ready-made skill is in `skill/iptime-cli/SKILL.md`.

## License

MIT.
