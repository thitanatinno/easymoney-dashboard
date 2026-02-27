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
        page.goto(redirect_url, wait_until="domcontentloaded", timeout=60_000)
    except Exception as exc:
        print(f"[WARN] goto(redirect_url) raised: {exc}")
    print(f"After goto — URL: {page.url!r}  title: {page.title()!r}")
    _dump_dom_state("after goto")

    # Wait for the SPA's session-check API calls (getGlobalUserInfo, getPublicKey, etc.)
    # to complete BEFORE inspecting the DOM.  Calling page.reload() here would abort
    # those in-flight requests, causing the Vue auth guard to fail and redirect back
    # to /login — which is the root cause of the white screen.
    print("Waiting for network idle after redirect (letting SPA auth settle)...")
    try:
        page.wait_for_load_state("networkidle", timeout=30_000)
        print("Network idle after redirect.")
    except Exception as exc:
        print(f"[WARN] networkidle after redirect timed out: {exc}")
    print(f"After networkidle — URL: {page.url!r}  title: {page.title()!r}")

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
