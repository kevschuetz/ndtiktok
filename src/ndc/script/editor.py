"""TikTok editor pass (D-20/D-21): punch up a grounded script without losing its evidence.

The editor sees the script in export format (one sentence per line + citation markers) and must
return the same format. It may only reuse markers that were in its input; the result enters as a
new version via the normal import path and every changed sentence is re-verified.
"""

from ndc import llm
from ndc.config import db_path
from ndc.db import Database
from ndc.script import edit


class PunchError(Exception):
    pass


def _text(message) -> str:
    data = message.model_dump(mode="json") if hasattr(message, "model_dump") else message
    return "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")


def punch(
    db: Database | None = None,
    version_id: int = 0,
    *,
    client=None,
    config: llm.LlmConfig | None = None,
) -> dict:
    db = db or Database(db_path())
    cfg = config or llm.load_llm_config()
    if cfg.editor is None:
        raise PunchError("llm.yaml has no 'editor' stage")
    conn = db.connect()
    try:
        v = conn.execute("SELECT * FROM script_version WHERE id = ?", (version_id,)).fetchone()
    finally:
        conn.close()
    if v is None:
        raise PunchError(f"script version {version_id} not found")
    exported = edit.export(db, v["sha256"])
    allowed = {r for ln in edit.parse_import(exported).lines for r in ln.refs}
    system, prompt_sha = llm.load_prompt(cfg.editor)
    request = {
        "model": cfg.editor.model,
        "max_tokens": cfg.editor.max_tokens,
        "output_config": {"effort": cfg.editor.effort},
        "system": system,
        "messages": [{"role": "user", "content": exported}],
    }
    msg, _ = llm.call(
        "editor",
        request,
        prompt_sha=prompt_sha,
        input_shas=[v["sha256"]],
        subject=("script_version", version_id),
        client=client,
        db=db,
        config=cfg,
    )
    out = _text(msg).strip()
    lines = out.splitlines()
    header = exported.splitlines()[0]
    body = [ln for ln in lines if not ln.lstrip().startswith("#")]
    out = "\n".join([header, *body]) + "\n"  # header is ours, never the model's
    try:
        parsed = edit.parse_import(out)
    except edit.EditError as e:
        raise PunchError(f"editor output unusable: {e}") from e
    invented = {r for ln in parsed.lines for r in ln.refs} - allowed
    if invented:
        raise PunchError(f"editor invented citation markers {sorted(invented)} — not imported")
    try:
        return edit.import_edit(db, out, client=client, config=cfg)
    except edit.EditError as e:
        raise PunchError(str(e)) from e
