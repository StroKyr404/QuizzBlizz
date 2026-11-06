import subprocess
import re
import socket
import threading
import time
import os
import atexit
from typing import Optional

class TunnelManager:
    def __init__(self, port: int = 8000):
        self.port = port
        self.public_url: Optional[str] = None
        self.process: Optional[subprocess.Popen] = None
        self.local_ip: str = self._detect_local_ip()
        atexit.register(self.stop_tunnel)

    def _detect_local_ip(self) -> str:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            # Doesn't need to be reachable, just creates routing socket
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "127.0.0.1"

    def get_join_url(self) -> str:
        if self.public_url:
            return self.public_url
        return f"http://{self.local_ip}:{self.port}"

    def start_tunnel(self) -> Optional[str]:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        cloudflared_path = os.path.join(base_dir, "cloudflared")
        
        if not os.path.exists(cloudflared_path) or not os.access(cloudflared_path, os.X_OK):
            # Check system path
            which = subprocess.run(["which", "cloudflared"], capture_output=True, text=True)
            if which.returncode == 0 and which.stdout.strip():
                cloudflared_path = which.stdout.strip()
            elif hasattr(os, "uname") and os.uname().sysname == "Darwin":
                # Auto-download portable cloudflared on macOS
                arch = "arm64" if os.uname().machine == "arm64" else "amd64"
                try:
                    print(f"📥 Lade Cloudflare-Tunnel für macOS ({arch}) herunter...")
                    subprocess.run(
                        f"curl -sL https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-darwin-{arch}.tgz | tar -xz -C '{base_dir}'",
                        shell=True, timeout=20
                    )
                    if os.path.exists(cloudflared_path):
                        os.chmod(cloudflared_path, 0o755)
                except Exception as dl_err:
                    print(f"Auto-Download fehlgeschlagen ({dl_err}). Nutze lokale IP.")
            
            if not os.path.exists(cloudflared_path) or not os.access(cloudflared_path, os.X_OK):
                print("ℹ️ cloudflared nicht verfügbar. Nutze lokale IP:", self.get_join_url())
                return None

        print("🚀 Starte sicheren Cloudflare-Tunnel für Schul-WLAN...")
        try:
            self.process = subprocess.Popen(
                [cloudflared_path, "tunnel", "--url", f"http://127.0.0.1:{self.port}"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1
            )

            url_pattern = re.compile(r"https://[a-zA-Z0-9-]+\.trycloudflare\.com")
            start_t = time.time()

            # Read stderr where cloudflared logs the tunnel URL
            while time.time() - start_t < 15:
                line = self.process.stderr.readline()
                if not line and self.process.poll() is not None:
                    break
                match = url_pattern.search(line)
                if match:
                    self.public_url = match.group(0)
                    print(f"✨ Tunnel aktiv! Weltweite HTTPS-URL: {self.public_url}")
                    return self.public_url
                time.sleep(0.1)

        except Exception as e:
            print(f"Tunnel-Start fehlgeschlagen ({e}). Wechsle zu lokaler IP.")

        return None

    def stop_tunnel(self):
        if self.process and self.process.poll() is None:
            print("Stoppe Cloudflare-Tunnel...")
            self.process.terminate()
            try:
                self.process.wait(timeout=3)
            except Exception:
                self.process.kill()
            self.process = None

tunnel_manager = TunnelManager(port=8000)
