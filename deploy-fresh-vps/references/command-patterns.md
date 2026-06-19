# Command Patterns

Use these as patterns, not blind scripts. Replace placeholders, verify distro/service names, and stop on any unexpected output.

## Local Discovery

```bash
command -v ssh
command -v ssh-keygen
ls -la ~/.ssh
ssh -G <alias-or-host> 2>/dev/null | sed -n '1,80p'
```

Generate a dedicated key only with user approval:

```bash
ssh-keygen -t ed25519 -a 100 -f ~/.ssh/<key-name> -C "<user-label>"
chmod 700 ~/.ssh
chmod 600 ~/.ssh/<key-name>
chmod 644 ~/.ssh/<key-name>.pub
```

## Initial Remote Read-Only Check

```bash
whoami
hostname
uptime
cat /etc/os-release
systemctl is-active ssh || systemctl is-active sshd || true
ss -ltnp | sed -n '1,120p'
grep -nE '^[[:space:]]*(Include|Port|PubkeyAuthentication|PasswordAuthentication|KbdInteractiveAuthentication|PermitRootLogin)' /etc/ssh/sshd_config /etc/ssh/sshd_config.d/*.conf 2>/dev/null || true
```

## SSH Bootstrap Pattern

Remote bootstrap intent:

```bash
NEW_PORT=<random-high-port>
PUBKEY_FILE=/tmp/codex-user-key.pub

umask 077
mkdir -p /root/.ssh
touch /root/.ssh/authorized_keys
grep -qxF -f "$PUBKEY_FILE" /root/.ssh/authorized_keys || cat "$PUBKEY_FILE" >> /root/.ssh/authorized_keys
chmod 700 /root/.ssh
chmod 600 /root/.ssh/authorized_keys
chown -R root:root /root/.ssh

BACKUP="/etc/ssh/sshd_config.codex-backup.$(date +%Y%m%d%H%M%S)"
cp -a /etc/ssh/sshd_config "$BACKUP"
mkdir -p /etc/ssh/sshd_config.d
cat > /etc/ssh/sshd_config.d/00-codex-bootstrap.conf <<EOF
Port 22
Port $NEW_PORT
PubkeyAuthentication yes
PasswordAuthentication yes
PermitRootLogin yes
EOF

sshd -t
systemctl restart ssh || systemctl restart sshd
sshd -T | egrep '^(port|pubkeyauthentication|passwordauthentication|kbdinteractiveauthentication|permitrootlogin) '
```

Local verification:

```bash
ssh -i <private-key> -p <new-port> -o PreferredAuthentications=publickey -o PasswordAuthentication=no <user>@<host> 'whoami; hostname'
```

## SSH Finalization Pattern

Before finalization, inspect `sshd -T` and active config. Ensure the final config produces exactly one `port` line.

Remote final intent:

```bash
FINAL_BACKUP="/etc/ssh/sshd_config.codex-pre-final.$(date +%Y%m%d%H%M%S)"
cp -a /etc/ssh/sshd_config "$FINAL_BACKUP"

# Adjust the main config and/or drop-ins so final sshd -T shows only the chosen port.
# Do not rely on a drop-in if the main config still adds Port 22 after Include.

cat > /etc/ssh/sshd_config.d/00-codex-final.conf <<EOF
Port <new-port>
PubkeyAuthentication yes
PasswordAuthentication no
KbdInteractiveAuthentication no
PermitRootLogin prohibit-password
EOF

sshd -t
systemctl restart ssh || systemctl restart sshd
sshd -T | egrep '^(port|pubkeyauthentication|passwordauthentication|kbdinteractiveauthentication|permitrootlogin) '
```

Local verification:

```bash
ssh -i <private-key> -p <new-port> -o PreferredAuthentications=publickey -o PasswordAuthentication=no <user>@<host> 'whoami; hostname'
ssh -p 22 -o ConnectTimeout=5 <user>@<host> true
ssh -i <private-key> -p <new-port> -o PreferredAuthentications=password -o PubkeyAuthentication=no <user>@<host> true
```

The old-port and forced-password checks should fail. Confirm the failure reason before proceeding.

## Local SSH Config

Append only after checking for an existing `Host` block:

