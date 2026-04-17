import requests
import time

# ====================== CẤU HÌNH ======================
TRIPO_API_KEY = "tsk_2cOhARmwZiAuV7hHXU1ket61OTlyEAU9xhVobJ31zCn"
PROMPT = "A futuristic sci-fi helmet, cyberpunk style, high poly, highly detailed, game ready asset, centered, clean topology"

headers = {
    "Authorization": f"Bearer {TRIPO_API_KEY}",
    "Content-Type": "application/json"
}

def run_tripo_v2():
    API_URL = "https://api.tripo3d.ai/v2/openapi/task"

    payload = {
        "type": "text_to_model",
        "prompt": PROMPT,
        "model_version": "v3.1-20260211"
    }

    print("Gui yeu cau tao model...")
    try:
        response = requests.post(API_URL, headers=headers, json=payload, timeout=30)
        response.raise_for_status()

        res_json = response.json()
        if res_json.get("code") != 0:
            print("Loi API:", res_json.get('message'))
            return

        task_id = res_json["data"]["task_id"]
        print("Task tao thanh cong! Task ID:", task_id)

        status_url = f"{API_URL}/{task_id}"
        max_attempts = 80
        print("Dang tao model...")

        for attempt in range(max_attempts):
            time.sleep(5)
            status_res = requests.get(status_url, headers=headers)
            status_data = status_res.json().get("data", {})
            status = status_data.get("status")

            if status == "success":
                print("\nHOAN THANH!")
                output = status_data.get("output", {})
                model_url = output.get("pbr_model") or output.get("model")

                if model_url:
                    print("Dang tai model...")
                    r = requests.get(model_url, timeout=60)
                    filename = "sci_fi_helmet.glb"

                    with open(filename, "wb") as f:
                        f.write(r.content)

                    print("Da tai xong:", filename)
                return

            elif status == "failed":
                print("\nTask that bai:", status_data)
                return

            progress = status_data.get("progress", 0)
            print(f"Trang thai: {status} ({progress}%)\r", end="")

        print("\nTimeout: Qua thoi gian cho.")

    except Exception as e:
        print("\nLoi:", e)

if __name__ == '__main__':
    run_tripo_v2()
