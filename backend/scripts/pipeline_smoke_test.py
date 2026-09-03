#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.request


STAGE_ORDER = ["project", "step1", "step2", "step3", "step4", "step5"]
DEFAULT_SCRIPT_TEXT = """
夜晚的城市天桥上，年轻女孩望着远处霓虹，轻声说“我一定要找到他”。
镜头切到街角便利店，男主低头整理货架，听见门铃响起后抬头。
女孩推门而入，两人四目相对，空气短暂停滞。
""".strip()


def print_ok(title: str, detail: str) -> None:
    print(f"[OK] {title}: {detail}")


def print_fail(title: str, detail: str) -> None:
    print(f"[FAIL] {title}: {detail}")


def request_json(method: str, url: str, payload: dict | None = None) -> tuple[int, dict]:
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    with urllib.request.urlopen(req, timeout=60) as resp:
        body = resp.read().decode("utf-8", errors="replace")
        return resp.status, json.loads(body) if body else {}


def request_json_allow_error(method: str, url: str, payload: dict | None = None) -> tuple[int, dict]:
    try:
        return request_json(method, url, payload)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        try:
            payload = json.loads(body) if body else {}
        except json.JSONDecodeError:
            payload = {"detail": body}
        return exc.code, payload


def expect_api_ok(status: int, payload: dict, title: str) -> dict:
    if status != 200:
        raise RuntimeError(f"{title}: HTTP {status} - {payload}")
    if payload.get("code") != 0:
        raise RuntimeError(f"{title}: code={payload.get('code')} payload={payload}")
    data = payload.get("data")
    if not isinstance(data, dict):
        raise RuntimeError(f"{title}: data 不是对象 - {payload}")
    return data


def should_run(current_stage: str, target_stage: str) -> bool:
    return STAGE_ORDER.index(current_stage) <= STAGE_ORDER.index(target_stage)


def latest_item(items: list[dict], key: str = "updated_at") -> dict | None:
    if not items:
        return None
    return sorted(items, key=lambda item: str(item.get(key) or ""), reverse=True)[0]


def try_cleanup_project(base_url: str, project_id: str) -> None:
    if not project_id:
        return
    status, payload = request_json_allow_error("DELETE", f"{base_url}/api/projects/{project_id}")
    if status == 200 and payload.get("code") == 0:
        deleted_files = payload.get("data", {}).get("deleted_files", 0)
        print_ok("清理测试项目", f"已删除 {project_id}，清理文件数 {deleted_files}")
    else:
        print_fail("清理测试项目", f"删除 {project_id} 失败: HTTP {status} - {payload}")