```sshconfig
Host <alias>
  HostName <host-or-ip>
  User <user>
  Port <new-port>
  IdentityFile <private-key>
  IdentitiesOnly yes
```

Verify:

```bash
ssh <alias> 'whoami; hostname'
```

## UFW Direct-IP Ports

Install and enable safely:

```bash
apt-get update
apt-get install -y ufw curl ca-certificates
ufw default deny incoming
ufw default allow outgoing
ufw allow <ssh-port>/tcp comment 'SSH management'
ufw --force enable
ufw status verbose
```

Open direct service ports intentionally:

```bash
ufw allow 443/tcp comment 'VLESS Reality direct'
ufw allow <panel-port>/tcp comment '3x-ui panel direct'
```

If the user wants to restrict panel access to known client IPs:

```bash
ufw delete allow <panel-port>/tcp
ufw allow from <trusted-client-ip-or-cidr> to any port <panel-port> proto tcp comment '3x-ui panel trusted source'
```

If subscription is enabled, use a separate random high port and apply the same public or trusted-source choice:

```bash
ufw allow <sub-port>/tcp comment '3x-ui subscription direct'
```

Verify:

```bash
ufw status numbered
ss -ltnp | egrep ':(<ssh-port>|443|<panel-port>|<sub-port>)'
```

From local machine:

```bash
nc -vz <host-ip> 443
nc -vz <host-ip> <panel-port>
curl -kI --connect-timeout 10 https://<host-ip>:<panel-port>/<panel-path>
```

Panel/subscription direct IP access should match the chosen policy: reachable if public, blocked if trusted-source or tunnel-only.

## 3x-ui Checks

Before installing, verify the current official project and install command. Record the exact command used.

Post-install checks:

```bash
systemctl status x-ui --no-pager
systemctl is-active x-ui
ss -ltnp | egrep ':(443|<panel-port>|<sub-port>)'
x-ui status || true
```

If diagnosing generated Xray config:

```bash
python3 - <<'PY'
import json
from pathlib import Path
p = Path('/usr/local/x-ui/bin/config.json')
c = json.loads(p.read_text())
for ib in c.get('inbounds', []):
    st = ib.get('streamSettings', {})
    rs = st.get('realitySettings', {})
    clients = ib.get('settings', {}).get('clients') or []
    print('port=', ib.get('port'), 'protocol=', ib.get('protocol'), 'network=', st.get('network'), 'security=', st.get('security'), 'clients=', len(clients))
    if clients:
        print('flow=', clients[0].get('flow'))
    if rs:
        print('serverNames=', rs.get('serverNames'), 'shortIds=', len(rs.get('shortIds') or []), 'dest=', rs.get('dest'))
PY
```

## Recommended Inbound and Client Defaults

Use these defaults when the user has no protocol preference:

```text
Inbound remark: <ssh-alias>-reality or US-VPS-Reality
Protocol: VLESS
Listen: 0.0.0.0 unless 3x-ui uses its own default listener semantics
Port: 443
Transport/network: TCP/RAW
Security: Reality
Flow: xtls-rprx-vision
Client count: 1 enabled client
Client label/email: <ssh-alias>-client-1
Client server: bare VPS IP by default
Panel access: https://<host-ip>:<panel-port>/<panel-path>
```

Reality-specific values:

```text
Private key: server-side only; do not print in chat
Public key: include in client export
Short ID: include in client export
SNI/serverName: use current 3x-ui generated default if validation passes
Destination: use current 3x-ui generated default if validation passes
```

Validation for SNI/destination:

```bash
getent hosts <server-name>
openssl s_client -connect <dest-host>:443 -servername <server-name> </dev/null 2>/dev/null | sed -n '1,12p'
```

## Client Export Validation

Generated files should include a `vless://` URI and, when requested, Mihomo/Clash.Meta YAML.

Check locally:

```bash
test -s <export-file>
rg -n 'vless://|type: vless|reality-opts|flow: xtls-rprx-vision|server:' <export-file>
```

If YAML is split into a separate file:

