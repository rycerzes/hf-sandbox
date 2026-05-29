"""Cloudflare Tunnel lifecycle management via the official Python SDK.

Requires: pip install cloudflare>=5.0.0
See: https://github.com/cloudflare/cloudflare-python
"""

from __future__ import annotations

from cloudflare import Cloudflare
from cloudflare.types.zero_trust.tunnels.cloudflared.configuration_update_params import (
    Config,
    ConfigIngress,
)


def _client(api_token: str) -> Cloudflare:
    """Create an authenticated Cloudflare client."""
    return Cloudflare(api_token=api_token)


def create_tunnel(account_id: str, api_token: str, name: str) -> tuple[str, str]:
    """Create a named tunnel. Returns (tunnel_id, connector_token)."""
    cf = _client(api_token)
    tunnel = cf.zero_trust.tunnels.cloudflared.create(
        account_id=account_id,
        name=name,
        config_src="cloudflare",
    )
    assert tunnel.id is not None, "Tunnel creation returned no ID"
    # Fetch the connector token separately
    token = cf.zero_trust.tunnels.cloudflared.token.get(
        tunnel_id=tunnel.id,
        account_id=account_id,
    )
    return tunnel.id, token


def configure_tunnel_ingress(
    account_id: str, api_token: str, tunnel_id: str, hostname: str
) -> None:
    """Set ingress rules to route traffic to localhost:8000.

    IMPORTANT: This must be called AFTER create_tunnel() and BEFORE running
    the job. Without ingress rules, a remotely-managed tunnel returns 503
    for all requests. Local config files are ignored when using --token.

    See: https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/get-started/create-remote-tunnel-api/
    See: https://github.com/cloudflare/cloudflared/issues/1029
    """
    cf = _client(api_token)
    ingress_rules: list[ConfigIngress] = [
        ConfigIngress(hostname=hostname, service="http://localhost:8000"),
        ConfigIngress(hostname="", service="http_status:404"),
    ]
    cf.zero_trust.tunnels.cloudflared.configurations.update(
        tunnel_id=tunnel_id,
        account_id=account_id,
        config=Config(ingress=ingress_rules),
    )


def add_dns_route(
    zone_id: str, api_token: str, tunnel_id: str, hostname: str
) -> str:
    """Create proxied CNAME record. Returns dns_record_id."""
    cf = _client(api_token)
    record = cf.dns.records.create(
        zone_id=zone_id,
        type="CNAME",
        name=hostname,
        content=f"{tunnel_id}.cfargotunnel.com",
        ttl=1,  # 1 = automatic
        proxied=True,
    )
    assert record is not None and record.id is not None, "DNS record creation returned no ID"
    return record.id


def delete_tunnel(account_id: str, api_token: str, tunnel_id: str) -> None:
    """Delete a tunnel (also cleans up connections)."""
    cf = _client(api_token)
    # Must clean up connections first
    cf.zero_trust.tunnels.cloudflared.connections.delete(
        tunnel_id=tunnel_id,
        account_id=account_id,
    )
    cf.zero_trust.tunnels.cloudflared.delete(
        tunnel_id=tunnel_id,
        account_id=account_id,
    )


def delete_dns_record(zone_id: str, api_token: str, record_id: str) -> None:
    """Delete a DNS record."""
    cf = _client(api_token)
    cf.dns.records.delete(
        dns_record_id=record_id,
        zone_id=zone_id,
    )
