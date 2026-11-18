---
name: iptime-cli
description: Look at or change a home ipTIME router (new admin UI, firmware 16.x) from the terminal - connected devices, DHCP reservations, port forwarding, Wi-Fi, WAN, remote admin. Use when the user asks who is on the network, to open a port, to reserve an IP, or to check the router.
---

# iptime-cli

Unofficial CLI for ipTIME routers with the new admin UI (firmware 16.x). Install with `pipx install iptime-cli`; address and credentials come from `IPTIME_HOST`, `IPTIME_USER`, `IPTIME_PASSWORD` or `~/.config/iptime-cli/config`.

## Reads (safe)

```console
iptime info --json
iptime clients --json
iptime wan --json
iptime wifi --json
iptime port list --json
iptime dhcp list --json
iptime remote-admin --json
iptime firmware check --json
```

## Writes (change the real router)

`iptime port add NAME --target IP --ext PORT [--int PORT] [--proto tcp|udp|tcpudp]`, `iptime port rm NAME`, `iptime dhcp reserve MAC IP [--name N]`, `iptime dhcp unreserve MAC`, `iptime remote-admin on|off`, `iptime firmware upgrade`, `iptime reboot`.

Always: run with `--dry-run`, show the request to the user, get a yes, run again with `--yes`, then read the state back. `firmware upgrade` and `reboot` drop the network for minutes. Never run `reboot`, `firmware upgrade` or `remote-admin on` unless the user asked for exactly that.

## Cautions

- Logging in can end the user's open browser admin session.
- Wi-Fi passwords stay hidden unless `--show-secrets`; do not print them.
- Do not loop on a failed login (captcha / lockout risk).
- Do not copy the user's real MACs, IPs or device names into public text.

Full instructions: `AGENTS.md`.
