import os
import urllib.request
import sys

VERSION = "0.4.1675469240"
TARGET_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app", "static", "models", "mediapipe")

FILES = [
    "hands.js",
    "hands.binarypb",
    "hand_landmark_full.tflite",
    "hand_landmark_lite.tflite",
    "hands_solution_packed_assets.data",
    "hands_solution_packed_assets_loader.js",
    "hands_solution_simd_wasm_bin.wasm",
    "hands_solution_simd_wasm_bin.js",
    "hands_solution_simd_wasm_bin.data",
    "hands_solution_wasm_bin.wasm",
    "hands_solution_wasm_bin.js",
]

os.makedirs(TARGET_DIR, exist_ok=True)

for name in FILES:
    url = f"https://cdn.jsdelivr.net/npm/@mediapipe/hands@{VERSION}/{name}"
    path = os.path.join(TARGET_DIR, name)
    print(f"Downloading {name} ...")
    try:
        urllib.request.urlretrieve(url, path)
        size_kb = os.path.getsize(path) / 1024
        print(f"  OK ({size_kb:.0f} KB)")
    except Exception as e:
        print(f"  FAILED: {e}")
        print(f"  Trying mirror...")
        try:
            mirror_url = f"https://unpkg.com/@mediapipe/hands@{VERSION}/{name}"
            urllib.request.urlretrieve(mirror_url, path)
            size_kb = os.path.getsize(path) / 1024
            print(f"  OK from mirror ({size_kb:.0f} KB)")
        except Exception as e2:
            print(f"  MIRROR ALSO FAILED: {e2}")
            print(f"  Please download manually from: {url}")
            sys.exit(1)

print(f"\nAll files downloaded to: {TARGET_DIR}")
