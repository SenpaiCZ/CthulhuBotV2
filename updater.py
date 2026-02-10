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
import datetime

# Configuration
REPO_URL = "https://github.com/SenpaiCZ/CthulhuBotV2/archive/refs/heads/master.zip"
ZIP_FILENAME = "update_pkg.zip"
EXTRACT_DIR = "update_extract_temp"
BACKUP_DIR = "backups"  # Must match BACKUP_FOLDER in dashboard/app.py

# Folders/Files to completely ignore during sync/copy/backup
# These are things we don't want to backup (too big/irrelevant) AND don't want to delete/overwrite
PROTECTED_DIRS = {
    "venv", ".git", "__pycache__", "soundboard", "backups",
    ".vscode", ".idea", "node_modules", "infodata", "data",
    EXTRACT_DIR
}

# Files in the root directory to never delete or overwrite
PROTECTED_FILES = {
    "config.json", ZIP_FILENAME, "updater.py.old", "update_temp_script.ps1"
}

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
        if platform.system() == "Windows":
            time.sleep(5)
        else:
            while os.path.exists(f"/proc/{pid}"):
                time.sleep(1)
    log("Process exited.")

def cleanup_old_updater():
    """Removes updater.py.old if it exists."""
    if os.path.exists("updater.py.old"):
        try:
            os.remove("updater.py.old")
            log("Removed old updater script.")
        except Exception as e:
            log(f"Could not remove updater.py.old: {e}")

def create_backup():
    log("Creating backup...")
    if not os.path.exists(BACKUP_DIR):
        os.makedirs(BACKUP_DIR)

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    temp_backup_dir = os.path.join(BACKUP_DIR, f"temp_{timestamp}")
    backup_zip = os.path.join(BACKUP_DIR, f"backup_{timestamp}.zip")

    try:
        # Copy files to temp dir
        shutil.copytree(".", temp_backup_dir, ignore=shutil.ignore_patterns(
            *PROTECTED_DIRS, ZIP_FILENAME, "*.log", "*.pyc", "__pycache__", EXTRACT_DIR
        ))

        # Zip it
        shutil.make_archive(os.path.splitext(backup_zip)[0], 'zip', temp_backup_dir)
        log(f"Backup saved to: {backup_zip}")

    except Exception as e:
        log(f"Backup failed: {e}")
        # Continue anyway? Or stop? usually continue with warning
    finally:
        if os.path.exists(temp_backup_dir):
            shutil.rmtree(temp_backup_dir)

def download_update():
    log(f"Downloading update from {REPO_URL}...")
    try:
        urllib.request.urlretrieve(REPO_URL, ZIP_FILENAME)
        log("Download complete.")
    except Exception as e:
        log(f"Download failed: {e}")
        sys.exit(1)

def sync_files(source_root, target_root):
    """
    Deletes files in target_root that are not in source_root,
    unless they are protected.
    """
    log("Synchronizing files (removing obsolete files)...")

    for root, dirs, files in os.walk(target_root):
        rel_path = os.path.relpath(root, target_root)

        # Skip protected directories
        path_parts = rel_path.split(os.sep)
        if any(p in PROTECTED_DIRS for p in path_parts):
            continue

        # Explicitly protect BACKUP_DIR and EXTRACT_DIR regardless of PROTECTED_DIRS set
        # This prevents accidental deletion if they are missing from PROTECTED_DIRS
        if rel_path == BACKUP_DIR or rel_path.startswith(BACKUP_DIR + os.sep):
            continue
        if rel_path == EXTRACT_DIR or rel_path.startswith(EXTRACT_DIR + os.sep):
            continue

        # Filter dirs traversal
        if rel_path == ".":
            dirs[:] = [d for d in dirs if d not in PROTECTED_DIRS and d != BACKUP_DIR and d != EXTRACT_DIR]

        # Check files
        for file in files:
            if rel_path == "." and file in PROTECTED_FILES:
                continue

            # Check if this file exists in source
            source_file_path = os.path.join(source_root, rel_path, file)
            if not os.path.exists(source_file_path):
                target_file_path = os.path.join(root, file)
                try:
                    os.remove(target_file_path)
                    log(f"Deleted obsolete file: {target_file_path}")
                except Exception as e:
                    log(f"Failed to delete {target_file_path}: {e}")

