# Quadpod Remote Access with Tailscale

This is a branch-only setup note. Do not run the setup script or change the live Pi until deployment is approved.

## Goal

Use Tailscale for private SSH/admin access to the Quadpod Pi from different networks without opening router ports. Local access through `quadpod.local` and the Quadpod hotspot should remain available as fallbacks.

## Proposed Setup

1. Install Tailscale on the Pi.
2. Start and enable `tailscaled`.
3. Authenticate the Pi into the APEC tailnet with hostname `quadpod-3`.
4. Enable Tailscale SSH for private remote updates.
5. Verify remote SSH using the Tailscale hostname or Tailscale IP.

## Deployment Command

Run only after approval:

```bash
sudo /opt/quadpod/scripts/setup-tailscale-remote-access.sh
```

## Notes

- Do not use router port forwarding for SSH or the Flask app.
- Keep the hotspot fallback in place for field recovery.
- Tailscale authentication requires an operator/admin to approve the login URL or provide a valid auth key.
