#!/usr/bin/env python3
"""Check that a published Sparkle appcast and referenced assets are reachable safely.

The release workflows use this after pushing to the MotionSmith Pages repository.
It rejects insecure redirects (including HTTPS -> HTTP downgrade) so a feed URL
that works in curl but violates macOS/Sparkle transport expectations fails closed.
"""

from __future__ import annotations

import argparse
import sys
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from collections.abc import Iterable
from dataclasses import dataclass
from typing import TextIO, cast
from urllib.parse import urlparse

SPARKLE_NAMESPACE = "http://www.andymatuschak.org/xml-namespaces/sparkle"


@dataclass(frozen=True)
class ReachabilityResult:
    """Reachability result for a published OTA URL."""

    url: str
    ok: bool
    error: str | None = None


class HTTPSOnlyRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Redirect handler that rejects non-HTTPS locations."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[no-untyped-def]
        if urlparse(newurl).scheme != "https":
            raise urllib.error.HTTPError(
                req.full_url,
                code,
                f"insecure redirect blocked: {newurl}",
                headers,
                fp,
            )
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _opener() -> urllib.request.OpenerDirector:
    return urllib.request.build_opener(HTTPSOnlyRedirectHandler)


def _ensure_https(url: str) -> None:
    if urlparse(url).scheme != "https":
        raise ValueError(f"URL must use HTTPS: {url}")


def fetch_bytes(url: str, *, timeout: float) -> bytes:
    """Fetch a URL with HTTPS-only redirects."""
    _ensure_https(url)
    request = urllib.request.Request(url, headers={"User-Agent": "MotionSmith-OTA-Check/1"})
    with _opener().open(request, timeout=timeout) as response:
        return cast(bytes, response.read())


def check_url(url: str, *, timeout: float) -> ReachabilityResult:
    """Check a referenced payload/release-notes URL using HEAD with GET fallback."""
    try:
        _ensure_https(url)
        request = urllib.request.Request(
            url,
            method="HEAD",
            headers={"User-Agent": "MotionSmith-OTA-Check/1"},
        )
        try:
            with _opener().open(request, timeout=timeout):
                return ReachabilityResult(url, True)
        except urllib.error.HTTPError as exc:
            if exc.code not in {403, 405, 501}:
                raise
        fetch_bytes(url, timeout=timeout)
        return ReachabilityResult(url, True)
    except (OSError, ValueError, urllib.error.HTTPError, urllib.error.URLError) as exc:
        return ReachabilityResult(url, False, str(exc))


def referenced_urls(appcast_xml: bytes) -> tuple[str, ...]:
    """Return enclosure and release-notes URLs referenced by a Sparkle appcast."""
    root = ET.fromstring(appcast_xml)
    urls: list[str] = []
    for enclosure in root.iter("enclosure"):
        url = (enclosure.get("url") or "").strip()
        if url:
            urls.append(url)
    for element in root.iter(f"{{{SPARKLE_NAMESPACE}}}releaseNotesLink"):
        if element.text and element.text.strip():
            urls.append(element.text.strip())
    for element in root.iter("sparkle:releaseNotesLink"):
        if element.text and element.text.strip():
            urls.append(element.text.strip())
    return tuple(dict.fromkeys(urls))


def run_check(appcast_url: str, *, timeout: float) -> tuple[bool, tuple[ReachabilityResult, ...]]:
    """Fetch the appcast and verify every referenced URL is reachable."""
    try:
        appcast = fetch_bytes(appcast_url, timeout=timeout)
        urls = referenced_urls(appcast)
    except (
        OSError,
        ValueError,
        ET.ParseError,
        urllib.error.HTTPError,
        urllib.error.URLError,
    ) as exc:
        return False, (ReachabilityResult(appcast_url, False, str(exc)),)

    results = [ReachabilityResult(appcast_url, True)]
    results.extend(check_url(url, timeout=timeout) for url in urls)
    return all(result.ok for result in results), tuple(results)


def retry_check(
    appcast_url: str,
    *,
    retries: int,
    delay: float,
    timeout: float,
) -> tuple[bool, tuple[ReachabilityResult, ...]]:
    """Retry reachability checks to tolerate GitHub Pages propagation."""
    last_results: tuple[ReachabilityResult, ...] = ()
    for attempt in range(1, retries + 1):
        ok, results = run_check(appcast_url, timeout=timeout)
        last_results = results
        if ok:
            print(f"OTA reachability passed on attempt {attempt}/{retries}.")
            return True, results
        print(f"OTA reachability attempt {attempt}/{retries} failed:", file=sys.stderr)
        _print_results(results, stream=sys.stderr)
        if attempt < retries:
            time.sleep(delay)
    return False, last_results


def _print_results(
    results: Iterable[ReachabilityResult],
    *,
    stream: TextIO = sys.stdout,
) -> None:
    for result in results:
        if result.ok:
            print(f"OK {result.url}", file=stream)
        else:
            print(f"FAIL {result.url}: {result.error}", file=stream)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("appcast_url")
    parser.add_argument("--retries", type=int, default=1)
    parser.add_argument("--delay", type=float, default=10.0)
    parser.add_argument("--timeout", type=float, default=20.0)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    ok, results = retry_check(
        args.appcast_url,
        retries=max(args.retries, 1),
        delay=max(args.delay, 0.0),
        timeout=max(args.timeout, 1.0),
    )
    _print_results(results)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
