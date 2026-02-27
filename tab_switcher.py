"""Tab-switcher module — opens extra tabs and cycles between all tabs.

Pure logic: no argparse, no browser setup, no env reads.
Receives an existing Playwright ``context`` and a list of already-open
``pages``, opens any additional URLs as new tabs, then loops indefinitely,
bringing each tab to the front in turn and sleeping ``interval_seconds``
between switches.

Before each tab is brought to the front, ``auth_guard.ensure_logged_in``
is called so a re-login is triggered transparently if the session expired.
"""

import time
from datetime import datetime
from typing import Any, Dict, List

from playwright.sync_api import BrowserContext, Page

import auth_guard


def run_tab_switcher(
    context: BrowserContext,
    pages: List[Page],
    extra_urls: List[str],
    login_kwargs: Dict[str, Any],
    interval_seconds: int = 300,
) -> None:
    """Open extra tabs then cycle between all tabs forever.

    Before each tab is brought to the front the auth guard checks whether
    the session has expired and re-authenticates if necessary (Option A).

    The caller is expected to wrap this in a ``try/except KeyboardInterrupt``
    so Ctrl-C can shut down cleanly.

    Args:
        context: Active Playwright browser context used to open new pages.
        pages: List of already-open pages (at minimum the post-login page).
        extra_urls: Additional URLs to open as new tabs before cycling starts.
        login_kwargs: Keyword arguments forwarded to ``login.login()`` when a
                      re-login is required.  Must contain at minimum: url,
                      redirect_url, username, password.
        interval_seconds: Seconds each tab stays in front before switching.
    """
    # Open extra tabs
    for url in extra_urls:
        print(f"Opening extra tab: {url}")
        new_page = context.new_page()
        new_page.goto(url, wait_until="domcontentloaded")
        pages.append(new_page)

    total = len(pages)
    print(f"Tab switcher started — {total} tab(s), interval {interval_seconds}s. Ctrl-C to stop.")

    index = 0
    while True:
        page = pages[index]
        ts = datetime.now().strftime("%F %T")
        print(f"[{ts}] Switching to tab {index + 1}/{total}: {page.url}")
        auth_guard.ensure_logged_in(page, login_kwargs)
        page.bring_to_front()
        time.sleep(interval_seconds)
        index = (index + 1) % total
