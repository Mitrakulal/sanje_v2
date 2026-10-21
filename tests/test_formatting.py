from bot.formatting import html_to_plain, split_html, to_telegram_html

SAMPLE = """### Best Time to Hit the Beaches

| Time of Day | Why It's Good | Typical Conditions |
|---|---|---|
| **Early Morning** | • Cooler, breezy air.<br>• Fewer crowds. | Forecast: warm with a low rain chance. |
| **Late Evening** | • Sunset views.<br>• Pleasant temperatures. | 90% chance of rain. |
"""


def test_headings_and_tables_become_readable_blocks():
    rendered = to_telegram_html(SAMPLE)

    assert "<b>Best Time to Hit the Beaches</b>" in rendered
    assert "<b>Early Morning</b>" in rendered
    assert "• <b>Why It's Good:</b> Cooler, breezy air." in rendered
    assert "• Fewer crowds." in rendered
    assert "• <b>Typical Conditions:</b> Forecast: warm" in rendered
    assert "|" not in rendered
    assert "###" not in rendered
    assert "<br>" not in rendered


def test_html_is_escaped():
    rendered = to_telegram_html("<script>alert(1)</script>")
    assert "&lt;script&gt;" in rendered
    assert "<script>" not in rendered


def test_split_html_keeps_chunks_under_limit():
    text = "\n".join(["a" * 100] * 50)
    chunks = split_html(text, limit=500)
    assert len(chunks) > 1
    assert all(len(chunk) <= 500 for chunk in chunks)


def test_html_to_plain_strips_tags():
    assert html_to_plain("<b>Hello</b> &amp; welcome") == "Hello & welcome"
