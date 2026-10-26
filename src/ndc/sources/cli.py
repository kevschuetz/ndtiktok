"""`ndc source` and `ndc corpus` sub-apps."""

import typer
from rich.console import Console
from rich.table import Table

from ndc.config import db_path
from ndc.db import Database
from ndc.sources import pubmed, store

app = typer.Typer(help="Sources: add, show, list, pick.", no_args_is_help=True)
corpus_app = typer.Typer(help="Corpus: lock and show a topic's source set.", no_args_is_help=True)
console = Console()


def _fail(exc: Exception, code: int = 1) -> typer.Exit:
    typer.echo(f"error: {exc}", err=True)
    return typer.Exit(code=code)


def _db() -> Database:
    return Database(db_path())


@app.command("add")
def add(
    pmid: str = typer.Option(..., "--pmid", help="PubMed ID"),
    topic: int = typer.Option(..., "--topic", help="Whitelisted topic id"),
) -> None:
    """Fetch a paper's abstract from PubMed, snapshot it and pick it for the topic."""
    db = _db()
    conn = db.connect()
    try:
        store.require_whitelisted(conn, topic)
    except store.StoreError as e:
        raise _fail(e) from e
    finally:
        conn.close()
    try:
        meta, rows, raw = pubmed.fetch_abstract(pmid)
        snap_id = store.store_snapshot(db, meta, rows, "pubmed_abstract", raw)
        store.pick(db, topic, snap_id)
    except (pubmed.SourceNotFound, pubmed.RetractedSource, store.StoreError) as e:
        raise _fail(e) from e
    typer.echo(f"snapshot {snap_id}: {len(rows)} sentences — {meta.title}")


@app.command("show")
def show(snapshot_id: int, sample: int = typer.Option(0, help="Show N random sentences")) -> None:
    """List a snapshot's numbered sentences."""
    conn = _db().connect()
    try:
        head = conn.execute(
            "SELECT ss.*, s.title, s.pmid, s.doi, s.awmf_reg_no FROM source_snapshot ss "
            "JOIN source s ON s.id = ss.source_id WHERE ss.id = ?",
            (snapshot_id,),
        ).fetchone()
        if head is None:
            raise _fail(Exception(f"snapshot {snapshot_id} not found"))
        typer.echo(f"{head['title']}  [{head['origin']}] sha256 {head['sha256']}")
        q = "SELECT ordinal, section, page, text FROM source_sentence WHERE snapshot_id = ?"
        q += " ORDER BY random() LIMIT ?" if sample else " ORDER BY ordinal LIMIT ?"
        for r in conn.execute(q, (snapshot_id, sample or -1)):
            loc = f"S.{r['page']}" if r["page"] is not None else (r["section"] or "")
            typer.echo(f"[{r['ordinal']}] ({loc}) {r['text']}")
    finally:
        conn.close()


@app.command("list")
def list_(topic: int = typer.Option(..., "--topic")) -> None:
    """List the snapshots picked for a topic."""
    conn = _db().connect()
    try:
        t = Table("snapshot", "origin", "sentences", "year", "id")
        t.add_column("title", no_wrap=True, overflow="ellipsis", max_width=36)
        for r in conn.execute(
            "SELECT ss.id, ss.origin, ss.n_sentences, s.year, "
            "COALESCE(s.pmid, s.doi, s.awmf_reg_no) AS ident, s.title FROM topic_pick tp "
            "JOIN source_snapshot ss ON ss.id = tp.snapshot_id "
            "JOIN source s ON s.id = ss.source_id "
            "WHERE tp.topic_id = ? ORDER BY tp.picked_at",
            (topic,),
        ):
            t.add_row(
                str(r["id"]),
                r["origin"],
                str(r["n_sentences"]),
                str(r["year"] or ""),
                str(r["ident"] or ""),
                (r["title"] or "")[:80],
            )
        console.print(t)
    finally:
        conn.close()


@app.command("pick-snapshot")
def pick_snapshot(topic: int, snapshot_id: int) -> None:
    """Add an existing snapshot (e.g. an AWMF guideline) to a topic's picks."""
    try:
        store.pick(_db(), topic, snapshot_id)
    except store.StoreError as e:
        raise _fail(e) from e
    typer.echo(f"picked snapshot {snapshot_id} for topic {topic}")


@app.command("unpick")
def unpick(topic: int, snapshot_id: int) -> None:
    store.unpick(_db(), topic, snapshot_id)
    typer.echo(f"unpicked snapshot {snapshot_id} from topic {topic}")


@corpus_app.command("lock")
def lock(topic_id: int) -> None:
    """Freeze the topic's picked snapshots into a corpus (2–5 sources)."""
    try:
        cid = store.lock_corpus(_db(), topic_id)
    except store.StoreError as e:
        raise _fail(e) from e
    conn = _db().connect()
    try:
        sha = conn.execute("SELECT sha256 FROM corpus WHERE id = ?", (cid,)).fetchone()[0]
    finally:
        conn.close()
    typer.echo(f"corpus {cid} sha256 {sha}")


