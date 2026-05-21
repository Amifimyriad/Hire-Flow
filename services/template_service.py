from __future__ import annotations

import html
import re
from html.parser import HTMLParser


PLACEHOLDER_PATTERN = re.compile(r"{{\s*([a-zA-Z0-9_]+)\s*}}")


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self._parts.append(data)

    def text(self) -> str:
        return " ".join(part.strip() for part in self._parts if part.strip())


def render_template(content: str, context: dict[str, str]) -> str:
    def replace(match: re.Match[str]) -> str:
        key = match.group(1)
        return context.get(key, "")

    return PLACEHOLDER_PATTERN.sub(replace, content)


def merge_signature(body_html: str, signature_html: str) -> str:
    if not signature_html.strip():
        return body_html
    return f"{body_html}<br><br>{signature_html}"


def html_to_text(content: str) -> str:
    extractor = _TextExtractor()
    extractor.feed(content)
    return html.unescape(extractor.text())

