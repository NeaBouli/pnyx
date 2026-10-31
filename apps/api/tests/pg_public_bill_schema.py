"""Install migration-owned functions before tests create PostgreSQL model indexes."""
import importlib.util
from pathlib import Path
from types import ModuleType

from sqlalchemy.ext.asyncio import AsyncConnection


def public_metadata_revision(*, legacy: bool = False) -> ModuleType:
    filename = (
        "z902a2b3c4d5_public_bill_metadata_index.py" if legacy
        else "z903a2b3c4d5_public_bill_sensitive_cost.py"
    )
    return _revision(filename)


def sensitivity_revision() -> ModuleType:
    return _revision("z904a2b3c4d5_persist_bill_sensitivity.py")


def _revision(filename: str) -> ModuleType:
    path = Path(__file__).resolve().parents[1] / "alembic/versions" / filename
    spec = importlib.util.spec_from_file_location("public_metadata_revision", path)
    assert spec is not None and spec.loader is not None
    revision = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(revision)
    return revision


async def install_public_bill_function(connection: AsyncConnection) -> None:
    await connection.exec_driver_sql(public_metadata_revision().FUNCTION_DDL)
