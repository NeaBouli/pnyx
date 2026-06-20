# Codex Restart Handoff — 2026-06-20

## Current commit

- Local repo: `33aa421 docs(bridge): record other-project Ollama scan`
- Server checkout: `/opt/ekklesia/app` at `33aa421`
- Local working tree was clean before this handoff file was added.

## Runtime status

- No service restart, no deploy, no Docker prune, no model deletion was performed during the Ollama/qwen audit.
- Ekklesia runtime still uses Ollama with `OLLAMA_MODEL=llama3.2:3b`.
- `qwen2.5:14b` is still installed in the Ollama model store and uses about 9 GB.

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
- Removing `qwen2.5:14b` remains a manual operator-confirmed action only.

## Next step after restart

If Gio explicitly confirms model deletion, do a final precheck, then remove only qwen:

```bash
docker exec ekklesia-ollama ollama ps
docker exec ekklesia-ollama ollama list
docker exec ekklesia-ollama ollama rm qwen2.5:14b
df -h /
docker exec ekklesia-ollama ollama list
docker exec ekklesia-monitor python3 monitor.py --once
```

Do not remove `llama3.2:3b`; it is the production-configured model.
