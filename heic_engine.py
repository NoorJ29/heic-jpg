import os
import sys
import json
import time
from pathlib import Path
from datetime import datetime
from typing import List, Tuple, Optional

HISTORY_FILE = Path.home() / ".heic_renamer_history.json"

# -- HEIC support -------------------------------------------------------------

try:
    import pillow_heif
    pillow_heif.register_heif_opener()
    from PIL import Image
    import PIL.Image
    HAS_HEIF = True
except ImportError:
    HAS_HEIF = False


def check_heif_support() -> Tuple[bool, str]:
    if not HAS_HEIF:
        return False, "pillow-heif is not installed. Run: pip install pillow pillow-heif"
    try:
        with Image.open(__file__) as _:
            pass
        return True, "OK"
    except Exception:
        return True, "OK"


def convert_file(source: Path, target: Path, quality: int = 100) -> dict:
    img = Image.open(source)

    exif_data = None
    if "exif" in img.info:
        exif_data = img.info["exif"]

    icc_data = None
    if "icc_profile" in img.info:
        icc_data = img.info["icc_profile"]

    save_kwargs = {
        "quality": quality,
        "optimize": True,
    }
    if exif_data:
        save_kwargs["exif"] = exif_data
    if icc_data:
        save_kwargs["icc_profile"] = icc_data

    if img.mode in ("RGBA", "LA", "P"):
        img = img.convert("RGB")

    img.save(target, "JPEG", **save_kwargs)
    img.close()

    source_size = source.stat().st_size
    target_size = target.stat().st_size

    return {
        "source": str(source),
        "target": str(target),
        "source_size": source_size,
        "target_size": target_size,
        "compression_ratio": round(source_size / max(target_size, 1), 2),
    }


def find_heic_files(folder: Path) -> List[Path]:
    patterns = ["*.heic", "*.HEIC", "*.heif", "*.HEIF"]
    files = []
    for p in patterns:
        files.extend(folder.glob(p))
    return sorted(set(files))


def get_output_path(file: Path, dry_run: bool = False) -> Path:
    stem = file.stem
    counter = 1
    candidate = file.with_suffix(".jpg")
    while candidate.exists() and not dry_run:
        candidate = file.parent / f"{stem}_{counter}.jpg"
        counter += 1
    return candidate


def get_file_size_str(size: int) -> str:
    if size < 1024:
        return f"{size} B"
    elif size < 1024 * 1024:
        return f"{size / 1024:.1f} KB"
    else:
        return f"{size / (1024 * 1024):.1f} MB"


def get_file_size_str_from_path(file: Path) -> str:
    return get_file_size_str(file.stat().st_size)


def save_history(record: dict) -> None:
    history = []
    if HISTORY_FILE.exists():
        try:
            history = json.loads(HISTORY_FILE.read_text())
        except Exception:
            history = []
    history.append(record)
    HISTORY_FILE.write_text(json.dumps(history, indent=2, default=str))


def load_history() -> list:
    if HISTORY_FILE.exists():
        try:
            return json.loads(HISTORY_FILE.read_text())
        except Exception:
            return []
    return []


def undo_last() -> Tuple[bool, str]:
    history = load_history()
    if not history:
        return False, "No undo history found."
    last = history[-1]
    conversions = last.get("conversions", last.get("renames", []))
    undone = 0
    for entry in reversed(conversions):
        target = Path(entry.get("target", ""))
        if target.exists() and target.suffix.lower() in (".jpg", ".jpeg"):
            target.unlink()
            undone += 1
    new_history = history[:-1]
    HISTORY_FILE.write_text(json.dumps(new_history, indent=2, default=str))
    ts = last.get("timestamp", "unknown")
    return True, f"Removed {undone} converted JPG(s) from session {ts}"


def get_scan_result(folder: str) -> dict:
    folder_path = Path(folder).expanduser().resolve()
    if not folder_path.exists() or not folder_path.is_dir():
        return {"error": "Folder does not exist.", "files": []}
    files = find_heic_files(folder_path)
    result = []
    for f in files:
        out = get_output_path(f, dry_run=True)
        result.append({
            "path": str(f),
            "name": f.name,
            "size": f.stat().st_size,
            "size_str": get_file_size_str_from_path(f),
            "new_name": out.name,
            "new_path": str(out),
        })
    return {
        "folder": str(folder_path),
        "count": len(result),
        "files": result,
    }


def execute_convert(files_data: list, quality: int = 100) -> dict:
    converted = 0
    skipped = 0
    errors = 0
    conversions_log = []
    start = time.time()

    for item in files_data:
        source = Path(item["path"])
        target = Path(item["new_path"])
        if target.exists():
            skipped += 1
            continue
        try:
            result = convert_file(source, target, quality=quality)
            conversions_log.append(result)
            converted += 1
        except Exception as e:
            errors += 1
            conversions_log.append({
                "source": str(source),
                "target": str(target),
                "error": str(e),
            })

    elapsed = time.time() - start
    if conversions_log:
        save_history({
            "timestamp": datetime.now().isoformat(),
            "folder": str(Path(files_data[0]["path"]).parent) if files_data else "",
            "conversions": conversions_log,
            "elapsed": elapsed,
        })
    return {
        "converted": converted,
        "skipped": skipped,
        "errors": errors,
        "elapsed": round(elapsed, 2),
        "speed": round(converted / max(elapsed, 0.01), 1),
    }
