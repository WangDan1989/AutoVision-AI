#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import urllib.error
import urllib.request


def request_json(method: str, url: str, payload: dict | None = None) -> tuple[int, dict]:
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as resp:
        body = resp.read().decode("utf-8", errors="replace")
        return resp.status, json.loads(body) if body else {}


def request_json_allow_error(method: str, url: str, payload: dict | None = None) -> tuple[int, dict]:
    try:
        return request_json(method, url, payload)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(body) if body else {}
        except json.JSONDecodeError:
            parsed = {"detail": body}
        return exc.code, parsed


def print_ok(title: str, detail: str) -> None:
    print(f"[OK] {title}: {detail}")


def print_fail(title: str, detail: str) -> None:
    print(f"[FAIL] {title}: {detail}")


def expect_api_ok(status: int, payload: dict, title: str) -> dict:
    if status != 200:
        raise RuntimeError(f"{title}: HTTP {status} - {payload}")
    if payload.get("code") != 0:
        raise RuntimeError(f"{title}: code={payload.get('code')} payload={payload}")
    data = payload.get("data")
    if not isinstance(data, dict):
        raise RuntimeError(f"{title}: data 不是对象 - {payload}")
    return data


def list_projects(base_url: str) -> list[dict]:
    status, payload = request_json_allow_error("GET", f"{base_url}/api/projects")
    data = expect_api_ok(status, payload, "查询项目列表")
    items = data.get("items") or []
    if not isinstance(items, list):
        raise RuntimeError(f"查询项目列表: items 不是数组 - {payload}")
    return items


def cleanup_projects(base_url: str, prefixes: list[str], dry_run: bool, limit: int) -> int:
    print(f"目标服务: {base_url}")
    print(f"匹配前缀: {', '.join(prefixes)}")
    items = list_projects(base_url)
    matched = [
        item for item in items
        if isinstance(item, dict) and any(str(item.get("name") or "").startswith(prefix) for prefix in prefixes)
    ]
    if limit > 0:
        matched = matched[:limit]

    if not matched:
        print_ok("批量清理", "没有匹配到需要删除的测试项目")
        return 0

    print_ok("批量清理", f"共匹配到 {len(matched)} 个项目")
    for item in matched:
        print(f" - {item.get('name')} ({item.get('id')})")

    if dry_run:
        print("\n结论: 当前为 dry-run，仅展示匹配结果，未执行删除。")
        return 0

    deleted_count = 0
    failed_count = 0
    for item in matched:
        project_id = str(item.get("id") or "")
        project_name = str(item.get("name") or project_id)
        status, payload = request_json_allow_error("DELETE", f"{base_url}/api/projects/{project_id}")
        if status == 200 and payload.get("code") == 0:
            deleted_files = payload.get("data", {}).get("deleted_files", 0)
            print_ok("删除项目", f"{project_name} 已删除，清理文件数 {deleted_files}")
            deleted_count += 1
        else:
            print_fail("删除项目", f"{project_name} 删除失败: HTTP {status} - {payload}")
            failed_count += 1

    if failed_count:
        print(f"\n结论: 批量清理完成，成功 {deleted_count} 个，失败 {failed_count} 个。")
        return 1
    print(f"\n结论: 批量清理完成，共删除 {deleted_count} 个测试项目。")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Cleanup test projects by prefix")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000", help="后端服务地址，默认 http://127.0.0.1:8000")
    parser.add_argument(
        "--prefix",
        action="append",
        dest="prefixes",
        help="按项目前缀匹配，可重复传入；默认清理 smoke 和 pipeline-smoke",
    )
    parser.add_argument("--dry-run", action="store_true", help="仅展示匹配到的项目，不实际删除")
    parser.add_argument("--limit", type=int, default=0, help="最多清理多少个项目，0 表示不限")
    args = parser.parse_args()
    prefixes = [item.strip() for item in (args.prefixes or ["smoke", "pipeline-smoke"]) if item and item.strip()]
    if not prefixes:
        raise SystemExit("至少需要一个有效前缀")
    return cleanup_projects(args.base_url.rstrip("/"), prefixes, args.dry_run, max(0, args.limit))


if __name__ == "__main__":
    raise SystemExit(main())
