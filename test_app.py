"""
End-to-end verification script for Zok application endpoints.
"""
from fastapi.testclient import TestClient
from api.index import app

client = TestClient(app)

def run_tests():
    print("Testing Zok Application Endpoints...")

    # 1. Landing
    r = client.get("/")
    assert r.status_code == 200, f"Landing failed: {r.status_code}"
    assert "ZOK" in r.text, "ZOK not in landing"
    print("[PASS] 1. Landing Page: PASS")

    # 2. Dr. Ayesha Edition
    r = client.get("/edition/ayesha")
    assert r.status_code == 200, f"Ayesha failed: {r.status_code}"
    assert "Dr. Ayesha" in r.text, "Ayesha name not in edition"
    assert "Three Things" in r.text, "Three Things not in edition"
    print("[PASS] 2. Dr. Ayesha Edition: PASS")

    # 3. Hamza Khan Edition
    r = client.get("/edition/hamza")
    assert r.status_code == 200, f"Hamza failed: {r.status_code}"
    assert "Hamza Khan" in r.text, "Hamza name not in edition"
    print("[PASS] 3. Hamza Khan Edition: PASS")

    # 4. Zara Ahmed Edition
    r = client.get("/edition/zara")
    assert r.status_code == 200, f"Zara failed: {r.status_code}"
    assert "Zara Ahmed" in r.text, "Zara name not in edition"
    print("[PASS] 4. Zara Ahmed Edition: PASS")

    # 5. PDF Download
    r = client.get("/edition/ayesha/pdf")
    assert r.status_code == 200, f"PDF failed: {r.status_code}"
    assert r.headers["content-type"] == "application/pdf", "Not PDF header"
    assert len(r.content) > 1000, "PDF content too short"
    print(f"[PASS] 5. Broadsheet PDF Generation: PASS ({len(r.content)} bytes)")

    # 6. Archive
    r = client.get("/archive/ayesha")
    assert r.status_code == 200, f"Archive failed: {r.status_code}"
    assert "Archive" in r.text, "Archive text missing"
    print("[PASS] 6. Archive Vault: PASS")

    # 7. Taste Profile
    r = client.get("/taste/ayesha")
    assert r.status_code == 200, f"Taste failed: {r.status_code}"
    assert "Taste Profile" in r.text, "Taste profile missing"
    print("[PASS] 7. Taste Profile: PASS")

    # 8. Simulate 7-Days
    r = client.get("/api/simulate/ayesha")
    assert r.status_code == 200, f"Simulate failed: {r.status_code}"
    data = r.json()
    assert "ndcg_scores" in data and len(data["ndcg_scores"]) == 7, "Simulation data error"
    print(f"[PASS] 8. Simulate 7-Days Learning API: PASS (NDCG: {data['ndcg_scores']})")

    # 9. Telemetry & Retention APIs
    r = client.post("/api/interact", json={"user_id": "ayesha", "article_id": "art-01", "dwell_time": 24.5, "scroll_depth": 0.9, "clicked_out": False, "saved": True})
    assert r.status_code == 200, f"Interact failed: {r.status_code}"
    r = client.post("/api/recall", json={"user_id": "ayesha", "edition_id": "ed-ayesha-today", "question": "Sample question", "correct": True})
    assert r.status_code == 200, f"Recall failed: {r.status_code}"
    print("[PASS] 9. Behavioral Telemetry & Retention APIs: PASS")

    # 10. Cognitive Onboarding Flow
    r = client.post("/onboard", data={"name": "Tariq Mehmood", "context": "Robotics engineer in Rawalpindi, passionate about autonomous drones", "reading_budget": 10}, follow_redirects=True)
    assert r.status_code == 200, f"Onboard failed: {r.status_code}"
    assert "Tariq Mehmood" in r.text, "New user name missing from edition"
    print("[PASS] 10. Cognitive Onboarding Flow: PASS")

    print("\nALL 10 TESTS PASSED! Ready for deployment and demonstration.")

if __name__ == "__main__":
    run_tests()
