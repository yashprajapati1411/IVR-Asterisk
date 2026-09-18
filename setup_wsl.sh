#!/bin/bash
set -e

echo "=== Installing Asterisk and Python in Ubuntu (WSL) ==="
export DEBIAN_FRONTEND=noninteractive

# 1. Update and install Asterisk and Python
apt-get update
apt-get install -y asterisk asterisk-modules asterisk-core-sounds-en python3 python3-pip python3-venv sox net-tools

# 2. Setup Python environment
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
cd "$DIR"
pip3 install --break-system-packages -r requirements.txt

# 3. Copy Configuration Files to Asterisk
cp asterisk_config/extensions.conf /etc/asterisk/
cp asterisk_config/pjsip.conf /etc/asterisk/
cp asterisk_config/rtp.conf /etc/asterisk/
cp asterisk_config/modules.conf /etc/asterisk/

# 4. Copy Sound Files
mkdir -p /var/lib/asterisk/sounds/ivr/gu
mkdir -p /var/lib/asterisk/sounds/ivr/cache
cp -r sounds/gu/* /var/lib/asterisk/sounds/ivr/gu/
chown -R asterisk:asterisk /var/lib/asterisk/sounds/ivr

# 5. Start Asterisk Service
service asterisk restart

# 6. Start FastAGI Server in the background
nohup python3 agi/server.py --host 0.0.0.0 --port 4573 > /var/log/fastagi.log 2>&1 &
echo $! > /var/run/fastagi.pid

echo "=== Asterisk and FastAGI are now running! ==="
asterisk -rx "core show uptime"
