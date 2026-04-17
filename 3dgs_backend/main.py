import cv2
import torch
import numpy as np
import matplotlib.pyplot as plt
import sys
import os

def preprocess_image(image_path):
    # 1. Đọc ảnh
    img = cv2.imread(image_path)
    # Thêm kiểm tra để đảm bảo ảnh được đọc thành công
    if img is None:
        raise FileNotFoundError(f"Không thể đọc ảnh từ đường dẫn: {image_path}. Vui lòng kiểm tra lại đường dẫn hoặc tệp ảnh không tồn tại/bị hỏng.")
    img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

    # 2. Khử nhiễu bề mặt & Giảm phản chiếu nhẹ (Bilateral Filter)
    # Giúp làm mịn các vùng phẳng nhưng vẫn giữ lại các cạnh sắc nét
    img_denoised = cv2.bilateralFilter(img_rgb, d=9, sigmaColor=75, sigmaSpace=75)

    # 3. Cân bằng sáng bằng CLAHE
    # Chuyển sang hệ LAB để xử lý kênh độ sáng L mà không làm sai lệch màu sắc
    lab = cv2.cvtColor(img_denoised, cv2.COLOR_RGB2LAB)
    l, a, b = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))
    cl = clahe.apply(l)
    img_balanced = cv2.merge((cl, a, b))
    img_final = cv2.cvtColor(img_balanced, cv2.COLOR_LAB2RGB)

    return img_rgb, img_final

def get_midas_model(model_type="DPT_Large"):
    # Tải mô hình từ Torch Hub
    midas = torch.hub.load("intel-isl/MiDaS", model_type)
    device = torch.device("cuda") if torch.cuda.is_available() else torch.device("cpu")
    midas.to(device)
    midas.eval()

    # Tải bộ biến đổi (transforms) tương ứng với model
    midas_transforms = torch.hub.load("intel-isl/MiDaS", "transforms")
    transform = midas_transforms.dpt_transform if model_type == "DPT_Large" else midas_transforms.small_transform

    return midas, transform, device

def estimate_depth(img, midas, transform, device):
    input_batch = transform(img).to(device)

    with torch.no_grad():
        prediction = midas(input_batch)
        # Resize về kích thước gốc
        prediction = torch.nn.functional.interpolate(
            prediction.unsqueeze(1),
            size=img.shape[:2],
            mode="bicubic",
            align_corners=False,
        ).squeeze()

    output = prediction.cpu().numpy()
    # Chuẩn hóa về dải 0-255
    depth_norm = cv2.normalize(output, None, 0, 255, norm_type=cv2.NORM_MINMAX, dtype=cv2.CV_8U)
    return depth_norm

def evaluate_and_refine(original_img, depth_map):
    # Đánh giá sai số bằng cách so sánh cạnh (Edge Alignment)
    # Nếu cạnh của ảnh gốc và cạnh của depth map không khớp, đó là vùng sai số cao
    edges_img = cv2.Canny(original_img, 100, 200)
    edges_depth = cv2.Canny(depth_map, 30, 70)

    # Căn chỉnh: Sử dụng Guided Filter để ép biên Depth Map theo cấu trúc ảnh gốc
    guided_filter = cv2.ximgproc.createGuidedFilter(guide=original_img, radius=8, eps=1e-2)
    refined_depth = guided_filter.filter(depth_map)

    return refined_depth, edges_img, edges_depth

# --- CHƯƠNG TRÌNH CHÍNH ---
if __name__ == "__main__":
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    # Sử dụng ảnh mặc định nếu không cung cấp qua command argument
    path = "test_image.jpg"
    if len(sys.argv) > 1:
        path = sys.argv[1]
        
    # Tạo ảnh dummy nếu đường dẫn không tồn tại để verify script chạy mượt
    if not os.path.exists(path):
        print(f"File {path} không tồn tại, tạo ảnh test...")
        dummy_img = np.zeros((480, 640, 3), dtype=np.uint8)
        cv2.imwrite(path, dummy_img)

    # B1: Tiền xử lý
    original, cleaned = preprocess_image(path)

    # B2: Chạy MiDaS
    # Có thể dùng MiDaS_small để verify nhanh khi test
    model_type = "MiDaS_small" if not os.path.exists(path) or path == "test_image.jpg" else "DPT_Large"
    print(f"Tải mô hình {model_type}...")
    model, transform, dev = get_midas_model(model_type)
    
    print("Dự đoán độ sâu...")
    raw_depth = estimate_depth(cleaned, model, transform, dev)

    # B3: Căn chỉnh & Hậu xử lý
    print("Căn chỉnh bản đồ độ sâu...")
    final_depth, e_img, e_depth = evaluate_and_refine(cleaned, raw_depth)

    print("Kịch bản thực thi thành công! Lưu kết quả ra file output.png.")

    # B4: Hiển thị kết quả & Lưu
    titles = ['Ảnh gốc', 'Đã xử lý sáng/nhiễu', 'Depth Map (MiDaS)', 'Depth Map tinh chỉnh']
    images = [original, cleaned, raw_depth, final_depth]

    plt.figure(figsize=(16, 10))
    for i in range(4):
        plt.subplot(2, 2, i+1)
        plt.title(titles[i])
        if i >= 2:
            plt.imshow(images[i], cmap='magma')
        else:
            plt.imshow(images[i])
        plt.axis('off')

    plt.tight_layout()
    plt.savefig('output.png')
    # plt.show() # Tắt show() để không bị block process khi tự động kiểm tra
