#!/usr/bin/env python3
"""Delete sandbox-* tunnels that are inactive (no connections).

Run periodically or before creating new sandboxes to prevent orphan accumulation.

Required env vars:
  CF_API_TOKEN  - Cloudflare API token with Tunnel:Edit + DNS:Edit
  CF_ACCOUNT_ID - Cloudflare account ID
  CF_ZONE_ID    - Cloudflare zone ID
  CF_DOMAIN     - Domain used for sandbox hostnames (e.g., "rycerz.es")
"""

import os
import sys

from cloudflare import Cloudflare
from cloudflare.types.dns.record_list_params import Name

TOKEN = os.environ.get("CF_API_TOKEN")
ACCOUNT = os.environ.get("CF_ACCOUNT_ID")
ZONE = os.environ.get("CF_ZONE_ID")
DOMAIN = os.environ.get("CF_DOMAIN")

if not TOKEN or not ACCOUNT or not ZONE or not DOMAIN:
    print("Error: CF_API_TOKEN, CF_ACCOUNT_ID, CF_ZONE_ID, and CF_DOMAIN must be set.")
    sys.exit(1)

cf = Cloudflare(api_token=TOKEN)

# List all tunnels with "sandbox-" prefix
tunnels = cf.zero_trust.tunnels.cloudflared.list(
    account_id=ACCOUNT,
    is_deleted=False,
    name="sandbox-",
)

deleted = 0
for t in tunnels:
    if not t.connections:  # no active connectors → orphaned
        assert t.id is not None, f"Tunnel {t.name} has no ID"
        print(f"Deleting orphan tunnel: {t.name} ({t.id})")
        try:
            cf.zero_trust.tunnels.cloudflared.connections.delete(
                tunnel_id=t.id,
                account_id=ACCOUNT,
            )
        except Exception as e:
            print(f"  Warning: failed to delete connections: {e}")

        try:
            cf.zero_trust.tunnels.cloudflared.delete(
                tunnel_id=t.id,
                account_id=ACCOUNT,
            )
        except Exception as e:
            print(f"  Warning: failed to delete tunnel: {e}")
            continue

        # Also clean DNS
        try:
            dns_records = cf.dns.records.list(
                zone_id=ZONE,
                name=Name(exact=f"{t.name}.{DOMAIN}"),
            )
            for rec in dns_records:
                assert rec.id is not None
                cf.dns.records.delete(
                    dns_record_id=rec.id,
                    zone_id=ZONE,
                )
                print(f"  Deleted DNS record: {rec.name}")
        except Exception as e:
            print(f"  Warning: failed to clean DNS: {e}")

        deleted += 1

print(f"\nDone. Deleted {deleted} orphan tunnel(s).")
