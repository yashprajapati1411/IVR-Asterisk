FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV ASTERISK_SOUNDS_DIR=/var/lib/asterisk/sounds/ivr

# Install Asterisk, Python, audio tools, and dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    asterisk \
    asterisk-modules \
    asterisk-core-sounds-en \
    python3 \
    python3-pip \
    python3-venv \
    sox \
    libsox-fmt-all \
    ffmpeg \
    curl \
    sqlite3 \
    net-tools \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Setup Python environment
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

# Copy application source code
COPY agi/ /app/agi/
COPY services/ /app/services/
COPY models/ /app/models/
COPY scripts/ /app/scripts/
COPY sounds/ /app/sounds/

# Copy Asterisk configuration files
COPY asterisk_config/extensions.conf /etc/asterisk/extensions.conf
COPY asterisk_config/pjsip.conf /etc/asterisk/pjsip.conf
COPY asterisk_config/rtp.conf /etc/asterisk/rtp.conf
COPY asterisk_config/modules.conf /etc/asterisk/modules.conf

# Setup sound directories in Asterisk sound path
RUN mkdir -p /var/lib/asterisk/sounds/ivr/gu && \
    mkdir -p /var/lib/asterisk/sounds/ivr/cache && \
    cp -r /app/sounds/gu/* /var/lib/asterisk/sounds/ivr/gu/ && \
    mkdir -p /var/lib/asterisk/agi-bin && \
    cp /app/agi/ivr_handler.py /var/lib/asterisk/agi-bin/ivr_handler.py && \
    chmod +x /var/lib/asterisk/agi-bin/ivr_handler.py

# Initialize database and prompts
RUN python3 scripts/seed_db.py && python3 scripts/generate_prompts.py

# Copy entrypoint script
COPY docker-entrypoint.sh /app/docker-entrypoint.sh
RUN chmod +x /app/docker-entrypoint.sh

# Expose SIP, RTP, and FastAGI ports
EXPOSE 5060/udp 5060/tcp 4573/tcp 10000-10100/udp

ENTRYPOINT ["/app/docker-entrypoint.sh"]
