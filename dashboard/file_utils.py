import os
import shutil
import zipfile
import re
import logging

logger = logging.getLogger("dashboard.file_utils")

ALLOWED_IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.webp'}
ALLOWED_AUDIO_EXTENSIONS = {'.mp3', '.wav', '.ogg', '.m4a', '.flac'}

def sanitize_filename(filename):
    """Sanitizes a filename to ensure it is safe for the filesystem."""
    # Keep only alphanumeric, dot, dash, underscore
    clean = re.sub(r'[^a-zA-Z0-9_.-]', '_', filename)
    # Remove leading/trailing dots/spaces
    clean = clean.strip('. ')
    return clean or 'unnamed'

def sync_get_soundboard_files(soundboard_folder):
    """Synchronously retrieves the soundboard file structure."""
    structure = {}
    if not os.path.exists(soundboard_folder):
        return structure

    # Level 1: Root files
    root_files = []
    # Level 2: Subdirectories
    folders = {}

    try:
        for entry in sorted(os.listdir(soundboard_folder)):
            entry_path = os.path.join(soundboard_folder, entry)

            if os.path.isfile(entry_path):
                 if os.path.splitext(entry)[1].lower() in ALLOWED_AUDIO_EXTENSIONS:
                    root_files.append({"name": entry, "path": entry})
            elif os.path.isdir(entry_path):
                folder_files = []
                for f in sorted(os.listdir(entry_path)):
                    f_path = os.path.join(entry_path, f)
                    if os.path.isfile(f_path) and os.path.splitext(f)[1].lower() in ALLOWED_AUDIO_EXTENSIONS:
                        folder_files.append({"name": f, "path": os.path.join(entry, f).replace('\\', '/')})
                if folder_files:
                    folders[entry] = folder_files

        if root_files:
            structure["Root"] = root_files

        # Sort folders by name and merge
        for k in sorted(folders.keys()):
            structure[k] = folders[k]
    except Exception as e:
        logger.error(f"Error scanning soundboard: {e}")

    return structure

def sync_save_bytes(file_bytes, target_path):
    """Synchronously saves bytes to the target path."""
    try:
        with open(target_path, 'wb') as f:
            f.write(file_bytes)
        return True, None
    except Exception as e:
        logger.error(f"Error saving bytes to {target_path}: {e}")
        return False, str(e)

def sync_extract_zip(zip_path, extract_dir):
    """Synchronously extracts audio files from a zip archive."""
    results = []
    try:
        if not os.path.exists(extract_dir):
            os.makedirs(extract_dir)

        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            for member in zip_ref.namelist():
                # Skip directories
                if member.endswith('/'): continue

                # Get basename to flatten structure
                base_name = os.path.basename(member)
                if not base_name: continue

                m_ext = os.path.splitext(base_name)[1].lower()
                if m_ext in ALLOWED_AUDIO_EXTENSIONS:
                    target_file = os.path.join(extract_dir, sanitize_filename(base_name))
                    with zip_ref.open(member) as source, open(target_file, 'wb') as target:
                        shutil.copyfileobj(source, target)
                    results.append(f"Extracted {base_name}")

        return True, results
    except Exception as e:
        logger.error(f"Error extracting zip {zip_path}: {e}")
        return False, [str(e)]

def sync_delete_path(path):
    """Synchronously deletes a file or directory."""
    try:
        if os.path.isfile(path):
            os.remove(path)
        elif os.path.isdir(path):
            shutil.rmtree(path)
        else:
            return False, "Path not found"
        return True, None
    except Exception as e:
        logger.error(f"Error deleting {path}: {e}")
        return False, str(e)

def sync_rename_path(old_path, new_path):
    """Synchronously renames a file or directory."""
    try:
        os.rename(old_path, new_path)
        return True, None
    except Exception as e:
        logger.error(f"Error renaming {old_path} to {new_path}: {e}")
        return False, str(e)

def sync_create_directory(path):
    """Synchronously creates a directory."""
    try:
        os.makedirs(path)
        return True, None
    except Exception as e:
        logger.error(f"Error creating directory {path}: {e}")
        return False, str(e)
