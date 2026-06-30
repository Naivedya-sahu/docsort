# Troubleshooting

## Remote model host (e.g. `HOME`) times out on port 1234

**Symptom:** `--host HOME` (or any non-localhost host) hangs / `URLError: timed out`,
while `localhost` works. `ping HOME` succeeds but `http://HOME:1234/v1/models` does not.

**Cause:** by default LM Studio binds to `127.0.0.1`, and Windows Firewall blocks
inbound TCP 1234 — so the model server is unreachable from other machines (the Pi5,
this laptop, etc.).

### Fix — on the HOST machine that runs the model (e.g. the desktop `HOME`)

**1. Make LM Studio serve on the network**
- LM Studio → **Developer** (or **Local Server**) tab → server settings →
  enable **"Serve on Local Network"** (binds `0.0.0.0` instead of `127.0.0.1`).
- Start the server. Note the port (default **1234**).

**2. Open the inbound firewall port (TCP 1234)**
- **PowerShell (Run as Administrator) — one line:**
  ```powershell
  New-NetFirewallRule -DisplayName "LM Studio 1234" -Direction Inbound `
    -Protocol TCP -LocalPort 1234 -Action Allow -Profile Private
  ```
- **Or GUI:** Windows Defender Firewall with Advanced Security → **Inbound Rules** →
  **New Rule…** → **Port** → **TCP** → **Specific local ports: 1234** → **Allow the connection**
  → tick **Private** (and **Domain** if applicable; leave **Public** off) → name it `LM Studio 1234`.

  To remove later: `Remove-NetFirewallRule -DisplayName "LM Studio 1234"`.

**3. Verify from the CLIENT machine** (the one running docsort)
```bash
python -c "import urllib.request,json;print([m['id'] for m in json.load(urllib.request.urlopen('http://HOME:1234/v1/models',timeout=8))['data']])"
```
Should list the loaded models. Then `docsort ... --host HOME` works.

### Notes
- Use the **hostname** (`HOME`) or the **LAN/Tailscale IP** (e.g. `192.168.31.211`,
  `100.x.y.z`) in `config.json` → `hosts`. Both are equivalent if DNS resolves.
- **Profile = Private** keeps the port open only on trusted networks. Do **not** allow
  it on the **Public** profile, and never port-forward 1234 to the internet — the API is
  unauthenticated.
- Over **Tailscale**, prefer the `100.x` tailnet IP/hostname; the tailnet is already
  access-controlled, so a Private-profile rule is enough.

## Other quick ones
| Symptom | Fix |
|---|---|
| `[warn] model server unreachable` | host down / firewall — see above. Script still runs but every file → 99UNS. |
| Configured model not used | it wasn't loaded; auto-resolve picked a loaded one (see the `[model] ... -> ...` line). Load the model in LM Studio to force it. |
| GUI won't open | needs Tkinter — bundled with standard CPython on Windows; on Linux `apt install python3-tk`. |
| PDFs skipped | reinstall so `pymupdf` is present. `.docx/.pptx` → `pip install "docsort[office]"`. |
| Everything 99UNS | model too weak — use a 7B/8B vision model, or `--frontier claude` for hard cases. |
