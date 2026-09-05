import sqlite3

DB_PATH = r"c:\Users\王丹\Documents\GitHub\AutoVision-AI\backend\autovision.db"
conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

cur.execute("SELECT id, task_type, status, error_code, error_message, entity_id, created_at FROM task_queue ORDER BY created_at DESC LIMIT 15")
rows = cur.fetchall()
print("=== task_queue 最近 15 条 ===")
for r in rows:
    print("---")
    for k in ["id", "task_type", "status", "error_code", "entity_id", "created_at"]:
        print(f"  {k}: {r[k]}")
    em = r["error_message"]
    if em:
        print(f"  error_message: {em[:1500]}")
        if len(em) > 1500:
            print(f"  ...[truncated, total {len(em)} chars]")
