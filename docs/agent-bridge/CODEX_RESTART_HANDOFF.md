# Codex Restart Handoff — 2026-06-20

## Current commit

- Local repo before qwen removal: `73bdcd3 docs(bridge): add restart handoff for Ollama disk audit`
- Server checkout before qwen removal: `/opt/ekklesia/app` at `73bdcd3`

## Runtime status

- No service restart, no deploy, no Docker prune, no Docker volume deletion, and no backup deletion was performed.
- Ekklesia runtime still uses Ollama with `OLLAMA_MODEL=llama3.2:3b`.
- `qwen2.5:14b` was removed after explicit Gio confirmation and final prechecks.
- `llama3.2:3b` remains installed and production-configured.

## Ollama/qwen audit result

- Ollama itself is still part of the ekklesia stack.
- `qwen2.5:14b` is not used by current runtime/code after the audit cleanup.
- The manual script `scripts/backfill_summary_ollama.py` no longer hardcodes qwen; it defaults to `OLLAMA_MODEL` or `llama3.2:3b` and supports `--model`.
- Running container env references found only:
  - `ekklesia-api`: `OLLAMA_URL=http://ollama:11434`, `OLLAMA_MODEL=llama3.2:3b`
  - `ekklesia-ollama`: `OLLAMA_HOST=0.0.0.0:11434`
- Other active projects checked with no Ollama/qwen references:
  - `/opt/parlay`
  - `/opt/vlabs`
  - `/opt/stealthx`
  - `/opt/inferno`
  - `/opt/plausible`
- Remaining qwen references are historical docs/release artifacts only:
  - `/opt/ekklesia/release-builds/pnyx-vc35`
  - `/opt/hetzner-migration`

## Disk cleanup policy

- Policy: `docs/agent-bridge/SERVER_CLEANUP_POLICY.md`
- Helper: `scripts/server-disk-maintenance.sh`
- Safe cleanup never deletes Docker volumes, backups, or Ollama models.
- `qwen2.5:14b` has already been removed; do not re-pull it unless Gio explicitly asks.

## Current cleanup result

- `/` improved from 91% used / 6.7G free to 79% used / 16G free.
- Ollama volume improved from 11G to 1.9G.
- Monitor single run passed 17 checks with no alerts.
- Do not remove `llama3.2:3b`; it is the production-configured model.
