#!/usr/bin/env python3
"""Dry-run monitor for Litovel.eu waste collection change announcements."""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from html.parser import HTMLParser
from typing import Iterable
from urllib.parse import urljoin
from urllib.request import Request, urlopen


DEFAULT_URLS = (
    "https://www.litovel.eu/cs/urad/uredni-deska/aktualni-informace/",
    "https://www.litovel.eu/cs/aktuality/",
)
USER_AGENT = "svoz-odpadu-litovel-monitor/1.0 (+https://svoz.litovle.cz)"

WASTE_PATTERNS = (
    ("svoz", re.compile(r"\bsvoz\w*", re.IGNORECASE)),
    ("odpad", re.compile(r"\bodpad\w*", re.IGNORECASE)),
    ("popelnice", re.compile(r"\bpopelnic\w*", re.IGNORECASE)),
    ("bioodpad", re.compile(r"\bbioodpad\w*", re.IGNORECASE)),
    ("plast", re.compile(r"\bplast\w*", re.IGNORECASE)),
    ("papir", re.compile(r"\bpap[ií]r\w*", re.IGNORECASE)),
)
CHANGE_PATTERNS = (
    ("zmena", re.compile(r"\bzm[eě]n\w*", re.IGNORECASE)),
    ("presun", re.compile(r"\bp[řr]esouv\w*|\bp[řr]esun\w*", re.IGNORECASE)),
    ("svatek", re.compile(r"\bsv[aá]t\w*", re.IGNORECASE)),
    ("termin", re.compile(r"\bterm[ií]n\w*", re.IGNORECASE)),
    ("vanocni", re.compile(r"\bv[aá]no[cč]\w*", re.IGNORECASE)),
    ("velikonoce", re.compile(r"\bvelikonoc\w*", re.IGNORECASE)),
)
DATE_PATTERN = re.compile(
    r"\b(\d{4}-\d{1,2}-\d{1,2}|\d{1,2}\.\s*\d{1,2}\.\s*(?:\d{4})?)\b"
)
CONTEXT_TAGS = {"article", "li", "tr", "p", "section", "div"}


@dataclass(frozen=True)
class ParsedArticle:
    title: str
    url: str
    context: str
    context_is_local: bool


@dataclass(frozen=True)
class CandidateArticle:
    title: str
    url: str
    publication_date: str | None
    reasons: tuple[str, ...]


class LitovelArticleParser(HTMLParser):
    def __init__(self, base_url: str):
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self._text_parts: list[str] = []
        self._current_link: dict[str, object] | None = None
        self._context_starts: list[int] = []
        self.links: list[ParsedArticle] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = dict(attrs)
        if tag in CONTEXT_TAGS:
            self._context_starts.append(len(self.document_text))
        if tag == "a" and attrs_dict.get("href"):
            self._current_link = {
                "href": attrs_dict["href"],
                "parts": [],
                "start": len(self.document_text),
                "context_start": self._context_starts[-1] if self._context_starts else None,
            }
        if tag == "time" and attrs_dict.get("datetime"):
            self._append_text(f" {attrs_dict['datetime']} ")

    def handle_endtag(self, tag: str) -> None:
        if tag in CONTEXT_TAGS and self._context_starts:
            self._context_starts.pop()

        if tag != "a" or self._current_link is None:
            return

        title = " ".join("".join(self._current_link["parts"]).split())
        href = str(self._current_link["href"])
        start = int(self._current_link["start"])
        context_start = self._current_link["context_start"]
        end = len(self.document_text)
        self._current_link = None

        if not title or href.startswith("#"):
            return

        context_is_local = context_start is not None
        if not context_is_local:
            context_start = max(0, start - 160)
        context_end = min(len(self.document_text), end + 160)
        context = self.document_text[context_start:context_end]
        self.links.append(
            ParsedArticle(
                title=title,
                url=urljoin(self.base_url, href),
                context=context,
                context_is_local=context_is_local,
            )
        )

    def handle_data(self, data: str) -> None:
        self._append_text(data)
        if self._current_link is not None:
            self._current_link["parts"].append(data)

    @property
    def document_text(self) -> str:
        return "".join(self._text_parts)

    def _append_text(self, text: str) -> None:
        if text.strip():
            self._text_parts.append(f" {text.strip()} ")


