FROM python:3.11-slim

WORKDIR /app
COPY . .

RUN pip install --no-cache-dir .

# HTTP transport; bind all interfaces. Port comes from $PORT (Cloud Run sets it), default 3000.
# MCP_ALLOWED_HOSTS: the SDK rejects unknown Host headers (DNS-rebinding protection).
# A container is reached through whatever hostname the platform assigns, so relax it
# here; set it to your actual hostname(s) instead if you prefer the check enforced.
ENV MCP_TRANSPORT=http \
    HOST=0.0.0.0 \
    PORT=3000 \
    MCP_ALLOWED_HOSTS=*
EXPOSE 3000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import os,urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:'+os.environ.get('PORT','3000')+'/health').status==200 else 1)"

# No --port here: argparse reads $PORT, so the container adapts to the host's injected PORT.
CMD ["celo-mcp-server", "--transport", "http", "--host", "0.0.0.0"]
