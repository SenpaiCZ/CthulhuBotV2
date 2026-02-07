#!/usr/bin/env python3
import os
import sys
import shutil
import time
import zipfile
import urllib.request
import subprocess
import platform
import argparse

# Configuration
REPO_URL = "https://github.com/SenpaiCZ/CthulhuBotV2/archive/refs/heads/master.zip"
ZIP_FILENAME = "update_pkg.zip"
EXTRACT_DIR = "update_extract_temp"
BACKUP_DIR = "backups"
EXCLUDED_DIRS = {
    "venv", ".git", "__pycache__", "soundboard", "backups",
    ".vscode", ".idea", "node_modules"
}
EXCLUDED_FILES = {
    "config.json", ZIP_FILENAME, "updater.py", "Procfile", ".gitignore", "setup.bat", "setup.sh", "update.bat"
}
# Special folders we don't want to overwrite if they exist (user data)
USER_DATA_DIRS = {"infodata", "data"}

def log(message):
    timestamp = time.strftime("[%H:%M:%S]")
    print(f"{timestamp} [Updater] {message}", flush=True)

def wait_for_pid(pid):
    if not pid:
        return
    log(f"Waiting for process {pid} to exit...")
    try:
        import psutil
        while psutil.pid_exists(pid):
            time.sleep(1)
    except ImportError:
        # Fallback if psutil is not installed (standard library only)
        if platform.system() == "Windows":
             # Simple dumb wait
            time.sleep(5)
        else:
            # Check /proc on Linux
            while os.path.exists(f"/proc/{pid}"):
                time.sleep(1)
    log("Process exited.")

def download_update():
    log(f"Downloading update from {REPO_URL}...")
    try:
        urllib.request.urlretrieve(REPO_URL, ZIP_FILENAME)
        log("Download complete.")
    except Exception as e:
        log(f"Download failed: {e}")
        sys.exit(1)

def extract_and_apply():
    log("Extracting update...")
    try:
        with zipfile.ZipFile(ZIP_FILENAME, 'r') as zip_ref:
            zip_ref.extractall(EXTRACT_DIR)

        # GitHub archives usually have a top-level folder
        entries = os.listdir(EXTRACT_DIR)
        if not entries:
            raise Exception("Empty zip file")

        extracted_root = os.path.join(EXTRACT_DIR, entries[0])

        log(f"Applying updates from {extracted_root}...")

        # Walk and copy
        for root, dirs, files in os.walk(extracted_root):
            rel_path = os.path.relpath(root, extracted_root)
            dest_dir = os.path.join(".", rel_path)

            # Filter directories
            if rel_path == ".":
                # Modify dirs in-place to prevent recursion into excluded/user dirs
                # We check if the dir is in our exclude list
                dirs[:] = [d for d in dirs if d not in EXCLUDED_DIRS and d not in USER_DATA_DIRS]

            # Create destination directory
            if rel_path != "." and not os.path.exists(dest_dir):
                os.makedirs(dest_dir, exist_ok=True)

            for file in files:
                if rel_path == "." and file in EXCLUDED_FILES:
                    continue

                src_file = os.path.join(root, file)
                dest_file = os.path.join(dest_dir, file)

                try:
                    shutil.copy2(src_file, dest_file)
                except Exception as e:
                    log(f"Failed to copy {file}: {e}")

        log("Update applied successfully.")

    except Exception as e:
        log(f"Extraction failed: {e}")
        sys.exit(1)
    finally:
        # Cleanup temp
        if os.path.exists(EXTRACT_DIR):
            try:
                shutil.rmtree(EXTRACT_DIR)
            except:
                pass
        if os.path.exists(ZIP_FILENAME):
            try:
                os.remove(ZIP_FILENAME)
            except:
                pass

def update_dependencies():
    log("Updating dependencies...")
    pip_cmd = [sys.executable, "-m", "pip", "install", "-r", "requirements.txt"]
    try:
        subprocess.check_call(pip_cmd)
        log("Dependencies updated.")
    except subprocess.CalledProcessError as e:
        log(f"Dependency update warning: {e}")

def restart_bot():
    log("Restarting bot...")

    cmd = [sys.executable, "bot.py"]

    if platform.system() == "Windows":
        # Create new console window
        flags = subprocess.CREATE_NEW_CONSOLE
        subprocess.Popen(cmd, creationflags=flags)
    else:
        # Standard Popen on Unix
        subprocess.Popen(cmd, close_fds=True)

    log("Bot restarted. Exiting updater.")
    sys.exit(0)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="CthulhuBotV2 Auto-Updater")
    parser.add_argument("pid", nargs='?', type=int, help="PID of the process to wait for")
    args = parser.parse_args()

    # 1. Wait
    if args.pid:
        wait_for_pid(args.pid)
        time.sleep(2) # Grace period

    # 2. Download
    download_update()

    # 3. Apply
    extract_and_apply()

    # 4. Dependencies
    update_dependencies()

    # 5. Restart
    restart_bot()
