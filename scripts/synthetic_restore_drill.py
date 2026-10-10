#!/usr/bin/env python3
"""Synthetic local Postgres 15 custom-format dump/restore drill (T-9065).

Default: offline plan only (no Docker, DB or subprocess calls).
--run: first verifies the API/Alembic Python imports in a child (fail closed),
then creates two NEW labelled PG15 containers from a cached image ID,
loads synthetic fixtures, pg_dump -Fc, pg_restore -l, restores into the
fresh target and compares counts plus the repo Alembic version marker.
Nothing is deleted; created containers and the private temp dir are kept
for owner-approved cleanup. This is NOT a production backup/RPO/RTO proof.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import secrets
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path
from typing import Callable, Sequence

REPO = Path(__file__).resolve().parents[1]
API_DIR = REPO / "apps" / "api"
IMAGE_ID = "sha256:29342cb52157b098821961d2c14eec3c019071f56a5d559e990cf07cf541ea9b"
LABEL = "ekklesia.drill=t9065-synthetic"
DB_NAME = "drill_synth_t9065"
DB_USER = "drill_user"
READY_MAX = 30
TIMEOUT = 120
FIXTURE_SQL = (
    "CREATE TABLE synth_items (id int PRIMARY KEY, qty int NOT NULL);"
    "INSERT INTO synth_items SELECT g, g*2 FROM generate_series(1,50) g;"
    "CREATE TABLE synth_notes (id int PRIMARY KEY, label text NOT NULL);"
    "INSERT INTO synth_notes SELECT g, 'note-'||g FROM generate_series(1,7) g;"
    "CREATE TABLE alembic_version (version_num varchar(32) PRIMARY KEY);"
)
SAMPLE_SQL = (
    "SELECT (SELECT count(*) FROM synth_items)||','||(SELECT sum(qty) FROM synth_items)"
    "||','||(SELECT count(*) FROM synth_notes)||','||"
    "(SELECT string_agg(version_num, ' ' ORDER BY version_num) FROM alembic_version);"
)
EXPECTED_SAMPLE_PREFIX = "50,2550,7,"
# Static import-only probe of what alembic env.py -> database/config need.
# Never imports app modules, settings, .env or env.py; never connects.
PREFLIGHT_CODE = (
    "from sqlalchemy.ext.asyncio import async_sessionmaker,create_async_engine,"
    "AsyncSession,async_engine_from_config;from sqlalchemy.orm import DeclarativeBase;"
    "import asyncpg;from pydantic import AliasChoices,Field;"
    "from pydantic_settings import BaseSettings,SettingsConfigDict;"
    "from alembic.config import Config;from alembic import command,context;"
    "from alembic.script import ScriptDirectory"
)
DEPENDENCY_FAIL = (
    "API Python dependencies missing or incompatible for this interpreter "
    "(need SQLAlchemy 2.x async_sessionmaker/DeclarativeBase, asyncpg, pydantic "
    "AliasChoices, pydantic-settings BaseSettings/SettingsConfigDict, alembic); "
    "install apps/api requirements yourself and retry. Nothing was created."
)

Runner = Callable[[Sequence[str]], str]


class DrillError(RuntimeError):
    pass


def default_runner(cmd: Sequence[str], env: dict | None = None, cwd: str | None = None) -> str:
    res = subprocess.run(list(cmd), check=True, capture_output=True, text=True,
                         timeout=TIMEOUT, env=env, cwd=cwd)
    return res.stdout.strip()


def expected_heads() -> list[str]:
    """Offline: read repo heads via ScriptDirectory (no DB, no env.py)."""
    from alembic.script import ScriptDirectory
    return sorted(ScriptDirectory(str(API_DIR / "alembic")).get_heads())


def preflight_imports(run_env: Callable = default_runner) -> None:
    """Import-only child before any resource: same interpreter, PATH-only env, cwd /."""
    try:
        run_env([sys.executable, "-c", PREFLIGHT_CODE],
                env={"PATH": os.environ.get("PATH", "")}, cwd=os.sep)
    except (subprocess.SubprocessError, OSError):
        raise DrillError(DEPENDENCY_FAIL) from None


def check_local_docker(environ: dict, run: Runner) -> str:
    host = environ.get("DOCKER_HOST", "")
    if host and not host.startswith("unix://"):
        raise DrillError("remote DOCKER_HOST refused")
    if environ.get("DOCKER_CONTEXT"):
        raise DrillError("explicit DOCKER_CONTEXT refused; use a default local context")
    endpoint = host or run(["docker", "context", "inspect", "--format",
                            "{{.Endpoints.docker.Host}}"])
    if not endpoint.startswith("unix://"):
        raise DrillError("non-local Docker endpoint refused")
    return endpoint


def check_major(version: str) -> None:
    if not re.match(r"^15(\.|$)", version.strip()):
        raise DrillError(f"server major is not 15: {version.strip()}")


def check_binding(binding: str) -> int:
    m = re.fullmatch(r"127\.0\.0\.1:(\d{4,5})", binding.strip().splitlines()[0])
    if not m:
        raise DrillError("target port binding is not 127.0.0.1")
    return int(m.group(1))


def check_archive(path: Path) -> None:
    with path.open("rb") as fh:
        if fh.read(5) != b"PGDMP":
            raise DrillError("dump is not a PGDMP custom archive")


def compare(source: str, target: str, heads: list[str]) -> None:
    if not source.startswith(EXPECTED_SAMPLE_PREFIX):
        raise DrillError("source sample counts differ from fixture")
    if source != target:
        raise DrillError("restored sample counts/version differ from source")
    if source.split(",", 3)[3].split() != heads:
        raise DrillError("alembic_version marker differs from repo heads")


def check_current(output: str, heads: list[str]) -> None:
    found = sorted(re.findall(r"\b([0-9a-z]{12})\b", output))
    if found != heads:
        raise DrillError(f"alembic current {found} != repo heads {heads}")


def alembic_current(port: int, password: str, scratch: Path, run_env: Callable = default_runner) -> str:
    """Actual repo Alembic in a child: empty CWD, sanitized env, absolute paths."""
    env = {"PATH": os.environ.get("PATH", ""), "ENVIRONMENT": "test",
           "DATABASE_URL": f"postgresql+asyncpg://{DB_USER}:{password}@127.0.0.1:{port}/{DB_NAME}"}
    code = ("import sys;from alembic.config import Config;from alembic import command;"
            f"sys.path.insert(0,{str(API_DIR)!r});c=Config({str(API_DIR / 'alembic.ini')!r});"
            f"c.set_main_option('script_location',{str(API_DIR / 'alembic')!r});"
            "command.current(c)")
    return run_env([sys.executable, "-c", code], env=env, cwd=str(scratch))


def docker_run(name: str, password: str, network_none: bool) -> list[str]:
    cmd = ["docker", "run", "-d", "--pull=never", "--name", name, "--label", LABEL,
           "-e", f"POSTGRES_PASSWORD={password}", "-e", f"POSTGRES_USER={DB_USER}",
           "-e", f"POSTGRES_DB={DB_NAME}"]
    cmd += ["--network", "none"] if network_none else ["-p", "127.0.0.1::5432"]
    return cmd + [IMAGE_ID]


def wait_ready(cid: str, run: Runner) -> None:
    for _ in range(READY_MAX):
        try:
            run(["docker", "exec", cid, "pg_isready", "-U", DB_USER, "-d", DB_NAME])
            run(["docker", "exec", cid, "psql", "-U", DB_USER, "-d", DB_NAME, "-tAc", "SELECT 1"])
            return
        except subprocess.CalledProcessError:
            run(["sleep", "1"])
    raise DrillError("pg_isready timeout")


def psql(cid: str, sql: str, run: Runner) -> str:
    return run(["docker", "exec", cid, "psql", "-v", "ON_ERROR_STOP=1", "-U", DB_USER,
                "-d", DB_NAME, "-tAc", sql])


CONTAINER_ID = re.compile(r"[0-9a-f]{64}")
FAILURE_STAGES = ("create_source", "create_target", "restore")


def _ack(receipt: dict, raw: str) -> None:
    """Record only a validated full-hex container ID; malformed output is never echoed."""
    cid = raw.strip() if isinstance(raw, str) else ""
    if CONTAINER_ID.fullmatch(cid):
        receipt["created"].append(cid)
    else:
        receipt["creation_uncertain"] = True


def _failure_receipt(receipt: dict, work: Path, stage: str) -> dict:
    """Closed whitelist: fixed stage/code, acknowledged IDs and the private workdir only."""
    out = {"status": "failed", "code": "DRILL_FAILED_AFTER_ALLOCATION",
           "stage": stage if stage in FAILURE_STAGES else "restore", "label": LABEL,
           "workdir_private": True, "workdir": str(work),
           "acknowledged_container_ids": [c for c in receipt["created"] if CONTAINER_ID.fullmatch(c)]}
    if stage.startswith("create_") or receipt.get("creation_uncertain"):
        out["creation_uncertain"] = True
        out["owner_warning"] = ("a failed or malformed create may have left an unacknowledged "
                                f"container; inspect label {LABEL} before owner-approved cleanup")
    return out


def drill(run: Runner = default_runner, run_env: Callable = default_runner) -> dict:
    os.umask(0o077)
    preflight_imports(run_env)
    heads = expected_heads()
    endpoint = check_local_docker({k: os.environ.get(k, "") for k in ("DOCKER_HOST", "DOCKER_CONTEXT")}, run)
    unbound_run = run
    run = lambda cmd: unbound_run(["docker", "--host", endpoint, *cmd[1:]] if cmd[0] == "docker" else cmd)
    run(["docker", "image", "inspect", "--format", "{{.Id}}", IMAGE_ID])
    tag = uuid.uuid4().hex[:12]
    password = secrets.token_hex(8)
    work = Path(tempfile.mkdtemp(prefix=f"drill-{tag}-"))
    receipt: dict = {"label": LABEL, "workdir_private": True, "heads": heads, "created": []}
    stage = "create_source"
    try:
        src = run(docker_run(f"drill-src-{tag}", password, True))
        _ack(receipt, src)
        stage = "create_target"
        tgt = run(docker_run(f"drill-tgt-{tag}", password, False))
        _ack(receipt, tgt)
        stage = "restore"
        return _drill_body(run, run_env, receipt, work, heads, password, src, tgt)
    except Exception as exc:
        exc.failure_receipt = _failure_receipt(receipt, work, stage)
        raise


def _drill_body(run: Runner, run_env: Callable, receipt: dict, work: Path, heads: list[str],
                password: str, src: str, tgt: str) -> dict:
    for cid in (src, tgt):
        wait_ready(cid, run)
        check_major(psql(cid, "SHOW server_version;", run))
    port = check_binding(run(["docker", "port", tgt, "5432/tcp"]))
    psql(src, FIXTURE_SQL + "INSERT INTO alembic_version VALUES "
         + ",".join(f"('{h}')" for h in heads) + ";", run)
    source_sample = psql(src, SAMPLE_SQL, run)
    dump = work / "synthetic.dump"
    run(["docker", "exec", src, "pg_dump", "-Fc", "-U", DB_USER, "-d", DB_NAME,
         "-f", "/tmp/synthetic.dump"])
    run(["docker", "cp", f"{src}:/tmp/synthetic.dump", str(dump)])
    check_archive(dump)
    (work / "toc.txt").write_text(run(["docker", "exec", src, "pg_restore", "-l",
                                       "/tmp/synthetic.dump"]))
    run(["docker", "cp", str(dump), f"{tgt}:/tmp/synthetic.dump"])
    run(["docker", "exec", tgt, "pg_restore", "--exit-on-error", "--no-owner", "--no-acl",
         "-U", DB_USER, "-d", DB_NAME, "/tmp/synthetic.dump"])
    target_sample = psql(tgt, SAMPLE_SQL, run)
    compare(source_sample, target_sample, heads)
    scratch = Path(tempfile.mkdtemp(prefix="alembic-scratch-", dir=work))
    check_current(alembic_current(port, password, scratch, run_env), heads)
    receipt.update(status="ok", sample=source_sample, dump_bytes=dump.stat().st_size,
                   server_version=psql(tgt, "SHOW server_version;", run))
    return receipt


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--run", action="store_true", help="execute synthetic local drill")
    args = ap.parse_args(argv)
    if not args.run:
        print("PLAN (dry-run, no Docker/DB calls): 2 new PG15 containers "
              f"from {IMAGE_ID[:19]}..., label {LABEL}; fixtures -> pg_dump -Fc -> "
              "PGDMP check -> pg_restore -l -> restore -> counts + alembic current.")
        return 0
    try:
        print(json.dumps(drill(), indent=1))
    except (DrillError, subprocess.SubprocessError, OSError) as exc:
        receipt = getattr(exc, "failure_receipt", None)
        if isinstance(exc, DrillError) and receipt is None:
            print(f"FAIL: DrillError: {exc}", file=sys.stderr)
        else:
            print(f"FAIL: {type(exc).__name__}", file=sys.stderr)
        if receipt is not None:
            print(json.dumps(receipt, indent=1), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
