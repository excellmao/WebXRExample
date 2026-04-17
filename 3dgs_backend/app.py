import os
import cv2
import uuid
from flask import Flask, request, send_file, jsonify
from flask_cors import CORS
from werkzeug.utils import secure_filename

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

if __name__ == '__main__':
    # Run the server on port 5000
    app.run(port=5000, debug=True)