def run(base_url: str, through: str, script_text: str, prefix: str, cleanup: bool) -> int:
    print(f"目标服务: {base_url}")
    print(f"目标阶段: {through}")
    project_id = ""
    first_segment_id = ""
    first_frame_id = ""
    try:
        status, payload = request_json_allow_error("GET", f"{base_url}/healthz")
        if status != 200 or payload.get("ok") is not True:
            raise RuntimeError(f"健康检查失败: HTTP {status} - {payload}")
        print_ok("健康检查", "/healthz 返回 ok=true")

        project_name = f"{prefix}-{int(time.time())}"
        status, payload = request_json_allow_error(
            "POST",
            f"{base_url}/api/projects",
            {
                "name": project_name,
                "description": "pipeline smoke test project",
                "aspect_ratio": "16:9",
                "target_width": 1280,
                "target_height": 720,
                "fps": 24,
            },
        )
        data = expect_api_ok(status, payload, "创建项目")
        project_id = str(data.get("id") or "")
        if not project_id:
            raise RuntimeError(f"创建项目: 返回数据缺少 id - {payload}")
        print_ok("创建项目", f"已创建 {project_id}")

        if not should_run("step1", through):
            print("\n结论: project 阶段 smoke test 已通过。")
            return 0

        status, payload = request_json_allow_error(
            "POST",
            f"{base_url}/api/projects/{project_id}/script/parse",
            {"raw_script_text": script_text},
        )
        data = expect_api_ok(status, payload, "Step 1 剧本拆解")
        segments = data.get("segments") or []
        if not isinstance(segments, list) or not segments:
            raise RuntimeError(f"Step 1 剧本拆解: 返回 segments 为空 - {payload}")
        first_segment_id = str(segments[0].get("id") or "")
        if not first_segment_id:
            status, payload = request_json_allow_error("GET", f"{base_url}/api/projects/{project_id}/segments")
            list_data = expect_api_ok(status, payload, "查询分镜列表")
            segment_items = list_data.get("items") or []
            if not segment_items:
                raise RuntimeError("查询分镜列表: 当前没有可用分镜")
            first_segment_id = str(segment_items[0].get("id") or "")
        print_ok("Step 1 剧本拆解", f"已生成分镜数 {len(segments)}，首个分镜 {first_segment_id}")

        if not should_run("step2", through):
            print("\n结论: Step 1 smoke test 已通过。")
            return 0

        status, payload = request_json_allow_error("POST", f"{base_url}/api/projects/{project_id}/assets/rebuild")
        data = expect_api_ok(status, payload, "Step 2 资产重建")
        print_ok("Step 2 资产重建", f"已完成，count={data.get('count', 0)}")

        if not should_run("step3", through):
            print("\n结论: Step 2 smoke test 已通过。")
            return 0

        status, payload = request_json_allow_error(
            "POST",
            f"{base_url}/api/segments/{first_segment_id}/frames/generate",
            {
                "prompt_override": "",
                "negative_prompt_override": "",
                "width": 1280,
                "height": 720,
            },
        )
        data = expect_api_ok(status, payload, "Step 3 首帧生成")
        first_frame_id = str(data.get("frame_id") or "")
        if not first_frame_id:
            status, payload = request_json_allow_error("GET", f"{base_url}/api/projects/{project_id}/frames")
            list_data = expect_api_ok(status, payload, "查询首帧列表")
            frame = latest_item(list_data.get("items") or [])
            first_frame_id = str((frame or {}).get("id") or "")
        if not first_frame_id:
            raise RuntimeError("Step 3 首帧生成: 未获取到 frame_id")
        print_ok("Step 3 首帧生成", f"已生成 frame_id={first_frame_id}")

        status, payload = request_json_allow_error(
            "POST",
            f"{base_url}/api/frames/{first_frame_id}/lock",
            {"is_locked": True},
        )
        data = expect_api_ok(status, payload, "Step 3 锁帧")
        if data.get("is_locked") is not True:
            raise RuntimeError(f"Step 3 锁帧: 返回 is_locked={data.get('is_locked')}")
        print_ok("Step 3 锁帧", f"已锁定 frame_id={first_frame_id}")

        if not should_run("step4", through):
            print("\n结论: Step 3 smoke test 已通过。")
            return 0

        status, payload = request_json_allow_error(
            "POST",
            f"{base_url}/api/segments/{first_segment_id}/videos/generate",
            {
                "duration_sec": 3,
                "fps": 24,
                "width": 1280,
                "height": 720,
            },
        )
        data = expect_api_ok(status, payload, "Step 4 视频生成")
        print_ok("Step 4 视频生成", f"已生成 video_clip_id={data.get('video_clip_id')}")

        status, payload = request_json_allow_error(
            "POST",
            f"{base_url}/api/segments/{first_segment_id}/audio/generate",
            {
                "track_type": "NARRATION",
                "voice_profile": "",
                "text_content": "这是一次最小流水线联调音频测试。",
            },
        )
        data = expect_api_ok(status, payload, "Step 4 音频生成")
        print_ok("Step 4 音频生成", f"已生成 audio_track_id={data.get('audio_track_id')}")

        if not should_run("step5", through):
            print("\n结论: Step 4 smoke test 已通过。")
            return 0

        status, payload = request_json_allow_error(
            "POST",
            f"{base_url}/api/projects/{project_id}/exports/generate",
            {
                "subtitle_enabled": False,
                "transition_enabled": False,
                "subtitle_items": [],
            },
        )
        data = expect_api_ok(status, payload, "Step 5 成片导出")
        print_ok("Step 5 成片导出", f"已生成 export_job_id={data.get('export_job_id')}")

        print("\n结论: 最小真实流水线 smoke test 已通过。")
        return 0
    except Exception as exc:  # noqa: BLE001
        print_fail("Pipeline Smoke Test", str(exc))
        if project_id:
            print(f"已创建测试项目: {project_id}")
        print("\n结论: 最小真实流水线 smoke test 未通过，请先修复当前阶段的阻断项。")
        return 1
    finally:
        if cleanup and project_id:
            try_cleanup_project(base_url, project_id)


def main() -> int:
    parser = argparse.ArgumentParser(description="AutoVision-AI pipeline smoke test")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000", help="后端服务地址，默认 http://127.0.0.1:8000")
    parser.add_argument(
        "--through",
        choices=STAGE_ORDER,
        default="step1",
        help="测试到哪个阶段，默认 step1，可选 project/step1/step2/step3/step4/step5",
    )
    parser.add_argument(
        "--script-text",
        default=DEFAULT_SCRIPT_TEXT,
        help="Step 1 使用的测试剧本文本",
    )
    parser.add_argument("--prefix", default="pipeline-smoke", help="测试项目名前缀，默认 pipeline-smoke")
    parser.add_argument("--cleanup", action="store_true", help="测试结束后自动删除测试项目")
    parser.add_argument("--keep-project", action="store_true", help="即使指定 --cleanup 也保留测试项目")
    args = parser.parse_args()
    cleanup = bool(args.cleanup and not args.keep_project)
    return run(
        args.base_url.rstrip("/"),
        args.through,
        args.script_text,
        args.prefix.strip() or "pipeline-smoke",
        cleanup,
    )


if __name__ == "__main__":
    raise SystemExit(main())
