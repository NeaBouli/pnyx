"""Constant-size ID predicates for asyncpg and the SQLite test backend."""
import json

from sqlalchemy import Boolean, JSON, String, bindparam
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.engine import Dialect
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.sql.functions import FunctionElement
from sqlalchemy.sql.selectable import SelectBase


class _IdSet(FunctionElement):
    type = Boolean()
    inherit_cache = True
    _is_implicitly_boolean = True


@compiles(_IdSet)
def _postgres_ids(element, compiler, **kwargs):
    column, ids = element.clauses
    # A relation permits a hash/semi join even with a generic prepared plan.
    # ANY(parameter) can scan the entire array for every candidate bill.
    return f"{compiler.process(column, **kwargs)} IN (SELECT unnest({compiler.process(ids, **kwargs)}))"


@compiles(_IdSet, "sqlite")
def _sqlite_ids(element, compiler, **kwargs):
    column, ids = element.clauses
    return f"{compiler.process(column, **kwargs)} IN (SELECT value FROM json_each({compiler.process(ids, **kwargs)}))"


def bill_ids_filter(column, ids):
    if isinstance(ids, SelectBase):
        return column.in_(ids)
    return _IdSet(column, bindparam(
        "bill_ids", sorted(ids), unique=True,
        type_=JSON().with_variant(ARRAY(String()), "postgresql"),
    ))


def raw_bill_ids_filter(column, ids, *, name, db=None):
    if db_dialect(db).name == "sqlite":
        return f"{column} IN (SELECT value FROM json_each(:{name}))", {name: json.dumps(sorted(ids))}
    return f"{column} IN (SELECT unnest(CAST(:{name} AS VARCHAR[])))", {name: sorted(ids)}


def db_dialect(db):
    from sqlalchemy.dialects.postgresql.asyncpg import dialect as postgres_dialect
    dialect = getattr(getattr(db, "bind", None), "dialect", None)
    if isinstance(dialect, Dialect):
        return dialect
    dialect = postgres_dialect()
    # Offline raw fragments use PostgreSQL's default standard-conforming
    # strings, just like the frozen index DDL. Connected dialects discover it.
    dialect._backslash_escapes = False
    return dialect
