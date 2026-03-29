<!--
@wiki-page CONTRIBUTING
@update-hint Update on workflow changes.
@ai-anchor WIKI_CONTRIBUTING
-->

# Οδηγός Συμμετοχής / Contributing Guide

## Setup
```bash
git clone https://github.com/NeaBouli/pnyx
cd pnyx/apps/api
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cd ../web && npm install
```

## Run Tests
```bash
# API Tests
cd apps/api && pytest tests/ -v

# Crypto Tests
cd packages/crypto && pytest tests/ -v

# Web Build
cd apps/web && npm run build
```

## Commit Conventions
```
feat(module): new functionality
fix(module): bug fix
docs: documentation
chore: infrastructure
test: tests
```

## Important Notes

- `/Users/gio/TrueRepublic` → **READ ONLY** — never modify
- `SERVER_SALT` → never commit in code
- Phone numbers → deleted IMMEDIATELY, never log
- Private keys → never leave the server in plaintext

## License

MIT License © 2026 Vendetta Labs
