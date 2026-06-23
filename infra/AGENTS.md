# AGENTS.md

- `infra/__main__.py` deploys the static site as a Cloudflare `WorkersScript` with `assets.directory = "../dist"`; the deploy artifact is `dist/`, not the repo root.
- Always run `../scripts/stage-assets.sh` before `pulumi up` or any deploy verification. `pulumi up` is the deploy; there is no wrangler step.
- Staging copies only the explicit asset manifest in `scripts/stage-assets.sh`; unlisted local files cannot enter `dist/`. Its regression test must cover any manifest change.
- Staging derives the service-worker cache key from the staged content. Local and CI deploys must use that same output without an additional stamp.
- This repo uses a DIY S3 backend on Linode Object Storage, not Pulumi Cloud. Backend/login details live in `README.md` here.
- `CLOUDFLARE_ACCOUNT_ID` is read from the environment, not committed config.
- `requirements.in` declares direct ranges; `requirements.txt` locks the complete Linux x86_64 / CPython 3.14 graph with hashes and binary-only installation. Regenerate it with the documented `uv pip compile` command and verify with `pip --require-hashes`.
- Minimal local verification for infra-only changes: `python -m py_compile __main__.py`.
- If repository behavior contradicts this file, patch `infra/AGENTS.md` in the same change and preserve the `infra/CLAUDE.md` symlink.
