# AGENTS.md

- `infra/__main__.py` deploys the static site as a Cloudflare `WorkersScript` with `assets.directory = "../dist"`; the deploy artifact is `dist/`, not the repo root.
- Always run `../scripts/stage-assets.sh` before `pulumi up` or any deploy verification. `pulumi up` is the deploy; there is no wrangler step.
- This repo uses a DIY S3 backend on Linode Object Storage, not Pulumi Cloud. Backend/login details live in `README.md` here.
- `CLOUDFLARE_ACCOUNT_ID` is read from the environment, not committed config.
- Keep infra edits compatible with the versions pinned in `requirements.txt`.
- Minimal local verification for infra-only changes: `python -m py_compile __main__.py`.
