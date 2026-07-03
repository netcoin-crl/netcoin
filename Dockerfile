# NetCoin dev node. Educational testnet software — do not expose to the
# internet without reading docs/PUBLIC_SEED_HOSTING.md.
FROM python:3.12-slim

WORKDIR /opt/netcoin
COPY pyproject.toml README.md LICENSE ./
COPY netcoin/ netcoin/
RUN pip install --no-cache-dir .

# Chain + wallet data live here; mount a volume to persist between runs.
ENV NETCOIN_DATA=/data
VOLUME ["/data"]
EXPOSE 28444 28445

# Joins the public testnet seeds by default. Override the CMD for a fully
# private local chain: python -m netcoin --data /data node --host 0.0.0.0
CMD ["python", "-m", "netcoin", "--data", "/data", "node", "--host", "0.0.0.0", "--port", "28444", "--seeds", "--sync-interval", "45"]
