# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses `MAJOR.MINOR.PATCH`.

## [0.1.3] - 2026-11-18

### Fixed

- `iptime call` hides Wi-Fi passwords unless `--show-secrets` is set.
- A method that is not in the catalog is treated as a write, so it cannot skip the write guard with
  a name ending in `/get`, `/show` or `/config`.
- A rejected re-login during a firmware upgrade stops the upgrade and reports the error instead of
  polling until the timeout.
- `remote-admin off` clears remote HTTPS administration as well as HTTP.

## [0.1.2] - 2026-11-18

### Changed

- Documentation release: the README, the Korean README, the demo recording and the social preview
  were rewritten, and the version moved with them. No behaviour change.

## [0.1.1] - 2026-11-17

### Fixed

- The config file is found in the Windows location, and the false permission warning is gone.

## [0.1.0] - 2026-11-17

### Added

- Command-line and Python client for the firmware 16.x admin UI: clients, DHCP reservations, port
  forwards, Wi-Fi and WAN status, remote administration, firmware check.
- `iptime methods` lists every known API method with its recorded kind and status.
- Bundled fake router, so the client can be exercised without hardware.
- Wi-Fi passwords hidden by default.
