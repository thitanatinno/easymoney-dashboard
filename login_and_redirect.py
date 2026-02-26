import argparse
import os
import time
from getpass import getpass

from playwright.sync_api import sync_playwright


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
    return p.parse_args()


def main():
    args = parse_args()
    os.makedirs(args.out_dir, exist_ok=True)

    # Credentials: prefer env, otherwise prompt
    user = os.environ.get("LOGIN_USER", "").strip()
    pw = os.environ.get("LOGIN_PASS", "")

    if not user:
        user = input("Username: ").strip()
    if not pw:
        pw = getpass("Password: ")

    chromium_path = args.chromium_path.strip() or None

    launch_args = []
    if args.fullscreen_mode == "kiosk":
        launch_args += ["--kiosk"]
    else:
        launch_args += ["--start-maximized"]

    # Some Pi-friendly flags (optional but often helps)
    launch_args += [
        "--no-default-browser-check",
        "--no-first-run",
        "--disable-infobars",
    ]

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=bool(args.headless),
            executable_path=chromium_path,
            args=launch_args,
        )

        # viewport=None => use full available window size
        context = browser.new_context(viewport=None)
        page = context.new_page()

        print(f"Opening: {args.url}")
        page.goto(args.url, wait_until="domcontentloaded")

        print("Filling credentials...")
        page.get_by_placeholder(args.username_placeholder).fill(user)
        page.locator(args.password_selector).fill(pw)
        page.get_by_role("button", name=args.login_button_text).click()

        print(f"Waiting {args.wait_seconds}s after login...")
        time.sleep(args.wait_seconds)

        print(f"Redirecting to: {args.redirect_url}")
        page.goto(args.redirect_url, wait_until="domcontentloaded")

        screenshot_path = os.path.join(args.out_dir, "after_redirect.png")
        page.screenshot(path=screenshot_path, full_page=True)
        print(f"Screenshot saved: {screenshot_path}")

        if args.keep_open and not args.headless:
            input("Done. Press Enter to close the browser...")

        context.close()
        browser.close()


if __name__ == "__main__":
    main()
