# Security — Tokens, Secrets, and Privacy

> **READ THIS BEFORE YOU START.** This framework is designed to be safe to push to a public GitHub repo. Follow these rules and nothing sensitive will ever leave your machine.

---

## TL;DR

| Where it lives | What goes in it | Pushed to GitHub? |
|----------------|-----------------|-------------------|
| `templates/brand-folder/config/*.example.json` | Placeholders only — `REPLACE_WITH_...` | ✅ Yes (safe) |
| `brands/[BRAND]/config/*.local.json` | Real tokens, app secrets, chat IDs | ❌ No — gitignored |
| `.env`, `*.env` | Any environment vars | ❌ No — gitignored |
| Any file ending in `.local.json` or `-tokens.json` | Real secrets | ❌ No — gitignored |
| The whole `brands/` folder | All brand-specific data | ❌ No — gitignored |

---

## Why the framework is safe to publish

The `.gitignore` blocks:

```
*.local.json
*-tokens.json
*.env
.env
.env.*
config/meta-tokens.json
**/config/meta-tokens.json
**/config/telegram-config.json
brands/
```

That means:
- All your real tokens live in `*.local.json` files inside `brands/[BRAND]/config/`.
- The `brands/` folder is itself excluded — so even if you forget the `.local` suffix on a file, it still won't be pushed.
- The example templates that **are** in the repo only contain placeholder strings like `REPLACE_WITH_META_APP_ID`.

---

## What to do (positive checklist)

- [ ] Real tokens go into `brands/[BRAND]/config/meta-tokens.local.json`.
- [ ] Real Telegram bot tokens go into `brands/[BRAND]/config/telegram-config.local.json`.
- [ ] When sharing the framework with a teammate, share **the repo**, not your `brands/` folder.
- [ ] Before any `git push`, run `git status` and confirm no `*.local.json` or `*.env` is staged.

---

## What NOT to do

- ❌ Do not paste a real token into any `.md` file inside `00-setup/` or `templates/`.
- ❌ Do not rename a `.local.json` to `.json` "just for a minute" — there is no minute.
- ❌ Do not commit a `brands/` folder, even if you think you've stripped the tokens.
- ❌ Do not include real Business Manager IDs, App IDs, or Ad Account IDs in screenshots that go into the repo. Blur them.

---

## If you accidentally committed a secret

1. **Rotate the token immediately** in Meta Business Settings → System Users → revoke + regenerate. Even if you delete the commit, assume it was scraped.
2. Remove the secret from history:
   ```bash
   # Option A: simple — remove file from history
   git filter-repo --path brands/SOMEBRAND/config/meta-tokens.local.json --invert-paths

   # Option B: if installed
   bfg --delete-files meta-tokens.local.json
   ```
3. Force-push:
   ```bash
   git push --force
   ```
4. Tell anyone who pulled the repo to re-clone (the secret is in their local copy).

---

## Recommended pre-push check

Add this to your shell as `safe-push`:

```bash
safe-push() {
  if git status --porcelain | grep -E "\.(local\.json|env|tokens\.json)$"; then
    echo "❌ A secrets file is staged. Aborting."
    return 1
  fi
  if git diff --cached | grep -E "(REPLACE_WITH|EAA[A-Za-z0-9]{50,})"; then
    echo "❌ Possible token in the diff. Aborting."
    return 1
  fi
  git push "$@"
}
```

Then use `safe-push origin main` instead of `git push origin main`.

---

## Reporting a security issue

If you find a hole in this framework's security model (e.g., a path that isn't gitignored, a template that leaks a secret), open an issue or PR.
