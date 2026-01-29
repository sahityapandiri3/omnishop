# Staging Environment Setup

## Environment URLs

| Environment | Frontend | Backend API |
|-------------|----------|-------------|
| **Production** | Vercel (main branch) | `https://app.omni-shop.in` |
| **Staging** | Vercel (staging branch) | `https://omnishop-staging.up.railway.app` |
| **Local** | `http://localhost:3000` | `http://localhost:8000` |

---

## Git Workflow

### Daily Development (on staging)

```bash
# Make sure you're on staging branch
git checkout staging

# Make your changes, then commit
git add .
git commit -m "Your commit message"

# Push to staging (triggers Vercel + Railway staging deployments)
git push
```

### Promote Staging to Production

```bash
# Switch to main branch
git checkout main

# Merge staging into main
git merge staging

# Push to production (triggers Vercel + Railway production deployments)
git push

# Go back to staging for next changes
git checkout staging
```

### Sync Staging with Production (if needed)

```bash
git checkout staging
git merge main
git push
```

---

## Vercel Configuration

- **Project:** omnishop (frontend)
- **Production Branch:** `main`
- **Preview Branch:** `staging` (and any other branches)

### Environment Variables

| Variable | Production | Preview (Staging) |
|----------|------------|-------------------|
| `NEXT_PUBLIC_API_URL` | `https://app.omni-shop.in` | `https://omnishop-staging.up.railway.app` |

---

## Railway Configuration

- **Project:** omnishop
- **Environments:** `production`, `staging`

### Staging Environment
- **API URL:** `https://omnishop-staging.up.railway.app`
- **Internal URL:** `omnishop.railway.internal`

---

## Quick Reference

```bash
# Check current branch
git branch

# Switch to staging
git checkout staging

# Switch to main (production)
git checkout main

# See recent commits
git log --oneline -5
```
