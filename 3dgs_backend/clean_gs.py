import numpy as np
from plyfile import PlyData, PlyElement
import open3d as o3d
import argparse

# Thiet lap cac muc tieu toi uu hoa (Point Count) cho tung thiet bi VR
PRESETS = {
    "low": 100_000,    # Danh cho thiet bi VR di dong cấu hình thap
    "medium": 300_000, # Muc tieu can bang giua do sac net va toc do render
    "high": 800_000,    # Danh cho may tinh co GPU manh (PCVR)
    "ultra": 1_500_000 # Them muc ultra cho pc cuc manh
}

def clean_gs_vr(input_path, output_path,
                preset="medium",
                sh_keep_ratio=0.3,
                use_radius_filter=True):

    print(f"\nLoading: {input_path}")
    plydata = PlyData.read(input_path)
    v = plydata['vertex'].data
    initial_count = len(v)

    # Kiem tra neu file dau vao khong co du lieu
    if initial_count == 0:
        raise ValueError("Error: Input PLY file is empty!")

    print(f"Initial points: {initial_count:,}")

    # ===== 1. Tinh toan kich thuoc thuc (Real Scale) =====
    # GS luu scale o dang Log, can chuyen ve gia tri thuc de xac dinh kich thuoc hat
    scales = np.exp(np.stack([v['scale_0'], v['scale_1'], v['scale_2']], axis=-1))
    max_s = np.max(scales, axis=1)

    # ===== 2. Loc nhieu khong gian (Spatial Filtering) =====
    # Loai bo cac diem "rac" bay lo lung khong thuoc ve vat the chinh
    if use_radius_filter and len(v) > 100:
        print("Running spatial filtering...")

        xyz = np.stack([v['x'], v['y'], v['z']], axis=-1)
        pcd = o3d.geometry.PointCloud()
        pcd.points = o3d.utility.Vector3dVector(xyz)

        # Tu dong xac dinh ban kinh loc dua tren kich thuoc vung bao (Bounding Box)
        bbox_min = np.min(xyz, axis=0)
        bbox_max = np.max(xyz, axis=0)
        scene_size = np.linalg.norm(bbox_max - bbox_min)
        radius = max(scene_size * 0.01, 0.01) # Gioi han ban kinh thich ung toi thieu 0.01

        # Xoa cac diem co it hon 5 lang gieng trong ban kinh xac dinh
        _, ind = pcd.remove_radius_outlier(nb_points=5, radius=radius)

        v = v[ind]
        max_s = max_s[ind]
        print(f"After spatial filter: {len(v):,}")

    # ===== 3. Loc thuoc tinh thich nghi (Adaptive Filtering) =====
    # Loai bo cac hat qua trong suot (Opacity thap) hoac hat "gia" co kich thuoc qua lon
    if len(v) > 100:
        opacity_th = np.percentile(v['opacity'], 30) # Loai bo 30% hat co do duc thap nhat
        scale_th = np.percentile(max_s, 90)           # Loai bo 10% hat co kich thuoc lon nhat (thuong la loi)

        print(f"Opacity threshold: {opacity_th:.4f}")
        print(f"Scale threshold: {scale_th:.4f}")

        mask = (v['opacity'] > opacity_th) & (max_s < scale_th)
        v = v[mask]
        max_s = max_s[mask]
        print(f"After attribute filter: {len(v):,}")

    # ===== 4. Cat tiam theo do quan trong (Importance Pruning) =====
    # Uu tien giu lai cac hat co do duc cao nhung kich thuoc nho (chi tiet vat thu)
    target = PRESETS[preset]
    importance = v['opacity'] / (max_s + 1e-6)

    if len(v) > target:
        print(f"Pruning to target: {target:,} points...")
        # Lay Top N hat quan trong nhat dung argpartition (hieu nang cao)
        idx = np.argpartition(importance, -target)[-target:]
        v = v[idx]
        importance = importance[idx]

        # Sap xep lai du lieu theo thu tu quan trong de toi uu hoa cache truy xuat
        v = v[np.argsort(-importance)]

    # ===== 5. Toi uu hoa dac thu cho VR (VR Optimization) =====

    # [FIX] Do NOT clip opacity for desktop/high-quality rendering. 
    # Clipping opacity to 0.5 causes the blurry, translucent look seen in the VR preset.
    # v['opacity'] = np.clip(v['opacity'], 0.0, 1.0)

    # 5.2 Nen du lieu mau sac (SH Compression):
    # Chi giu lai mot ty le cac he so Spherical Harmonics (f_rest) de giam dung luong file
    print("Compressing SH coefficients...")
    sh_indices = [int(name.split("_")[-1]) for name in v.dtype.names if name.startswith("f_rest")]
    max_sh = max(sh_indices) if len(sh_indices) > 0 else 0
    sh_keep_limit = int(max_sh * sh_keep_ratio)

    keep_fields = []
    for name in v.dtype.names:
        if name.startswith("f_dc"):
            keep_fields.append(name) # Luon giu mau sac co ban (Degree 0)
        elif name.startswith("f_rest"):
            idx = int(name.split("_")[-1])
            if idx <= sh_keep_limit:
                keep_fields.append(name)
        else:
            keep_fields.append(name) # Giu nguyen X, Y, Z, Rotation, Scale

    # Safely recreate the structured array with only the kept fields
    new_dtype = [(name, v.dtype[name]) for name in keep_fields]
    v_new = np.empty(v.shape, dtype=new_dtype)
    for name in keep_fields:
        v_new[name] = v[name]
    v = v_new
    # 
    # [FIX] Standard plyfile library does not support float16 ('f2') binary output.
    # We will keep colors as float32 to ensure compatibility with Unity PLY importer.
    # The file size is already significantly reduced by pruning the f_rest coefficients.

    # ===== 6. Luu file PLY da toi uu =====
    final_count = len(v)
    reduction = (1 - final_count / initial_count) * 100

    print(f"\nSaving output: {output_path}")
    PlyData([PlyElement.describe(v, 'vertex')], text=False).write(output_path)

    print("Status: Success")
    print(f"Summary: {initial_count:,} -> {final_count:,} points ({reduction:.1f}% reduced)\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="GS Optimization for Unity VR")

    parser.add_argument("--input", "-i", required=True, help="Path to input PLY")
    parser.add_argument("--output", "-o", required=True, help="Path to output PLY")
    parser.add_argument("--preset", choices=["low", "medium", "high", "ultra"], default="medium")
    parser.add_argument("--sh_ratio", type=float, default=0.3, help="Ratio of SH coefficients to keep")
    parser.add_argument("--no_spatial", action="store_true", help="Skip spatial filtering")

    args = parser.parse_args()

    clean_gs_vr(
        args.input,
        args.output,
        preset=args.preset,
        sh_keep_ratio=args.sh_ratio,
        use_radius_filter=not args.no_spatial
    )
