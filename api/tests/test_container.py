from innesto.epub.container import Epub


def test_metadata_and_spine(sample_epub):
    with Epub(sample_epub) as epub:
        title, author, lang = epub.metadata()
        assert (title, author, lang) == ("A Small Sample", "Jane Tester", "en")
        hrefs = [s.href for s in epub.spine]
        assert hrefs == ["OEBPS/title.xhtml", "OEBPS/text/ch01.xhtml", "OEBPS/text/ch02.xhtml"]
        assert epub.spine[0].linear is False and epub.spine[1].linear is True
        assert [s.index for s in epub.text_sections()] == [0, 1, 2]


def test_toc_nav(sample_epub):
    with Epub(sample_epub) as epub:
        toc = epub.toc()
        assert [t.label for t in toc] == ["Chapter One", "Chapter Two"]
        assert toc[0].href == "OEBPS/text/ch01.xhtml"
        assert toc[0].subitems[0].href == "OEBPS/text/ch01.xhtml#part2"


def test_cover(sample_epub):
    with Epub(sample_epub) as epub:
        cover = epub.cover()
        assert cover is not None and cover.href == "OEBPS/images/cover.png"
        assert epub.read(cover.href)[:4] == b"\x89PNG"
