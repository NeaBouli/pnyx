"""Keep all representation SQL/ORM writers behind an invalidating commit.

Scan production Python, including standalone scripts and seeds. Mutation-only
helpers are checked through every caller; they must not invalidate before commit.
The inventory in representation-performance.md records the resulting boundaries.
"""
import ast
from collections import defaultdict
from pathlib import Path
import re
import subprocess

import pytest

from models import CitizenVote, ParliamentBill, ZkVoteReceipt

ROOT = Path(__file__).resolve().parents[3]
MODELS = {model.__name__: set(model.__table__.columns.keys())
          for model in (ParliamentBill, CitizenVote, ZkVoteReceipt)}
TABLES = "|".join(model.__tablename__ for model in (ParliamentBill, CitizenVote, ZkVoteReceipt))
SQL_WRITE = re.compile(
    rf'\b(?:INSERT\s+INTO|UPDATE|DELETE\s+FROM|TRUNCATE(?:\s+TABLE)?)\s+'
    rf'(?:(?:"?\w+"?)\s*\.\s*)?["`]?({TABLES})\b', re.I,
)
BOUNDARIES = {"commit_and_invalidate_representation", "invalidate_representation_cache"}
DML = {"insert", "update", "delete", "bulk_insert_mappings", "bulk_update_mappings"}


def sql_text(node):
    return "".join(n.value for n in ast.walk(node)
                   if isinstance(n, ast.Constant) and isinstance(n.value, str))


def local_nodes(function):
    """Do not attribute nested functions' writes/commits to their enclosing function."""
    todo = list(function.body)
    while todo:
        node = todo.pop()
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        yield node
        todo.extend(ast.iter_child_nodes(node))


def scan(sources):
    functions, calls, callers, writers, commits, guarded = {}, {}, defaultdict(set), set(), set(), set()
    by_name = defaultdict(set)
    for path, source in sources.items():
        tree = ast.parse(source)
        aliases = {node.asname or node.name: node.name for node in ast.walk(tree)
                   if isinstance(node, ast.alias) and node.name in MODELS}
        for name in MODELS:
            aliases.setdefault(name, name)
        dml_aliases = {node.asname or node.name: node.name for node in ast.walk(tree)
                       if isinstance(node, ast.alias) and node.name in DML}
        sql_names = set()
        for node in tree.body:
            if isinstance(node, (ast.Assign, ast.AnnAssign)) and node.value is not None:
                if SQL_WRITE.search(sql_text(node.value)):
                    targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                    sql_names.update(n.id for target in targets for n in ast.walk(target) if isinstance(n, ast.Name))
        for fn in ast.walk(tree):
            if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            key = (path, fn.name)
            functions[key] = fn
            by_name[fn.name].add(key)
            nodes = list(local_nodes(fn))
            fn_calls = [n for n in nodes if isinstance(n, ast.Call)]
            calls[key] = {n.func.id for n in fn_calls if isinstance(n.func, ast.Name)}
            if calls[key] & BOUNDARIES:
                guarded.add(key)
            if any(isinstance(n.func, ast.Attribute) and n.func.attr == "commit" for n in fn_calls):
                commits.add(key)
            # Track selected model instances through result.scalar(s), loops and
            # local aliases. This also finds mutations named x/existing, not just bill.
            tracked = {arg.arg for arg in (*fn.args.posonlyargs, *fn.args.args, *fn.args.kwonlyargs)
                       if arg.annotation and any(isinstance(n, ast.Name) and n.id in aliases
                                                 for n in ast.walk(arg.annotation))}
            tracked.update(arg.arg for arg in fn.args.args if arg.arg in {"bill", "receipt"})

            def tracked_expr(expr):
                return any(isinstance(n, ast.Name) and n.id in (tracked | aliases.keys())
                           for n in ast.walk(expr))

            for _ in range(len(nodes)):
                before = set(tracked)
                for n in nodes:
                    if isinstance(n, (ast.Assign, ast.AnnAssign)) and n.value is not None and tracked_expr(n.value):
                        targets = n.targets if isinstance(n, ast.Assign) else [n.target]
                        tracked.update(t.id for target in targets for t in ast.walk(target) if isinstance(t, ast.Name))
                    if isinstance(n, (ast.For, ast.AsyncFor)) and tracked_expr(n.iter):
                        tracked.update(t.id for t in ast.walk(n.target) if isinstance(t, ast.Name))
                if tracked == before:
                    break
            for n in nodes:
                if isinstance(n, ast.Constant) and isinstance(n.value, str) and SQL_WRITE.search(n.value):
                    writers.add(key)
                if isinstance(n, (ast.BinOp, ast.JoinedStr)) and SQL_WRITE.search(sql_text(n)):
                    writers.add(key)
                if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load) and n.id in sql_names:
                    writers.add(key)
                if isinstance(n, ast.Attribute) and isinstance(n.ctx, ast.Store) and tracked_expr(n.value):
                    if any(n.attr in fields for fields in MODELS.values()):
                        writers.add(key)
                if not isinstance(n, ast.Call):
                    continue
                name = n.func.id if isinstance(n.func, ast.Name) else getattr(n.func, "attr", "")
                name = dml_aliases.get(name, name)
                if name in aliases or (name in DML and (
                    (isinstance(n.func, ast.Name) and n.args and tracked_expr(n.args[0])) or
                    (name == "delete" and n.args and tracked_expr(n.args[0])) or
                    (isinstance(n.func, ast.Attribute) and any(
                        isinstance(part, ast.Name) and part.id in aliases
                        for part in ast.walk(n.func.value)))
                )):
                    writers.add(key)
                if name == "setattr" and n.args and tracked_expr(n.args[0]):
                    writers.add(key)
    for key, names in calls.items():
        for name in names:
            targets = {(key[0], name)} if (key[0], name) in functions else by_name[name]
            for target in targets:
                callers[target].add(key)
    # Vote mutations share _commit_vote_write; other service entry points may
    # delegate to a committing writer. Resolve those boundaries transitively.
    forward = set(guarded)
    while True:
        added = {key for key, names in calls.items() if any(
            target in forward for name in names for target in
            ({(key[0], name)} if (key[0], name) in functions else by_name[name]))}
        if added <= forward:
            break
        forward |= added

    def covered(key, visiting=frozenset()):
        if key[0].startswith("apps/api/alembic/versions/"):
            # Revisions run synchronously inside Alembic's transaction. The
            # async runner invalidates only after that transaction commits.
            return ("apps/api/alembic/env.py", "run_async_migrations") in guarded
        if key in commits:
            return False
        if key in forward:
            return True
        if key in visiting or not callers[key]:
            return False
        return all(covered(parent, visiting | {key}) for parent in callers[key])

    missing = {key for key in writers if not covered(key)}
    # A prior guarded call must never excuse a subsequent naked commit.
    affected = set(writers)
    while True:
        parents = {parent for key in affected for parent in callers[key]}
        if parents <= affected:
            break
        affected |= parents
    missing |= affected & commits
    return sorted(f"{path}:{functions[(path, name)].lineno} {name}" for path, name in missing)


