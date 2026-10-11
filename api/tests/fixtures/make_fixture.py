"""Build a small, valid EPUB 3 fixture for tests. Run: python tests/fixtures/make_fixture.py"""

from __future__ import annotations

import zipfile
from pathlib import Path

HERE = Path(__file__).parent
OUT = HERE / "sample.epub"

CONTAINER = """<?xml version="1.0" encoding="UTF-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles><rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/></rootfiles>
</container>"""

OPF = """<?xml version="1.0" encoding="UTF-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="uid">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:identifier id="uid">urn:uuid:11111111-2222-3333-4444-555555555555</dc:identifier>
    <dc:title>A Small Sample</dc:title>
    <dc:creator>Jane Tester</dc:creator>
    <dc:language>en</dc:language>
    <meta property="dcterms:modified">2026-01-01T00:00:00Z</meta>
  </metadata>
  <manifest>
    <item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>
    <item id="cover-image" href="images/cover.png" media-type="image/png" properties="cover-image"/>
    <item id="title" href="title.xhtml" media-type="application/xhtml+xml"/>
    <item id="ch1" href="text/ch01.xhtml" media-type="application/xhtml+xml"/>
    <item id="ch2" href="text/ch02.xhtml" media-type="application/xhtml+xml"/>
    <item id="css" href="style.css" media-type="text/css"/>
  </manifest>
  <spine>
    <itemref idref="title" linear="no"/>
    <itemref idref="ch1"/>
    <itemref idref="ch2"/>
  </spine>
</package>"""

NAV = """<?xml version="1.0" encoding="UTF-8"?>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops">
<head><title>Contents</title></head>
<body>
  <nav epub:type="toc"><h1>Contents</h1>
    <ol>
      <li><a href="text/ch01.xhtml">Chapter One</a>
        <ol><li><a href="text/ch01.xhtml#part2">The Garden</a></li></ol>
      </li>
      <li><a href="text/ch02.xhtml">Chapter Two</a></li>
    </ol>
  </nav>
</body></html>"""

TITLE = """<?xml version="1.0" encoding="UTF-8"?>
<html xmlns="http://www.w3.org/1999/xhtml"><head><title>A Small Sample</title></head>
<body><h1>A Small Sample</h1><p>by Jane Tester</p></body></html>"""

CH1 = """<?xml version="1.0" encoding="UTF-8"?>
<html xmlns="http://www.w3.org/1999/xhtml"><head><title>Chapter One</title>
<link rel="stylesheet" href="../style.css"/></head>
<body>
<h1>Chapter One</h1>
<p>John is reading a book. He reads <em>very</em> slowly, but he enjoys every page.</p>
<p>The old red house stood at the end of the street. Maria opened the door and walked into the kitchen, where a small cat was sleeping on the table.</p>
<p id="part2">In the garden, the children played happily until the sun went down. “Come inside,” said their mother, “dinner is ready.”</p>
<p>Nobody answered. The children were hiding behind the <strong>enormous</strong> oak tree, and they laughed quietly.</p>
</body></html>"""

CH2 = """<?xml version="1.0" encoding="UTF-8"?>
<html xmlns="http://www.w3.org/1999/xhtml"><head><title>Chapter Two</title></head>
<body>
<h1>Chapter Two</h1>
<p>The next morning, the village was quiet. A baker was already working, and the smell of fresh bread filled the narrow street.</p>
<p>Maria bought two loaves and a bottle of milk. She thanked the baker, who smiled and wished her a good day.</p>
<ul><li>bread</li><li>milk</li><li>a letter for her grandmother</li></ul>
<p>On the way home she met an old friend. They talked for a long time about the weather, the harvest, and the strange lights that people had seen above the hills.</p>
</body></html>"""

CSS = "body { font-family: serif; }"

# 1x1 transparent PNG
PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4890000000d4944415478"
    "9c6360000002000154a24f5d0000000049454e44ae426082")


def build(out: Path = OUT) -> Path:
    with zipfile.ZipFile(out, "w") as zf:
        zf.writestr(zipfile.ZipInfo("mimetype"), "application/epub+zip", compress_type=zipfile.ZIP_STORED)
        zf.writestr("META-INF/container.xml", CONTAINER, zipfile.ZIP_DEFLATED)
        zf.writestr("OEBPS/content.opf", OPF, zipfile.ZIP_DEFLATED)
        zf.writestr("OEBPS/nav.xhtml", NAV, zipfile.ZIP_DEFLATED)
        zf.writestr("OEBPS/title.xhtml", TITLE, zipfile.ZIP_DEFLATED)
        zf.writestr("OEBPS/text/ch01.xhtml", CH1, zipfile.ZIP_DEFLATED)
        zf.writestr("OEBPS/text/ch02.xhtml", CH2, zipfile.ZIP_DEFLATED)
        zf.writestr("OEBPS/style.css", CSS, zipfile.ZIP_DEFLATED)
        zf.writestr("OEBPS/images/cover.png", PNG, zipfile.ZIP_DEFLATED)
    return out


if __name__ == "__main__":
    print(build())
