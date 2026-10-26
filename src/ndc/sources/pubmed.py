"""PubMed E-utilities client: polite (tool/email, rate-limited), retried, never logs keys."""

import os
import threading
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field

import httpx
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
MAX_XML_BYTES = 20 * 1024 * 1024


class SourceNotFound(Exception):
    pass


class RetractedSource(Exception):
    pass


@dataclass
class SourceMeta:
    kind: str
    title: str
    pmid: str | None = None
    pmcid: str | None = None
    doi: str | None = None
    authors: list[str] = field(default_factory=list)
    year: int | None = None
    journal: str | None = None
    pubtypes: list[str] = field(default_factory=list)
    language: str | None = None
    awmf_reg_no: str | None = None
    awmf_version: str | None = None
    awmf_valid_until: str | None = None
    awmf_status: str | None = None


@dataclass
class SentenceRow:
    text: str
    section: str | None = None
    page: int | None = None


def _retryable(exc: BaseException) -> bool:
    if isinstance(exc, httpx.TransportError):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code == 429 or exc.response.status_code >= 500
    return False


class _RateLimiter:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._last = 0.0

    def wait(self, interval: float) -> None:
        with self._lock:
            delta = time.monotonic() - self._last
            if delta < interval:
                time.sleep(interval - delta)
            self._last = time.monotonic()


_LIMITER = _RateLimiter()
_client: httpx.Client | None = None


def set_client(client: httpx.Client | None) -> None:
    """Inject an httpx client (tests use httpx.MockTransport)."""
    global _client
    _client = client


def _http() -> httpx.Client:
    global _client
    if _client is None:
        _client = httpx.Client(timeout=20.0, headers={"User-Agent": "ndc/0.1"})
    return _client


def _base_params() -> dict:
    p = {"tool": "ndc", "email": os.environ.get("NCBI_EMAIL") or "ndc@localhost"}
    if os.environ.get("NCBI_API_KEY"):
        p["api_key"] = os.environ["NCBI_API_KEY"]
    return p


@retry(
    retry=retry_if_exception(_retryable),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=0.5, max=8),
    reraise=True,
)
def get(endpoint: str, params: dict) -> httpx.Response:
    _LIMITER.wait(0.11 if os.environ.get("NCBI_API_KEY") else 0.34)
    r = _http().get(f"{EUTILS}/{endpoint}", params={**_base_params(), **params})
    r.raise_for_status()
    return r


def esummary(pmids: list[str]) -> dict:
    """esummary JSON `result` dict keyed by pmid (each may carry an `error` key)."""
    r = get("esummary.fcgi", {"db": "pubmed", "retmode": "json", "id": ",".join(pmids)})
    return r.json().get("result", {})


def _text(el: ET.Element | None) -> str:
    return "".join(el.itertext()).strip() if el is not None else ""


def parse_efetch(xml_bytes: bytes, pmid: str) -> tuple[SourceMeta, list[SentenceRow]]:
    """Parse one PubmedArticle; raises SourceNotFound / RetractedSource."""
    from ndc.sources.split import split_sentences  # local: keeps pysbd import lazy

    if len(xml_bytes) > MAX_XML_BYTES or b"<!ENTITY" in xml_bytes:
        raise SourceNotFound(f"PMID {pmid}: refusing oversized or entity-bearing XML")
    root = ET.fromstring(xml_bytes)
    art = root.find(".//PubmedArticle")
    if art is None:
        raise SourceNotFound(f"PMID {pmid} not found")
    pubtypes = [_text(p) for p in art.findall(".//PublicationTypeList/PublicationType")]
    retracted = "Retracted Publication" in pubtypes or any(
        c.get("RefType") == "RetractionIn"
        for c in art.findall(".//CommentsCorrectionsList/CommentsCorrections")
    )
    if retracted:
        raise RetractedSource(f"PMID {pmid} is retracted")
    article = art.find(".//Article")
    title = _text(article.find("ArticleTitle")) if article is not None else ""
    if not title:
        raise SourceNotFound(f"PMID {pmid}: no title")
    authors = [
        _text(a.find("LastName")) or _text(a.find("CollectiveName"))
        for a in art.findall(".//AuthorList/Author")
    ]
    year = None
    for path in (".//JournalIssue/PubDate/Year", ".//ArticleDate/Year"):
        y = _text(art.find(path))
        if y.isdigit():
            year = int(y)
            break
    if year is None:
        medline = _text(art.find(".//JournalIssue/PubDate/MedlineDate"))
        if medline[:4].isdigit():
            year = int(medline[:4])
    ids = {i.get("IdType"): _text(i) for i in art.findall(".//PubmedData/ArticleIdList/ArticleId")}
    lang = _text(art.find(".//Article/Language")) or None
    meta = SourceMeta(
        kind="pubmed",
        title=title,
        pmid=pmid,
        pmcid=ids.get("pmc") or None,
        doi=(ids.get("doi") or "").lower() or None,
        authors=[a for a in authors if a],
        year=year,
        journal=_text(art.find(".//Journal/ISOAbbreviation")) or _text(art.find(".//Journal/Title")),
        pubtypes=pubtypes,
        language=lang,
    )
    rows: list[SentenceRow] = []
    for ab in art.findall(".//Abstract/AbstractText"):
        section = ab.get("Label") or "Abstract"
        for s in split_sentences(_text(ab), "en"):
            rows.append(SentenceRow(text=s, section=section))
    if not rows:
        raise SourceNotFound(f"PMID {pmid}: no abstract")
    return meta, rows


def fetch_abstract(pmid: str) -> tuple[SourceMeta, list[SentenceRow], bytes]:
    pmid = pmid.strip()
    if not pmid.isdigit():
        raise SourceNotFound(f"invalid PMID {pmid!r}")
    summ = esummary([pmid]).get(pmid, {})
    if not summ or "error" in summ:
        raise SourceNotFound(f"PMID {pmid} not found")
    raw = get("efetch.fcgi", {"db": "pubmed", "retmode": "xml", "id": pmid}).content
    meta, rows = parse_efetch(raw, pmid)
    return meta, rows, raw
