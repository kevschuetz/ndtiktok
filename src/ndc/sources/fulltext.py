"""JATS full text -> sentence rows (D-10): abstract + intro/results/discussion/conclusions only."""

import re
import xml.etree.ElementTree as ET

import yaml

from ndc.config import config_dir
from ndc.sources.pubmed import SentenceRow
from ndc.sources.split import split_sentences

_DROP_TAGS = {
    "xref",
    "table-wrap",
    "fig",
    "disp-formula",
    "inline-formula",
    "table",
    "graphic",
    "supplementary-material",
    "fn",
}
_BRACKET_CITE = re.compile(r"\s*(\[[\d\s,;–\-]*\]|\([\s,;–\-]*\))")


class FullTextError(Exception):
    pass


def _cfg() -> dict:
    return yaml.safe_load((config_dir() / "retrieval.yaml").read_text(encoding="utf-8"))["fulltext"]


def _strip(el: ET.Element) -> None:
    """Remove citation/table/figure elements, keeping each removed element's tail text in place."""
    children = list(el)
    prev = None
    for child in children:
        if child.tag in _DROP_TAGS:
            tail = child.tail or ""
            if prev is not None:
                prev.tail = (prev.tail or "") + tail
            else:
                el.text = (el.text or "") + tail
            el.remove(child)
        else:
            _strip(child)
            prev = child


def _norm_title(t: str) -> str:
    return re.sub(r"^[\d.\s]+", "", t.strip().lower())


def _classify(title: str, keep: list[str], drop: list[str]) -> bool | None:
    t = _norm_title(title)
    if any(t == d or t.startswith(d) for d in drop):
        return False
    if any(t == k or t.startswith(k) or k in t for k in keep):
        return True
    return None


def _paras(el: ET.Element) -> list[str]:
    out = []
    for p in el.iter("p"):
        txt = "".join(p.itertext())
        txt = _BRACKET_CITE.sub("", txt)
        out.append(txt)
    return out


def jats_to_sentences(xml_bytes: bytes) -> list[SentenceRow]:
    cfg = _cfg()
    if len(xml_bytes) > int(cfg["max_xml_bytes"]) or b"<!ENTITY" in xml_bytes:
        raise FullTextError("refusing oversized or entity-bearing XML")
    root = ET.fromstring(xml_bytes)
    keep = [k.lower() for k in cfg["keep_sections"]]
    drop = [d.lower() for d in cfg["drop_sections"]]
    rows: list[SentenceRow] = []
    abstract = root.find(".//front/article-meta/abstract")
    if abstract is not None:
        _strip(abstract)
        for para in _paras(abstract):
            rows += [SentenceRow(s, "Abstract") for s in split_sentences(para, "en")]
    body = root.find(".//body")
    if body is None:
        raise FullTextError("no <body> in full text")
    _strip(body)
    for sec in body.findall("./sec"):
        title = (
            "".join(sec.find("title").itertext()).strip() if sec.find("title") is not None else ""
        )
        if _classify(title, keep, drop) is not True:
            continue
        top = re.sub(r"^[\d.\s]+", "", title).strip() or "Body"
        direct = [c for c in sec if c.tag == "p"]
        for p in direct:
            txt = _BRACKET_CITE.sub("", "".join(p.itertext()))
            rows += [SentenceRow(s, top) for s in split_sentences(txt, "en")]
        for sub in sec.findall("./sec"):
            st = sub.find("title")
            label = f"{top} › {''.join(st.itertext()).strip()}" if st is not None else top
            for para in _paras(sub):
                rows += [SentenceRow(s, label) for s in split_sentences(para, "en")]
    if not rows:
        raise FullTextError("no sentences extracted from full text")
    return rows
