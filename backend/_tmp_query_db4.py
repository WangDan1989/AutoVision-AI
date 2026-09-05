import sqlite3

DB_PATH = r"c:\Users\王丹\Documents\GitHub\AutoVision-AI\backend\autovision.db"
conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

cur.execute("PRAGMA table_info(storyboard_frames)")
print("=== storyboard_frames 列 ===")
for r in cur.fetchall():
    print(r)

cur.execute("SELECT * FROM storyboard_frames ORDER BY created_at DESC LIMIT 1")
row = cur.fetchone()
print("\n=== 最新 1 条 frame ===")
cols = [d[0] for d in cur.description]
for k, v in zip(cols, row):
    sv = str(v)
    if len(sv) > 200:
        sv = sv[:200] + "..."
    print(f"  {k}: {sv}")
