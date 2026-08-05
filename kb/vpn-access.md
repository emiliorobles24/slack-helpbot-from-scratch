# VPN access for remote work

The VPN is required for the internal admin tools, the finance systems, and the staging environment. Most SaaS apps (email, Slack, docs) do not need it.

## Connect for the first time

The VPN client is preinstalled on managed laptops; look for the client in your menu bar (Mac) or system tray (Windows). Sign in with your Okta credentials and approve the MFA push. Choose the gateway closest to you; "Auto" is fine for almost everyone. If the client is missing, install it from the company self-service app store on your laptop, not from the public internet.

## VPN keeps disconnecting

Frequent drops are almost always local network instability, not the VPN service. In order: switch from Wi-Fi to a wired connection or move closer to the router, disconnect and pick a specific gateway instead of Auto, restart the client, then reboot. If drops continue on a stable network, note the exact disconnect times and open a ticket; the times let the network team match your session against gateway logs.

## Cannot reach an internal tool while connected

Confirm the padlock icon shows connected, then try the tool's full URL rather than a bookmark. If one specific tool fails while others work, that tool's allowlist may not include your group; open a ticket naming the tool and the error you see.
