import re
from pathlib import Path


LANDING_HTML = Path(__file__).resolve().parents[3] / "docs" / "index.html"


def test_democracy_cycle_contains_no_fabricated_vote_result() -> None:
    html = LANDING_HTML.read_text(encoding="utf-8")

    assert "1.247" not in html
    assert "33% Υπέρ" not in html
    assert "67% Κατά" not in html
    assert "Ν. 4933 Ιδιωτικά Πανεπιστήμια" not in html


def test_democracy_cycle_has_explicit_waiting_and_live_data_targets() -> None:
    html = LANDING_HTML.read_text(encoding="utf-8")

    assert 'id="demoYesLabel"' in html
    assert 'id="demoNoLabel"' in html
    assert 'id="resultTotal"' in html
    assert 'id="resultYesLabel"' in html
    assert 'id="resultNoLabel"' in html
    assert 'id="resultMajority"' in html
    assert 'id="latestBillTitle"' in html
    assert "Αναμονή πραγματικών δεδομένων" in html
    assert "window._liveResult=data" in html


def test_live_result_language_switch_is_text_only_and_uses_site_electorate() -> None:
    html = LANDING_HTML.read_text(encoding="utf-8")

    assert "if (t) el.textContent = t;" in html
    assert "if (t) el.innerHTML = t;" not in html
    assert re.search(r'data-(?:el|en)="[^"]*<', html) is None
    assert "total/electorate*100" in html
    assert "var electorate=9810040" in html
    assert "/ 9.810.040" in html
    assert "/ 9,810,040" in html
