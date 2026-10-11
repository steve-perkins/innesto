"""Minimal EPUB container reader: metadata, spine, table of contents, cover.

Implemented on the standard library `zipfile` plus lxml so that no copyleft
EPUB library is needed. The spine order here must match foliate-js's
`book.sections` order on the client, because sidecar sections are addressed by
spine index: both derive from the OPF <spine> itemrefs in document order,
including non-linear items.
"""

from __future__ import annotations

import posixpath
import zipfile
from dataclasses import dataclass, field
from urllib.parse import unquote, urldefrag

from lxml import etree

NS = {
    "c": "urn:oasis:names:tc:opendocument:xmlns:container",
    "opf": "http://www.idpf.org/2007/opf",
    "dc": "http://purl.org/dc/elements/1.1/",
    "ncx": "http://www.daisy.org/z3986/2005/ncx/",
    "xhtml": "http://www.w3.org/1999/xhtml",
    "epub": "http://www.idpf.org/2007/ops",
}

IMAGE_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp", "image/svg+xml"}


@dataclass
class ManifestItem:
    id: str
    href: str            # container-absolute path, e.g. "OEBPS/ch01.xhtml"
    media_type: str
    properties: set[str] = field(default_factory=set)


@dataclass
class SpineItem:
    index: int
    href: str
    media_type: str
    linear: bool = True


@dataclass
class TocItem:
    label: str
    href: str            # container-absolute path, may include #fragment
    subitems: list["TocItem"] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"label": self.label, "href": self.href,
                "subitems": [s.to_dict() for s in self.subitems]}


@dataclass
class EpubInfo:
    title: str
    author: str | None
    language: str | None
    spine: list[SpineItem]
    toc: list[TocItem]
    cover_href: str | None
    cover_media_type: str | None


