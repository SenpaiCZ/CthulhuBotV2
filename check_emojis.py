import sqlite3
import os

db_path = 'data/database.sqlite'
if not os.path.exists(db_path):
    print(f"{db_path} not found")
    exit(1)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()
cursor.execute("SELECT category, key, value FROM global_emojis WHERE category='System'")
rows = cursor.fetchall()
for r in rows:
    print(r)
conn.close()
