import sqlite3
from types import SimpleNamespace

import pytest
from sqlalchemy.dialects import sqlite

from models import ParliamentBill
from services.source_identity import find_existing_parliament_bill, official_law_id

LAW = "97e0885f-30fe-45f3-bbe9-b4de0151a84f"
OTHER = "726dad50-ab77-453c-9590-b4e4012a069e"


def url(law=LAW, path="Psifisthenta-Nomoschedia"):
    return f"https://www.hellenicparliament.gr/Nomothetiko-Ergo/{path}?law_id={law}"


class DB:
    """Exercise the real lookup SQL against SQLite without application data."""
    def __init__(self, rows):
        self.rows = {row.id: row for row in rows}
        self.connection = sqlite3.connect(":memory:")
        columns = ", ".join(f'"{c.name}" TEXT' for c in ParliamentBill.__table__.columns)
        self.connection.execute(f"CREATE TABLE parliament_bills ({columns})")
        self.connection.executemany("INSERT INTO parliament_bills (id, source, parliament_url) VALUES (?, ?, ?)",
                                    [(r.id, r.source, r.parliament_url) for r in rows])

    async def execute(self, statement):
        sql = str(statement.compile(dialect=sqlite.dialect(), compile_kwargs={"literal_binds": True}))
        found = [self.rows[r[0]] for r in self.connection.execute(sql).fetchall()]
        return SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: found),
                               scalar_one_or_none=lambda: found[0] if found else None)


def row(identity="GR-5422-2026", link=None, source="PARLIAMENT"):
    return ParliamentBill(id=identity, source=source, parliament_url=link or url())


@pytest.mark.parametrize("path", ["Katatethenta-Nomosxedia", "Anazitisi-Nomothetikon-Ergon"])
async def test_source_uuid_reuses_legacy_id_across_url_paths(path):
    existing = row(link=url(LAW.upper(), path))
    db = DB([existing])
    try:
        assert await find_existing_parliament_bill(db, bill_id="GR-" + LAW[:8], url=url()) is existing
    finally:
        db.connection.close()


async def test_duplicate_official_identities_stop_instead_of_choosing_votes_to_keep():
    db = DB([row(), row("GR-" + LAW[:8])])
    try:
        with pytest.raises(ValueError, match="Multiple stored bills"):
            await find_existing_parliament_bill(db, bill_id="GR-new", url=url())
    finally:
        db.connection.close()


async def test_internal_id_collision_does_not_overwrite_another_law():
    db = DB([row("GR-short", url(OTHER))])
    try:
        with pytest.raises(ValueError, match="another official"):
            await find_existing_parliament_bill(db, bill_id="GR-short", url=url())
    finally:
        db.connection.close()


async def test_other_source_and_uuid_in_unbound_parameter_do_not_match():
    db = DB([row(source="DIAVGEIA"), row("GR-other", url(OTHER) + "&related=" + LAW)])
    try:
        assert await find_existing_parliament_bill(db, bill_id="GR-new", url=url()) is None
    finally:
        db.connection.close()


@pytest.mark.parametrize("link", [
    None, "https://example.org/Nomothetiko-Ergo/?law_id=" + LAW,
    url() + "&law_id=" + LAW, url("00000000-0000-0000-0000-000000000000"),
    url().replace("https://", "http://"), url().replace("www.", "user@www."),
])
def test_only_bound_official_nonzero_identities_are_used(link):
    assert official_law_id(link) is None
