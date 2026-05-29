<picture>
  <source media="(prefers-color-scheme: dark)" srcset="assets/banner-dark.png">
  <img alt="hf-sandbox" src="assets/banner-light.png">
</picture>

Modal-style sandbox API on top of Hugging Face Jobs.

```python
from hf_sandbox import Sandbox

sb = Sandbox.create(image="python:3.12")
proc = sb.exec("python", "-c", "print(1+1)")  # → CompletedProcess(stdout='2\n', returncode=0, ...)
sb.write_file("/tmp/foo.txt", "hello")
print(sb.read_file("/tmp/foo.txt"))           # → 'hello'
sb.terminate()
```

## How it works

`Sandbox.create()` launches an HF Job that:

1. `pip install`s a tiny FastAPI RPC server (FastAPI + uvicorn)
2. starts the server on `localhost:8000`
3. opens a [Cloudflare Tunnel](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/) so the master process can reach it

By default, an anonymous "quick tunnel" is used (zero config). If you set Cloudflare credentials, named tunnels are used instead — no rate limits and deterministic URLs.

The client polls the job logs for the tunnel URL (or uses the predetermined hostname for named tunnels), then talks to the sandbox over plain HTTPS.

`exec`, `write_file`, `read_file` are simple authenticated POSTs.
`terminate()` cancels the job and cleans up any Cloudflare resources.

## Install

```bash
pip install hf-sandbox
```

Requires `hf auth login` (the same token is forwarded to the sandbox so it can access HF Hub).

## Named Tunnels (recommended)

The default quick tunnel mode uses Cloudflare's free `trycloudflare.com` service, which is rate-limited and can fail with 429 errors under load.

For reliable usage, configure **named Cloudflare Tunnels**:

```bash
export CF_API_TOKEN="your-cloudflare-api-token"
export CF_ACCOUNT_ID="your-account-id"
export CF_ZONE_ID="your-zone-id"
export CF_DOMAIN="yourdomain.com"
```

This gives you:
- No rate limits
- Deterministic URLs (`https://sandbox-{id}.yourdomain.com`)
- Production-grade Cloudflare SLA

### Setup

1. Add a domain to [Cloudflare DNS](https://dash.cloudflare.com/) (free plan works)
2. Create a **Custom API Token** at https://dash.cloudflare.com/profile/api-tokens:
   - Click **"Create Token"** → **"Create Custom Token"**
   - Add permissions:
     | Scope | Resource | Permission |
     |-------|----------|------------|
     | Account | Cloudflare Tunnel | Edit |
     | Zone | DNS | Edit |
   - Under **Account Resources**, select your specific account
   - Under **Zone Resources**, select your specific zone/domain
   - Do **not** use a Global API Key — scope the token to least privilege
3. Set the four environment variables above

When `CF_API_TOKEN` is not set, hf-sandbox falls back to the original zero-config quick tunnel behavior.

## Limits

- Image must have Python + `pip` (used to install the RPC server and download `cloudflared`).
- **Quick tunnel mode**: Cloudflare's free `trycloudflare.com` URLs are best-effort — rate-limited and not suitable for production. Use named tunnels for reliability.
- **Named tunnel mode**: Requires a Cloudflare account and domain. Free tier supports up to 50 concurrent tunnels.

## Security

The sandbox runs **untrusted code by design**. A few things to be aware of:

- **HF token forwarding is opt-in.** By default, your HF token is *not* exposed to the sandbox. Pass `forward_hf_token=True` to `Sandbox.create()` if your workload needs it. With it enabled, anything running inside the sandbox can read the token from `/proc/self/environ` and use it to act as you on the Hub.
- **Cloudflare sees all tunnel traffic.** Requests, responses, and the auth token transit Cloudflare's infrastructure (via `trycloudflare.com` or your named tunnel). They state they don't log it, but it's a trust relationship. Don't run sensitive workloads through it.
- **Auth token** is a 256-bit random URL-safe string per sandbox, sent as `Bearer` on every authenticated endpoint. The tunnel URL alone gets you nothing.

## Telemetry

`hf-sandbox` reports anonymous usage data to help us understand how the library is used. Two events are sent per sandbox:

- `hf-sandbox/create` — flavor, timeout, whether `forward_hf_token` was set, and a random per-sandbox session id
- `hf-sandbox/terminate` — same session id, duration in seconds, and termination reason

We never send: the image name, commands, file paths, file contents, the tunnel URL, the auth token, your HF token, your username, or anything from inside the sandbox.

Disable by setting `HF_HUB_DISABLE_TELEMETRY=1` (or `DO_NOT_TRACK=1`).