@corpus_app.command("show")
def corpus_show(topic_id: int) -> None:
    conn = _db().connect()
    try:
        c = store.latest_corpus(conn, topic_id)
        if c is None:
            raise _fail(Exception(f"topic {topic_id} has no locked corpus"))
        typer.echo(f"corpus {c['id']} sha256 {c['sha256']} locked {c['locked_at']}")
        for r in conn.execute(
            "SELECT position, snapshot_id, short_cite FROM corpus_source WHERE corpus_id = ? "
            "ORDER BY position",
            (c["id"],),
        ):
            typer.echo(f"  [{r['position']}] snapshot {r['snapshot_id']}  {r['short_cite']}")
    finally:
        conn.close()


@app.command("search")
def search_cmd(
    topic: int,
    query: str = typer.Option(None, "--query", help="Replace the topic part of the query"),
    as_json: bool = typer.Option(False, "--json", help="Print rows as JSON"),
) -> None:
    """Ranked PubMed shortlist for a topic (guidelines/SR/MA first; OA and safety flags)."""
    import json as _json

    from ndc.sources import search as search_mod

    db = _db()
    try:
        run_id = search_mod.search(db, topic, query)
    except (search_mod.SearchError, pubmed.SourceNotFound) as e:
        raise _fail(e) from e
    conn = db.connect()
    try:
        run = conn.execute("SELECT * FROM search_run WHERE id = ?", (run_id,)).fetchone()
        rows = conn.execute(
            "SELECT * FROM source_candidate WHERE search_run_id = ? ORDER BY rank", (run_id,)
        ).fetchall()
    finally:
        conn.close()
    if as_json:
        typer.echo(_json.dumps([dict(r) for r in rows], ensure_ascii=False, indent=1))
        return
    typer.echo(f"query: {run['query']}")
    t = Table("rank", "score", "type", "year", "OA", "⚠", "pmid")
    t.add_column("title", no_wrap=True, overflow="ellipsis", max_width=42)
    for r in rows:
        oa = "?" if r["is_oa"] is None else ("ja" if r["is_oa"] else "–")
        t.add_row(
            str(r["rank"]),
            f"{r['score']:.1f}",
            r["tier"] or "",
            str(r["year"] or ""),
            oa,
            "⚠" if r["safety_flag"] else "",
            r["pmid"] or "",
            (r["title"] or "")[:90],
        )
    console.print(t)
    typer.echo(f"pick with: ndc source pick {topic} <rank> [<rank> ...]")


@app.command("pick")
def pick_cmd(topic: int, ranks: list[int]) -> None:
    """Store abstract (+ OA full text) for the given ranks of the topic's newest search."""
    from ndc.sources import europepmc, fulltext
    from ndc.sources import search as search_mod

    db = _db()
    conn = db.connect()
    try:
        store.require_whitelisted(conn, topic)
        run = search_mod.latest_run(conn, topic)
        if run is None:
            raise _fail(Exception(f"no search for topic {topic}; run ndc source search {topic}"))
        cands = {}
        for rk in ranks:
            row = conn.execute(
                "SELECT * FROM source_candidate WHERE search_run_id = ? AND rank = ?",
                (run["id"], rk),
            ).fetchone()
            if row is None:
                raise _fail(Exception(f"rank {rk} not in search run {run['id']}"))
            cands[rk] = row
    except store.StoreError as e:
        raise _fail(e) from e
    finally:
        conn.close()
    for rk, c in cands.items():
        try:
            meta, rows, raw = pubmed.fetch_abstract(c["pmid"])
            abs_id = store.store_snapshot(db, meta, rows, "pubmed_abstract", raw)
            store.pick(db, topic, abs_id)
        except (pubmed.SourceNotFound, pubmed.RetractedSource, store.StoreError) as e:
            raise _fail(Exception(f"rank {rk}: {e}")) from e
        ft_msg = "kein OA-Volltext"
        pmcid = meta.pmcid or c["pmcid"]
        if pmcid and c["is_oa"]:
            try:
                xml = europepmc.fulltext_xml(pmcid)
                ft_rows = fulltext.jats_to_sentences(xml)
                ft_id = store.store_snapshot(db, meta, ft_rows, "epmc_fulltext", xml)
                store.pick(db, topic, ft_id)
                ft_msg = f"Volltext {len(ft_rows)} Sätze (snapshot {ft_id})"
            except Exception as e:  # keep the abstract; report the full-text problem
                ft_msg = f"Volltext fehlgeschlagen: {type(e).__name__}: {e}"
        typer.echo(
            f"rank {rk}: {meta.title[:80]} — Abstract {len(rows)} Sätze "
            f"(snapshot {abs_id}); {ft_msg}"
        )
