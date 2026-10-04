"""EKA-13: the production docker-proxy must be a pinned, read-only, monitor-only boundary.

docker-proxy mounts the host Docker socket (host-root equivalent). It must run a
released image pinned by manifest digest, deny Docker API writes (POST=0), enable
no Docker API namespace while Tier-2 is disabled, and be reachable only by
monitor over a dedicated internal network. Tier-2 Docker restart is therefore
fixed off in prod.
Static parse of the real compose file — no containers, no sockets.
"""
from pathlib import Path
from urllib.parse import urlparse

import yaml  # hard import: a missing PyYAML must fail, not skip

COMPOSE_FILE = Path(__file__).resolve().parents[3] / "infra" / "docker" / "docker-compose.prod.yml"
PROXY = "docker-proxy"
MONITOR = "monitor"
APP_NETWORK = "ekklesia"
PROXY_IMAGE = (
    "ghcr.io/tecnativa/docker-socket-proxy:v0.4.2"
    "@sha256:1f3a6f303320723d199d2316a3e82b2e2685d86c275d5e3deeaf182573b47476"
)
# Complete proxy environment: any other key would enable another API namespace
# (e.g. EXEC, IMAGES, ALLOW_RESTARTS) or change defaults.
PROXY_ENV = {
    "CONTAINERS": "0",
    "EVENTS": "0",
    "PING": "0",
    "POST": "0",
    "VERSION": "0",
    "LOG_LEVEL": "warning",
}
SOCKET_MOUNT = "/var/run/docker.sock:/var/run/docker.sock:ro"


def _load() -> dict:
    return yaml.safe_load(COMPOSE_FILE.read_text(encoding="utf-8"))


def _networks(service: dict) -> set[str]:
    nets = service.get("networks") or []
    return set(nets) if isinstance(nets, (list, dict)) else set()


def _proxy_network(compose: dict) -> str:
    nets = _networks(compose["services"][PROXY])
    assert len(nets) == 1, f"{PROXY} must join exactly one network, got {sorted(nets)}"
    return next(iter(nets))


def _env(service: dict) -> dict[str, str]:
    env = service.get("environment") or {}
    assert isinstance(env, dict), "environment must use mapping syntax"
    return {k: str(v) for k, v in env.items()}


def test_proxy_image_is_release_tag_pinned_by_digest() -> None:
    image = _load()["services"][PROXY]["image"]
    assert image == PROXY_IMAGE
    assert ":latest" not in image


def test_proxy_joins_only_a_dedicated_internal_network() -> None:
    compose = _load()
    net = _proxy_network(compose)
    assert net != APP_NETWORK
    definition = compose["networks"][net] or {}
    assert definition.get("internal") is True
    assert not definition.get("external"), "private network must be Compose-owned, not external"


def test_monitor_is_the_only_peer_and_keeps_app_network() -> None:
    compose = _load()
    net = _proxy_network(compose)
    members = {name for name, svc in compose["services"].items() if net in _networks(svc)}
    assert members == {PROXY, MONITOR}
    assert _networks(compose["services"][MONITOR]) == {APP_NETWORK, net}
    for name, service in compose["services"].items():
        assert service.get("network_mode") not in {
            f"service:{MONITOR}",
            "container:ekklesia-monitor",
        }, f"{name} must not inherit the monitor network namespace"


def test_proxy_policy_enables_no_docker_api_namespace() -> None:
    proxy = _load()["services"][PROXY]
    assert _env(proxy) == PROXY_ENV
    assert "env_file" not in proxy, (
        "capabilities must not be injectable through an env file"
    )


def test_socket_mount_stays_read_only() -> None:
    assert _load()["services"][PROXY]["volumes"] == [SOCKET_MOUNT]


def test_proxy_publishes_no_host_port() -> None:
    proxy = _load()["services"][PROXY]
    assert "ports" not in proxy
    assert "network_mode" not in proxy


def test_monitor_reaches_proxy_via_service_dns() -> None:
    host = urlparse(_env(_load()["services"][MONITOR])["DOCKER_HOST"])
    assert (host.scheme, host.hostname, host.port) == ("tcp", PROXY, 2375)


def test_production_tier2_restart_is_fixed_off() -> None:
    raw = _load()["services"][MONITOR]["environment"]["AUTO_RECOVERY_T2"]
    assert raw == "false", "must be the literal string, not an env-overridable default"
