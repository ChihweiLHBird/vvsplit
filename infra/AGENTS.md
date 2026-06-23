# AGENTS.md

- `infra/__main__.py` deploys the static site as a Cloudflare `WorkersScript` with `assets.directory = "../dist"`; the deploy artifact is `dist/`, not the repo root.
- Always run `../scripts/stage-assets.sh` before `pulumi up` or any deploy verification. `pulumi up` is the deploy; there is no wrangler step.
- Staging currently copies the working tree through a denylist, so ignored local files are not automatically safe. Inspect the staged file list and keep virtual environments/tool state out of `dist/` until staging is allowlist-based.
- CI stamps the staged service-worker cache key with the commit SHA; local staging does not. A manual deploy must stamp/bump `dist/sw.js` when app-shell content changes.
- This repo uses a DIY S3 backend on Linode Object Storage, not Pulumi Cloud. Backend/login details live in `README.md` here.
- `CLOUDFLARE_ACCOUNT_ID` is read from the environment, not committed config.
- `requirements.txt` currently constrains major-version ranges (`pulumi` 3.x and `pulumi-cloudflare` 6.x); it is not a lock file and does not pin transitive dependencies or hashes.
- Minimal local verification for infra-only changes: `python -m py_compile __main__.py`.
- If repository behavior contradicts this file, patch `infra/AGENTS.md` in the same change and preserve the `infra/CLAUDE.md` symlink.
