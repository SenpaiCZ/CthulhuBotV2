import os
import datetime


def get_system_backups(backup_folder: str) -> list[dict]:
    if not os.path.exists(backup_folder):
        return []

    files = []
    try:
        for f in os.listdir(backup_folder):
            if f.endswith('.zip'):
                full_path = os.path.join(backup_folder, f)
                stat = os.stat(full_path)
                files.append({
                    "name": f,
                    "size": stat.st_size,
                    "created": datetime.datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
                })
        files.sort(key=lambda x: x['created'], reverse=True)
    except Exception as e:
        print(f"Error scanning backups: {e}")

    return files
