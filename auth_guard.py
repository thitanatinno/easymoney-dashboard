"""Auth-guard module — detects session expiry and re-triggers login when needed.

Pure logic: no argparse, no browser setup, no env reads.
Receives an already-open Playwright ``page`` and login kwargs, checks whether
the page is showing a login form, and re-authenticates if so.
"""

from typing import Any, Dict

from playwright.sync_api import Page

import login as login_module


def needs_relogin(
    page: Page,
    username_placeholder: str = "Login Account",
    password_selector: str = "input[name='password']",
    login_button_text: str = "Login",
    timeout_ms: int = 2000,
) -> bool:
    """Return True if the page is currently showing a login form.

    Uses short timeouts so it fails fast when the session is healthy.

    Args:
        page: Active Playwright page to inspect.
        username_placeholder: Placeholder text of the username input.
        password_selector: CSS selector for the password input.
        login_button_text: Visible text of the submit button.
        timeout_ms: Max ms to wait for each element visibility check.
    """
    try:
        page.get_by_placeholder(username_placeholder).wait_for(state="visible", timeout=timeout_ms)
        page.locator(password_selector).wait_for(state="visible", timeout=timeout_ms)
        page.get_by_role("button", name=login_button_text).wait_for(state="visible", timeout=timeout_ms)
        return True
    except Exception:
        return False


def ensure_logged_in(page: Page, login_kwargs: Dict[str, Any]) -> None:
    """Re-login if the page is currently showing the login form.

    Passes through all kwargs directly to ``login.login()``, so the caller
    must supply at minimum: url, redirect_url, username, password.

    Args:
        page: Active Playwright page to inspect and potentially re-authenticate.
        login_kwargs: Dict of keyword arguments forwarded to ``login.login()``.
                      Must include: url, redirect_url, username, password.
                      Optional: username_placeholder, password_selector,
                                login_button_text, wait_seconds.
    """
    if needs_relogin(
        page,
        username_placeholder=login_kwargs.get("username_placeholder", "Login Account"),
        password_selector=login_kwargs.get("password_selector", "input[name='password']"),
        login_button_text=login_kwargs.get("login_button_text", "Login"),
    ):
        print(f"[auth_guard] Session expired on {page.url} — re-logging in...")
        login_module.login(page=page, **login_kwargs)
        print("[auth_guard] Re-login complete.")
    else:
        print(f"[auth_guard] Session OK on {page.url}")
