import sqlite3

DB_PATH = r"c:\Users\王丹\Documents\GitHub\AutoVision-AI\backend\autovision.db"
conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

pid = "9fa70d64af3c4ea49d06d6c43c3b8e48"

print("=== projects.current_step_unlock:")
cur.execute("SELECT id, name, status, current_step_unlock FROM projects WHERE id=?", (pid,))
print(dict(cur.fetchone()))

print("\n=== storyboard_frames 全部 6 条 is_locked 状态:")
cur.execute("SELECT segment_id, frame_type, version_no, is_locked, status, created_at FROM storyboard_frames WHERE project_id=? ORDER BY created_at", (pid,))
rows = cur.fetchall()
for r in rows:
    print(f"  seg={r['segment_id'][:8]} ver={r['version_no']} locked={r['is_locked']} status={r['status']} type={r['frame_type']}")

print(f"\n共 {len(rows)} 条 frames，其中锁定数：{sum(1 for r in rows if r['is_locked']==1)}")

print("\n=== script_segments 6 个镜头：")
cur.execute("SELECT id, segment_no, segment_name FROM script_segments WHERE project_id=? ORDER BY segment_no", (pid,))
for r in cur.fetchall():
    print(f"  #{r['segment_no']} {dict(r)['id'][:8]}... {r['segment_name']}")
