import psutil

class TunnelService:
    @staticmethod
    def get_status() -> dict:
        """
        Check if the cloudflared process is running and return its status.
        """
        is_running = False
        for proc in psutil.process_iter(['name']):
            try:
                if 'cloudflared' in proc.info['name'].lower():
                    is_running = True
                    break
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
        
        return {
            "status": "Online" if is_running else "Offline",
            "is_running": is_running
        }

    @staticmethod
    def get_public_url() -> str:
        """
        Retrieve the tunnel URL using project standard settings loader.
        """
        try:
            from loadnsave import load_settings
            settings = load_settings()
            return settings.get('tunnel_url', "Not Configured")
        except Exception:
            return "Not Configured"