```bash
YAML_FILE=<yaml-file>
python3 - "$YAML_FILE" <<'PY'
import sys, yaml
for path in sys.argv[1:]:
    with open(path, 'r', encoding='utf-8') as f:
        yaml.safe_load(f)
    print('yaml_ok', path)
PY
```

## Final User Handbook

Create the final handoff from a local JSON summary. This JSON contains secrets, so keep it in the user-approved directory with restrictive permissions and do not print it.

Minimal shape:

```json
{
  "generated_at": "<ISO-8601 timestamp>",
  "server": {
    "host_ip": "<host-ip>",
    "hostname": "<remote-hostname>",
    "os": "<remote-os>",
    "ssh_alias": "<ssh-alias>",
    "ssh_user": "<ssh-user>",
    "ssh_port": "<ssh-port>",
    "identity_file": "<private-key-path>",
    "ssh_command": "ssh <ssh-alias>",
    "password_auth": "disabled"
  },
  "firewall": {
    "enabled": true,
    "rules": [
      "allow <ssh-port>/tcp for SSH",
      "allow 443/tcp for VLESS Reality",
      "allow <panel-port>/tcp for 3x-ui panel"
    ]
  },
  "panel": {
    "url": "https://<host-ip>:<panel-port>/<panel-path>",
    "username": "<panel-username>",
    "password": "<panel-password>",
    "port": "<panel-port>",
    "path": "<panel-path>",
    "access": "direct IP, random high port, random path",
    "service_status": "active"
  },
  "inbound": {
    "remark": "<inbound-remark>",
    "protocol": "VLESS",
    "port": 443,
    "transport": "TCP/RAW",
    "security": "Reality",
    "flow": "xtls-rprx-vision",
    "server_name": "<sni>",
    "public_key": "<reality-public-key>",
    "short_id": "<reality-short-id>",
    "route": "bare VPS IP"
  },
  "client": {
    "name": "<client-label>",
    "enabled": true,
    "server": "<host-ip>",
    "vless_uri": "<vless-uri>",
    "export_file": "<local-client-export-file>",
    "mihomo_file": "<local-mihomo-yaml-or-empty>",
    "subscription_url": "<subscription-url-or-empty>"
  },
  "files": {
    "technical_runbook": "<local-runbook-file>",
    "client_export": "<local-client-export-file>",
    "handoff_doc": "<local-final-handbook>"
  },
  "verification": {
    "ssh": "ssh <ssh-alias> works with public key only",
    "panel": "3x-ui panel reachable by direct IP URL",
    "inbound": "443 is listening and config matches export",
    "client_export": "client export file exists and was validated"
  },
  "troubleshooting": {
    "problem_placeholder": "<describe the issue here>"
  }
}
```

Render without exposing contents:

```bash
SUMMARY_FILE="<approved-dir>/deployment-summary.json"
FINAL_DOC="<approved-dir>/VPS-使用说明.md"
chmod 600 "$SUMMARY_FILE"
python3 <skill-dir>/scripts/render-user-handbook.py --input "$SUMMARY_FILE" --output "$FINAL_DOC"
chmod 600 "$FINAL_DOC"
test -s "$FINAL_DOC"
rg -n '^(#|##) ' "$FINAL_DOC"
```

Only the heading check should be printed. Do not print the final handbook itself unless the user explicitly asks to reveal the sensitive values in chat.

The generated troubleshooting section must provide a copyable, sanitized request for another assistant. It should include basic connection facts only: VPS IP/host, SSH user, SSH port, SSH alias, identity-file path, SSH command, OS/hostname, and that 3x-ui is deployed. It must not ask the user to attach the whole handbook by default, and it must not include panel passwords, client import URIs, UUIDs, Reality keys, or subscription tokens.

## Known Good Shape

The previously successful deployment used:

```text
SSH: random high port, publickey only, local ssh alias
Firewall: UFW enabled, SSH allowed, 443 open for direct Reality, panel/subscription direct by chosen ports
Panel: 3x-ui on a random high port with random path, reached as IP:port/path
Subscription: optional random high port/path, full subscription URL includes generated token/path
Inbound: VLESS, 443, TCP/RAW, Reality, xtls-rprx-vision
Client: one enabled client with UUID, xtls-rprx-vision flow, Reality public key, short ID, and bare-IP server value
```
