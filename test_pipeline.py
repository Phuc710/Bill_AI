import sys
import argparse
import json
from pathlib import Path

# Add root to path
_ROOT = Path(__file__).resolve().parent
sys.path.append(str(_ROOT))

from core.pipeline import InvoicePipeline
from core.config import Config

def run_test(image_path: str, fast_mode: bool):
    # Set config mode
    Config.FAST_MODE = fast_mode
    mode_str = "🚀 FAST MODE (Skip Detect)" if fast_mode else "🚀 STANDARD MODE (Full Flow)"
    
    print(f"{mode_str} for: {image_path}")
    
    # Ensure dirs
    Config.ensure_dirs()
    
    # Load image
    img_file = _ROOT / image_path
    if not img_file.exists():
        print(f"❌ Error: {image_path} not found.")
        return

    data = img_file.read_bytes()
    
    pipeline = InvoicePipeline()
    result = pipeline.run(data, filename=image_path)
    
    print("\n" + "="*50)
    print(f"📊 STATUS: {result['status']} | MESSAGE: {result['message']}")
    print("="*50)
    
    if result.get('structured'):
        print("\n💎 STRUCTURED OUTPUT:")
        # Show a summary of structured data
        s = result['structured']
        print(f"  Store: {s.get('store_name') or '—'}")
        print(f"  Total: {s.get('total') or 0:,.0f} VND")
        print(f"  Items: {len(s.get('items') or [])} items")
        
        if True: # Always show JSON for automated verification
            print(json.dumps(s, indent=2, ensure_ascii=False))
        
        meta = result.get('meta', {})
        print("\n⏱ THỜI GIAN THỰC THI (PERFORMANCE STATS):")
        timing = meta.get('timing_ms', {})
        
        step_names = {
            "input": "Đọc ảnh",
            "precheck": "Kiểm tra sơ bộ",
            "detect": "Tìm vùng hóa đơn",
            "standardize": "Chuẩn hóa",
            "ocr": "Đọc chữ (OCR)",
            "gemini": "AI Trích xuất",
            "total": "Tổng Pipeline"
        }
        
        for step, ms in timing.items():
            name = step_names.get(step, step)
            print(f"  {name:20}: {ms:>8.1f} ms")
        print(f"  Thời gian hoàn thành : {meta.get('processing_time_ms'):>8.1f} ms")
    else:
        print("\n❌ Pipeline failed to produce structured data.")
        if result.get('message'):
            print(f"  Error: {result['message']}")

    print("\n" + "="*50)
    print(f"📁 Log saved to: {result.get('log_path')}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("image", nargs="?", default="bill_long.png")
    parser.add_argument("--fast", action="store_true", help="Run in FAST_MODE (skip detection)")
    parser.add_argument("--standard", action="store_true", help="Run in STANDARD_MODE (full flow)")
    args = parser.parse_args()

    # Default to config if neither flag passed, or use fast if specified
    mode = Config.FAST_MODE
    if args.fast: mode = True
    if args.standard: mode = False

    run_test(args.image, mode)
