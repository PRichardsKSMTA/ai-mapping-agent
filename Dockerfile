# syntax=docker/dockerfile:1

########################################
# Builder
########################################
FROM python:3.11.13-slim-bookworm AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Minimal tools to add Microsoft APT repo
RUN apt-get update \
 && apt-get install -y --no-install-recommends curl gnupg ca-certificates \
 && rm -rf /var/lib/apt/lists/*

# Add Microsoft SQL Server ODBC repo (Debian 12 / bookworm)
RUN curl -fsSL https://packages.microsoft.com/keys/microsoft.asc | gpg --dearmor -o /usr/share/keyrings/ms-prod.gpg \
 && echo "deb [arch=amd64 signed-by=/usr/share/keyrings/ms-prod.gpg] https://packages.microsoft.com/debian/12/prod bookworm main" > /etc/apt/sources.list.d/microsoft-prod.list

# Optional build-time packages (headers/libs for compiling wheels)
COPY packages.build.txt /tmp/packages.build.txt
RUN if [ -s /tmp/packages.build.txt ]; then \
      apt-get update \
   && ACCEPT_EULA=Y DEBIAN_FRONTEND=noninteractive \
      apt-get install -y --no-install-recommends $(tr -d '\r' </tmp/packages.build.txt) \
   && rm -rf /var/lib/apt/lists/*; \
    fi

# Python deps into an isolated venv
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .
RUN pip install --upgrade --no-cache-dir pip \
 && pip install --no-cache-dir -r requirements.txt


########################################
# Runtime
########################################
FROM python:3.11.13-slim-bookworm AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    STREAMLIT_SERVER_HEADLESS=true \
    PORT=8501 \
    USE_POSTPROCESS=0

WORKDIR /app

# Base OS updates + minimal tools to add Microsoft repo
RUN apt-get update \
 && apt-get upgrade -y \
 && apt-get install -y --no-install-recommends curl gnupg ca-certificates \
 && rm -rf /var/lib/apt/lists/*

# Add Microsoft SQL Server ODBC repo (Debian 12 / bookworm)
RUN curl -fsSL https://packages.microsoft.com/keys/microsoft.asc | gpg --dearmor -o /usr/share/keyrings/ms-prod.gpg \
 && echo "deb [arch=amd64 signed-by=/usr/share/keyrings/ms-prod.gpg] https://packages.microsoft.com/debian/12/prod bookworm main" > /etc/apt/sources.list.d/microsoft-prod.list

# Install runtime OS deps from packages.txt (CRLF-safe + EULA accepted)
COPY packages.txt /tmp/packages.txt
RUN if [ -s /tmp/packages.txt ]; then \
      apt-get update \
   && ACCEPT_EULA=Y DEBIAN_FRONTEND=noninteractive \
      apt-get install -y --no-install-recommends $(tr -d '\r' </tmp/packages.txt) \
   && rm -rf /var/lib/apt/lists/*; \
    fi

# Remove one-time tools to trim CVE surface
RUN apt-get purge -y curl gnupg || true \
 && apt-get autoremove -y \
 && rm -rf /var/lib/apt/lists/*

# Bring in the prebuilt virtualenv
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# App files
COPY . .

# Normalize Windows line endings on shell scripts (and ensure executable)
RUN find /app -maxdepth 1 -type f -name "*.sh" -exec sed -i 's/\r$//' {} \; \
 && chmod +x /app/*.sh || true

# Ensure scripts are executable (helps on Windows checkouts)
RUN chmod +x /app/start.sh || true

# Least privilege
RUN useradd --create-home --shell /usr/sbin/nologin appuser \
 && chown -R appuser:appuser /app
USER appuser

# HEALTHCHECK: exec-form, no heredoc
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=5 \
  CMD ["python","-c","import os,sys,urllib.request; url=f'http://127.0.0.1:{os.environ.get(\"PORT\",\"8501\")}/_stcore/health'; r=urllib.request.urlopen(url, timeout=3); sys.exit(0 if r.status==200 else 1)"]

# Entry point:
CMD ["/bin/sh","-lc","if [ \"$USE_POSTPROCESS\" = \"1\" ]; then python /app/start_postprocess.py --server.port=${PORT} --server.address=0.0.0.0; else /app/start.sh; fi"]
