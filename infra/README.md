# bunnysplit infra (Pulumi + Python)

The [`pulumi-cloudflare`](https://www.pulumi.com/registry/packages/cloudflare/)
provider (bridged from the Cloudflare v5 Terraform provider) uploads the
Worker's static assets itself, so `pulumi up` **is** the deploy — there is no
wrangler. State lives in **Linode Object Storage** (a Pulumi DIY S3 backend) —
no Pulumi Cloud account. Two clouds, separate concerns: Cloudflare hosts the
app, Linode holds the state.

## What this manages

- `WorkersScript` "bunnysplit" — an **assets-only** Worker (no Worker JS) serving
  the static site from `../dist`.

## One-time bootstrap

### 1. Create a Linode Object Storage bucket

Cloud Manager → Object Storage → Create Bucket, e.g. `bunnysplit-pulumi-state`.
Note its **cluster endpoint**, `https://<cluster-id>.linodeobjects.com`
(e.g. `us-southeast-1.linodeobjects.com`, `us-ord-1.linodeobjects.com`).

### 2. Object Storage key

You already have one. (Otherwise: Cloud Manager → Object Storage → Access Keys
→ Create — note the **Access Key** and **Secret Key**.)

### 3. Cloudflare API token

My Profile → API Tokens → Custom token: **Account → Workers Scripts → Edit**
(for a custom domain, also add **Zone → Workers Routes → Edit** and
**Zone → DNS → Edit** for that zone).

### 4. Set env

```bash
export CLOUDFLARE_API_TOKEN=<token>           # Cloudflare provider auth
export CLOUDFLARE_ACCOUNT_ID=<account id>
export AWS_ACCESS_KEY_ID=<Linode access key>  # DIY S3 backend creds
export AWS_SECRET_ACCESS_KEY=<Linode secret key>
export PULUMI_CONFIG_PASSPHRASE=<passphrase>  # encrypts secrets in state
```

### 5. Point Pulumi at the Linode backend, create the stack

```bash
pulumi login 's3://bunnysplit-pulumi-state?endpoint=<cluster-id>.linodeobjects.com&region=us-east-1'
cd infra
pulumi stack init production
```

`region=us-east-1` is the value Linode expects regardless of the actual
cluster; the cluster is selected by the `endpoint`.

CI creates the `production` stack automatically on first deploy (the
`pulumi/actions` step sets `upsert: true`), so this manual `stack init` is
only needed for a local `pulumi up`.

### 6. Stage assets, then up

The deployment dependency lock targets Linux x86_64 with CPython 3.14, matching
GitHub Actions. Use that environment for a local deploy. Dependency updates are
declared in `requirements.in` and compiled into the fully pinned, hash-checked,
binary-only `requirements.txt` using the command documented in
`requirements.in`.

```bash
./scripts/stage-assets.sh        # builds ./dist
cd infra && pulumi up             # creates venv, installs deps, deploys
```

Pulumi auto-creates `infra/venv`, installs the locked `requirements.txt`, then deploys.
The Worker serves at `https://bunnysplit.<account-subdomain>.workers.dev`.

## Day-to-day

```bash
./scripts/stage-assets.sh
cd infra && pulumi up
```

`pulumi up` re-uploads only changed assets.

## CI / workflow

A reusable `test` job (`.github/workflows/test.yml`: `py_compile` + unit tests,
no secrets) is called by two workflows:

- **`ci.yml`** — runs `test` on every PR. A PR (even one editing a workflow)
  can't reach credentials.
- **`deploy.yml`** — on push to `main` (and manual dispatch): runs `test`, then
  an env-gated `deploy` job that stages `dist/` (including its content-derived
  `CACHE_VERSION`) and runs `pulumi/actions@v7` `up`. Dispatch with
  `action=plan` runs `preview`.

> **Set up the gate.** Settings → Environments → create `production` with
> yourself as a **required reviewer** so each prod deploy pauses for approval.
> Without it, push-to-`main` auto-deploys.

### GitHub secrets (Settings → Secrets and variables → Actions)

| Secret | For |
|---|---|
| `CLOUDFLARE_API_TOKEN` | Provider auth (Workers Scripts:Edit; + Workers Routes:Edit & DNS:Edit for a custom domain). |
| `CLOUDFLARE_ACCOUNT_ID` | Read by the program. |
| `PULUMI_STATE_ACCESS_KEY_ID` | Linode key → `AWS_ACCESS_KEY_ID`. |
| `PULUMI_STATE_SECRET_ACCESS_KEY` | Linode secret → `AWS_SECRET_ACCESS_KEY`. |
| `PULUMI_CONFIG_PASSPHRASE` | Encrypts secrets in Pulumi state. |

### GitHub variables (not secrets)

| Variable | For |
|---|---|
| `PULUMI_STATE_ENDPOINT` | `<cluster-id>.linodeobjects.com` |
| `PULUMI_STATE_BUCKET` | State bucket name (default `bunnysplit-pulumi-state`). |

## State backend (Linode Object Storage)

Linode Object Storage is S3-compatible (Ceph/RGW), so it works as a Pulumi DIY
backend. `region=us-east-1` is required. Addressing style: the AWS SDK v2
rewrites to virtual-hosted (`<bucket>.<endpoint>`) when path-style is off
(`s3ForcePathStyle` omitted), `hostname_immutable` is unset, and the bucket
name is host-compatible — so this config serves state at
`bunnysplit-pulumi-state.<cluster>.linodeobjects.com` (needs a dot-free bucket
name to fit Linode's `*.<cluster>` TLS wildcard). Add `s3ForcePathStyle=true`
to force path-style (`<endpoint>/<bucket>/<key>`) instead. The `s3://…` login
string looks the same either way; confirm the real style in `pulumi --debug`
HTTP logs. If `pulumi login`/`up` fails on checksum errors, the store rejects
the AWS SDK's default request checksums — set
`AWS_REQUEST_CHECKSUM_CALCULATION=when_required`.

Keep the state bucket **private** (the default). State holds the account id and
Worker metadata, plus any Pulumi secrets (encrypted via the passphrase).

## Custom domain (e.g. bunnysplit.zliang.me)

The program creates a `cloudflare.WorkersCustomDomain` when `CUSTOM_DOMAIN` is
set (Cloudflare auto-creates the DNS record + TLS cert; a subdomain works the
same as an apex). To enable it:

1. The zone must already be in your Cloudflare account (e.g. `zliang.me`).
2. Get its **Zone ID**: dashboard → select the domain → Overview → Zone ID.
3. Extend the API token: add **Zone → Workers Routes → Edit** (and
   **Zone → DNS → Edit**) for that zone, on top of Workers Scripts:Edit.
4. Set config — locally as env, in CI as repo **variables**:
   ```bash
   export CUSTOM_DOMAIN=bunnysplit.zliang.me
   export CLOUDFLARE_ZONE_ID=<zliang.me zone id>
   ```
   CI: add `CUSTOM_DOMAIN` as a repo **variable** and `CLOUDFLARE_ZONE_ID` as
   a **secret** (both are non-credentials, so either scope works; this matches
   how `CLOUDFLARE_ACCOUNT_ID` is stored).
5. `./scripts/stage-assets.sh && cd infra && pulumi up`.

Leave `CUSTOM_DOMAIN` unset to skip the domain (the Worker still serves at
`*.workers.dev`). Field names are from the provider's Terraform schema —
`pulumi preview` will flag any mismatch on the first run.