def test_all_representation_writers_invalidate():
    tracked = subprocess.check_output(["git", "ls-files", "--", "*.py"], cwd=ROOT, text=True).splitlines()
    paths = [path for path in tracked
             if "/tests/" not in f"/{path}" and "/.venv/" not in f"/{path}" and not path.startswith("vendor/")]
    sources = {path: (ROOT / path).read_text() for path in paths
               if not Path(path).name.startswith("test_")}
    assert not (missing := scan(sources)), "Writers missing post-commit invalidation:\n" + "\n".join(missing)


@pytest.mark.parametrize("write", [
    'await db.execute(text("UPDATE parliament_bills SET title_el = :title"))',
    'await conn.execute(\'DELETE FROM public."citizen_votes"\')',
    'await conn.execute("INSERT INTO zk_vote_receipts VALUES ($1)", value)',
    'await db.execute(text("TRUNCATE TABLE parliament_bills"))',
    'db.add(ParliamentBill(title_el="new"))',
    'await db.execute(update(CitizenVote).values(vote="NO"))',
    'await db.execute(pg_insert(ParliamentBill).values(title_el="new"))',
    'await db.execute(ParliamentBill.__table__.delete())',
    'await db.delete(x)',
    'x.party_votes_parliament = {}',
    'setattr(x, "summary_long_el", "AMKA")',
    'x.vote_commitment = "NO"',
])
def test_guard_rejects_sql_and_orm_writes(write):
    source = f'from sqlalchemy import insert as pg_insert\nasync def future_writer(db, x: ParliamentBill):\n    {write}\n    await db.commit()\n'
    assert scan({"future.py": source}) == ["future.py:2 future_writer"]
    assert scan({"future.py": source.replace("await db.commit()", "await commit_and_invalidate_representation(db)")}) == []


def test_guard_follows_mutation_helpers_and_checks_every_caller():
    sources = {"future.py": '''
def mutate(x: ParliamentBill):
    x.summary_long_el = "AMKA"
async def safe(db, bill):
    mutate(bill)
    await commit_and_invalidate_representation(db)
async def missed(db, bill):
    mutate(bill)
    await db.commit()
'''}
    assert any("mutate" in missing for missing in scan(sources))
    sources["future.py"] = sources["future.py"].replace("await db.commit()", "await commit_and_invalidate_representation(db)")
    assert scan(sources) == []


def test_guard_finds_sql_in_module_constants():
    source = '''
SQL = "UPDATE " + "parliament_bills SET title_el = $1"
async def future_writer(conn):
    await conn.execute(SQL, "AMKA")
'''
    assert scan({"future.py": source}) == ["future.py:3 future_writer"]
