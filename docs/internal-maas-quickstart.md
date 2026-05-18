# Internal MaaS Quickstart

This guide is for a hardware team that wants to run `pyslang-mcp` on an
internal server, against an internal RTL checkout.

The recommended bring-up path is:

1. mount one RTL checkout read-only into a container
2. run `pyslang-mcp` over MCP Streamable HTTP inside that container
3. protect it with a bearer token
4. keep the server port bound to `127.0.0.1` unless your IT/security team puts
   a real internal gateway in front of it

The current setup is intended for internal bring-up. It is not a public
hosted service.

## Is Docker Required?

No. Docker is strongly recommended for the first corporate bring-up because it
avoids Python environment problems and gives a simple read-only mount boundary.

Use the native Python path if Docker is not available on the target server.
The native path works, but the server process can see whatever the operating
system user can read, so use a dedicated service account with access only to
the intended RTL checkout.

| Path | Use when | Main tradeoff |
|---|---|---|
| Docker Compose | you can run Docker on the internal server | easiest install and cleaner filesystem boundary |
| Native Python | Docker is not available or not allowed | fewer moving parts, but isolation depends on the OS user and file permissions |

## What You Need

For the recommended Docker path:

- a Linux server or workstation
- Docker with Docker Compose
- an RTL checkout on that server
- this `pyslang-mcp` repo checkout

You do not need to install Python packages by hand. The container build does
that.

For the native Python path:

- a Linux server or workstation
- Python 3.11 or 3.12
- an RTL checkout on that server
- either internet access to PyPI or an internally mirrored wheel/package

## Fastest Path: Docker Compose

From the repo root, run:

```bash
python3 scripts/setup_internal_maas.py --workspace /absolute/path/to/your/rtl
```

Replace `/absolute/path/to/your/rtl` with the directory that contains your RTL
checkout. The script writes `deploy/internal/.env` and prints a bearer token.

Start the service:

```bash
cd deploy/internal
docker compose up -d --build
```

Check that the container is running:

```bash
docker compose ps
```

Check the logs if needed:

```bash
docker compose logs -f
```

Stop the service:

```bash
docker compose down
```

### Docker Path Detail

Inside the container, your RTL checkout is always mounted at:

```text
/workspace
```

That means MCP tool calls should use:

```json
{
  "project_root": "/workspace",
  "filelist": "compile/project.f"
}
```

Use paths relative to the RTL checkout for `filelist`, `files`, and
`include_dirs`.

## No-Docker Path: Native Python

Use this when Docker is not available in the corporate environment.

Create a virtual environment:

```bash
python3 -m venv /opt/pyslang-mcp-venv
/opt/pyslang-mcp-venv/bin/pip install --upgrade pip
/opt/pyslang-mcp-venv/bin/pip install 'pyslang-mcp>=0.1.0'
```

Generate a bearer token:

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

Start the service. Replace the token value with the generated token:

```bash
export PYSLANG_MCP_HTTP_BEARER_TOKEN='replace-with-generated-token'
/opt/pyslang-mcp-venv/bin/pyslang-mcp \
  --transport streamable-http \
  --experimental-enable-http \
  --http-host 127.0.0.1 \
  --http-port 8000 \
  --http-require-bearer-token
```

For native Python, tool calls use the real path on the server:

```json
{
  "project_root": "/proj/chip/team/block_a",
  "filelist": "compile/project.f"
}
```

Keep `--http-host 127.0.0.1` unless the service is behind your company's
normal internal gateway, VPN, firewall, and TLS setup.

For a persistent native deployment, run that command under your normal service
manager, such as `systemd`, using a dedicated Unix user that has read access
only to the intended RTL checkout.

There is a starter `systemd` unit at:

```text
deploy/internal/systemd/pyslang-mcp.service.example
```

Copy it to your server's systemd unit directory, replace the token and RTL path,
then start it with your normal systemd workflow.

Typical commands:

```bash
sudo useradd --system --home /nonexistent --shell /usr/sbin/nologin pyslang-mcp
sudo cp deploy/internal/systemd/pyslang-mcp.service.example /etc/systemd/system/pyslang-mcp.service
sudo vi /etc/systemd/system/pyslang-mcp.service
sudo systemctl daemon-reload
sudo systemctl enable --now pyslang-mcp
sudo systemctl status pyslang-mcp
```

## Connecting From Your Laptop

The compose file binds the MCP port to `127.0.0.1` on the server. That is
intentional: it avoids accidentally exposing RTL analysis on the whole network.
Use the same binding for the native Python path.

If the service runs on a remote server, use an SSH tunnel:

```bash
ssh -L 8000:127.0.0.1:8000 your-user@your-internal-server
```

Then configure your MCP client to use:

```text
http://127.0.0.1:8000/mcp
```

Send this HTTP header with requests:

```text
Authorization: Bearer <token>
```

For Docker Compose, the token is in `deploy/internal/.env`. For native Python,
use the token you exported as `PYSLANG_MCP_HTTP_BEARER_TOKEN`.

Generic MCP client shape:

```json
{
  "mcpServers": {
    "pyslang-mcp-internal": {
      "url": "http://127.0.0.1:8000/mcp",
      "headers": {
        "Authorization": "Bearer replace-with-token-from-env-file"
      }
    }
  }
}
```

Different MCP clients use different config field names for remote HTTP
servers. The required pieces are the URL and the `Authorization` header.

## Changing The RTL Checkout Or Port

For Docker Compose, edit:

```text
deploy/internal/.env
```

Example:

```text
PYSLANG_MCP_WORKSPACE=/proj/chip/team/block_a
PYSLANG_MCP_HTTP_PORT=8000
PYSLANG_MCP_HTTP_BEARER_TOKEN=long-random-token
```

Restart after changes:

```bash
cd deploy/internal
docker compose up -d
```

For native Python, change the real `project_root` path in the MCP tool call.
The native service itself does not mount a workspace.

## Team Server Notes

For one engineer or a small trusted group, the SSH tunnel pattern is the
simplest safe starting point.

For a broader team, put an internal gateway in front of this service:

- company SSO or VPN
- HTTPS/TLS
- request logging that does not store source code
- per-user tokens or service tokens
- firewall rules that restrict who can reach the server

Do not bind the Compose port to `0.0.0.0`, or run native Python with
`--http-host 0.0.0.0`, unless the service is protected by your company's normal
internal access controls.

## Security Properties

What this setup does:

- mounts the RTL checkout read-only
- runs as a non-root user inside the container
- drops Linux capabilities in Compose
- makes the container filesystem read-only except `/tmp`
- requires a bearer token for MCP HTTP requests
- keeps path access under the `project_root` supplied in each tool call

For native Python, only the bearer-token and `project_root` checks apply by
default. Use a dedicated service account and OS permissions to keep the process
away from unrelated files.

What this setup does not do:

- it does not provide company SSO by itself
- it does not manage multiple users or multiple workspaces
- it does not clone private repositories
- it does not replace your company's normal network and access controls
- it does not run simulation, synthesis, waveform tools, or arbitrary shell
  commands

## Common Problems

If Docker says the port is already in use, regenerate the env file with a
different port:

```bash
python3 scripts/setup_internal_maas.py --workspace /absolute/path/to/your/rtl --port 8010 --force
```

If a tool call says the path is outside the project root:

- Docker path: use `/workspace` as `project_root` and keep source paths
  relative to that directory.
- Native Python path: use the real RTL checkout path as `project_root` and keep
  source paths under that directory.

If the MCP client gets `401`, check that it is sending:

```text
Authorization: Bearer <token>
```
