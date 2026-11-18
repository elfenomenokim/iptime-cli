"""Regression tests for the Codex review fixes. Run from the repo root:

    PYTHONPATH=src python3 -m unittest discover -s tests -v

Everything runs against the bundled fake router; no real router is touched.
"""
from __future__ import annotations

import contextlib
import io
import os
import sys
import threading
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from iptime_cli import cli
from iptime_cli.catalog import classify
from iptime_cli.client import CaptchaError, Router
from iptime_cli.fake_router import FakeServer


def serve(**kwargs) -> tuple[FakeServer, str]:
    server = FakeServer(("127.0.0.1", 0), **kwargs)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, f"127.0.0.1:{server.server_address[1]}"


def run_cli(argv: list[str]) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    old = os.environ.get("IPTIME_PASSWORD")
    os.environ["IPTIME_PASSWORD"] = "secret"
    try:
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = cli.main(argv)
    finally:
        if old is None:
            os.environ.pop("IPTIME_PASSWORD", None)
        else:
            os.environ["IPTIME_PASSWORD"] = old
    return code, out.getvalue(), err.getvalue()


class TestCallMasksPasswords(unittest.TestCase):
    """`iptime call` must not print Wi-Fi passwords unless --show-secrets."""

    def setUp(self):
        self.server, host = serve()
        self.addCleanup(self.server.shutdown)
        self.base = ["--host", host, "--user", "admin"]

    def test_system_info_call_masks_password(self):
        code, out, _ = run_cli(self.base + ["call", "system/info"])
        self.assertEqual(code, 0)
        self.assertIn('"password": "********"', out)
        self.assertNotIn("example-wifi-key", out)

    def test_bss_show_call_masks_password(self):
        code, out, _ = run_cli(self.base + ["call", "wireless/bss/show"])
        self.assertEqual(code, 0)
        self.assertNotIn("example-wifi-key", out)

    def test_show_secrets_unmasks(self):
        _, out, _ = run_cli(self.base + ["call", "system/info", "--show-secrets"])
        self.assertIn("example-wifi-key", out)

    def test_json_mode_masks_too(self):
        _, out, _ = run_cli(self.base + ["call", "wireless/bss/show", "--json"])
        self.assertNotIn("example-wifi-key", out)


class TestUnknownMethodCountsAsWrite(unittest.TestCase):
    """Only methods from the admin bundle/observed list may classify as reads."""

    def test_unknown_suffixes_are_writes(self):
        for name in ("unregistered/info", "unregistered/show", "unregistered/get",
                     "unregistered/config", "wireless/bogus/list"):
            self.assertEqual(classify(name), "write", name)

    def test_known_reads_still_read(self):
        for name in ("system/info", "wireless/bss/show", "dhcpd/lease/show",
                     "network/interface/lan/config"):
            self.assertEqual(classify(name), "read", name)

    def test_call_refuses_unknown_without_write(self):
        server, host = serve()
        self.addCleanup(server.shutdown)
        code, _, err = run_cli(["--host", host, "--user", "admin", "call", "unregistered/info"])
        self.assertEqual(code, 1)
        self.assertIn("not a read", err)
        self.assertEqual(server.calls, [])          # nothing was sent

    def test_call_unknown_dry_run_sends_nothing(self):
        server, host = serve()
        self.addCleanup(server.shutdown)
        code, out, _ = run_cli(["--host", host, "--user", "admin",
                                "call", "unregistered/info", "--dry-run"])
        self.assertEqual(code, 0)
        self.assertIn("dry run", out)
        self.assertEqual(server.calls, [])


class TestUpgradeStopsOnRejectedRelogin(unittest.TestCase):
    """A refused reauthentication during the firmware poll must abort at once."""

    def test_captcha_after_reboot_stops_polling(self):
        server, host = serve()
        self.addCleanup(server.shutdown)

        def flip_to_captcha():
            while server.state["up_stage"] is None:
                time.sleep(0.02)
            server.captcha = True

        threading.Thread(target=flip_to_captcha, daemon=True).start()
        router = Router(host, "admin", "secret", timeout=5)
        started = time.monotonic()
        with self.assertRaises(CaptchaError):
            router.upgrade_firmware(wait_timeout=30, poll=0.2)
        self.assertLess(time.monotonic() - started, 15, "must not poll until the timeout")
        # only the initial login plus the single refused reauthentication may
        # reach the router: the rejected login must not be retried in a loop
        logins = [c for c in server.calls if c.get("method") == "session/login"]
        self.assertLessEqual(len(logins), 2, f"login retried in a loop: {len(logins)} attempts")


class TestRemoteAdminOffClosesHttps(unittest.TestCase):
    def test_off_clears_both_flags(self):
        server, host = serve()
        self.addCleanup(server.shutdown)
        server.state["http"]["remotehttps_flag"] = True
        router = Router(host, "admin", "secret", timeout=5)
        self.addCleanup(router.close)
        router.set_remote_admin(False)
        self.assertFalse(server.state["http"]["remotehttp_flag"])
        self.assertFalse(server.state["http"]["remotehttps_flag"])

    def test_on_keeps_http_flag(self):
        server, host = serve()
        self.addCleanup(server.shutdown)
        router = Router(host, "admin", "secret", timeout=5)
        self.addCleanup(router.close)
        router.set_remote_admin(True)
        self.assertTrue(server.state["http"]["remotehttp_flag"])


if __name__ == "__main__":
    unittest.main()
