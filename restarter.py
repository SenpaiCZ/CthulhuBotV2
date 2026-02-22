import os
import sys
import time
import subprocess
import argparse
import platform
import psutil

def log(message):
    timestamp = time.strftime("[%H:%M:%S]")
    print(f"{timestamp} [Restarter] {message}", flush=True)

def wait_for_pid(pid):
    if not pid:
        return
    log(f"Waiting for process {pid} to exit...")
    try:
        while psutil.pid_exists(pid):
            # If zombie, treat as exited
            try:
                proc = psutil.Process(pid)
                if proc.status() == psutil.STATUS_ZOMBIE:
                    log(f"Process {pid} is a zombie. Proceeding.")
                    break
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                break
            except Exception:
                pass
            time.sleep(1)
    except ImportError:
        # Fallback if psutil is missing (should be in requirements.txt)
        if platform.system() == "Windows":
            time.sleep(5)
        else:
            while os.path.exists(f"/proc/{pid}"):
                time.sleep(1)
    log("Process exited.")

def restart_bot():
    log("Starting bot...")
    cmd = [sys.executable, "bot.py"]

    if platform.system() == "Windows":
        # Windows: CREATE_NEW_CONSOLE ensures it runs in a new console window
        flags = subprocess.CREATE_NEW_CONSOLE
        subprocess.Popen(cmd, creationflags=flags)
    else:
        # Linux/Unix: close_fds=True ensures the new process doesn't inherit file descriptors
        subprocess.Popen(cmd, close_fds=True)

    log("Bot restarted. Exiting restarter.")
    sys.exit(0)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Bot Restarter")
    parser.add_argument("pid", type=int, help="PID of the process to wait for")
    args = parser.parse_args()

    # Wait for the old process to exit
    wait_for_pid(args.pid)

    # Start the new process
    restart_bot()
