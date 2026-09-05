import sqlite3

DB_PATH = r"c:\Users\王丹\Documents\GitHub\AutoVision-AI\backend\autovision.db"
conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

cur.execute("PRAGMA table_info(task_queue)")
print("=== task_queue 列 ===")
for r in cur.fetchall():
    print(r)

cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
print("\n=== 所有表 ===")
for r in cur.fetchall():
    print(r[0])
