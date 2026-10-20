import pytest

from innesto.pipeline.candidates import Extractor
from innesto.pipeline.difficulty import score


@pytest.fixture(scope="module")
def extractor():
    return Extractor()


def by_kind(cands, kind):
    return {c.text for c in cands if c.kind == kind}


def test_basic_sentence(extractor):
    text = "John is reading a book. He reads very slowly, but he enjoys every page."
    cands = extractor.extract_block(text, 0)
    for c in cands:                       # offsets always point at the text they claim
        assert text[c.start:c.end] == c.text
    assert "a book" in by_kind(cands, "np")
    assert "John is reading" in by_kind(cands, "vp")
    assert "He reads" in by_kind(cands, "vp")
    assert "very" in by_kind(cands, "word") and "slowly" in by_kind(cands, "word")
    assert "John is reading a book." in by_kind(cands, "sentence")
    # proper nouns never become word/np candidates
    assert "John" not in by_kind(cands, "word") and "John" not in by_kind(cands, "np")


def test_offsets_shift_with_block_offset(extractor):
    text = "The old red house stood at the end of the street."
    cands = extractor.extract_block(text, 1000)
    np = next(c for c in cands if c.text == "The old red house")
    assert (np.start, np.end) == (1000, 1017) and np.kind == "np" and np.level >= 2
    assert "at the end of the street" in by_kind(cands, "pp") or "of the street" in by_kind(cands, "pp")


def test_clause_and_levels(extractor):
    text = "In the garden, the children played happily until the sun went down."
    cands = extractor.extract_block(text, 0)
    assert any(c.kind == "clause" and "until the sun went down" in c.text for c in cands)
    assert "In the garden" in by_kind(cands, "pp")
    levels = {c.kind: c.level for c in cands}
    assert levels["sentence"] == 5


def test_score_scale():
    assert score("np", False, ["book"]) [0] == 1          # very common noun
    assert score("np", False, ["scabbard"])[0] >= 3        # rare noun pushes level up
    assert score("sentence", False, ["book"])[0] == 5
    lvl_easy, d_easy = score("word", False, ["very"])
    lvl_hard, d_hard = score("clause", False, ["harvest"])
    assert d_easy < d_hard and lvl_easy < lvl_hard


def test_vp_keeps_proper_subject_and_never_lone_verb(extractor):
    cands = extractor.extract_block("John is reading a book. Maria opened the door. Come inside.", 0)
    vps = by_kind(cands, "vp")
    assert "John is reading" in vps and "Maria opened" in vps
    assert "Come" not in vps and "opened" not in vps


def test_postprocess_fits_fragments():
    from innesto.pipeline.translate.base import postprocess
    assert postprocess("very", "Molto.") == "molto"
    assert postprocess("a book", "Un libro") == "un libro"
    assert postprocess("John is reading a book.", "John sta leggendo un libro.") == "John sta leggendo un libro."
    assert postprocess("the door", "“la porta”") == "la porta"
    assert postprocess("Nobody answered", "nessuno ha risposto") == "Nessuno ha risposto"
    assert postprocess("dinner", "cena a cena") == "cena"
    assert postprocess("happily", "felicemente felice") == "felicemente"
    assert postprocess("upstairs", "al piano di sopra") == "al piano di sopra"
    assert postprocess("However", "Tuttavia,") == "Tuttavia"
    assert postprocess("he said:", "ha detto:") == "ha detto:"
    assert postprocess("x", None) is None


def test_runaway_translations_are_dropped():
    from innesto.pipeline.translate.base import degenerate, postprocess
    assert postprocess("thousand", "millemila " + "mila" * 60) is None
    assert postprocess("draped over the rover", "#" * 256) is None
    assert postprocess("However", "Tuttavia, la Commissione non è stata in grado di risolvere i problemi.") is None
    assert degenerate("likewise", "allo stesso modo anche allo stesso modo allo stesso modo.")
    # Memorised lines carrying training-corpus formatting.
    assert degenerate("the vote", "Presidente. — La discussione è chiusa.")
    assert degenerate("I marvel", "# I marvel #")
    assert degenerate("grimly", "- Oh, no.")
    # Repetition or formatting the source has, and ordinary expansions, are fine.
    assert postprocess("ha ha ha", "ah ah ah") == "ah ah ah"
    assert not degenerate("- Yes, sir.", "- Sì, signore.")
    assert not degenerate("Mr. Chairman", "Signor Presidente")
    assert not degenerate("ad", "annuncio pubblicitario")
    assert not degenerate("of media relations", "de las relaciones entre los medios de comunicación")


def test_ct2_retries_unusable_output():
    from types import SimpleNamespace
    from innesto.pipeline.translate.base import SpanRequest
    from innesto.pipeline.translate.ct2 import CT2Provider

    outputs = {"thousand": ["mila" * 40], "Thousand": ["Migliaia", "Mille"],
               "book": ["libro"], "Book": ["Libro"], "x": ["zz" * 50], "X": ["zz" * 50],
               "neither": ["Non lo so."], "Neither": ["Neither", "Non lo so.", "Nessuno"]}
    stock = {"Non lo so."}          # as likely from a blank source as from the real one
    calls = []

    def translate_batch(tokens, **opts):
        calls.append([t[0] for t in tokens])
        return [SimpleNamespace(hypotheses=[[h] for h in outputs[t[0]]]) for t in tokens]

    def score_batch(sources, targets, **opts):
        return [SimpleNamespace(log_probs=[-5.0 if s == ["."] or t[0] in stock else -0.5])
                for s, t in zip(sources, targets)]

    p = object.__new__(CT2Provider)
    p.sp_src = SimpleNamespace(encode=lambda s, out_type: [s])
    p.sp_tgt = SimpleNamespace(decode=lambda h: h[0], encode=lambda s, out_type: [s])
    p.translator = SimpleNamespace(translate_batch=translate_batch, score_batch=score_batch)

    got = p.translate_batch([SpanRequest(t) for t in ("thousand", "book", "x", "neither")])
    # The copy "Neither" and stock "Non lo so." are passed over for "Nessuno".
    assert got == ["migliaia", "libro", None, "nessuno"]
    assert calls == [["thousand", "book", "x", "neither"], ["Thousand", "X", "Neither"], ["x"]]


def test_copula_vp_includes_predicate(extractor):
    cands = extractor.extract_block("Dinner is ready. The cat is on the table.", 0)
    vps = by_kind(cands, "vp")
    assert "Dinner is ready" in vps and "Dinner is" not in vps
