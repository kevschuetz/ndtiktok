from ndc.script import sources_list as sl


def test_pack_comments_never_truncates():
    entries = [
        "Soler-Gutiérrez 2023 (PMID 36608036)",
        "Graziano 2016 (PMID 27180913)",
        "Shaw 2014 (PMID 24480998)",
        "Faraone 2021 (PMID 33549739)",
        "AWMF 028-045 (Version 2.0)",
    ]
    parts = sl.pack_comments(entries, "Quellen", 150)
    assert all(len(p) <= 150 for p in parts)
    joined = " ".join(parts)
    assert all(e in joined for e in entries)
    one = sl.pack_comments(entries[:2], "Quellen", 150)
    assert one == ["Quellen: Soler-Gutiérrez 2023 (PMID 36608036); Graziano 2016 (PMID 27180913)"]
    multi = sl.pack_comments(entries, "Quellen", 80)
    assert multi[0].startswith(f"Quellen 1/{len(multi)}: ")
    long = sl.pack_comments(["x" * 200], "Quellen", 150)
    assert long == ["Quellen: " + "x" * 200]
