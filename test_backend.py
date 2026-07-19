import requests
import time
import json
import uuid

BASE_URL = "http://127.0.0.1:8000"

def run_tests():
    print("========================================")
    print("🏥 Starting Backend Verification Tests 🏥")
    print("========================================\n")

    # TEST 1: Healthcheck
    try:
        print("--> 1. Testing /healthz endpoint...")
        res = requests.get(f"{BASE_URL}/healthz")
        res.raise_for_status()
        print("✅ Healthcheck Passed!\n")
    except Exception as e:
        print(f"❌ Server not running. Did you start uvicorn? Error: {e}")
        return

    # TEST 2: Submit a Correction (Data Readiness Desk)
    print("--> 2. Testing /corrections/submit (New Hackathon Feature)...")
    correction_payload = {
        "facility_id": "test-fac-123",
        "facility_name": "Test Hospital Patna",
        "correction_text": "I visited this hospital yesterday and the ICU is permanently closed.",
        "evidence_link": "https://example.com/news",
        "submitted_by": "TestUser"
    }
    try:
        res = requests.post(f"{BASE_URL}/corrections/submit", json=correction_payload)
        res.raise_for_status()
        data = res.json()
        print(f"✅ Corrections API Passed! Response: {data.get('message')}\n")
    except Exception as e:
        print(f"❌ Corrections API Failed: {e}\n")

    # TEST 3: Triage Analyze (Step 1 of Triage)
    print("--> 3. Testing /triage/analyze...")
    analyze_payload = {
        "symptoms_text": "I need emergency surgery and oxygen support in Bihar right now."
    }
    session_id = None
    try:
        res = requests.post(f"{BASE_URL}/triage/analyze", json=analyze_payload, timeout=90)
        res.raise_for_status()
        data = res.json()
        session_id = data.get("session_id")
        print(f"✅ Triage Analyze Passed! Session ID: {session_id}")
        print(f"   Extracted Capabilities: {data.get('capabilities_needed')}\n")
    except Exception as e:
        print(f"❌ Triage Analyze Failed: {e}\n")

    # TEST 4: Match Facilities (Triggers LLM Judge & Data Desert)
    if session_id:
        print("--> 4. Testing /triage/match_facilities (LLM Judge & Data Desert)...")
        print("   (This takes 10-20 seconds because it calls the AI Judge...)")
        match_payload = {
            "session_id": session_id,
            "top_k": 3,
            "state_hint": "Bihar"
        }
        try:
            res = requests.post(f"{BASE_URL}/triage/match_facilities", json=match_payload, timeout=120)
            res.raise_for_status()
            data = res.json()
            
            print("✅ Match Facilities Passed!")
            
            # Check Data Desert
            desert = data.get("desert_analysis")
            if desert:
                print(f"🏜️  Data Desert Triggered: {desert}")
            else:
                print("🌳 No Desert Detected.")
                
            # Check LLM Judge
            judge = data.get("llm_judge")
            if judge:
                print(f"⚖️  LLM Judge Score: {judge.get('trust_score')}/100")
                print(f"📝 Judge Note: {judge.get('judge_note')}")
            else:
                print("⚠️  LLM Judge missing from response.")
                
        except Exception as e:
            print(f"❌ Match Facilities Failed: {e}\n")

if __name__ == "__main__":
    run_tests()
