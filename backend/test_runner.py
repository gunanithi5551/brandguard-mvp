"""
Autonomous End-to-End Test Runner for BrandGuard AI.
Pings POST http://localhost:8000/api/review and validates the 200 OK response and JSON schema.
"""
import json
import sys
import requests

API_URL = "http://localhost:8000/api/review"
TEST_PAYLOAD = {"content": "We guarantee a 100% ROI for our customers!"}
REQUIRED_KEYS = {"status", "broken_rule", "explanation", "suggestion"}


def main() -> int:
    print(f"[TEST] Sending POST request to {API_URL}")
    print(f"[TEST] Payload: {json.dumps(TEST_PAYLOAD)}")
    try:
        response = requests.post(API_URL, json=TEST_PAYLOAD, timeout=15)
    except Exception as exc:
        print(f"[FAIL] Could not connect to FastAPI server: {exc}")
        return 1

    print(f"[TEST] HTTP Status Code: {response.status_code}")
    if response.status_code != 200:
        print(f"[FAIL] Expected 200 OK, got {response.status_code}: {response.text}")
        return 1

    try:
        data = response.json()
    except Exception as exc:
        print(f"[FAIL] Response is not valid JSON: {exc}")
        return 1

    print(f"[TEST] Response JSON:\n{json.dumps(data, indent=2)}")

    missing = REQUIRED_KEYS - set(data.keys())
    if missing:
        print(f"[FAIL] Response JSON missing required keys: {missing}")
        return 1

    if data.get("status") != "flagged":
        print(f"[FAIL] Expected status 'flagged' for violating payload, got '{data.get('status')}'")
        return 1

    print("[PASS] BrandGuard AI E2E API test succeeded with 200 OK and valid schema!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