def extract_articles(html: str, base_url: str) -> list[ParsedArticle]:
    parser = LitovelArticleParser(base_url)
    parser.feed(html)
    return _deduplicate_articles(parser.links)


def find_candidate_articles(articles: Iterable[ParsedArticle]) -> list[CandidateArticle]:
    candidates = []
    for article in articles:
        reasons = _match_reasons(
            article.title,
            article.url,
            article.context if article.context_is_local else "",
        )
        if reasons:
            candidates.append(
                CandidateArticle(
                    title=article.title,
                    url=article.url,
                    publication_date=_extract_publication_date(article.context),
                    reasons=tuple(reasons),
                )
            )
    return candidates


def fetch_url(url: str, timeout: int) -> str:
    request = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(request, timeout=timeout) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        return response.read().decode(charset, errors="replace")


def run(urls: Iterable[str], timeout: int, dry_run: bool) -> int:
    print("Litovel.eu watcher")
    print(f"Mode: {'dry-run' if dry_run else 'dry-run forced'}")
    print("This script does not modify files, commit, push, create issues, or create PRs.")
    print()

    all_candidates: list[CandidateArticle] = []
    for url in urls:
        print(f"Fetching: {url}")
        try:
            html = fetch_url(url, timeout)
        except Exception as exc:
            print(f"  ERROR: {exc}")
            continue

        articles = extract_articles(html, url)
        candidates = find_candidate_articles(articles)
        all_candidates.extend(candidates)
        print(f"  links scanned: {len(articles)}")
        print(f"  candidates: {len(candidates)}")

    print()
    print_candidate_summary(_deduplicate_candidates(all_candidates))
    return 0


def print_candidate_summary(candidates: list[CandidateArticle]) -> None:
    print(f"Candidate articles found: {len(candidates)}")
    if not candidates:
        return

    for index, candidate in enumerate(candidates, start=1):
        print(f"{index}. {candidate.title}")
        print(f"   URL: {candidate.url}")
        print(f"   Date: {candidate.publication_date or 'unknown'}")
        print(f"   Reason: {', '.join(candidate.reasons)}")


def _match_reasons(title: str, url: str, context: str) -> list[str]:
    title_url = f"{title} {url}"
    full_text = f"{title_url} {context}"
    waste_matches = [name for name, pattern in WASTE_PATTERNS if pattern.search(full_text)]
    change_matches = [name for name, pattern in CHANGE_PATTERNS if pattern.search(full_text)]
    if not waste_matches or not change_matches:
        return []

    title_waste_matches = [name for name, pattern in WASTE_PATTERNS if pattern.search(title_url)]
    title_change_matches = [name for name, pattern in CHANGE_PATTERNS if pattern.search(title_url)]
    if not title_waste_matches and not title_change_matches:
        return []

    return [f"waste:{name}" for name in waste_matches] + [
        f"change:{name}" for name in change_matches
    ]


def _extract_publication_date(text: str) -> str | None:
    match = DATE_PATTERN.search(text)
    if not match:
        return None
    return " ".join(match.group(1).split())


def _deduplicate_articles(articles: Iterable[ParsedArticle]) -> list[ParsedArticle]:
    seen = set()
    deduplicated = []
    for article in articles:
        key = article.url
        if key in seen:
            continue
        seen.add(key)
        deduplicated.append(article)
    return deduplicated


def _deduplicate_candidates(
    candidates: Iterable[CandidateArticle],
) -> list[CandidateArticle]:
    seen = set()
    deduplicated = []
    for candidate in candidates:
        if candidate.url in seen:
            continue
        seen.add(candidate.url)
        deduplicated.append(candidate)
    return deduplicated


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--url",
        action="append",
        dest="urls",
        help="Litovel.eu listing page to scan. Can be used more than once.",
    )
    parser.add_argument("--timeout", type=int, default=20)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="Run without modifying files or creating GitHub objects. This is always enabled.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    return run(args.urls or DEFAULT_URLS, timeout=args.timeout, dry_run=True)


if __name__ == "__main__":
    raise SystemExit(main())
