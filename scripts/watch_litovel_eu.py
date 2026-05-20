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
)
USER_AGENT = "svoz-odpadu-litovel-monitor/1.0 (+https://svoz.litovle.cz)"

WASTE_PATTERNS = (
    ("svoz", re.compile(r"\bsvoz\w*", re.IGNORECASE)),
    ("odpad", re.compile(r"\bodpad\w*", re.IGNORECASE)),
    ("odpadu", re.compile(r"\bodpadu\b", re.IGNORECASE)),
    ("bioodpad", re.compile(r"\bbioodpad\w*", re.IGNORECASE)),
    ("bioodpadu", re.compile(r"\bbioodpadu\b", re.IGNORECASE)),
    ("kontejner", re.compile(r"\bkontejner\w*", re.IGNORECASE)),
    ("nadoba", re.compile(r"\bn[aá]dob\w*", re.IGNORECASE)),
    ("nadoby", re.compile(r"\bn[aá]doby\b", re.IGNORECASE)),
    ("popelnice", re.compile(r"\bpopelnic\w*", re.IGNORECASE)),
    ("plast", re.compile(r"\bplast\w*", re.IGNORECASE)),
    ("papir", re.compile(r"\bpap[ií]r\w*", re.IGNORECASE)),
    ("fcc", re.compile(r"\bfcc\b", re.IGNORECASE)),
)
CHANGE_PATTERNS = (
    ("zmena", re.compile(r"\bzm[eě]n\w*", re.IGNORECASE)),
    ("zmeny", re.compile(r"\bzm[eě]ny\b", re.IGNORECASE)),
    ("presun", re.compile(r"\bp[řr]esouv\w*|\bp[řr]esun\w*", re.IGNORECASE)),
    ("presouva", re.compile(r"\bp[řr]esouv[aá]\b", re.IGNORECASE)),
    ("presunut", re.compile(r"\bp[řr]esunut\w*", re.IGNORECASE)),
    ("nahradni", re.compile(r"\bn[aá]hradn[ií]\w*", re.IGNORECASE)),
    ("mimoradny", re.compile(r"\bmimo[řr][aá]dn\w*", re.IGNORECASE)),
    ("zruseni", re.compile(r"\bzru[šs]en[ií]\b", re.IGNORECASE)),
    ("svatek", re.compile(r"\bsv[aá]t\w*", re.IGNORECASE)),
    ("svatky", re.compile(r"\bsv[aá]tky\b", re.IGNORECASE)),
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
class MatchedArticle:
    title: str
    url: str
    publication_date: str | None
    topic_reasons: tuple[str, ...]
    change_reasons: tuple[str, ...]
    decision: str
    ignored_reason: str | None = None


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


def find_matched_articles(articles: Iterable[ParsedArticle]) -> list[MatchedArticle]:
    matches = []
    for article in articles:
        topic_reasons, change_reasons = _match_reasons(
            article.title,
            article.url,
            article.context if article.context_is_local else "",
        )
        if not topic_reasons:
            continue

        decision = "candidate" if change_reasons else "ignored"
        ignored_reason = None
        if decision == "ignored":
            ignored_reason = "waste-related article but no change-related term"

        matches.append(
            MatchedArticle(
                title=article.title,
                url=article.url,
                publication_date=_extract_publication_date(article.context),
                topic_reasons=tuple(topic_reasons),
                change_reasons=tuple(change_reasons),
                decision=decision,
                ignored_reason=ignored_reason,
            )
        )
    return matches


def find_candidate_articles(articles: Iterable[ParsedArticle]) -> list[MatchedArticle]:
    return [
        article
        for article in find_matched_articles(articles)
        if article.decision == "candidate"
    ]


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

    all_matches: list[MatchedArticle] = []
    for url in urls:
        print(f"Fetching: {url}")
        try:
            html = fetch_url(url, timeout)
        except Exception as exc:
            print(f"  ERROR: {exc}")
            continue

        articles = extract_articles(html, url)
        matches = find_matched_articles(articles)
        topic_matches = [match for match in matches if match.topic_reasons]
        change_candidates = [
            match for match in matches if match.decision == "candidate"
        ]
        all_matches.extend(matches)
        print(f"  links scanned: {len(articles)}")
        print(f"  topic matches: {len(topic_matches)}")
        print(f"  change candidates: {len(change_candidates)}")

    print()
    print_match_summary(_deduplicate_matches(all_matches))
    return 0


def print_match_summary(matches: list[MatchedArticle]) -> None:
    candidates = [match for match in matches if match.decision == "candidate"]
    ignored = [match for match in matches if match.decision == "ignored"]
    print(f"Topic matches found: {len(matches)}")
    print(f"Candidate articles found: {len(candidates)}")

    for index, candidate in enumerate(candidates, start=1):
        print(f"{index}. {candidate.title}")
        print(f"   URL: {candidate.url}")
        print(f"   Date: {candidate.publication_date or 'unknown'}")
        print(f"   Topic reasons: {', '.join(candidate.topic_reasons)}")
        print(f"   Change reasons: {', '.join(candidate.change_reasons)}")

    if ignored:
        print()
        print(f"Ignored topic matches: {len(ignored)}")
    for index, ignored_match in enumerate(ignored, start=1):
        print(f"{index}. {ignored_match.title}")
        print(f"   URL: {ignored_match.url}")
        print(f"   Date: {ignored_match.publication_date or 'unknown'}")
        print(f"   Topic reasons: {', '.join(ignored_match.topic_reasons)}")
        print(f"   Ignored: {ignored_match.ignored_reason}")


def _match_reasons(title: str, url: str, context: str) -> tuple[list[str], list[str]]:
    full_text = f"{title} {url} {context}"
    waste_matches = [name for name, pattern in WASTE_PATTERNS if pattern.search(full_text)]
    change_matches = [name for name, pattern in CHANGE_PATTERNS if pattern.search(full_text)]
    return (
        [f"topic:{name}" for name in waste_matches],
        [f"change:{name}" for name in change_matches],
    )


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


def _deduplicate_matches(matches: Iterable[MatchedArticle]) -> list[MatchedArticle]:
    seen = set()
    deduplicated = []
    for match in matches:
        if match.url in seen:
            continue
        seen.add(match.url)
        deduplicated.append(match)
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
