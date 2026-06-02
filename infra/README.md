# vvsplit infra (Pulumi + Python)

The [`pulumi-cloudflare`](https://www.pulumi.com/registry/packages/cloudflare/)
provider (bridged from the Cloudflare v5 Terraform provider) uploads the
Worker's static assets itself, so `pulumi up` **is** the deploy — there is no
wrangler. State lives in **Linode Object Storage** (a Pulumi DIY S3 backend) —
no Pulumi Cloud account. Two clouds, separate concerns: Cloudflare hosts the
app, Linode holds the state.

## What this manages

- `WorkersScript` "vvsplit" — an **assets-only** Worker (no Worker JS) serving
  the static site from `../dist`.

## One-time bootstrap

### 1. Create a Linode Object Storage bucket

Cloud Manager → Object Storage → Create Bucket, e.g. `vvsplit-pulumi-state`.
Note its **cluster endpoint**, `https://<cluster-id>.linodeobjects.com`
(e.g. `us-southeast-1.linodeobjects.com`, `us-ord-1.linodeobjects.com`).

### 2. Object Storage key

You already have one. (Otherwise: Cloud Manager → Object Storage → Access Keys
→ Create — note the **Access Key** and **Secret Key**.)

### 3. Cloudflare API token

My Profile → API Tokens → Custom token: **Account → Workers Scripts → Edit**
(+ **Zone → DNS → Edit** only when adding a custom domain).

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
pulumi login 's3://vvsplit-pulumi-state?endpoint=<cluster-id>.linodeobjects.com&region=us-east-1&s3ForcePathStyle=true'
cd infra
pulumi stack init production
```

`region=us-east-1` is the value Linode expects regardless of the actual
cluster; the cluster is selected by the `endpoint`.

### 6. Stage assets, then up

```bash
./scripts/stage-assets.sh        # builds ./dist
cd infra && pulumi up             # creates venv, installs deps, deploys
```

Pulumi auto-creates `infra/venv`, installs `requirements.txt`, then deploys.
The Worker serves at `https://vvsplit.<account-subdomain>.workers.dev`.

## Day-to-day

```bash
./scripts/stage-assets.sh
cd infra && pulumi up
```

`pulumi up` re-uploads only changed assets.

## CI / workflow

`.github/workflows/deploy.yml`, two jobs by privilege:

- **`test`** — every PR and push. **No secrets**: Python tests, the JS-free
  audit, and `py_compile` of the Pulumi program. A PR (even one editing the
  workflow) can't reach the credentials.
- **`deploy`** — push to `main` (and manual dispatch), gated by the
  `production` GitHub Environment. Stages `dist/`, stamps `CACHE_VERSION`,
  then `pulumi/actions@v7` runs `up`. Dispatch with `action=plan` runs
  `preview` only.

> **Set up the gate.** Settings → Environments → create `production` with
> yourself as a **required reviewer** so each prod deploy pauses for approval.
> Without it, push-to-`main` auto-deploys.

### GitHub secrets (Settings → Secrets and variables → Actions)

| Secret | For |
|---|---|
| `CLOUDFLARE_API_TOKEN` | Provider auth (Workers Scripts:Edit; +DNS:Edit for a custom domain). |
| `CLOUDFLARE_ACCOUNT_ID` | Read by the program. |
| `OBJECT_STORAGE_ACCESS_KEY_ID` | Linode key → `AWS_ACCESS_KEY_ID`. |
| `OBJECT_STORAGE_SECRET_ACCESS_KEY` | Linode secret → `AWS_SECRET_ACCESS_KEY`. |
| `PULUMI_CONFIG_PASSPHRASE` | Encrypts secrets in Pulumi state. |

### GitHub variables (not secrets)

| Variable | For |
|---|---|
| `PULUMI_STATE_ENDPOINT` | `<cluster-id>.linodeobjects.com` |
| `PULUMI_STATE_BUCKET` | State bucket name (default `vvsplit-pulumi-state`). |

## State backend (Linode Object Storage)

Linode Object Storage is S3-compatible (Ceph/RGW), so it works as a Pulumi DIY
backend. `s3ForcePathStyle=true` and `region=us-east-1` are required. If
`pulumi login`/`up` fails on checksum errors, the store rejects the AWS SDK's
default request checksums — set
`AWS_REQUEST_CHECKSUM_CALCULATION=when_required`.

Keep the state bucket **private** (the default). State holds the account id and
Worker metadata, plus any Pulumi secrets (encrypted via the passphrase).

## Enabling a custom domain

Add a `cloudflare.WorkersCustomDomain` resource in `__main__.py` (verify the
current input names in the [provider docs](https://www.pulumi.com/registry/packages/cloudflare/)),
give the API token `Zone:DNS:Edit`, and `pulumi up`.
