import sqlite3

DB_PATH = r"c:\Users\王丹\Documents\GitHub\AutoVision-AI\backend\autovision.db"
conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

# 查 task_queue 最新
cur.execute("SELECT id, task_type, status, error_code, entity_id, created_at, finished_at FROM task_queue ORDER BY created_at DESC LIMIT 5")
print("=== task_queue 最近 5 条 ===")
for r in cur.fetchall():
    print("---")
    for k in ["id", "task_type", "status", "error_code", "entity_id", "created_at", "finished_at"]:
        print(f"  {k}: {r[k]}")
    em = cur.execute("SELECT error_message FROM task_queue WHERE id=?", (r["id"],)).fetchone()["error_message"]
    if em:
        print(f"  error_message: {em[:800]}")
        if len(em) > 800:
            print(f"  ...[truncated {len(em)}]")

print()
# 查 storyboard_frames
cur.execute("SELECT COUNT(*) AS cnt FROM storyboard_frames WHERE project_id='9fa70d64af3c4ea49d06d6c43c3b8e48'")
n = cur.fetchone()["cnt"]
print(f"=== storyboard_frames: project 9fa7.. 有 {n} 条记录 ===")
if n > 0:
    cur.execute("SELECT id, segment_id, frame_type, image_url, is_locked, created_at FROM storyboard_frames ORDER BY created_at DESC LIMIT 3")
    for r in cur.fetchall():
        print(dict(r))

print()
# 查 projects 的 current_step_unlock
cur.execute("SELECT id, name, status, current_step_unlock FROM projects WHERE id='9fa70d64af3c4ea49d06d6c43c3b8e48'")
p = cur.fetchone()
print(f"=== project ===")
print(dict(p))
