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
    p.add_argument("--fullscreen-mode", choices=["kiosk", "maximized"], default="kiosk")
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
        # Stability / rendering fixes for Raspberry Pi (ARM)
        # NOTE: do NOT add --disable-software-rasterizer here — on ARM without
        # a GPU, software rasterizer is the only rendering path; disabling it
        # causes a completely blank (white) screen.
        "--no-sandbox",
        "--disable-dev-shm-usage",
        "--disable-gpu",
        "--use-gl=swiftshader",           # force software renderer (SwiftShader)
        "--ignore-gpu-blocklist",
        "--disable-features=VizDisplayCompositor",
    ]
    if args.fullscreen_mode == "kiosk":
        launch_args += ["--kiosk"]

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=bool(args.headless),
            executable_path=chromium_path,
            args=launch_args,
        )

        context = browser.new_context(viewport=None)
        page = context.new_page()

        # Fix B — log JS errors and console errors to help diagnose blank screen
        page.on("pageerror", lambda exc: print(f"[PAGE JS ERROR] {exc}"))
        page.on("console", lambda msg: print(f"[CONSOLE {msg.type.upper()}] {msg.text}") if msg.type == "error" else None)

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
        page.bring_to_front()

        screenshot_path = os.path.join(args.out_dir, "after_redirect.png")
        page.screenshot(path=screenshot_path, full_page=True)
        print(f"Screenshot saved: {screenshot_path}")

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
