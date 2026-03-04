"""Entry point — parses args, sets up Playwright, coordinates login and tab switching.

Environment variables:
    LOGIN_USER          Account username (prompted if absent).
    LOGIN_PASS          Account password (prompted if absent).
    TAB_SWITCH          "true" | "false" — whether to run tab cycling after login.
                        Defaults to "true".
"""

import argparse
import os
import time
from getpass import getpass

from playwright.sync_api import sync_playwright

import login as login_module
import tab_switcher as tab_switcher_module


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--url", required=True)
    p.add_argument("--redirect-url", required=True)
    p.add_argument("--username-placeholder", default="Login Account")
    p.add_argument("--password-selector", default="input[name='password']")
    p.add_argument("--login-button-text", default="Login")
    p.add_argument("--wait-seconds", type=int, default=5)
    p.add_argument("--headless", type=int, choices=[0, 1], default=0)
    p.add_argument("--chromium-path", default="")
    p.add_argument("--out-dir", required=True)
    p.add_argument("--keep-open", type=int, choices=[0, 1], default=1)
    # Tab-switching options (only used when TAB_SWITCH env var is "true")
    p.add_argument(
        "--extra-tab-urls",
        nargs="*",
        default=[],
        metavar="URL",
        help="Additional URLs to open as extra tabs for cycling.",
    )
    p.add_argument(
        "--tab-switch-interval",
        type=int,
        default=300,
        metavar="SECONDS",
        help="Seconds between tab switches (default: 300).",
    )
    return p.parse_args()


def apply_fullscreen(context, page) -> None:
    # """Try all three fullscreen strategies in sequence (CDP → F11 → JS requestFullscreen)."""
    # # 1. CDP
    # try:
    #     cdp = context.new_cdp_session(page)
    #     try:
    #         result = cdp.send("Browser.getWindowForTarget")
    #         window_id = result["windowId"]
    #         cdp.send(
    #             "Browser.setWindowBounds",
    #             {"windowId": window_id, "bounds": {"windowState": "fullscreen"}},
    #         )
    #         print("CDP fullscreen applied.")
    #     finally:
    #         cdp.detach()
    # except Exception as exc:
    #     print(f"[WARN] CDP fullscreen failed (non-fatal): {exc}")

    # 2. F11
    try:
        page.keyboard.press("F11")
        print("F11 sent — browser fullscreen triggered.")
    except Exception as exc:
        print(f"[WARN] F11 fullscreen failed (non-fatal): {exc}")

    # 3. Kiosk via JS requestFullscreen
    try:
        page.evaluate("document.documentElement.requestFullscreen()")
        print("JS requestFullscreen (kiosk-style) applied.")
    except Exception as exc:
        print(f"[WARN] JS requestFullscreen failed (non-fatal): {exc}")


def main():
    args = parse_args()

    # Read TAB_SWITCH env var — defaults to "true"
    tab_switch_enabled = os.environ.get("TAB_SWITCH", "true").strip().lower() == "true"

    os.makedirs(args.out_dir, exist_ok=True)

    # Credentials: prefer env, otherwise prompt
    user = os.environ.get("LOGIN_USER", "").strip()
    pw = os.environ.get("LOGIN_PASS", "")
    if not user:
        user = input("Username: ").strip()
    if not pw:
        pw = getpass("Password: ")

    chromium_path = args.chromium_path.strip() or None

    launch_args = [
        # # Stability / rendering fixes for Raspberry Pi (ARM)
        # # NOTE: do NOT add --disable-software-rasterizer here — on ARM without
        # # a GPU, software rasterizer is the only rendering path; disabling it
        # # causes a completely blank (white) screen.
        # #
        # # NOTE: do NOT add --disable-features=VizDisplayCompositor here either.
        # # VizDisplayCompositor is responsible for pushing rendered frames to the
        # # physical display.  Disabling it causes the page to render correctly in
        # # Playwright's internal buffer (screenshots work) but nothing is ever
        # # composited to the screen → completely white physical display.
        # "--no-sandbox",
        # "--disable-dev-shm-usage",
        # "--disable-gpu",
        # "--use-gl=swiftshader",           # force software renderer (SwiftShader)
        # "--ignore-gpu-blocklist",
        # "--force-color-profile=srgb",     # stable colour space for Pi framebuffer
    ]
    print("Applying fullscreen — window size 1920x1080.")
    launch_args += ["--window-size=1920,1080"]

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=bool(args.headless),
            executable_path=chromium_path,
            args=launch_args,
        )

        context = browser.new_context(viewport={"width": 1920, "height": 1080})
        page = context.new_page()

        # ── Diagnostic listeners ──────────────────────────────────────────────
        page.on("pageerror", lambda exc: print(f"[PAGE JS ERROR] {exc}"))

        # ALL console levels (not just errors) — warnings / logs often reveal why SPA is blank
        def _log_console(msg):
            level = msg.type.upper()
            print(f"[CONSOLE {level}] {msg.text}")
            # also print any attached JS values
            for i, arg in enumerate(msg.args):
                try:
                    print(f"  arg[{i}]: {arg.json_value()}")
                except Exception:
                    pass
        page.on("console", _log_console)

        # Failed network requests (404, net::ERR_*, etc.)
        page.on(
            "requestfailed",
            lambda req: print(
                f"[REQUEST FAILED] {req.method} {req.url}  "
                f"failure={req.failure}"
            ),
        )

        # Non-2xx HTTP responses (bundle missing, API 401/403, etc.)
        def _log_bad_response(resp):
            if resp.status >= 400:
                print(f"[HTTP {resp.status}] {resp.request.method} {resp.url}")
        page.on("response", _log_bad_response)

        # --- Fullscreen (pre-login) ---
        apply_fullscreen(context, page)

        # --- Login ---
        login_module.login(
            page=page,
            url=args.url,
            redirect_url=args.redirect_url,
            username=user,
            password=pw,
            username_placeholder=args.username_placeholder,
            password_selector=args.password_selector,
            login_button_text=args.login_button_text,
            wait_seconds=args.wait_seconds,
        )

        # Give the SPA a moment to finish rendering after networkidle
        time.sleep(2)
        print("Bringing page to front...")
        page.bring_to_front()

        # --- Tab switching ---
        if tab_switch_enabled:
            print("TAB_SWITCH=true — starting tab switcher.")
            login_kwargs = dict(
                url=args.url,
                redirect_url=args.redirect_url,
                username=user,
                password=pw,
                username_placeholder=args.username_placeholder,
                password_selector=args.password_selector,
                login_button_text=args.login_button_text,
                wait_seconds=args.wait_seconds,
            )
            try:
                tab_switcher_module.run_tab_switcher(
                    context=context,
                    pages=[page],
                    extra_urls=args.extra_tab_urls,
                    login_kwargs=login_kwargs,
                    interval_seconds=args.tab_switch_interval,
                )
            except KeyboardInterrupt:
                print("\nTab switcher stopped by user.")
        else:
            print("TAB_SWITCH=false — skipping tab switcher.")
            if args.keep_open and not args.headless:
                input("Done. Press Enter to close the browser...")

        context.close()
        browser.close()


if __name__ == "__main__":
    main()
