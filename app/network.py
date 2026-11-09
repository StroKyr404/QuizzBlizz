import socket
import subprocess
from typing import Optional

class NetworkManager:
    def __init__(self, port: int = 8000):
        self.port = port
        self.local_ip: str = self._detect_local_ip()

    def _detect_local_ip(self) -> str:
        # Method 1: Connect to external IP via UDP routing socket
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            if ip and not ip.startswith("127."):
                return ip
        except Exception:
            pass

        # Method 2: Check active network interfaces via ifconfig (macOS / Linux)
        try:
            out = subprocess.check_output(["ifconfig"], text=True)
            for line in out.splitlines():
                line = line.strip()
                if line.startswith("inet ") and "127.0.0.1" not in line:
                    parts = line.split()
                    if len(parts) >= 2 and not parts[1].startswith("127."):
                        return parts[1]
        except Exception:
            pass

        return "127.0.0.1"

    def get_base_url(self) -> str:
        return f"http://{self.local_ip}:{self.port}"

    def get_join_url(self) -> str:
        return f"http://{self.local_ip}:{self.port}"

network_manager = NetworkManager(port=8000)
