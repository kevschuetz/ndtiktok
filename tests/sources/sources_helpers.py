"""Offline PubMed/Europe PMC/Crossref responses for tests/sources (no network, no keys)."""

import json
import os
from pathlib import Path

import httpx
import pytest

from ndc.db import Database
from ndc.sources import pubmed

FIX = Path(__file__).resolve().parent.parent / "fixtures" / "sources"


def fixture_bytes(name: str) -> bytes:
    return (FIX / name).read_bytes()


class Router:
    """Map (path-suffix, id param) -> fixture body; records calls."""

    def __init__(self):
        self.routes: dict[tuple[str, str], tuple[int, bytes]] = {}
        self.calls: list[httpx.Request] = []

    def add(self, endpoint: str, ident: str, body: bytes, status: int = 200):
        self.routes[(endpoint, ident)] = (status, body)

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.calls.append(request)
        endpoint = request.url.path.rsplit("/", 1)[-1]
        ident = request.url.params.get("id", "")
        if (endpoint, ident) in self.routes:
            status, body = self.routes[(endpoint, ident)]
            return httpx.Response(status, content=body)
        return httpx.Response(404, content=b"not routed")



def esummary_json(pmid: str, title: str, year: str = "2020", doi: str | None = None) -> bytes:
    ids = [{"idtype": "pubmed", "value": pmid}]
    if doi:
        ids.append({"idtype": "doi", "value": doi})
    return json.dumps(
        {"result": {"uids": [pmid], pmid: {"uid": pmid, "title": title, "pubdate": year,
                                            "articleids": ids}}}
    ).encode()
