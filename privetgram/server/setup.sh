#!/usr/bin/env bash
# Privetgram server setup (any Linux VPS with Docker).
#
#   sudo ./setup.sh /path/to/server_pkcs1.key
#
# The key must be the private half of the public key built into the APK.
# Re-running is safe: passwords and the invite code are kept in privetgram.env.
set -euo pipefail

KEY=$(realpath "${1:?usage: setup.sh server_pkcs1.key}")
HERE=$(cd "$(dirname "$0")" && pwd)
COMMIT=8adf26bc071159c12a62c22ad49625a73e922e79   # teamgram-server
cd "$HERE"

command -v docker >/dev/null || { echo "Install Docker first: curl -fsSL https://get.docker.com | sh"; exit 1; }
docker compose version >/dev/null || { echo "docker compose plugin is missing"; exit 1; }
command -v python3 >/dev/null || { echo "python3 is missing"; exit 1; }
command -v openssl >/dev/null || { echo "openssl is missing"; exit 1; }
grep -q "BEGIN RSA PRIVATE KEY" "$KEY" || { echo "$KEY is not a PKCS#1 RSA private key"; exit 1; }

# 1. source
if [ ! -d teamgram-server ]; then
  git init -q teamgram-server
  git -C teamgram-server remote add origin https://github.com/teamgram/teamgram-server.git
  git -C teamgram-server fetch -q --depth 1 origin "$COMMIT"
  git -C teamgram-server checkout -q FETCH_HEAD
  for p in "$HERE"/patches/*.patch; do git -C teamgram-server apply "$p"; echo "patched $(basename "$p")"; done
fi
git -C teamgram-server checkout -q -- teamgramd/etc2   # fresh templates before configuring

# 2. secrets (generated once)
if [ ! -f privetgram.env ]; then
  umask 077
  cat > privetgram.env <<EOF
MYSQL_ROOT_PASSWORD=$(openssl rand -hex 16)
MYSQL_PASSWORD=$(openssl rand -hex 16)
MINIO_ROOT_PASSWORD=$(openssl rand -hex 16)
INVITE_CODE=${INVITE_CODE:-$(openssl rand -hex 4)}
EOF
fi
FP=$(python3 "$HERE/rsa_fingerprint.py" "$KEY")
sed -i '/^KEY_FINGERPRINT=/d' privetgram.env
echo "KEY_FINGERPRINT=$FP" >> privetgram.env
cp privetgram.env .env

# 3. configs
install -m 600 "$KEY" teamgram-server/teamgramd/bin/server_pkcs1.key
python3 "$HERE/configure.py" teamgram-server privetgram.env
mkdir -p data logs

# 4. run
docker compose up -d --build

. ./privetgram.env
IP=$(curl -fsS4 --max-time 5 https://ifconfig.me 2>/dev/null || hostname -I | awk '{print $1}')
cat <<EOF

Privetgram server is starting (first start takes a minute or two: MySQL is being initialised).
  Address for the app:  $IP   (port ${MTPROTO_PORT:-10443}, TCP must be open in the firewall)
  Invite code:          $INVITE_CODE   (the "SMS code" when a NEW number signs up)
  Key fingerprint:      $FP

Logs:            docker compose logs -f teamgram
Lost-device code: docker compose logs teamgram | grep "login code for"
EOF
