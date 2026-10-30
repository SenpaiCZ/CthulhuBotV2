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

def wait_for_pid(pid, timeout=20):
    if not pid:
        return
    log(f"Waiting for process {pid} to exit...")
    start = time.time()
    try:
        while psutil.pid_exists(pid):
            if time.time() - start >= timeout:
                log(f"Process {pid} did not exit within {timeout}s — terminating.")
                try:
                    proc = psutil.Process(pid)
                    proc.terminate()
                    proc.wait(timeout=5)
                except Exception:
                    try:
                        psutil.Process(pid).kill()
                    except Exception:
                        pass
                break
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
            while os.path.exists(f"/proc/{pid}") and (time.time() - start < timeout):
                time.sleep(1)
    log("Process exited.")


def terminate_existing_bot_processes():
    """Ensure no duplicate bot.py instances from the same directory remain running."""
    my_pid = os.getpid()
    cwd = os.path.abspath(".")
    try:
        for proc in psutil.process_iter(["pid", "cmdline", "cwd"]):
            try:
                if proc.pid == my_pid:
                    continue
                cmdline = proc.info.get("cmdline") or []
                if not any(os.path.basename(arg) == "bot.py" for arg in cmdline):
                    continue
                proc_cwd = proc.info.get("cwd")
                if proc_cwd and os.path.abspath(proc_cwd) != cwd:
                    continue
                log(f"Terminating leftover bot.py process (PID {proc.pid})...")
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except psutil.TimeoutExpired:
                    proc.kill()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
    except Exception as e:
        log(f"Process scan warning: {e}")


def restart_bot():
    terminate_existing_bot_processes()
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
