import zipfile

from innesto.epub.textstream import extract


def test_stream_is_verbatim_and_blocks_split(sample_epub):
    with zipfile.ZipFile(sample_epub) as zf:
        data = zf.read("OEBPS/text/ch01.xhtml")
    ts = extract(data)
    # Inline markup does not break the stream; text node contents are verbatim.
    assert "He reads very slowly, but he enjoys every page." in ts.text
    assert "the enormous oak tree" in ts.text
    # Smart quotes (literal characters) come through unchanged.
    assert "“Come inside,”" in ts.text
    # Blocks: h1 + 4 paragraphs.
    texts = [ts.text[a:b].strip() for a, b in ts.blocks]
    assert texts[0] == "Chapter One"
    assert texts[1].startswith("John is reading a book.")
    assert len(texts) == 5
    assert ts.hash.startswith("sha256:") and ts.word_count > 60


def test_skips_script_and_comments_but_keeps_tails():
    data = b"""<?xml version="1.0"?><html xmlns="http://www.w3.org/1999/xhtml"><head><title>T</title></head>
    <body><p>Hello<!-- c --> world<script>var x = 1;</script> again.</p><div>Two<br/>lines</div></body></html>"""
    ts = extract(data)
    assert ts.text == "Hello world again.Twolines"
    assert [ts.text[a:b] for a, b in ts.blocks] == ["Hello world again.", "Two", "lines"]


def test_html_fallback_for_malformed_xml():
    data = b"<html><body><p>It&rsquo;s <b>bold</b> &amp; broken<p>second</body></html>"
    ts = extract(data)
    assert ts.text == "It’s bold & brokensecond"
    assert len(ts.blocks) == 2
