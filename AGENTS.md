# AGENTS.md — iptime-cli

Instructions for an AI agent asked to look at or change an ipTIME router (new admin UI, firmware 16.x) from a terminal.

## Repository work

- CLI package: `src/iptime_cli/`; user and protocol notes: `skill/iptime-cli/SKILL.md`.
- Run from this directory with `python -m iptime_cli --help` or `python -m iptime_cli <command>`.
- Try read commands against the bundled fake router: `python -m iptime_cli.fake_router --port 8080`, then set `IPTIME_HOST=127.0.0.1:8080` and `IPTIME_PASSWORD=secret` in another shell.
- Install a local checkout with `python -m pip install -e .`; the executable is `iptime`.
- No test or lint command is configured in this repository. Do not claim router-model coverage from the fake server.
- Keep the client dependency-free and compatible with Python 3.9. Use type hints and the existing `argparse` command structure.
- Keep fake-router data synthetic. Never add a real router address, credential, MAC address, device name or hostname.
- Never send write calls to real hardware while testing. Writes, remote administration, firmware upgrade and reboot require the user’s exact authorization and the dry-run procedure below.

## When to use it

Use it for: who is connected, which IP a device has, reserving a DHCP address, opening or closing a port forward, checking Wi-Fi/WAN/firmware, switching remote (WAN) admin off.

Do not use it when the router shows an old admin page (firmware 14.x and earlier; the tool answers `old admin UI not supported yet`), for another brand, or to change Wi-Fi settings (read-only here).

## Install and configure

```console
$ pipx install iptime-cli        # or: uvx iptime-cli ...
$ export IPTIME_HOST=192.168.0.1 IPTIME_USER=admin IPTIME_PASSWORD=...
```

The password may also live in `~/.config/iptime-cli/config` (`password = ...`, mode 0600). Never put it in a command line, a commit or a message. Ask the user for the address and credentials if they are not already configured.

## Use

```console
$ iptime info --json            # model, firmware, latest firmware
$ iptime clients --json         # every device: ip, mac, name, wired/wireless, lease
$ iptime port list --json
$ iptime dhcp list --json
$ iptime methods --json         # every known API method, kind and status
$ iptime call <method> [params-json]
```

Every read command takes `--json` and prints one JSON value. On failure the exit code is 1 and stderr has `error: ...`.

## Writes: always dry-run first

`port add|rm`, `dhcp reserve|unreserve`, `remote-admin on|off`, `firmware upgrade`, `reboot`, and `call` of any method that is not a read change the real router.

1. Run the command with `--dry-run` and read the printed request.
2. Show it to the user and get a yes for that exact change.
3. Run it again with `--yes` instead of `--dry-run`, then read it back (`port list`, `dhcp list`, `remote-admin`).

`iptime firmware check --json` is a read. `firmware upgrade` reboots the router and drops the network for a few minutes (a person should run it by hand at a quiet time; never schedule it). Do not run `reboot`, `firmware upgrade` or `remote-admin on` without the user asking for exactly that. `remote-admin on` opens the admin page to the internet.

## Things to know

- Logging in can end a browser admin session the user has open. Say so before you connect to a router someone may be using.
- Wi-Fi passwords are hidden unless `--show-secrets` is given. Do not print them into logs or messages.
- Do not retry a failed login in a loop; the router can ask for a captcha or block logins. Stop and report the error text.
- `iptime call` refuses methods that are not reads unless `--write` is given; use `iptime methods --kind write` to see them. Unknown methods count as writes.
- Do not paste real MAC addresses, IPs or device names of the user's network into public places.

## Verify

1. The command exited 0.
2. For a write: read the state again and check the change is there.
3. If the router was unreachable, say so; do not guess its state.
