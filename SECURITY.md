# Security policy

## Supported versions

Security fixes go into the latest release. Upgrade before reporting, in case the problem is
already fixed.

| Version | Supported |
| --- | --- |
| 0.1.3 | Yes |
| Older | No |

## Reporting a vulnerability

Report it privately, not in a public issue: use the
[Report a vulnerability](https://github.com/elfenomenokim/iptime-cli/security/advisories/new) form
on the repository's Security tab.

Include the command, the version (`iptime --version`), the router model and firmware, and what an
attacker could do with the result. You get a reply within a few days. Say how you want to be
credited if you want a name in the release note. Do not include a real password, MAC address or
public address in the report.

## In scope

- A password, Wi-Fi key or other credential printed or logged without `--show-secrets`, including
  in `iptime call` output, an error message or a debug log.
- A write request sent for a command that is documented as read-only, or a write sent while
  `--dry-run` is set.
- A method that is not in the catalog treated as a read, so it skips the write guard.
- A credential written to a file with wider permissions than the documented config file, or
  written into a command argument.
- Retrying a login after the router answered with a captcha, a lockout or a rejected password.

## Not a vulnerability

- Reading or changing your own router with the credentials you supplied. That is what the tool
  does.
- An unofficial API that a firmware update changed. Open an issue; it is a bug, not a
  vulnerability.
- A password you put on the command line yourself, where your shell history records it. Use the
  config file or the environment variable.

## Disclosure

Once a fix is released, the advisory is published with credit to the reporter unless they prefer
otherwise.
