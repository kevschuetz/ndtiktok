"""Europe PMC REST client: OA status lookup and JATS full text (retried, rate-limited)."""

import os

import httpx
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from ndc.sources.pubmed import _RateLimiter, _retryable

BASE = "https://www.ebi.ac.uk/europepmc/webservices/rest"
_LIMITER = _RateLimiter()
_client: httpx.Client | None = None


def set_client(client: httpx.Client | None) -> None:
    global _client
    _client = client


def _http() -> httpx.Client:
    global _client
    if _client is None:
        email = os.environ.get("NCBI_EMAIL") or "ndc@localhost"
        _client = httpx.Client(timeout=30.0, headers={"User-Agent": f"ndc/0.1 (mailto:{email})"})
    return _client


@retry(
    retry=retry_if_exception(_retryable),
    stop=stop_after_attempt(4),
    wait=wait_exponential(multiplier=1, max=15),
    reraise=True,
)
def _get(path: str, params: dict | None = None) -> httpx.Response:
    _LIMITER.wait(0.2)
    r = _http().get(f"{BASE}/{path}", params=params)
    r.raise_for_status()
    return r


def oa_status(pmids: list[str]) -> dict[str, dict]:
    """pmid -> {"is_oa": bool, "pmcid": str|None} for every pmid Europe PMC knows."""
    out: dict[str, dict] = {}
    for i in range(0, len(pmids), 50):
        chunk = pmids[i : i + 50]
        q = "(" + " OR ".join(f"EXT_ID:{p}" for p in chunk) + ") AND SRC:MED"
        r = _get("search", {"query": q, "format": "json", "resultType": "lite", "pageSize": 100})
        for res in r.json().get("resultList", {}).get("result", []):
            pmid = res.get("pmid") or res.get("id")
            if pmid:
                out[pmid] = {
                    "is_oa": res.get("isOpenAccess") == "Y",
                    "pmcid": res.get("pmcid"),
                }
    return out


def fulltext_xml(pmcid: str) -> bytes:
    if not pmcid.upper().startswith("PMC") or not pmcid[3:].isdigit():
        raise ValueError(f"invalid PMCID {pmcid!r}")
    return _get(f"{pmcid.upper()}/fullTextXML").content
