"""BƯỚC 2/4 — Sửa tự động những lỗi bắt buộc mà máy sửa được AN TOÀN.   ★★

Test:  pytest tests/test_autofix.py -q

`fix(ds, issues, cfg) -> list[dict]`: duyệt `issues` (chỉ lỗi severity ERROR), sửa thẳng vào thư mục `ds`,
và trả về danh sách thay đổi; mỗi phần tử có khoá: image, line, action, before, after
(đây chính là file `03_fixes.csv` — bằng chứng pipeline đã làm gì, người có thể kiểm lại).

| code lỗi                                       | cách sửa                                    | action           |
|------------------------------------------------|---------------------------------------------|------------------|
| BAD_FORMAT, BAD_CLASS_ID, BOX_ZERO, DUP_BOX    | xoá dòng đó khỏi file nhãn                  | "drop_line"      |
| BOX_OUT_OF_IMAGE                               | cắt box về trong [0,1] (giữ nguyên lớp)     | "clip_box"       |
| MISSING_LABEL_FILE                             | KHÔNG sửa file (máy không thể bịa nhãn): ghi 1 dòng fix, before="(không có file)", after="chuyển người gán" | "needs_label" |
| BAD_CLASS_NAME                                 | ghi lại `names` trong data.yaml đúng `cfg["classes"]` | "rename_classes" |
| DUP_IMAGE_*, LEAK_TEST, CORRUPT_IMAGE, BAD_SIZE| xoá ảnh + nhãn khỏi `ds`                    | "remove_image"   |

Bẫy cần nghĩ tới (có test cho từng cái)
- Một file có NHIỀU dòng lỗi: số dòng trong `issues` là số dòng GỐC. Nếu xoá từng dòng một thì số dòng lệch.
  Gom theo file, rồi ghi lại MỘT lần.
- Sau khi cắt, box có thể không còn diện tích (nằm hẳn ngoài ảnh): lúc đó xoá dòng thay vì ghi box rỗng.
- Một dòng có 2 lỗi (vd. BOX_OUT_OF_IMAGE + DUP_BOX): xoá dòng thắng, chỉ ghi 1 fix `drop_line`, không ghi thêm `clip_box`. Dòng trống ở giữa file vẫn đếm vào số dòng gốc.
- Ảnh vừa bị xoá (DUP_IMAGE_*...) mà còn issue dòng của chính nó: bỏ qua êm, không được báo lỗi/chết.
- Không động tới lỗi WARN (cảnh báo là việc của người). Không sửa file ở `data/raw/` — chỉ sửa `ds`.
- Chạy lần 2 trên dữ liệu đã sửa phải không làm gì thêm (idempotent) — NGOẠI LỆ duy nhất: `needs_label` được ghi lại mỗi lần còn lỗi `MISSING_LABEL_FILE` (vì ảnh vẫn chưa có nhãn).

- `needs_label` KHÔNG tạo file nhãn rỗng (rỗng = "ảnh nền", khác với "chưa gán"). `review_queue` sẽ đẩy ảnh này lên đầu hàng đợi cho người.

Gợi ý: `yaml.safe_load / safe_dump`.
"""
from collections import defaultdict  # noqa: F401

import yaml  # noqa: F401

from ..common import ERROR, parse_yolo_line  # noqa: F401


DROP = {"BAD_FORMAT", "BAD_CLASS_ID", "BOX_ZERO", "DUP_BOX"}
REMOVE = {"DUP_IMAGE_EXACT", "DUP_IMAGE_NEAR", "LEAK_TEST", "CORRUPT_IMAGE", "BAD_SIZE"}


def fix(ds, issues, cfg):
    errs = [i for i in issues if i.severity == ERROR]
    fixes = []
    removed = set()

    for i in errs:                                          # 1) xoá ảnh
        if i.code in REMOVE and i.image not in removed:
            removed.add(i.image)
            img = ds.image_path(i.image)
            before = img.name if img else i.image
            if img and img.exists():
                img.unlink()
            lp = ds.label_path(i.image)
            if lp.exists():
                lp.unlink()
            fixes.append({"image": i.image, "line": "", "action": "remove_image", "before": before, "after": f"(đã xoá: {i.code})"})

    per_file = defaultdict(dict)                            # 2) sửa dòng: gom theo file, số dòng GỐC
    for i in errs:
        if i.image in removed or i.line is None:
            continue
        if i.code in DROP:
            per_file[i.image][i.line] = "drop"
        elif i.code == "BOX_OUT_OF_IMAGE":
            per_file[i.image].setdefault(i.line, "clip")
    for stem, acts in per_file.items():
        p = ds.label_path(stem)
        if not p.exists():
            continue
        raw = p.read_text(encoding="utf-8", errors="replace").splitlines()
        out, changed = [], False
        for n, text in enumerate(raw, 1):
            act = acts.get(n)
            if act is None or not text.strip():
                out.append(text)
                continue
            changed = True
            if act == "clip":
                try:
                    cid, x, y, w, h = parse_yolo_line(text)
                    x1, y1 = max(0.0, x - w / 2), max(0.0, y - h / 2)
                    x2, y2 = min(1.0, x + w / 2), min(1.0, y + h / 2)
                    if x2 - x1 > 1e-9 and y2 - y1 > 1e-9:
                        new = f"{cid} {(x1 + x2) / 2:.6f} {(y1 + y2) / 2:.6f} {x2 - x1:.6f} {y2 - y1:.6f}"
                        out.append(new)
                        fixes.append({"image": stem, "line": n, "action": "clip_box", "before": text, "after": new})
                        continue
                except ValueError:
                    pass
            fixes.append({"image": stem, "line": n, "action": "drop_line", "before": text, "after": ""})
        if changed:
            p.write_text("\n".join(out) + ("\n" if out else ""), encoding="utf-8")

    for i in errs:                                          # 3) việc còn lại
        if i.code == "MISSING_LABEL_FILE" and i.image not in removed:
            fixes.append({"image": i.image, "line": "", "action": "needs_label", "before": "(không có file)", "after": "chuyển người gán"})
        elif i.code == "BAD_CLASS_NAME":
            d = (yaml.safe_load(ds.yaml_path.read_text(encoding="utf-8")) if ds.yaml_path.exists() else None) or {}
            before = d.get("names")
            d["names"] = dict(enumerate(cfg["classes"])) if isinstance(before, dict) else list(cfg["classes"])
            ds.yaml_path.write_text(yaml.safe_dump(d, allow_unicode=True, sort_keys=False), encoding="utf-8")
            fixes.append({"image": i.image, "line": "", "action": "rename_classes", "before": str(before), "after": str(d["names"])})
    return fixes
