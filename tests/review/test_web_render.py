from ndc.review import web_render as wr


def test_list_empty_state():
    html = wr.render_list([], [])
    assert "Nichts zu prüfen" in html and "ndc script verify" in html


def test_error_page_fixed_copy():
    html = wr.render_error(404, "Nicht gefunden.")
    assert "Nicht gefunden." in html and "<script" not in html
