from __future__ import annotations
import logging, os, re, tempfile
from dataclasses import dataclass
from typing import Optional
from PIL import Image, ImageEnhance, ImageFilter, ImageOps
from contextlib import contextmanager, redirect_stderr, redirect_stdout

log = logging.getLogger("billai.ocr")

@contextmanager
def _suppress_output():
    """Suppress Python stdout/stderr + set ORT loglevel to ERROR."""
    os.environ["ORT_LOGGING_LEVEL"] = "3"
    import logging as _l
    old_level = _l.getLogger().level
    _l.getLogger().setLevel(_l.ERROR)
    try:
        with open(os.devnull, "w") as fnull:
            with redirect_stdout(fnull), redirect_stderr(fnull):
                yield
    finally:
        _l.getLogger().setLevel(old_level)

_CONF_THRESHOLD = 0.40
_MIN_CHARS      = 30
_MIN_SIDE       = 640   # ⬇️ 800→640: receipt không cần cao hơn
_MAX_SIDE       = 1280  # ⬇️ 1500→1280: Nhỏ hơn sẽ làm CPU tính toán ma trận lẹ hơn (Tối ưu Inference time)

# ── Warm-up model ngay lúc import ────────────────────────────────────────────
# vncv load ONNX model lần đầu tốn ~2-3s — warm up sẵn để tránh delay ở request đầu
_vncv_ready = False
def _warmup():
    global _vncv_ready
    if _vncv_ready:
        return
    try:
        from vncv import extract_text as _et
        import numpy as np
        _dummy = Image.new("RGB", (64, 64), color=255)
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
            _dummy.save(f, format="JPEG"); p = f.name
        with _suppress_output():
            _et(p, lang="vi", return_dict=True)
        os.remove(p)
        _vncv_ready = True
        log.info("vncv model warmed up")
    except Exception:
        pass

_warmup()  # chạy ngay khi import module này


@dataclass(slots=True)
class OCRTextResult:
    text_raw:        str
    confidence_avg:  float
    preprocess_mode: str           = "standard"
    error_type:      Optional[str] = None
    error_message:   Optional[str] = None


def _resize(img: Image.Image) -> Image.Image:
    w, h = img.size
    long_s, short_s = max(w, h), min(w, h)
    if long_s > _MAX_SIDE:
        s = _MAX_SIDE / long_s
    elif short_s < _MIN_SIDE and max(w * (sc := _MIN_SIDE / short_s), h * sc) <= _MAX_SIDE * 1.5:
        s = sc
    else:
        return img
    return img.resize((int(w * s), int(h * s)), Image.Resampling.LANCZOS)


def _preprocess(img: Image.Image, aggressive: bool = False) -> Image.Image:
    g = ImageOps.autocontrast(img.convert("L"), cutoff=0 if aggressive else 1)
    if aggressive:
        g = ImageEnhance.Contrast(g).enhance(2.5)
        g = g.point(lambda x: 0 if x < 128 else 255)
    else:
        g = g.filter(ImageFilter.UnsharpMask(radius=1.5, percent=120, threshold=3))
    return _resize(g).convert("RGB")


_JUNK = re.compile(r"^[^\w\d]{0,3}$", re.UNICODE)
def _cleanup(lines: list[str]) -> str:
    return "\n".join(
        re.sub(r" {2,}", " ", ln.strip())
        for raw in lines
        if (ln := raw.strip()) and not _JUNK.match(ln) and re.search(r"[\w\d]", ln, re.UNICODE)
    )


def _run(img: Image.Image, aggressive: bool = False) -> OCRTextResult:
    mode = "aggressive" if aggressive else "standard"
    tmp  = None
    try:
        processed = _preprocess(img, aggressive)
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
            processed.save(f, format="JPEG", quality=85)  # ⬇️ 95→85: nhỏ hơn, I/O nhanh hơn
            tmp = f.name
        from vncv import extract_text
        with _suppress_output():
            items = extract_text(tmp, lang="vi", return_dict=True) or []
        pairs = [(str(i["text"]).strip(), float(i.get("confidence", 0)))
                 for i in items if str(i.get("text", "")).strip()]
        lines, confs = zip(*pairs) if pairs else ([], [])
        return OCRTextResult(_cleanup(list(lines)), sum(confs) / len(confs) if confs else 0.0, mode)
    except ImportError as e:
        return OCRTextResult("", 0.0, mode, "import_error", str(e))
    except Exception as e:
        log.exception(f"OCR failed ({mode}): {e}")
        return OCRTextResult("", 0.0, mode, "ocr_error", str(e)[:300])
    finally:
        if tmp and os.path.exists(tmp):
            os.remove(tmp)


def extract_text(img: Image.Image) -> OCRTextResult:
    r = _run(img)
    if r.error_type or (r.confidence_avg >= _CONF_THRESHOLD and len(r.text_raw) >= _MIN_CHARS):
        return r
    log.info(f"Low quality (conf={r.confidence_avg:.2f}, chars={len(r.text_raw)}) → aggressive")
    r2 = _run(img, aggressive=True)
    if r2.confidence_avg > r.confidence_avg and len(r2.text_raw) >= len(r.text_raw) \
       or len(r2.text_raw) > len(r.text_raw) * 1.2:
        return r2
    return r