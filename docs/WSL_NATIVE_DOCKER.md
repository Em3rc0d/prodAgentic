# prodAgentic — Native Docker Engine inside WSL

This runbook is for the specific case where Docker Engine runs inside a WSL distribution and the Windows host cannot consume WSL-published loopback ports reliably.

## Symptom

The stack is healthy inside WSL:

```text
frontend container -> HTTP 200
WSL curl :3000    -> HTTP 200
backend /health   -> HTTP 200
```

but a Windows browser or `curl.exe` to `http://127.0.0.1:3000` gets a connection reset.

That means the application is healthy and the failure is the Windows↔WSL localhost-forwarding boundary.

## Preferred command

From WSL, at the repository root:

```bash
bash scripts/docker-wsl-up.sh
```

The launcher:

1. verifies that it is running under WSL;
2. discovers the IPv4 source address of WSL's default route;
3. refuses to continue unless that address is RFC1918 private space;
4. binds only frontend/backend to that private WSL address;
5. keeps Mongo published only on `127.0.0.1:27017`;
6. compiles the browser API origin to the same WSL address;
7. enables the private-HTTP build exception explicitly;
8. aligns backend CORS and frontend authority;
9. removes stale Compose orphans;
10. prints the exact Windows URL to open.

Example output:

```text
prodAgentic WSL NAT mode
  WSL IP:   172.30.98.229
  Frontend: http://172.30.98.229:3000
  Backend:  http://172.30.98.229:8000
  Mongo:    127.0.0.1:27017 only

Open this URL from Windows:
http://172.30.98.229:3000
```

Use the printed address rather than `localhost:3000` for that WSL session.

## Why the frontend must be rebuilt

`NEXT_PUBLIC_API_URL` is compiled into the Next.js browser bundle. In WSL NAT fallback mode the browser cannot depend on Windows localhost forwarding, so the frontend must be built with:

```text
NEXT_PUBLIC_API_URL=http://<WSL_IP>:8000
```

The normal production gate still rejects non-HTTPS remote origins. RFC1918 HTTP is accepted only when all of the following are true:

```text
PRODAGENTIC_ALLOW_PRIVATE_HTTP_API=true
origin protocol = http
origin address  = RFC1918 IPv4
```

Supported private ranges:

```text
10.0.0.0/8
172.16.0.0/12
192.168.0.0/16
```

The explicit exception is intended only for local/private Docker operation.

## Manual equivalent

If the helper script cannot be used, resolve the WSL address:

```bash
WSL_IP="$(ip -4 route get 1.1.1.1 | awk '{for (i = 1; i <= NF; i++) if ($i == "src") {print $(i + 1); exit}}')"
echo "$WSL_IP"
```

Then start the stack with matching browser/backend boundaries:

```bash
PRODAGENTIC_WEB_BIND_HOST="$WSL_IP" \
NEXT_PUBLIC_API_URL="http://$WSL_IP:8000" \
PRODAGENTIC_ALLOW_PRIVATE_HTTP_API=true \
CORS_ALLOWED_ORIGINS="http://localhost:3000,http://127.0.0.1:3000,http://$WSL_IP:3000" \
FRONTEND_URL="http://$WSL_IP:3000" \
LINKEDIN_REDIRECT_URI="http://$WSL_IP:8000/api/integrations/linkedin/callback" \
docker compose up -d --build --remove-orphans
```

Open:

```text
http://<WSL_IP>:3000
```

## WSL IP lifecycle

Under WSL NAT the private address can change after WSL is shut down or Windows restarts. Re-run:

```bash
bash scripts/docker-wsl-up.sh
```

The launcher rebuilds the frontend with the current browser-visible backend origin.

## Normal Docker path remains unchanged

When Windows/Docker Desktop localhost publication works correctly, continue using:

```bash
docker compose up --build
```

and open:

```text
http://localhost:3000
```

Default Compose behavior remains loopback-only. WSL private-address publication happens only when the explicit override is supplied.

## Do not expose Mongo

The WSL fallback intentionally does not change Mongo's host publication:

```text
127.0.0.1:27017
```

There is no reason for the Windows browser to connect directly to Mongo.

## Diagnostics

Confirm application health inside WSL:

```bash
docker compose ps
docker compose logs --tail=100 frontend
curl -v http://127.0.0.1:3000/
curl -v http://127.0.0.1:8000/health/live
```

Confirm the WSL-bound path:

```bash
WSL_IP="$(ip -4 route get 1.1.1.1 | awk '{for (i = 1; i <= NF; i++) if ($i == "src") {print $(i + 1); exit}}')"
curl -v "http://$WSL_IP:3000/"
curl -v "http://$WSL_IP:8000/health/live"
```

From Windows PowerShell or CMD, use the same private address:

```powershell
curl.exe http://<WSL_IP>:3000/
curl.exe http://<WSL_IP>:8000/health/live
```

If both private-address requests succeed, continue with `mk1/test/LOCAL_ACCEPTANCE.md`.