def update_self_in_place(src_path, dest_path):
    """
    Updates the running script by renaming the current one to .old
    and moving the new one to .py
    """
    try:
        if os.path.exists(dest_path):
            old_path = dest_path + ".old"
            if os.path.exists(old_path):
                os.remove(old_path)
            os.rename(dest_path, old_path)

        shutil.copy2(src_path, dest_path)
        log(f"Updated {os.path.basename(dest_path)} successfully.")
    except Exception as e:
        log(f"Failed to self-update {os.path.basename(dest_path)}: {e}")

def extract_and_apply():
    log("Extracting update...")
    try:
        with zipfile.ZipFile(ZIP_FILENAME, 'r') as zip_ref:
            zip_ref.extractall(EXTRACT_DIR)

        entries = os.listdir(EXTRACT_DIR)
        if not entries:
            raise Exception("Empty zip file")

        extracted_root = os.path.join(EXTRACT_DIR, entries[0])

        log(f"Applying updates from {extracted_root}...")

        # 1. Sync (Delete obsolete files)
        sync_files(extracted_root, ".")

        # 2. Copy/Overwrite new files
        for root, dirs, files in os.walk(extracted_root):
            rel_path = os.path.relpath(root, extracted_root)
            dest_dir = os.path.join(".", rel_path)

            if rel_path == ".":
                dirs[:] = [d for d in dirs if d not in PROTECTED_DIRS]

            if rel_path != "." and not os.path.exists(dest_dir):
                os.makedirs(dest_dir, exist_ok=True)

            for file in files:
                src_file = os.path.join(root, file)
                dest_file = os.path.join(dest_dir, file)

                if rel_path == "." and file in PROTECTED_FILES:
                    continue

                if rel_path == "." and file == "updater.py":
                    update_self_in_place(src_file, dest_file)
                    continue

                try:
                    shutil.copy2(src_file, dest_file)
                except Exception as e:
                    log(f"Failed to copy {file}: {e}")

        log("Update applied successfully.")

    except Exception as e:
        log(f"Extraction failed: {e}")
        sys.exit(1)
    finally:
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

def restart_bot(detached=True):
    if detached:
        log("Restarting bot (detached)...")
        cmd = [sys.executable, "bot.py"]
        if platform.system() == "Windows":
            flags = subprocess.CREATE_NEW_CONSOLE
            subprocess.Popen(cmd, creationflags=flags)
        else:
            subprocess.Popen(cmd, close_fds=True)
        log("Bot restarted. Exiting updater.")
        sys.exit(0)
    else:
        log("Restarting bot (foreground)...")
        # Just return, let the calling script handle it?
        # Or exec?
        # If we return, the calling script (e.g. update.bat) can continue.
        pass

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="CthulhuBotV2 Auto-Updater")
    parser.add_argument("pid", nargs='?', type=int, help="PID of the process to wait for")
    parser.add_argument("--no-restart", action="store_true", help="Do not restart the bot automatically")
    parser.add_argument("--no-backup", action="store_true", help="Skip backup")
    args = parser.parse_args()

    # 0. Cleanup old updater if exists
    cleanup_old_updater()

    # 1. Wait
    if args.pid:
        wait_for_pid(args.pid)
        time.sleep(2)

    # 2. Backup
    if not args.no_backup:
        create_backup()

    # 3. Download
    download_update()

    # 4. Apply (Sync + Update)
    extract_and_apply()

    # 5. Dependencies
    update_dependencies()

    # 6. Restart
    if not args.no_restart:
        restart_bot(detached=True)
    else:
        log("Update finished. Please restart the bot manually.")
