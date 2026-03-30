# POLIS — Setup Guide

## Prerequisites
- GitHub account
- `gh` CLI (optional, for label creation)
- `wrangler` CLI (for Cloudflare Worker deployment)

## 1. Create the Community Repository

```bash
gh repo create NeaBouli/pnyx-community --public --description "POLIS Community Tickets"
```

Enable Issues in the repo settings.

## 2. Create Required Labels

```bash
gh label create "status:pending"  --color "f59e0b" --repo NeaBouli/pnyx-community
gh label create "status:open"     --color "22c55e" --repo NeaBouli/pnyx-community
gh label create "status:claimed"  --color "3b82f6" --repo NeaBouli/pnyx-community
gh label create "status:resolved" --color "8b5cf6" --repo NeaBouli/pnyx-community
gh label create "category:bug"      --color "ef4444" --repo NeaBouli/pnyx-community
gh label create "category:feature"  --color "3b82f6" --repo NeaBouli/pnyx-community
gh label create "category:docs"     --color "8b5cf6" --repo NeaBouli/pnyx-community
gh label create "category:infra"    --color "f59e0b" --repo NeaBouli/pnyx-community
gh label create "category:ux"       --color "ec4899" --repo NeaBouli/pnyx-community
gh label create "category:security" --color "dc2626" --repo NeaBouli/pnyx-community
```

## 3. Create GitHub OAuth App

1. Go to: https://github.com/settings/developers → OAuth Apps → New
2. Application name: `POLIS - ekklesia.gr`
3. Homepage URL: `https://neabouli.github.io/pnyx`
4. Callback URL: `https://neabouli.github.io/pnyx/tickets/auth/callback.html`
5. Save the **Client ID** and **Client Secret**

## 4. Deploy Cloudflare Worker

```bash
cd cloudflare-worker
npm install -g wrangler
wrangler login
wrangler secret put GITHUB_CLIENT_ID     # paste your Client ID
wrangler secret put GITHUB_CLIENT_SECRET # paste your Client Secret
wrangler deploy
```

Note the Worker URL (e.g., `https://polis-oauth-proxy.your-account.workers.dev`)

## 5. Update Configuration

Edit `docs/tickets/config.js`:

```javascript
oauth: {
  clientId: "YOUR_GITHUB_CLIENT_ID",
  workerUrl: "https://polis-oauth-proxy.your-account.workers.dev",
  callbackPath: "/pnyx/tickets/auth/callback.html",
},
```

## 6. Deploy

```bash
git add docs/ cloudflare-worker/
git commit -m "feat(polis): Tier 1 ticket system"
git push origin main
```

## Multi-Community Deployment

Any project can fork `docs/tickets/` to their own GitHub Pages:
1. Copy `docs/tickets/` to your repo's `docs/` folder
2. Create your own community repo (Step 1)
3. Create your own OAuth App (Step 3)
4. Deploy your own Worker (Step 4)
5. Update `config.js` with your values
6. Push — done

## Architecture

- **Storage**: GitHub Issues API (NeaBouli/pnyx-community)
- **Votes**: GitHub Reactions (+1, API-enforced 1 per user)
- **Auth**: GitHub OAuth 2.0 via Cloudflare Worker
- **Moderation**: Label-based state machine, 3-vote quorum
- **Phase 2**: PoW (browser-native SHA-256, stub ready)
- **Phase 3**: Nullifier (ekklesia MOD-01, stub ready)
