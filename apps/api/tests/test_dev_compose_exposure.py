"""EKA-18: the local dev Compose stack must publish its datastores on IPv4 loopback only.

db (repo-public dev password fallback) and redis (no auth) are reachable by any
network neighbour when published on all interfaces. The API container keeps
reaching them over the Compose network (service DNS), host tools over loopback.
Static parse of the real compose file — no containers, no sockets.
"""
from pathlib import Path
from urllib.parse import urlparse

import pytest
import yaml  # hard import: a missing PyYAML must fail, not skip

COMPOSE_FILE = Path(__file__).resolve().parents[3] / "infra" / "docker" / "docker-compose.yml"
LOOPBACK = "127.0.0.1"
DATASTORE_PORTS = {"db": "5432", "redis": "6379"}


def _load_services() -> dict:
    return yaml.safe_load(COMPOSE_FILE.read_text(encoding="utf-8"))["services"]


def _parse_port(entry: object) -> tuple[str | None, str | None, str]:
    """Return (host_ip, published, target) for a short- or long-syntax ports entry.

    host_ip is None when absent, i.e. Compose binds on all host interfaces.
    """
    if isinstance(entry, dict):
        published = entry.get("published")
        return (
            entry.get("host_ip"),
            None if published is None else str(published),
            str(entry["target"]),
        )
    spec = str(entry).split("/", 1)[0]
    if spec.startswith("["):
        host_ip, _, rest = spec[1:].partition("]")
        published, _, target = rest.lstrip(":").rpartition(":")
        return host_ip, published or None, target
    parts = spec.rsplit(":", 2)
    if len(parts) == 3:
        return parts[0], parts[1], parts[2]
    if len(parts) == 2:
        return None, parts[0], parts[1]
    return None, None, parts[0]


def _is_loopback_only(entry: object) -> bool:
    host_ip, _, _ = _parse_port(entry)
    return host_ip == LOOPBACK


@pytest.mark.parametrize("service", sorted(DATASTORE_PORTS))
def test_datastore_ports_bind_ipv4_loopback_only(service: str) -> None:
    ports = _load_services()[service].get("ports") or []
    assert ports, f"{service} must still publish a host port for local tools"
    exposed = [p for p in ports if not _is_loopback_only(p)]
    assert not exposed, f"{service} publishes on non-loopback interfaces: {exposed}"


@pytest.mark.parametrize("service,port", sorted(DATASTORE_PORTS.items()))
def test_datastore_keeps_host_tool_port_on_loopback(service: str, port: str) -> None:
    parsed = [_parse_port(p) for p in _load_services()[service]["ports"]]
    assert (LOOPBACK, port, port) in parsed


@pytest.mark.parametrize(
    "entry",
    [
        "5432:5432",
        "5432",
        "0.0.0.0:5432:5432",
        "[::]:5432:5432",
        ":5432:5432",
        "192.168.1.10:5432:5432",
        "localhost:5432:5432",
        "127.0.0.2:5432:5432",
        "0.0.0.0:6379:6379/tcp",
        {"target": 5432, "published": 5432},
        {"target": 6379, "published": 6379, "host_ip": "0.0.0.0"},
        {"target": 6379, "published": 6379, "host_ip": "::"},
        {"target": 6379, "published": 6379, "host_ip": ""},
    ],
)
def test_non_loopback_host_ip_classes_are_rejected(entry: object) -> None:
    assert not _is_loopback_only(entry)


@pytest.mark.parametrize(
    "entry",
    [
        "127.0.0.1:5432:5432",
        "127.0.0.1:6379:6379/tcp",
        {"target": 5432, "published": 5432, "host_ip": "127.0.0.1"},
    ],
)
def test_ipv4_loopback_entries_are_accepted(entry: object) -> None:
    assert _is_loopback_only(entry)


def test_api_reaches_datastores_via_service_dns() -> None:
    api = _load_services()["api"]
    env = api["environment"]
    assert urlparse(env["DATABASE_URL"]).hostname == "db"
    assert urlparse(env["REDIS_URL"]).hostname == "redis"
    assert {"db", "redis"} <= set(api["depends_on"])
