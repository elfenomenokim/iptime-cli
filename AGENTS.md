# AGENTS.md — iptime-cli

Instructions for an AI agent asked to look at or change an ipTIME router (new admin UI, firmware 16.x) from a terminal.

## Set up for a user

Goal: the user can run `iptime info` against their own ipTIME router. Run these steps in order.

1. Check what is present.
   - `uv --version` prints a version. If not: `curl -LsSf https://astral.sh/uv/install.sh | sh`, then open a new shell or `export PATH="$HOME/.local/bin:$PATH"`.
   - Ask which router model and firmware the user has. Only the new admin UI (firmware 16.x) works; `old admin UI not supported yet` means stop and say so.
2. Install: `uv tool install iptime-cli` (no other dependency, Python 3.9+; uv fetches Python itself). `iptime --version` prints `0.1.4` or newer.
3. Rehearse on the bundled fake router before touching hardware:
   `uvx --from iptime-cli python -m iptime_cli.fake_router --port 8089 &`, then
   `IPTIME_HOST=127.0.0.1:8089 IPTIME_USER=admin IPTIME_PASSWORD=secret iptime info` prints `Model            ipTIME FAKE-1000`. Stop the fake router afterwards.
4. Only the person can supply these. Ask exactly: "공유기 관리 주소(보통 192.168.0.1)와 관리자 아이디, 비밀번호를 알려주세요. 지금 공유기 관리 화면을 브라우저에 열어 두셨다면 로그인이 풀릴 수 있으니 닫아 주세요."
   Save them without printing the password: `IPTIME_HOST`, `IPTIME_USER` as environment variables, and the password in `~/.config/iptime-cli/config` (`password = ...`, `chmod 600`). Never put it in a command line, a commit or a message.
5. Prove it, read-only: `iptime info --json` exits 0 and prints one JSON object with `product` and `firmware`. Then `iptime clients` lists the user's devices.
6. If it fails, in this order:
   - `error: cannot reach http://...`: wrong address, or the user is not on the router's network. Ask the user; do not scan the network.
   - `error: login failed: ...`: wrong user or password. Stop after one try (a captcha or login block follows repeated failures) and ask the user to check by logging in from a browser.
   - `old admin UI not supported yet`: firmware older than 16.x. The tool cannot help.
   - HTTPS router with a self-signed certificate: add `--insecure` only after the user agrees.
7. Writes (`port add`, `dhcp reserve`, `remote-admin`, `reboot`, `firmware upgrade`) are not part of setup; see "Writes: always dry-run first" below.

## Repository work

- CLI package: `src/iptime_cli/`; user and protocol notes: `skill/iptime-cli/SKILL.md`.
- Run from this directory with `python -m iptime_cli --help` or `python -m iptime_cli <command>`.
- Try read commands against the bundled fake router: `python -m iptime_cli.fake_router --port 8080`, then set `IPTIME_HOST=127.0.0.1:8080` and `IPTIME_PASSWORD=secret` in another shell.
- Install a local checkout with `python -m pip install -e .`; the executable is `iptime`.
- No lint command is configured in this repository. Run the regression tests with
  `PYTHONPATH=src python3 -m unittest discover -s tests` (they use the bundled fake router only).
  Do not claim router-model coverage from the fake server.
- Keep the client dependency-free and compatible with Python 3.9. Use type hints and the existing `argparse` command structure.
- Keep fake-router data synthetic. Never add a real router address, credential, MAC address, device name or hostname.
- Never send write calls to real hardware while testing. Writes, remote administration, firmware upgrade and reboot require the user’s exact authorization and the dry-run procedure below.

## When to use it

Use it for: who is connected, which IP a device has, reserving a DHCP address, opening or closing a port forward, checking Wi-Fi/WAN/firmware, switching remote (WAN) admin off.

Do not use it when the router shows an old admin page (firmware 14.x and earlier; the tool answers `old admin UI not supported yet`), for another brand, or to change Wi-Fi settings (read-only here).

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

## Code Review Rules

A change is a real defect when it:

- lets a write method run without `--yes`, or makes `--dry-run` send the change.
- puts a flag, JSON field or exit code out of step with the README, or makes a read print more than one JSON value.
- loses the `error: ...` stderr line or the exit code 1 on failure.
- adds a runtime dependency, or uses syntax newer than Python 3.9.
- commits a real router address, credential, MAC address, device name or hostname.
- prints a Wi-Fi password without `--show-secrets`, or retries a failed login in a loop.
- treats an unknown API method as a read.

Not defects: wording, formatting, comment style, requested extra tests, or a renamed helper.
