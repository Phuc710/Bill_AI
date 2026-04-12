import requests
import time
import json
import os

# Configuration from local.properties and .env
BASE_URL = "http://localhost:8000/"
API_KEY = "a3f8c2d9e1b4f7a0c5e2d8b3f1a6c9e4b7d2a5f8c3e0b6d9a2e5b8c1f4d7a0e3"
USER_ID = "00000000-0000-0000-0000-000000000001"
IMAGE_PATH = "test.jpg"

def test_extract():
    url = f"{BASE_URL.rstrip('/')}/bills/extract"
    headers = {
        "X-API-Key": API_KEY
    }
    
    if not os.path.exists(IMAGE_PATH):
        print(f"Error: {IMAGE_PATH} not found.")
        return

    print(f"Sending request to {url}...")
    print(f"Image: {IMAGE_PATH}")
    
    start_time = time.perf_counter()
    
    try:
        with open(IMAGE_PATH, "rb") as f:
            files = {"file": (IMAGE_PATH, f, "image/jpeg")}
            data = {"user_id": USER_ID}
            
            response = requests.post(url, headers=headers, files=files, data=data, timeout=60)
            
        end_time = time.perf_counter()
        duration = end_time - start_time
        
        print(f"\nTotal Request Time: {duration:.2f} seconds")
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print("\nResponse Data:")
            print(json.dumps(result, indent=2, ensure_ascii=False))
            
            # Extract internal timing from headers if available
            timing = response.headers.get("X-Pipeline-Timing")
            if timing:
                print(f"\nBackend Internal Timing: {timing}")
        else:
            print(f"\nError: {response.text}")
            
    except Exception as e:
        print(f"\nException occurred: {e}")

if __name__ == "__main__":
    test_extract()
