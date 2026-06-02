"""vvsplit — Cloudflare Worker (static assets), Pulumi + Python.

Assets-only Worker (no `content`), so no Worker JS. Pulumi uploads ./dist
itself, so there is no wrangler. State lives in R2 (DIY S3 backend).
"""

import os

import pulumi
import pulumi_cloudflare as cloudflare

# From env, so the account id stays out of committed config (same secret CI uses).
account_id = os.environ["CLOUDFLARE_ACCOUNT_ID"]

worker = cloudflare.WorkersScript(
    "vvsplit",
    account_id=account_id,
    script_name="vvsplit",
    compatibility_date="2024-11-01",
    assets={
        "directory": "../dist",
        "config": {
            "html_handling": "auto-trailing-slash",
            "not_found_handling": "none",  # SW owns offline routing
        },
    },
)

pulumi.export("script_name", worker.script_name)
