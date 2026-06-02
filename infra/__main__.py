"""vvsplit — Cloudflare Worker (static assets), Pulumi + Python.

Assets-only Worker (no `content`), so no Worker JS. Pulumi uploads ./dist
itself, so there is no wrangler. State lives in Linode Object Storage (DIY
S3 backend).
"""

import os

import pulumi
import pulumi_cloudflare as cloudflare

# From env, so the account id stays out of committed config (same secret CI uses).
account_id = os.getenv("CLOUDFLARE_ACCOUNT_ID")

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

# Optional custom domain (e.g. vvsplit.zliang.me). Cloudflare auto-creates the
# DNS record and TLS cert. The zone must already exist in this account.
custom_domain = os.getenv("CUSTOM_DOMAIN")
if custom_domain:
    zone_id = os.getenv("CLOUDFLARE_ZONE_ID")
    if not zone_id:
        raise ValueError("CUSTOM_DOMAIN is set but CLOUDFLARE_ZONE_ID is missing")
    cloudflare.WorkersCustomDomain(
        "vvsplit-domain",
        account_id=account_id,
        hostname=custom_domain,
        service=worker.script_name,
        zone_id=zone_id,
    )
    pulumi.export("custom_domain", custom_domain)