class Epub:
    def __init__(self, path):
        self.zf = zipfile.ZipFile(path)
        self._names = set(self.zf.namelist())
        self.opf_path = self._find_opf()
        self.opf_dir = posixpath.dirname(self.opf_path)
        self.opf = etree.fromstring(self.zf.read(self.opf_path))
        self.manifest = self._read_manifest()
        self.spine = self._read_spine()

    # -- container ---------------------------------------------------------

    def close(self) -> None:
        self.zf.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def has(self, href: str) -> bool:
        return href in self._names

    def read(self, href: str) -> bytes:
        return self.zf.read(href)

    def resolve(self, href: str, base_dir: str | None = None) -> str:
        """Resolve an href relative to the OPF (or another directory) into a
        container-absolute path, keeping any #fragment."""
        path, frag = urldefrag(href)
        base = self.opf_dir if base_dir is None else base_dir
        full = posixpath.normpath(posixpath.join(base, unquote(path))) if path else ""
        if full == ".":
            full = ""
        return f"{full}#{frag}" if frag else full

    def _find_opf(self) -> str:
        root = etree.fromstring(self.zf.read("META-INF/container.xml"))
        rf = root.find(".//c:rootfile", NS)
        if rf is None or not rf.get("full-path"):
            raise ValueError("container.xml has no rootfile")
        return rf.get("full-path")

    # -- package document --------------------------------------------------

    def _read_manifest(self) -> dict[str, ManifestItem]:
        items: dict[str, ManifestItem] = {}
        for el in self.opf.findall("opf:manifest/opf:item", NS):
            props = set((el.get("properties") or "").split())
            items[el.get("id")] = ManifestItem(
                id=el.get("id"), href=self.resolve(el.get("href", "")),
                media_type=el.get("media-type", ""), properties=props)
        return items

    def _read_spine(self) -> list[SpineItem]:
        spine: list[SpineItem] = []
        for el in self.opf.findall("opf:spine/opf:itemref", NS):
            item = self.manifest.get(el.get("idref"))
            if item is None:
                continue
            spine.append(SpineItem(index=len(spine), href=item.href,
                                   media_type=item.media_type,
                                   linear=el.get("linear", "yes") != "no"))
        return spine

    def _dc(self, name: str) -> str | None:
        el = self.opf.find(f"opf:metadata/dc:{name}", NS)
        return el.text.strip() if el is not None and el.text else None

    def metadata(self) -> tuple[str, str | None, str | None]:
        title = self._dc("title") or posixpath.basename(self.opf_path)
        authors = [e.text.strip() for e in self.opf.findall("opf:metadata/dc:creator", NS)
                   if e.text and e.text.strip()]
        return title, (", ".join(authors) or None), self._dc("language")

    # -- cover -------------------------------------------------------------

    def cover(self) -> ManifestItem | None:
        for item in self.manifest.values():
            if "cover-image" in item.properties:
                return item
        meta = self.opf.find("opf:metadata/opf:meta[@name='cover']", NS)
        if meta is not None and meta.get("content") in self.manifest:
            item = self.manifest[meta.get("content")]
            if item.media_type in IMAGE_TYPES:
                return item
        for item in self.manifest.values():
            if item.media_type in IMAGE_TYPES and "cover" in item.id.lower():
                return item
        return None

    # -- table of contents -------------------------------------------------

    def toc(self) -> list[TocItem]:
        nav = next((i for i in self.manifest.values() if "nav" in i.properties), None)
        if nav is not None and self.has(nav.href):
            items = self._toc_from_nav(nav)
            if items:
                return items
        ncx_id = self.opf.find("opf:spine", NS).get("toc") if self.opf.find("opf:spine", NS) is not None else None
        ncx = self.manifest.get(ncx_id) if ncx_id else None
        if ncx is None:
            ncx = next((i for i in self.manifest.values()
                        if i.media_type == "application/x-dtbncx+xml"), None)
        if ncx is not None and self.has(ncx.href):
            return self._toc_from_ncx(ncx)
        return []

    def _toc_from_nav(self, nav: ManifestItem) -> list[TocItem]:
        doc = etree.fromstring(self.read(nav.href), etree.XMLParser(recover=True))
        base = posixpath.dirname(nav.href)
        toc_nav = None
        for el in doc.iter("{%s}nav" % NS["xhtml"]):
            if "toc" in (el.get("{%s}type" % NS["epub"]) or "").split():
                toc_nav = el
                break
        if toc_nav is None:
            return []
        ol = toc_nav.find("xhtml:ol", NS)
        return self._nav_list(ol, base) if ol is not None else []

    def _nav_list(self, ol, base: str) -> list[TocItem]:
        out: list[TocItem] = []
        for li in ol.findall("xhtml:li", NS):
            a = li.find("xhtml:a", NS)
            span = li.find("xhtml:span", NS)
            label_el = a if a is not None else span
            label = " ".join("".join(label_el.itertext()).split()) if label_el is not None else ""
            href = self.resolve(a.get("href", ""), base) if a is not None else ""
            sub_ol = li.find("xhtml:ol", NS)
            subs = self._nav_list(sub_ol, base) if sub_ol is not None else []
            out.append(TocItem(label=label, href=href, subitems=subs))
        return out

    def _toc_from_ncx(self, ncx: ManifestItem) -> list[TocItem]:
        doc = etree.fromstring(self.read(ncx.href), etree.XMLParser(recover=True))
        base = posixpath.dirname(ncx.href)
        nav_map = doc.find("ncx:navMap", NS)
        return self._ncx_points(nav_map, base) if nav_map is not None else []

    def _ncx_points(self, parent, base: str) -> list[TocItem]:
        out: list[TocItem] = []
        for np_ in parent.findall("ncx:navPoint", NS):
            text = np_.find("ncx:navLabel/ncx:text", NS)
            content = np_.find("ncx:content", NS)
            label = " ".join((text.text or "").split()) if text is not None else ""
            href = self.resolve(content.get("src", ""), base) if content is not None else ""
            out.append(TocItem(label=label, href=href, subitems=self._ncx_points(np_, base)))
        return out

    # -- convenience -------------------------------------------------------

    def info(self) -> EpubInfo:
        title, author, language = self.metadata()
        cover = self.cover()
        return EpubInfo(title=title, author=author, language=language,
                        spine=self.spine, toc=self.toc(),
                        cover_href=cover.href if cover else None,
                        cover_media_type=cover.media_type if cover else None)

    def text_sections(self) -> list[SpineItem]:
        """Spine items that are (X)HTML documents, i.e. candidates for processing."""
        return [s for s in self.spine
                if s.media_type in ("application/xhtml+xml", "text/html")]
