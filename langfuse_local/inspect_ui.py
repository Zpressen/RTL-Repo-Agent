"""Log into the local demo and save real screenshots (requires Playwright)."""

import json
import os
from pathlib import Path

from dotenv import dotenv_values
from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent


def main() -> None:
    env = dotenv_values(HERE / ".env")
    report = json.loads((HERE / "artifacts/latest-run.json").read_text())
    base_url = os.environ.get("LANGFUSE_BASE_URL", "http://localhost:3000")
    project = env["LANGFUSE_INIT_PROJECT_ID"]
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1600, "height": 1050}, device_scale_factor=1)
        page.set_default_timeout(60000)
        page.goto(f"{base_url}/auth/sign-in", wait_until="domcontentloaded")
        page.locator('input[name="email"]').fill(env["LANGFUSE_INIT_USER_EMAIL"])
        page.locator('input[name="password"]').fill(env["LANGFUSE_INIT_USER_PASSWORD"])
        page.get_by_role("button", name="Sign in", exact=True).click()
        page.wait_for_url(lambda url: "/auth/sign-in" not in url, timeout=45000)
        # Wait for the app to render the authenticated user before navigating.
        page.get_by_text("Local Demo", exact=True).first.wait_for()
        print("Signed into local Langfuse")
        page.goto(f"{base_url}/project/{project}/observations", wait_until="domcontentloaded")
        page.get_by_text("demo-rag-success", exact=True).first.wait_for()
        page.screenshot(path=str(HERE / "artifacts/observations.png"), full_page=True)
        (HERE / "artifacts/observations-ui.txt").write_text(page.locator("body").inner_text())
        print("Saved observations screenshot:", page.url)
        for trace in report["traces"]:
            page.goto(trace["trace_url"], wait_until="domcontentloaded")
            page.get_by_text("retrieve-documents", exact=True).first.wait_for()
            # Let the detail panels finish rendering before capturing them.
            page.wait_for_timeout(1500)
            page.screenshot(path=str(HERE / f"artifacts/trace-{trace['scenario']}.png"), full_page=True)
            text = page.locator("body").inner_text()
            (HERE / f"artifacts/trace-{trace['scenario']}-ui.txt").write_text(text)
            assert "retrieve-documents" in text
            print("Viewed trace:", trace["scenario"], page.url)
        browser.close()


if __name__ == "__main__":
    main()
