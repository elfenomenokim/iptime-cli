# Contributing to iptime-cli

Fixes and reports are welcome. You do not need to ask before opening a pull request for a bug fix.

## Before you start

- **A bug:** open an [issue](https://github.com/elfenomenokim/iptime-cli/issues/new/choose) with
  the command, the output, your router model and firmware version (`iptime info`). Do not paste a
  password, a MAC address, a public IP or a device name.
- **A new router model or firmware:** say which model, which firmware, and which commands answered.
  The tool supports the firmware 16.x admin UI only.
- **A security problem:** do not open a public issue. See [SECURITY.md](SECURITY.md).

## Set up

```sh
git clone https://github.com/elfenomenokim/iptime-cli
cd iptime-cli
PYTHONPATH=src python3 -m unittest discover -s tests
PYTHONPATH=src python3 -m iptime_cli.fake_router --port 8080   # in one shell
IPTIME_HOST=127.0.0.1:8080 IPTIME_PASSWORD=secret \
  PYTHONPATH=src python3 -m iptime_cli clients --json          # in another
```

The regression tests use the bundled fake router only. They prove the client, not a router model.

## Rules a patch must keep

- Keep the client dependency-free and compatible with Python 3.9.
- Keep the fake router and every fixture synthetic. No real address, credential, MAC address,
  device name or hostname.
- Never send a write call to real hardware while testing. Writes, remote administration, a firmware
  upgrade and a reboot need the user's exact authorization and the documented dry run.
- A method that is not in the catalog is a write, not a read, until someone records what it does.
- Wi-Fi passwords stay hidden unless the caller passes `--show-secrets`, including in `iptime call`
  output.

## What a good patch has

- **A test in `tests/test_regressions.py`** that fails without the change, or a recorded response
  in the fake router that shows the bug.
- **A line under Unreleased** in [CHANGELOG.md](CHANGELOG.md) when a user will notice.
- **The model and firmware you tested** written in the pull request, or a statement that only the
  fake router answered (the `tests` workflow runs the fake-router suite on Ubuntu, macOS and Windows
  with Python 3.9 and 3.13).

## Review

Every pull request runs an automatic DeepSeek review. Ask for another pass with `@codex review` or
`@claude review` in a comment. If a finding looks wrong, say why in the pull request.

## Licence

Contributions are licensed under the MIT licence in [LICENSE](LICENSE).
