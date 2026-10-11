"""Candidate span extraction with spaCy.

For each block of the text stream we emit every span that *could* be shown in
the target language. The reader picks a non-overlapping subset according to
the user's Level and Density, so candidates may nest and overlap freely.

Kinds (see schema/sidecar.schema.json):
  word      standalone token safe to swap alone: adverb, interjection,
            coordinating conjunction, spelled-out number, bare noun
  np        noun chunk including its determiner/possessive and modifiers
  vp        verb with auxiliaries, negation, particles and a pronoun subject
  pp        preposition + its noun phrase
  clause    subordinate clause (subtree of a non-root verb)
  sentence  whole sentence

Spans are always whole grammatical units so that agreement (articles, gender,
number) is resolved inside the span by the translator rather than against the
surrounding English.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from functools import lru_cache

import spacy
from spacy.tokens import Doc, Span, Token

from .difficulty import score

CONTENT_POS = {"NOUN", "VERB", "ADJ", "ADV", "NUM", "INTJ"}
WORD_POS = {"ADV", "INTJ", "CCONJ", "NUM"}
EXCLUDED_ENTS = {"PERSON", "GPE", "LOC", "ORG", "FAC", "NORP", "EVENT", "WORK_OF_ART",
                 "LAW", "LANGUAGE", "PRODUCT"}
VP_CHILD_DEPS = {"aux", "auxpass", "neg", "prt"}
CLAUSE_DEPS = {"advcl", "ccomp", "xcomp", "relcl", "acl", "conj", "csubj", "parataxis"}
MAX_CLAUSE_TOKENS = 16
MAX_SENTENCE_TOKENS = 40
MIN_SENTENCE_TOKENS = 3

_STRIP_RE = re.compile(r"^[\s\W_]+|[\s\W_]+$", re.UNICODE)


@dataclass
class Candidate:
    start: int                      # offsets into the section text stream
    end: int
    text: str
    kind: str
    level: int
    difficulty: float
    lemmas: list[str] = field(default_factory=list)
    sentence: tuple[int, int] = (0, 0)

    @property
    def key(self) -> tuple[int, int]:
        return (self.start, self.end)


@lru_cache(maxsize=4)
def load_nlp(model: str = "en_core_web_sm"):
    return spacy.load(model, exclude=["textcat"])


def _excluded_tokens(doc: Doc) -> set[int]:
    """Tokens that must not appear inside word/np/vp/pp candidates: proper
    nouns and named entities. The small NER model produces false positives on
    ordinary lowercase phrases, so an entity only counts when it looks like a
    name (contains a PROPN or a capitalised non-sentence-initial token)."""
    bad = {t.i for t in doc if t.pos_ == "PROPN"}
    for ent in doc.ents:
        if ent.label_ not in EXCLUDED_ENTS:
            continue
        namelike = any(t.pos_ == "PROPN" or (t.is_title and not t.is_sent_start) for t in ent)
        if namelike:
            bad.update(range(ent.start, ent.end))
    return bad


def _content_lemmas(span: Span) -> list[str]:
    out: list[str] = []
    for t in span:
        if t.pos_ in CONTENT_POS and t.is_alpha:
            lemma = t.lemma_.lower()
            if lemma not in out:
                out.append(lemma)
    return out


def _trim(doc: Doc, start_char: int, end_char: int, keep_final_punct: bool) -> tuple[int, int] | None:
    """Trim surrounding whitespace/punctuation (quotes, commas...) from a char range."""
    text = doc.text
    s, e = start_char, end_char
    while s < e and (text[s].isspace() or (not text[s].isalnum() and text[s] not in "¿¡")):
        s += 1
    if keep_final_punct:
        while e > s and text[e - 1].isspace():
            e -= 1
        # keep one closing sentence punctuation mark, drop quotes/brackets after it
        while e > s and text[e - 1] in "”\"')]»":
            e -= 1
    else:
        while e > s and not text[e - 1].isalnum():
            e -= 1
    return (s, e) if e > s else None


class Extractor:
    def __init__(self, nlp=None, lang: str = "en"):
        self.nlp = nlp or load_nlp()
        self.lang = lang

    def extract_block(self, text: str, offset: int) -> list[Candidate]:
        """Candidates for one block whose text starts at `offset` in the stream."""
        if not text.strip():
            return []
        doc = self.nlp(text)
        excluded = _excluded_tokens(doc)
        found: dict[tuple[int, int], Candidate] = {}

        def add(span_start_tok: int, span_end_tok: int, kind: str, sent: Span,
                allow_proper: bool = False, modified: bool = False) -> None:
            if not allow_proper and any(i in excluded for i in range(span_start_tok, span_end_tok)):
                return
            span = doc[span_start_tok:span_end_tok]
            rng = _trim(doc, span.start_char, span.end_char, keep_final_punct=(kind == "sentence"))
            if rng is None:
                return
            s, e = rng
            span_text = text[s:e]
            if not any(ch.isalpha() for ch in span_text):
                return
            key = (offset + s, offset + e)
            if key in found:
                # keep the "larger" kind ordering stable: first writer wins unless
                # the new kind is more specific (word < np < vp < pp < clause < sentence)
                return
            lemmas = _content_lemmas(span)
            level, difficulty = score(kind, modified, lemmas, self.lang)
            found[key] = Candidate(
                start=key[0], end=key[1], text=span_text, kind=kind, level=level,
                difficulty=difficulty, lemmas=lemmas,
                sentence=(offset + sent.start_char, offset + sent.end_char))

        for sent in doc.sents:
            n_tokens = sum(1 for t in sent if not t.is_space and not t.is_punct)

            # sentence
            if MIN_SENTENCE_TOKENS <= n_tokens <= MAX_SENTENCE_TOKENS:
                add(sent.start, sent.end, "sentence", sent, allow_proper=True)

            for tok in sent:
                # word
                if tok.is_alpha and tok.pos_ in WORD_POS and tok.i not in excluded:
                    add(tok.i, tok.i + 1, "word", sent)
                # bare noun: no determiner/possessive/number/adjective attached
                elif tok.pos_ == "NOUN" and tok.is_alpha and tok.i not in excluded and not any(
                        c.dep_ in ("det", "poss", "nummod", "amod", "compound") for c in tok.children) \
                        and tok.dep_ != "compound":
                    add(tok.i, tok.i + 1, "word", sent)

                # verb phrase: verb + aux/neg/particles + its subject (pronoun or a
                # short noun phrase), contiguous. A verb is never swapped alone,
                # because a conjugated form needs its subject for agreement.
                if tok.pos_ == "VERB" or (tok.pos_ == "AUX" and tok.dep_ == "ROOT"):
                    core = [tok.i] + [c.i for c in tok.children if c.dep_ in VP_CHILD_DEPS]
                    subj = [c for c in tok.children if c.dep_ in ("nsubj", "nsubjpass")]
                    subj_tokens: list[int] = []
                    if subj:
                        sub = list(subj[0].subtree)
                        if len(sub) <= 5 and not any(t.i in excluded for t in sub):
                            subj_tokens = [t.i for t in sub]
                    # With a usable subject ("the children played"); otherwise the
                    # verb with its auxiliaries ("is reading"), never a lone verb.
                    for members in ([*core, *subj_tokens], core) if subj_tokens else (core,):
                        covered = set(members)
                        if len(covered) < 2:
                            continue
                        lo, hi = min(members), max(members) + 1
                        if all(i in covered or doc[i].is_punct for i in range(lo, hi)):
                            add(lo, hi, "vp", sent)
                            break

                # prepositional phrase: ADP + object subtree, contiguous
                if tok.pos_ == "ADP" and tok.dep_ == "prep":
                    objs = [c for c in tok.children if c.dep_ in ("pobj", "pcomp")]
                    if objs:
                        sub = list(tok.subtree)
                        lo, hi = sub[0].i, sub[-1].i + 1
                        if hi - lo == len(sub) and 2 <= hi - lo <= 8:
                            add(lo, hi, "pp", sent)

                # clause: subtree of a dependent verb
                if tok.pos_ in ("VERB", "AUX") and tok.dep_ in CLAUSE_DEPS:
                    sub = list(tok.subtree)
                    lo, hi = sub[0].i, sub[-1].i + 1
                    size = sum(1 for t in sub if not t.is_punct and not t.is_space)
                    if hi - lo == len(sub) and 3 <= size <= MAX_CLAUSE_TOKENS and (lo, hi) != (sent.start, sent.end):
                        add(lo, hi, "clause", sent, allow_proper=True)

            # noun phrases
            for chunk in doc.noun_chunks:
                if chunk.start < sent.start or chunk.end > sent.end:
                    continue
                if chunk.root.pos_ not in ("NOUN",):
                    continue
                has_det = any(t.dep_ in ("det", "poss") for t in chunk)
                if len(chunk) == 1 and not has_det:
                    continue            # bare nouns are handled as "word"
                modified = any(t.dep_ in ("amod", "compound", "nummod") for t in chunk)
                add(chunk.start, chunk.end, "np", sent, modified=modified)

        return sorted(found.values(), key=lambda c: (c.start, -(c.end - c.start)))

    def extract_stream(self, text: str, blocks: list[tuple[int, int]]) -> list[Candidate]:
        out: list[Candidate] = []
        for a, b in blocks:
            out.extend(self.extract_block(text[a:b], a))
        return out
