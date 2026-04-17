import os
import cv2
import uuid
from flask import Flask, request, send_file, jsonify
from flask_cors import CORS
from werkzeug.utils import secure_filename
import time
import requests

from dotenv import load_dotenv

load_dotenv()

raw_key = os.getenv("TRIPO_API_KEY", "")
current_key = raw_key.strip().replace('"', '').replace("'", "")


# Securely fetch the key
TRIPO_API_KEY = os.getenv("TRIPO_API_KEY")
if not TRIPO_API_KEY:
    print("WARNING: TRIPO_API_KEY is missing from the .env file!")

# 🌟 Import your exact functions from your main.py!
from main import preprocess_image, get_midas_model, estimate_depth, evaluate_and_refine

app = Flask(__name__)
# Allow your Vite frontend (usually localhost:5173) to talk to this server
CORS(app)

# Create temp folders for processing images
UPLOAD_FOLDER = 'uploads'
OUTPUT_FOLDER = 'outputs'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# 🌟 CRITICAL PERFORMANCE BOOST 🌟
# We load the MiDaS model ONCE when the server boots up.
# If we put this inside the route, it would take 5 seconds to load every time you upload a photo!
print("Booting AI Engine...")
model, transform, dev = get_midas_model("DPT_Large")
print("AI Engine Ready! Waiting for photos...")

@app.route('/api/midas', methods=['POST'])
def process_photo():
    # 1. Check if the frontend actually sent a file
    if 'image' not in request.files:
        return jsonify({"error": "No image sent in request"}), 400

    file = request.files['image']
    if file.filename == '':
        return jsonify({"error": "Empty filename"}), 400

    # 2. Save the uploaded file securely
    filename = secure_filename(file.filename)
    unique_id = str(uuid.uuid4())[:8] # Prevent overwriting if multiple people upload at once
    input_path = os.path.join(UPLOAD_FOLDER, f"{unique_id}_{filename}")
    output_path = os.path.join(OUTPUT_FOLDER, f"{unique_id}_depth.png")

    file.save(input_path)

    try:
        # 3. RUN YOUR CUSTOM PIPELINE
        print(f"Processing {filename}...")
        original, cleaned = preprocess_image(input_path)
        raw_depth = estimate_depth(cleaned, model, transform, dev)
        final_depth, _, _ = evaluate_and_refine(cleaned, raw_depth)

        # 4. Save the depth map to disk
        cv2.imwrite(output_path, final_depth)

        # 5. Shoot the final depth map directly back to the Vite frontend!
        return send_file(output_path, mimetype='image/png')

    except Exception as e:
        print(f"AI Error: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        # Optional: Delete the input image to save hard drive space
        if os.path.exists(input_path):
            os.remove(input_path)

@app.route('/api/text-to-3d', methods=['POST'])
def generate_3d():
    data = request.json
    prompt = data.get('prompt', '')

    print(f"User requested 3D model: {prompt}")

    # 1. Prepare the Request
    headers = {
        "Authorization": f"Bearer {TRIPO_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "type": "text_to_model",
        "prompt": prompt
    }

    try:
        # 2. Submit the Task to Tripo3D
        print("Submitting task to Tripo3D...")
        submit_res = requests.post("https://api.tripo3d.ai/v2/openapi/task", headers=headers, json=payload)
        submit_res.raise_for_status() # Check for HTTP errors

        task_id = submit_res.json()['data']['task_id']
        print(f"Task submitted successfully! Task ID: {task_id}")

        # 3. Poll the API until it's finished (Checking every 3 seconds)
        status = "queued"
        while status in ["queued", "running"]:
            time.sleep(3)
            print("Checking status...")
            status_res = requests.get(f"https://api.tripo3d.ai/v2/openapi/task/{task_id}", headers=headers)
            result_data = status_res.json()['data']
            status = result_data['status']

        # 4. Handle the Result
        if status == "success":
            print("Model finished! Extracting download link...")

            # 🌟 THE FIX: Tripo3D v2 uses 'output' instead of 'result'
            output_data = result_data.get('output', {})

            # Safely grab the model URL (Tripo sometimes provides 'pbr_model' instead of 'model')
            model_url = output_data.get('model') or output_data.get('pbr_model')

            if not model_url:
                print(f"DEBUG Full API Response: {result_data}")
                raise ValueError("Could not find the model URL in the Tripo3D response.")

            print("Downloading model from Tripo3D...")
            # Download the actual .glb file from the URL
            model_response = requests.get(model_url)

            # Save it temporarily
            temp_path = os.path.join(os.path.dirname(__file__), f"temp_{task_id}.glb")
            with open(temp_path, 'wb') as f:
                f.write(model_response.content)

            print("Success! Sending to WebXR...")
            # Send the REAL generated model to your WebXR frontend!
            return send_file(temp_path, mimetype='model/gltf-binary')

        else:
            print("Task failed or was cancelled.")

    except Exception as e:
        print(f"API Error: {e}")
        # Fallback to placeholder if there's a connection error

    # --- THE FALLBACK ---
    # If anything above fails (or if you don't have credits), it still sends the placeholder so your site doesn't break
    print("Falling back to placeholder.glb...")
    placeholder_path = os.path.join(os.path.dirname(__file__), 'placeholder.glb')

    if not os.path.exists(placeholder_path):
        return jsonify({"error": "placeholder.glb not found"}), 404

    return send_file(placeholder_path, mimetype='model/gltf-binary')

if __name__ == '__main__':
    # Run the server on port 5000
    app.run(port=5000, debug=True)