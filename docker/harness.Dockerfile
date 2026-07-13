FROM node:24-bookworm-slim

RUN apt-get update \
 && apt-get install -y --no-install-recommends ca-certificates git python3 ripgrep \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /opt/benchmark
COPY toolchain/package.json toolchain/package-lock.json /opt/benchmark/toolchain/
RUN npm ci --prefix /opt/benchmark/toolchain --no-audit --no-fund
ENV PATH="/opt/benchmark/toolchain/node_modules/.bin:$PATH" \
    PYTHONPATH="/opt/benchmark" \
    HOME="/tmp/benchmark-home" \
    NO_COLOR="1" \
    DO_NOT_TRACK="1"
COPY benchkit /opt/benchmark/benchkit
COPY adapters /opt/benchmark/adapters
RUN mkdir -p /tmp/benchmark-home
