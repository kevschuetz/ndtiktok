"""Hashtag harvest from competitor post descriptions (MKT-03, plan 01-14).

Counts, per tag, the distinct accounts using it and the median views of mid-tier posts carrying
it, over the chosen language's selected sample. Case variants are merged (key = lowercase,
which keeps ß), the most frequent original spelling is kept for display. A tag is excluded when
the checker does not return "ok" for it (block or an un-overridden warn: a hashtag has no
override flow), or when it is a community self-identification tag (#ActuallyAutistic).
Read-only on the DB; zero network.
"""

import re
import statistics
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import yaml

from ndc.checks.engine import check
from ndc.db import Database

TAG_RE = re.compile(r"#[\wäöüÄÖÜß]+")
COMMUNITY_SELF_ID = {"#actuallyautistic"}
_CAMEL = re.compile(r"(?<=[a-zäöüß])(?=[A-ZÄÖÜ])")


@dataclass
class TagStat:
    tag: str
    display: str
    n_accounts: int
    n_posts: int
    mid_n_posts: int
    mid_median_views: float | None
    median_views: float | None
    accounts: list[str] = field(default_factory=list)
    check_status: str = "ok"
    excluded: bool = False
    exclusion_reason: str | None = None


def _median(values: list[int]) -> float | None:
    return float(statistics.median(values)) if values else None


def _safety(display: str, lang: str) -> tuple[str, list[str]]:
    """Worst checker status over the tag, the bare word and its camel-case split."""
    bare = display.lstrip("#")
    variants = {display, bare, _CAMEL.sub(" ", bare)}
    rank = {"ok": 0, "needs_override": 1, "blocked": 2}
    worst, rules = "ok", set()
    for text in variants:
        res = check(text, lang, level="topic")
        rules.update(f.rule_id for f in res.findings)
        if rank[res.status] > rank[worst]:
            worst = res.status
    return worst, sorted(rules)


def harvest(db: Database, lang: str, selected_only: bool = True) -> list[TagStat]:
    sql = (
        "SELECT a.handle, a.platform, a.tier, p.views, p.description"
        " FROM competitor_post p JOIN competitor_account a ON a.id = p.account_id"
        " LEFT JOIN competitor_candidate c ON c.handle = a.handle AND c.platform = a.platform"
        " WHERE a.language = ? AND p.description IS NOT NULL"
    )
    if selected_only:
        sql += " AND c.status = 'selected'"
    conn = db.connect()
    try:
        rows = conn.execute(sql, (lang,)).fetchall()
    finally:
        conn.close()

    spellings: dict[str, Counter] = defaultdict(Counter)
    accounts: dict[str, set] = defaultdict(set)
    posts: Counter = Counter()
    views_all: dict[str, list[int]] = defaultdict(list)
    views_mid: dict[str, list[int]] = defaultdict(list)
    for handle, platform, tier, views, desc in rows:
        found = TAG_RE.findall(unicodedata.normalize("NFC", desc))
        keys = set()
        for raw in found:
            key = raw.lower()
            spellings[key][raw] += 1
            keys.add(key)
        for key in keys:
            accounts[key].add(f"{platform}:{handle}")
            posts[key] += 1
            if views is not None:
                views_all[key].append(views)
                if tier == "mid":
                    views_mid[key].append(views)

    out = []
    for key in posts:
        display = spellings[key].most_common(1)[0][0]
        status, rules = _safety(display, lang)
        stat = TagStat(
            tag=key,
            display=display,
            n_accounts=len(accounts[key]),
            n_posts=posts[key],
            mid_n_posts=len(views_mid[key]),
            mid_median_views=_median(views_mid[key]),
            median_views=_median(views_all[key]),
            accounts=sorted(accounts[key]),
            check_status=status,
        )
        if key in COMMUNITY_SELF_ID:
            stat.excluded, stat.exclusion_reason = True, "community_self_id"
        elif status != "ok":
            stat.excluded, stat.exclusion_reason = True, f"{status}: {', '.join(rules)}"
        out.append(stat)
    out.sort(key=lambda s: (-s.n_accounts, -s.n_posts, s.tag))
    return out


def write_harvest(stats: list[TagStat], path: Path, lang: str, selected_only: bool = True) -> int:
    data = {
        "language": lang,
        "generated_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "sample": "selected accounts" if selected_only else "all accounts",
        "method": "regex #[\\wäöüÄÖÜß]+ over competitor_post.description; case merged",
        "tags": [
            {
                "tag": s.tag,
                "display": s.display,
                "n_accounts": s.n_accounts,
                "n_posts": s.n_posts,
                "mid_n_posts": s.mid_n_posts,
                "mid_median_views": s.mid_median_views,
                "median_views": s.median_views,
                "check_status": s.check_status,
                "excluded": s.excluded,
                "exclusion_reason": s.exclusion_reason,
                "accounts": s.accounts,
            }
            for s in stats
        ],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(data, allow_unicode=True, sort_keys=False, width=100), encoding="utf-8"
    )
    return len(stats)
