import os
import time

SOUNDBOARD_FOLDER = "soundboard"
BACKUP_FOLDER = "backups"
IMAGES_FOLDER = "images"
FONTS_FOLDER = os.path.join("data", "fonts")
OLD_FONTS_FOLDER = os.path.join("dashboard", "static", "fonts")
server_volumes = {} # guild_id (str) -> {'music': 1.0, 'soundboard': 0.5}
guild_mixers = {} # guild_id (str) -> MixingAudioSource
_failed_login_attempts = {} # ip (str) -> [timestamp, ...]

BASIC_FONTS = [
    "Arial", "Verdana", "Helvetica", "Tahoma", "Trebuchet MS", "Times New Roman",
    "Georgia", "Garamond", "Courier New", "Brush Script MT"
]

_APP_START = time.monotonic()

_PUBLIC_API = {'/api/status'}

MORSE_CODE_MAP = {
    'A': '.-', 'B': '-...', 'C': '-.-.', 'D': '-..', 'E': '.', 'F': '..-.',
    'G': '--.', 'H': '....', 'I': '..', 'J': '.---', 'K': '-.-', 'L': '.-..',
    'M': '--', 'N': '-.', 'O': '---', 'P': '.--.', 'Q': '--.-', 'R': '.-.',
    'S': '...', 'T': '-', 'U': '..-', 'V': '...-', 'W': '.--', 'X': '-..-',
    'Y': '-.--', 'Z': '--..',
    '1': '.----', '2': '..---', '3': '...--', '4': '....-', '5': '.....',
    '6': '-....', '7': '--...', '8': '---..', '9': '----.', '0': '-----',
    ',': '--..--', "'": '.----.',
    '/': '-..-.', '(': '-.--.', ')': '-.--.-', '&': '.-...', ':': '---...',
    ';': '-.-.-.', '=': '-...-', '+': '.-.-.', '-': '-....-', '_': '..--.-',
    '"': '.-..-.', '$': '...-..-', '@': '.--.-.'
}
