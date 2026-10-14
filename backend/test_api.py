"""
VIDYA-X AI — API Integration Tests
Tests /api/health and /api/upload endpoints using FastAPI TestClient.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_health():
    print("Testing GET /api/health...")
    resp = client.get("/api/health")
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
    data = resp.json()
    assert data.get("status") == "ok", f"Expected status 'ok', got {data}"
    assert data.get("service") == "VIDYA-X AI Backend"
    print("  [OK] Health check returned:", data)

def test_liveness_and_readiness_probes():
    print("Testing GET /health (liveness)...")
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json().get("status") == "ok"

    print("Testing GET /health/ready (readiness)...")
    resp = client.get("/health/ready")
    assert resp.status_code in [200, 503]
    if resp.status_code == 200:
        assert resp.json().get("status") == "ready"
        assert resp.json().get("database") == "connected"
    else:
        assert resp.json().get("status") == "unhealthy"
        assert resp.json().get("database") == "disconnected"

    print("Testing GET /health/ai (diagnostics)...")
    resp = client.get("/health/ai")
    assert resp.status_code == 200
    assert resp.json().get("status") == "ok"
    assert "cloud_llm_ready" in resp.json()

def test_upload_unsupported():
    print("Testing POST /api/upload with unsupported file...")
    files = {"file": ("test.jpg", b"fake image bytes", "image/jpeg")}
    data = {"course_name": "Physics"}
    resp = client.post("/api/upload", files=files, data=data)
    assert resp.status_code == 400, f"Expected 400, got {resp.status_code}"
    res = resp.json()
    assert res.get("success") is False
    assert "Unsupported file type" in res.get("error", "")
    print("  [OK] Unsupported file rejected gracefully:", res.get("error"))

def test_upload_pdf():
    print("Testing POST /api/upload with valid PDF...")
    import fitz
    doc = fitz.open()
    p = doc.new_page()
    p.insert_text((50, 50), "Thermodynamics and Heat Engines", fontsize=14)
    pdf_bytes = doc.tobytes()
    doc.close()

    files = {"file": ("Thermodynamics.pdf", pdf_bytes, "application/pdf")}
    data = {"course_name": "Physics"}
    resp = client.post("/api/upload", files=files, data=data)
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    res = resp.json()
    assert res.get("success") is True
    assert res.get("source_type") == "pdf"
    assert res.get("units_extracted") == 1
    assert "file_" in res.get("file_id")
    print("  [OK] PDF uploaded and extracted successfully:", res)

if __name__ == "__main__":
    print("=== Running FastAPI Integration Tests ===")
    test_health()
    test_upload_unsupported()
    test_upload_pdf()
    print("=== ALL API TESTS PASSED! ===")
