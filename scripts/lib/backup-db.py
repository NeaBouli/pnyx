"""Read a backup URI on stdin; invoke Docker with separate libpq variables.

Only the dedicated-URL path needs Python 3 (stdlib only). Never report parser
exceptions: their messages can contain credentials from the supplied URI.
"""
import os
import re
import subprocess
import sys
from urllib.parse import parse_qsl, unquote, urlsplit


OPTIONS = {
    "sslmode": "PGSSLMODE", "sslcert": "PGSSLCERT", "sslkey": "PGSSLKEY",
    "sslrootcert": "PGSSLROOTCERT", "sslcrl": "PGSSLCRL", "sslcrldir": "PGSSLCRLDIR",
    "connect_timeout": "PGCONNECT_TIMEOUT", "application_name": "PGAPPNAME",
    "target_session_attrs": "PGTARGETSESSIONATTRS", "channel_binding": "PGCHANNELBINDING",
    "gssencmode": "PGGSSENCMODE", "ssl_min_protocol_version": "PGSSLMINPROTOCOLVERSION",
    "ssl_max_protocol_version": "PGSSLMAXPROTOCOLVERSION",
}


def connection_env(uri):
    if re.search(r"%(?![0-9a-fA-F]{2})", uri) or any(c.isspace() for c in uri):
        raise ValueError
    parsed = urlsplit(uri)
    if parsed.scheme not in ("postgres", "postgresql") or parsed.fragment:
        raise ValueError
    values = {
        "PGHOST": unquote(parsed.hostname or "", errors="strict"),
        "PGPORT": str(parsed.port or 5432),
        "PGUSER": unquote(parsed.username or "", errors="strict"),
        "PGPASSWORD": unquote(parsed.password or "", errors="strict"),
        "PGDATABASE": unquote(parsed.path.removeprefix("/"), errors="strict"),
    }
    if not all(values[key] for key in ("PGHOST", "PGUSER", "PGDATABASE")):
        raise ValueError
    # A URI must never reach PGDATABASE, even through percent encoding.
    if "://" in values["PGDATABASE"]:
        raise ValueError
    for key, value in parse_qsl(parsed.query, keep_blank_values=True, strict_parsing=True, errors="strict"):
        if key not in OPTIONS or OPTIONS[key] in values:
            raise ValueError
        values[OPTIONS[key]] = value
    for key, value in values.items():
        if "\0" in value or (key != "PGPASSWORD" and any(ord(c) < 32 for c in value)):
            raise ValueError
    # Do not inherit a bootstrap password, service file or other PG overrides.
    return {**{k: v for k, v in os.environ.items() if not k.startswith("PG") and k != "BACKUP_DATABASE_URL"}, **values}


def main():
    try:
        env = connection_env(sys.stdin.read())
    except (ValueError, UnicodeError):
        print("Invalid BACKUP_DATABASE_URL; expected a PostgreSQL URI with host, user and database and supported libpq options", file=sys.stderr)
        return 2
    args = ["docker", "exec"]
    for name in env:
        if name.startswith("PG"):
            args.extend(("--env", name))
    return subprocess.run([*args, *sys.argv[1:]], env=env, check=False).returncode


if __name__ == "__main__":
    sys.exit(main())
