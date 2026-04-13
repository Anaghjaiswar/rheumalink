import requests
import base64
import json
import os

# --- CONFIGURATION ---
# Agar local test kar rahe ho toh http://127.0.0.1:8001/v1/extract
# Agar Droplet par hai toh http://YOUR_DROPLET_IP:8001/v1/extract
API_URL = "http://ai_service:8001/v1/extract" 

# Wahi key jo aapne register_clinic.py se DB mein daali thi
API_KEY = "rheuma_secret_pilibhit_001" 

# Sample image ka path (e.g., 'report.jpg')
IMAGE_PATH = "test_data/image.png" 
REPORT_TYPE = "ESR" # e.g., 'ESR', 'CBC', 'LFT'

def test_pipeline():
    if not os.path.exists(IMAGE_PATH):
        print(f"❌ Error: File '{IMAGE_PATH}' nahi mili. Ek image wahan rakho.")
        return

    print(f"🚀 Testing Pipeline for: {REPORT_TYPE}...")

    # 1. Image ko Base64 mein convert karna
    with open(IMAGE_PATH, "rb") as image_file:
        encoded_string = base64.b64encode(image_file.read()).decode('utf-8')

    # 2. Payload taiyar karna (As per schemas.py)
    payload = {
        "image_base64": encoded_string,
        "report_type": REPORT_TYPE,
        "mime_type": "image/jpeg" # Change to 'application/pdf' if testing PDF
    }

    # 3. Headers (As per utils.py)
    headers = {
        "X-Clinic-Key": API_KEY,
        "Content-Type": "application/json"
    }

    try:
        # 4. Request bhejna
        response = requests.post(API_URL, json=payload, headers=headers)
        
        print(f"📡 Status Code: {response.status_code}")
        
        if response.status_code == 200:
            print("✅ Success! AI Response:")
            print(json.dumps(response.json(), indent=4))
        elif response.status_code == 401:
            print("❌ Unauthorized: API Key galat hai.")
        elif response.status_code == 402:
            print("❌ Forbidden: Subscription expired (is_active=False in DB).")
        else:
            print(f"❌ Error: {response.text}")

    except Exception as e:
        print(f"❌ Connection Error: {str(e)}")

if __name__ == "__main__":
    test_pipeline()