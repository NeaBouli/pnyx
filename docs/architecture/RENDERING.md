# Offline architecture rendering

Status: **Rendered locally / NotLive**, checked on 2026-10-10 (UTC).
This manual check validates the existing diagram sources; it is not a production
deployment, a new architecture map, or evidence that the described runtime is live.

## Pinned inputs

Baseline: `c60c4aaea029ed6a04e0e84bf365de12984a704c`.

| Source | SHA-256 | Expected diagrams |
|---|---|---|
| `docs/architecture/map.puml` | `67f1fd7e9994651a9f31d44d6ffd667739279023212e5601722e2ac8c2e41b08` | 40 |
| `docs/architecture/main-path.puml` | `db282c6839a478dcddda09314eda27dea3231ee1a5abc9f6a02e591e5137a62e` | 26 |

Dedicated cached renderer: `plantuml/plantuml:1.2026.8`, PlantUML `1.2026.8`.
Its immutable Docker **Image.Id** is
`sha256:d08610df482510844382caa4e016ba2bf7e3231f630f02ee12f250f3416c62b1`;
this is a local image ID, not a registry digest. Its JAR is `/opt/plantuml.jar`.
An existing compatible Docker runtime and GNU `timeout` inside the image are prerequisites.
The command never pulls an image or installs tools. Missing prerequisites mean
**NOT RUN**; this document does not enable Docker on any CI fallback host.

## Reproduce manually

Run from the repository root after verifying the two source hashes above.
Reject include directives; use the `SECURE` profile and no container network.
Only the architecture source directory is mounted read-only. Use separate
`/out/map` and `/out/main-path` directories: the decks contain duplicate explicit
diagram names. The first flat render exited `0` but could overwrite those files,
so that run does not prove a complete output set. Existing 49 tracked SVGs remain
unrefreshed; generated SVGs and logs belong in a fresh temporary directory.

```sh
if rg -n '^[[:space:]]*!include' docs/architecture/map.puml docs/architecture/main-path.puml; then
  exit 2
fi
t9045_output=$(mktemp -d)
t9045_image=sha256:d08610df482510844382caa4e016ba2bf7e3231f630f02ee12f250f3416c62b1
for t9045_deck in map main-path; do
  mkdir "$t9045_output/$t9045_deck"
  docker run --pull=never \
    --network=none --user=501:20 --read-only --cap-drop=ALL \
    --security-opt=no-new-privileges --cpus=2 --memory=2g --pids-limit=256 \
    --ulimit cpu=180:180 --ulimit fsize=33554432:33554432 \
    --tmpfs /tmp:rw,nosuid,nodev,size=128m --workdir=/sources \
    --mount "type=bind,source=$PWD/docs/architecture,target=/sources,readonly" \
    --mount "type=bind,source=$t9045_output,target=/out" \
    --entrypoint /usr/bin/env "$t9045_image" -i \
    PATH=/opt/java/openjdk/bin:/usr/bin:/bin PLANTUML_SECURITY_PROFILE=SECURE \
    timeout 180s java -DPLANTUML_SECURITY_PROFILE=SECURE \
    -jar /opt/plantuml.jar -tsvg -failfast2 -o "/out/$t9045_deck" "$t9045_deck.puml" \
    >"$t9045_output/$t9045_deck/render.log" 2>&1 || exit $?
done
```

Java executes the pinned JAR with `-tsvg -failfast2` in a cleared environment.
Any diagram/syntax failure is never success. GNU timeout returns
`124` on deadline expiry; forced termination can return `137`.
Any other nonzero exit, missing SVG, or wrong output count also fails this check.

Observed: exit `0`, **40 map + 26 main-path SVGs**, all parsed as valid SVG XML
with nonempty dimensions and no syntax-error markers. Input hashes matched after
rendering. The renderer reported PlantUML `1.2026.8 / 149874a` and Graphviz `14.0.1`.
Its version probe warned about an unavailable optional Graphviz GD plugin; SVG
generation still succeeded. This is rendering/XML evidence, not a visual layout
or semantic architecture review. The existing committed SVG gallery is unchanged.
No production data, credentials, application services or automatic CI job participate.
