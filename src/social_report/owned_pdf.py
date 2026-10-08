"""Local headless-browser PDF rendering for the self-contained owned report."""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import List, Mapping, Optional

COMMON_BROWSER_PATHS = (
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
    "/usr/bin/google-chrome",
    "/usr/bin/google-chrome-stable",
    "/usr/bin/chromium",
    "/usr/bin/chromium-browser",
    "/usr/bin/microsoft-edge",
)


def find_pdf_browser(environ: Optional[Mapping[str, str]] = None) -> Optional[Path]:
    values = environ if environ is not None else os.environ
    explicit = values.get("SOCIAL_REPORT_BROWSER", "").strip()
    if explicit:
        path = Path(explicit).expanduser()
        return path if path.is_file() else None
    for command in (
        "google-chrome",
        "google-chrome-stable",
        "chromium",
        "chromium-browser",
        "microsoft-edge",
    ):
        resolved = shutil.which(command)
        if resolved:
            return Path(resolved)
    return next((Path(item) for item in COMMON_BROWSER_PATHS if Path(item).is_file()), None)


def pdf_command(
    browser: Path, html_path: Path, pdf_path: Path, *, user_data_dir: Path
) -> List[str]:
    return [
        str(browser),
        "--headless=new",
        "--disable-gpu",
        "--no-pdf-header-footer",
        "--print-to-pdf-no-header",
        f"--user-data-dir={user_data_dir}",
        f"--print-to-pdf={pdf_path}",
        html_path.resolve().as_uri(),
    ]


def render_pdf(html_path: Path, pdf_path: Path) -> Mapping[str, object]:
    browser = find_pdf_browser()
    if browser is None:
        return {
            "status": "PDF_RENDERER_UNAVAILABLE",
            "message": (
                "Set SOCIAL_REPORT_BROWSER to Chrome, Chromium, or Edge to generate report.pdf."
            ),
        }
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="social-report-pdf-") as temp:
        temporary = Path(temp)
        staged_pdf = temporary / "report.pdf"
        command = pdf_command(
            browser,
            html_path,
            staged_pdf,
            user_data_dir=temporary / "browser-profile",
        )
        try:
            process = subprocess.Popen(
                command,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except OSError as error:
            return {"status": "PDF_RENDER_FAILED", "message": str(error)[:300]}

        deadline = time.monotonic() + 45
        previous_size = -1
        stable_polls = 0
        try:
            while time.monotonic() < deadline:
                if staged_pdf.exists():
                    current_size = staged_pdf.stat().st_size
                    if current_size >= 1000 and current_size == previous_size:
                        stable_polls += 1
                    else:
                        stable_polls = 0
                    previous_size = current_size
                    if stable_polls >= 2:
                        break
                if process.poll() is not None and not staged_pdf.exists():
                    break
                time.sleep(0.2)
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=3)

        if not staged_pdf.exists():
            return {
                "status": "PDF_RENDER_FAILED",
                "message": "Headless browser did not create a PDF",
            }
        data = staged_pdf.read_bytes()
        if not data.startswith(b"%PDF-") or len(data) < 1000:
            return {"status": "PDF_RENDER_FAILED", "message": "Renderer output is not a valid PDF"}
        staged_pdf.replace(pdf_path)
    return {
        "status": "PASS",
        "path": str(pdf_path),
        "browser": browser.name,
        "bytes": pdf_path.stat().st_size,
    }
