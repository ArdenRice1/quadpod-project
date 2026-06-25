#!/usr/bin/env python3
import argparse
import json
import statistics
import time
from pathlib import Path

from playwright.sync_api import sync_playwright


def main():
    parser = argparse.ArgumentParser(description="Render and measure the Quadpod web UI.")
    parser.add_argument("--base-url", default="http://127.0.0.1:5050")
    parser.add_argument("--output-dir", default="artifacts/ui")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    report = {"pages": [], "performance_ms": {}, "console_errors": []}

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        for name, width, height in [
            ("mobile", 390, 844),
            ("desktop", 1440, 1000),
        ]:
            page = browser.new_page(viewport={"width": width, "height": height})
            page.on(
                "console",
                lambda message: report["console_errors"].append(message.text)
                if message.type == "error"
                else None,
            )
            response = page.goto(f"{args.base_url}/setup-check", wait_until="networkidle")
            closed = page.locator("details[open]").count() == 0
            overflow = page.evaluate(
                "() => document.documentElement.scrollWidth > document.documentElement.clientWidth"
            )
            summaries = page.locator(".tool-panel summary").all()
            summary_heights = [round(item.bounding_box()["height"], 1) for item in summaries]

            page.locator("#networkPanel summary").click()
            page.wait_for_timeout(250)
            page.locator("#calibrationPanel summary").click()
            page.wait_for_timeout(250)
            page.screenshot(path=output_dir / f"setup-{name}.png", full_page=True)

            report["pages"].append(
                {
                    "name": name,
                    "status": response.status if response else None,
                    "collapsed_by_default": closed,
                    "horizontal_overflow": overflow,
                    "summary_heights": summary_heights,
                }
            )
            page.close()

        page = browser.new_page(viewport={"width": 390, "height": 844})
        page.goto(f"{args.base_url}/archive", wait_until="networkidle")
        page.screenshot(path=output_dir / "archive-mobile.png", full_page=True)
        report["pages"].append(
            {
                "name": "archive-mobile",
                "horizontal_overflow": page.evaluate(
                    "() => document.documentElement.scrollWidth > document.documentElement.clientWidth"
                ),
            }
        )

        for path in ["/", "/setup-check", "/archive", "/network", "/health", "/api/status"]:
            samples = []
            for _ in range(8):
                started = time.perf_counter()
                response = page.goto(f"{args.base_url}{path}", wait_until="domcontentloaded")
                samples.append((time.perf_counter() - started) * 1000)
                if not response or response.status >= 400:
                    raise RuntimeError(f"{path} returned {response.status if response else 'no response'}")
            report["performance_ms"][path] = {
                "median": round(statistics.median(samples), 1),
                "max": round(max(samples), 1),
            }
        page.close()
        browser.close()

    report_path = output_dir / "report.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 1 if report["console_errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
