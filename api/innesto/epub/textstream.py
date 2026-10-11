"""The section *text stream*: every text node under <body>, in document order,
concatenated verbatim. Sidecar candidates are addressed by character offsets
into this stream, and the reader rebuilds the identical stream from the live
DOM, so the two implementations must agree exactly:

- text node contents are taken verbatim (no whitespace normalisation);
- <script> and <style> subtrees contribute nothing;
- comments and processing instructions contribute nothing (their tails do);
- the document is parsed as XML first and, if that fails, as HTML, which is
  also what foliate-js does for malformed EPUB sections.

`blocks` are the stream ranges delimited by block-level elements. Sentences
never cross a block boundary, so NLP runs per block.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

from lxml import etree, html

XHTML_NS = "http://www.w3.org/1999/xhtml"

SKIP_TAGS = {"script", "style", "template", "svg", "math"}
BLOCK_TAGS = {
    "address", "article", "aside", "blockquote", "body", "br", "caption", "dd",
    "details", "dialog", "div", "dl", "dt", "fieldset", "figcaption", "figure",
    "footer", "form", "h1", "h2", "h3", "h4", "h5", "h6", "header", "hgroup",
    "hr", "li", "main", "nav", "ol", "p", "pre", "section", "summary", "table",
    "tbody", "td", "tfoot", "th", "thead", "tr", "ul",
}

_WORD_RE = re.compile(r"\w+", re.UNICODE)


@dataclass
class TextStream:
    text: str
    blocks: list[tuple[int, int]]      # [start, end) ranges, non-empty, non-overlapping

    @property
    def hash(self) -> str:
        return "sha256:" + hashlib.sha256(self.text.encode("utf-8")).hexdigest()

    @property
    def word_count(self) -> int:
        return len(_WORD_RE.findall(self.text))


def _localname(tag) -> str | None:
    if not isinstance(tag, str):
        return None                      # comment, PI, entity
    return tag.rsplit("}", 1)[-1].lower()


def parse_section(data: bytes):
    """Parse XHTML bytes as XML, falling back to HTML like browsers/foliate do."""
    try:
        return etree.fromstring(data, etree.XMLParser(resolve_entities=False, no_network=True))
    except etree.XMLSyntaxError:
        return html.fromstring(data)


def _find_body(root):
    if _localname(root.tag) == "body":
        return root
    for el in root.iter():
        if _localname(el.tag) == "body":
            return el
    return root


def extract(data: bytes) -> TextStream:
    root = parse_section(data)
    body = _find_body(root)
    parts: list[str] = []
    boundaries: list[int] = [0]
    pos = 0

    def emit(s: str | None) -> None:
        nonlocal pos
        if s:
            parts.append(s)
            pos += len(s)

    def boundary() -> None:
        if boundaries[-1] != pos:
            boundaries.append(pos)

    def walk(el, is_root: bool) -> None:
        name = _localname(el.tag)
        if name is None:                 # comment / PI: only the tail is text
            pass
        elif name in SKIP_TAGS:
            pass
        else:
            block = name in BLOCK_TAGS
            if block:
                boundary()
            emit(el.text)
            for child in el:
                walk(child, False)
            if block:
                boundary()
        if not is_root:
            emit(el.tail)

    walk(body, True)
    boundary()
    text = "".join(parts)
    blocks = [(a, b) for a, b in zip(boundaries, boundaries[1:]) if text[a:b].strip()]
    return TextStream(text=text, blocks=blocks)
