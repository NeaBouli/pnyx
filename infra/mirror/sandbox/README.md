# Ekklesia Sandbox Mirror

Read-only sandbox mirror for the public ekklesia static site.

## Host

- Server: Sandbox CX33
- IPv4: `204.168.165.143`
- Public URL: `http://mirror.204.168.165.143.nip.io:18100`
- Install path: `/opt/ekklesia-mirror`

## Safety Boundary

- Separate stack from `/opt/hub`.
- Separate container: `ekklesia-mirror-web`.
- Separate port: `18100`.
- No PostgreSQL, no Redis, no forum, no newsletter, no identity service.
- Static public pages only.
- `/api/*` allows only `GET`, `HEAD`, and `OPTIONS` and proxies to `https://api.ekklesia.gr/api/*`.
- Writes/votes/identity remain on the primary ekklesia service.

## Deploy

```bash
cd /opt/ekklesia-mirror
docker compose up -d
docker exec ekklesia-mirror-web nginx -t
curl -fsS http://127.0.0.1:18100/health
```
