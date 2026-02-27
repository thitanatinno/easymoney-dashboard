"""Login module — handles authentication and initial redirect.

Pure logic: no argparse, no browser setup.
Receives an already-created Playwright ``page`` object and performs the full
login sequence, then navigates to ``redirect_url``.
"""

from playwright.sync_api import Page


def login(
    page: Page,
    url: str,
    redirect_url: str,
    username: str,
    password: str,
    username_placeholder: str = "Login Account",
    password_selector: str = "input[name='password']",
    login_button_text: str = "Login",
    wait_seconds: int = 5,
) -> None:
    """Authenticate against *url* then navigate to *redirect_url*.

    Args:
        page: Active Playwright page to drive.
        url: Login page URL.
        redirect_url: URL to navigate to after successful login.
        username: Account username.
        password: Account password.
        username_placeholder: Placeholder text of the username input.
        password_selector: CSS selector for the password input.
        login_button_text: Visible text of the submit button.
        wait_seconds: Seconds to wait after clicking login before redirecting.
    """
    def _dump_dom_state(label: str) -> None:
        """Print a JS-level snapshot of the DOM so we can diagnose blank screens."""
        print(f"\n══ DOM SNAPSHOT [{label}] ══")
        try:
            info = page.evaluate("""
                () => ({
                    readyState:       document.readyState,
                    title:            document.title,
                    bodyLen:          document.body ? document.body.innerHTML.length : -1,
                    appExists:        !!document.getElementById('app'),
                    appChildCount:    document.getElementById('app')
                                        ? document.getElementById('app').children.length : -1,
                    appInnerLen:      document.getElementById('app')
                                        ? document.getElementById('app').innerHTML.length : -1,
                    appDisplay:       document.getElementById('app')
                                        ? getComputedStyle(document.getElementById('app')).display : 'N/A',
                    appVisibility:    document.getElementById('app')
                                        ? getComputedStyle(document.getElementById('app')).visibility : 'N/A',
                    appOpacity:       document.getElementById('app')
                                        ? getComputedStyle(document.getElementById('app')).opacity : 'N/A',
                    windowW:          window.innerWidth,
                    windowH:          window.innerHeight,
                    devicePixelRatio: window.devicePixelRatio,
                    scriptErrors:     window.__lastError || null,
                })
            """)
            for k, v in info.items():
                print(f"  {k}: {v}")
        except Exception as exc:
            print(f"  [_dump_dom_state error] {exc}")

        # Print first 500 chars of #app innerHTML so we can see if it's blank
        try:
            snippet = page.evaluate("""
                () => {
                    const el = document.getElementById('app');
                    return el ? el.innerHTML.slice(0, 500) : '(no #app)';
                }
            """)
            print(f"  #app innerHTML[:500]: {snippet!r}")
        except Exception as exc:
            print(f"  [innerHTML snippet error] {exc}")
        print(f"══ END SNAPSHOT [{label}] ══\n")

    print(f"Opening: {url}")
    page.goto(url, wait_until="domcontentloaded")
    print(f"Login page loaded — URL: {page.url!r}  title: {page.title()!r}")

    print("Filling credentials...")
    page.get_by_placeholder(username_placeholder).fill(username)
    page.locator(password_selector).fill(password)
    page.get_by_role("button", name=login_button_text).click()

    print("Waiting for network idle after login...")
    try:
        page.wait_for_load_state("networkidle", timeout=wait_seconds * 1000)
        print("Network idle reached.")
    except Exception as exc:
        print(f"[WARN] wait_for_load_state(networkidle) timed out or errored: {exc}")
    print(f"After login click — URL: {page.url!r}  title: {page.title()!r}")

    print(f"Redirecting to: {redirect_url}")
    try:
        page.goto(redirect_url, wait_until="load", timeout=60_000)
    except Exception as exc:
        print(f"[WARN] goto(redirect_url) raised: {exc}")
    print(f"After goto — URL: {page.url!r}  title: {page.title()!r}")
    _dump_dom_state("after goto")

    # Hash-based SPAs (#/route) don't trigger a real load event on goto.
    # A reload forces the full page load INCLUDING the hash route rendering.
    print("Reloading to force hash-route SPA render...")
    try:
        page.reload(wait_until="load", timeout=60_000)
    except Exception as exc:
        print(f"[WARN] reload() raised: {exc}")
    print(f"After reload — URL: {page.url!r}  title: {page.title()!r}")
    _dump_dom_state("after reload")

    print("Waiting for SPA root element to be visible...")
    try:
        page.locator("#app > *").wait_for(state="visible", timeout=60_000)
        print("SPA root element is visible.")
    except Exception as exc:
        print(f"[ERROR] SPA root element never became visible: {exc}")
        _dump_dom_state("SPA root wait FAILED")
        # Also try broader selectors to understand what IS in the DOM
        for sel in ["#app", "body > *", "[id]", "main", "div"]:
            try:
                count = page.locator(sel).count()
                print(f"  selector {sel!r} count = {count}")
                if count > 0:
                    try:
                        text = page.locator(sel).first.inner_text(timeout=1000)
                        print(f"    first text[:200]: {text[:200]!r}")
                    except Exception:
                        pass
            except Exception:
                pass

    _dump_dom_state("login() complete")
