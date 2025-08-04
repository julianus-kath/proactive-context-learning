FROM n8nio/n8n:latest

# Switch to root user to install dependencies
USER root

# Install Python and other build dependencies
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    build-essential \
    && ln -s /usr/bin/python3 /usr/bin/python \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install the SQLite community node
RUN npm install -g n8n-nodes-sqlite3

# Set the environment variable to enforce file permissions
ENV N8N_ENFORCE_SETTINGS_FILE_PERMISSIONS=true

# Switch back to node user
USER node

# Command to run
CMD ["n8n", "start"]
