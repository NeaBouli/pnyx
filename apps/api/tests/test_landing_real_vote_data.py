import re

from tests.repo_paths import read_page_with_scripts


def test_democracy_cycle_contains_no_fabricated_vote_result() -> None:
    html = read_page_with_scripts("docs/index.html")

    assert "1.247" not in html
    assert "33% Υπέρ" not in html
    assert "67% Κατά" not in html
    assert "Ν. 4933 Ιδιωτικά Πανεπιστήμια" not in html


def test_democracy_cycle_has_explicit_waiting_and_live_data_targets() -> None:
    html = read_page_with_scripts("docs/index.html")

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
    html = read_page_with_scripts("docs/index.html")

    assert "if (t) el.textContent = t;" in html
    assert "if (t) el.innerHTML = t;" not in html
    assert re.search(r'data-(?:el|en)="[^"]*<', html) is None
    assert "total/electorate*100" in html
    assert "var electorate=9810040" in html
    assert "/ 9.810.040" in html
    assert "/ 9,810,040" in html
