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
    print(f"Opening: {url}")
    page.goto(url, wait_until="domcontentloaded")

    print("Filling credentials...")
    page.get_by_placeholder(username_placeholder).fill(username)
    page.locator(password_selector).fill(password)
    page.get_by_role("button", name=login_button_text).click()

    print("Waiting for network idle after login...")
    page.wait_for_load_state("networkidle", timeout=wait_seconds * 1000)

    print(f"Redirecting to: {redirect_url}")
    page.goto(redirect_url, wait_until="domcontentloaded")
