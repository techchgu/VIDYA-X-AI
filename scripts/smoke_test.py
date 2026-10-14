"""
VIDYA-X AI — Deployment Smoke Test Suite (Step 16)
Non-destructive health and integration verification designed to run against
either a live deployed server (HTTPS/HTTP) or a local ASGI instance.

Verifies:
  1. /health liveness probe returns HTTP 200 and version info.
  2. /health/ready readiness probe confirms database connectivity.
  3. /health/ai reports model provider status without leaking secrets.
  4. /api/dashboard/summary handles default/demo student queries cleanly.
  5. /api/tutor/ask produces grounded response with citations on demo content.
  6. /api/tutor/ask safely abstains on out-of-domain query.
  7. /api/courses/{course_id}/visuals responds without filesystem path leakage.
"""

import sys
import os
import json
import urllib.request
import urllib.error

# Target host: command-line arg, or environment variable, or default localhost:8000
TARGET_URL = sys.argv[1] if len(sys.argv) > 1 else os.getenv("SMOKE_TARGET_URL", "http://localhost:8000")
TARGET_URL = TARGET_URL.rstrip("/")


def log_result(test_name: str, passed: bool, detail: str = ""):
    badge = "[PASS]" if passed else "[FAIL]"
    print(f"  {badge}  {test_name} {f'— {detail}' if detail else ''}")


def request_json(path: str, method: str = "GET", payload: dict = None):
    url = f"{TARGET_URL}{path}"
    headers = {"Accept": "application/json"}
    data = None
    if payload is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(payload).encode("utf-8")

    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = resp.read().decode("utf-8")
            return resp.status, json.loads(body)
    except urllib.error.HTTPError as err:
        try:
            body = err.read().decode("utf-8")
            return err.code, json.loads(body)
        except Exception:
            return err.code, {"error": err.reason}
    except Exception as exc:
        return 0, {"error": str(exc)}


def run_smoke_tests():
    print("=" * 65)
    print(f"  VIDYA-X AI — Production Smoke Tests")
    print(f"  Target: {TARGET_URL}")
    print("=" * 65)

    passed_count = 0
    total_count = 7

    # 1. Health Probe
    status, body = request_json("/health")
    test1 = status == 200 and body.get("status") == "ok"
    log_result("1. Liveness Probe (/health)", test1, f"version={body.get('version')}")
    if test1: passed_count += 1

    # 2. Readiness Probe
    status, body = request_json("/health/ready")
    test2 = status == 200 and body.get("status") == "ready" and body.get("database") == "connected"
    log_result("2. Readiness Probe (/health/ready)", test2, f"db={body.get('database')}")
    if test2: passed_count += 1

    # 3. AI Diagnostics Probe
    status, body = request_json("/health/ai")
    test3 = status == 200 and "embedding_provider" in body and "vision_provider" in body
    # Confirm no keys were leaked
    no_leaks = "key" not in "".join(str(v).lower() for v in body.values())
    log_result("3. AI Provider Diagnostic (/health/ai)", test3 and no_leaks, f"llm_ready={body.get('cloud_llm_ready')}")
    if test3 and no_leaks: passed_count += 1

    # 4. Dashboard Summary
    status, body = request_json("/api/dashboard/summary?student_id=student_demo&course_id=course_demo_physics")
    test4 = status == 200 and body.get("success") is True and "materials_count" in body
    log_result("4. Dashboard Summary API", test4, f"chunks={body.get('chunks_count', 0)}")
    if test4: passed_count += 1

    # 5. Tutor Grounded Query
    tutor_payload = {
        "course_id": "course_demo_physics",
        "question": "What is Newton's Second Law relating force, mass, and acceleration?",
        "student_id": "student_demo",
    }
    status, body = request_json("/api/tutor/ask", method="POST", payload=tutor_payload)
    test5 = status == 200 and body.get("success") is True and body.get("supported") is True and len(body.get("citations", [])) > 0
    log_result("5. Grounded AI Tutor Response with Citations", test5, f"citations={len(body.get('citations', []))}")
    if test5: passed_count += 1

    # 6. Tutor Safe Abstention
    abstention_payload = {
        "course_id": "course_demo_physics",
        "question": "What is the biological pathway of photosynthesis in chloroplasts?",
        "student_id": "student_demo",
    }
    status, body = request_json("/api/tutor/ask", method="POST", payload=abstention_payload)
    test6 = status == 200 and body.get("success") is True and body.get("supported") is False and len(body.get("citations", [])) == 0
    log_result("6. Safe Abstention on Out-of-Domain Query", test6, "abstained correctly")
    if test6: passed_count += 1

    # 7. Visual Assets Security & Masking
    status, body = request_json("/api/courses/course_demo_physics/visuals?page_size=5")
    test7 = status == 200 and body.get("success") is True
    # Confirm image_path is never exposed in asset list
    no_path_leak = True
    for asset in body.get("assets", []):
        if "image_path" in asset:
            no_path_leak = False
            break
    log_result("7. Visual Assets Course API & Path Masking", test7 and no_path_leak, f"assets_found={body.get('total', 0)}")
    if test7 and no_path_leak: passed_count += 1

    print("-" * 65)
    print(f"  Summary: {passed_count}/{total_count} smoke tests passed")
    print("=" * 65)

    return passed_count == total_count


if __name__ == "__main__":
    success = run_smoke_tests()
    sys.exit(0 if success else 1)
