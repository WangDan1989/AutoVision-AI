#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.parse
import urllib.request


def request_json(method: str, url: str, payload: dict | None = None) -> tuple[int, dict]:
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    with urllib.request.urlopen(req, timeout=10) as resp:
        body = resp.read().decode("utf-8")
        return resp.status, json.loads(body)


def print_ok(title: str, detail: str) -> None:
    print(f"[OK] {title}: {detail}")


def print_fail(title: str, detail: str) -> None:
    print(f"[FAIL] {title}: {detail}")


def expect(condition: bool, title: str, detail: str) -> None:
    if not condition:
        raise RuntimeError(f"{title}: {detail}")


def check_api_response(payload: dict, title: str) -> dict:
    expect(payload.get("code") == 0, title, f"返回 code={payload.get('code')}")
    expect(isinstance(payload.get("data"), dict), title, "返回 data 不是对象")
    return payload["data"]


def run(base_url: str) -> int:
    project_name = f"smoke-{int(time.time())}"
    print(f"目标服务: {base_url}")
    try:
        status, payload = request_json("GET", f"{base_url}/healthz")
        expect(status == 200, "健康检查", f"HTTP {status}")
        expect(payload.get("ok") is True, "健康检查", f"响应体为 {payload}")
        print_ok("健康检查", "/healthz 返回 ok=true")

        status, payload = request_json(
            "POST",
            f"{base_url}/api/projects",
            {
                "name": project_name,
                "description": "smoke test project",
                "aspect_ratio": "16:9",
                "target_width": 1280,
                "target_height": 720,
                "fps": 24,
            },
        )
        expect(status == 200, "创建项目", f"HTTP {status}")
        data = check_api_response(payload, "创建项目")
        project_id = str(data.get("id") or "")
        expect(project_id, "创建项目", f"返回数据缺少 id: {payload}")
        print_ok("创建项目", f"已创建 {project_id}")

        status, payload = request_json("GET", f"{base_url}/api/projects/{project_id}")
        expect(status == 200, "读取项目", f"HTTP {status}")
        data = check_api_response(payload, "读取项目")
        expect(data.get("name") == project_name, "读取项目", f"name 不匹配: {data.get('name')}")
        expect(isinstance(data.get("preferences"), dict), "读取项目", "preferences 缺失")
        print_ok("读取项目", "项目详情与默认偏好返回正常")

        status, payload = request_json(
            "PATCH",
            f"{base_url}/api/projects/{project_id}/preferences",
            {"export": {"subtitle_enabled": False, "transition_enabled": False}},
        )
        expect(status == 200, "更新偏好", f"HTTP {status}")
        data = check_api_response(payload, "更新偏好")
        export_prefs = data.get("preferences", {}).get("export", {})
        expect(export_prefs.get("subtitle_enabled") is False, "更新偏好", f"subtitle_enabled={export_prefs.get('subtitle_enabled')}")
        expect(export_prefs.get("transition_enabled") is False, "更新偏好", f"transition_enabled={export_prefs.get('transition_enabled')}")
        print_ok("更新偏好", "export patch 生效")

        project_query = urllib.parse.urlencode({"project_id": project_id})
        list_checks = [
            ("任务列表", f"{base_url}/api/tasks?{project_query}"),
            ("分镜列表", f"{base_url}/api/projects/{project_id}/segments"),
            ("资产列表", f"{base_url}/api/projects/{project_id}/assets"),
            ("首帧列表", f"{base_url}/api/projects/{project_id}/frames"),
            ("视频列表", f"{base_url}/api/projects/{project_id}/videos"),
            ("音频列表", f"{base_url}/api/projects/{project_id}/audio"),
            ("导出列表", f"{base_url}/api/projects/{project_id}/exports"),
        ]
        for title, url in list_checks:
            status, payload = request_json("GET", url)
            expect(status == 200, title, f"HTTP {status}")
            data = check_api_response(payload, title)
            expect(isinstance(data.get("items"), list), title, f"items 不是数组: {payload}")
            print_ok(title, f"接口可访问，当前 items={len(data['items'])}")

        print("\n结论: 最小 smoke test 已通过，后端基础接口链路正常。")
        return 0
    except Exception as exc:  # noqa: BLE001
        print_fail("Smoke Test", str(exc))
        print("\n结论: 最小 smoke test 未通过，请先修复以上阻断项。")
        return 1


def main() -> int:
    parser = argparse.ArgumentParser(description="AutoVision-AI backend minimal smoke test")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000", help="后端服务地址，默认 http://127.0.0.1:8000")
    args = parser.parse_args()
    return run(args.base_url.rstrip("/"))


if __name__ == "__main__":
    raise SystemExit(main())
