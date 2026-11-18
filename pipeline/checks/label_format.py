"""CHECK 2 — Dòng nhãn YOLO: sai định dạng, ID lớp lạ, box tràn ảnh, box rỗng, box lặp.   (Script 2 trong slide)   ★★

Test:  pytest tests/test_label_format.py -q

Mỗi dòng nhãn: `id cx cy w h` (5 số, toạ độ 0–1). Trả về list[Issue]; `Issue.line` = số dòng (đếm từ 1).

| code             | severity | khi nào                                                                  |
|------------------|----------|--------------------------------------------------------------------------|
| BAD_FORMAT       | ERROR    | không đúng 5 cột số (dùng `parse_yolo_line`, bắt `ValueError`)           |
| BAD_CLASS_ID     | ERROR    | id lớp ngoài 0..len(ds.classes)-1                                        |
| BOX_ZERO         | ERROR    | w <= 0 hoặc h <= 0                                                       |
| BOX_OUT_OF_IMAGE | ERROR    | mép box vượt [0,1] quá `cfg["label_format"]["overflow_tol"]`; extra={"overflow": mức tràn} |
| DUP_BOX          | ERROR    | cùng lớp với một dòng TRƯỚC ĐÓ và IoU > `dup_box_iou`; báo ở dòng SAU    |
| BOX_TINY         | WARN     | cạnh ngắn của box (px) < `min_box_px`  (cần `ds.image_size(stem)`)       |
| BOX_HUGE         | WARN     | w*h > `max_box_frac`                                                     |

Gợi ý
- Mép trái = x - w/2, mép phải = x + w/2 (xem câu hỏi "dòng YOLO nào lỗi?" trong slide).
- Một dòng hỏng (BAD_FORMAT, BAD_CLASS_ID, BOX_ZERO) thì `continue`, đừng kiểm tiếp hình học của dòng đó.
- Dòng thiếu cột làm script của slide dừng giữa chừng: đây là lý do phải `try/except`.
- `iou_xywh(a, b)` có sẵn trong common.py.
- Ngưỡng nằm trong `cfg["label_format"]` — đừng viết cứng số vào code.
"""
from ..common import ERROR, WARN, Issue, iou_xywh, parse_yolo_line  # noqa: F401


def run(ds, cfg):
    c = cfg["label_format"]
    tol, min_px, max_frac, dup_iou = c["overflow_tol"], c["min_box_px"], c["max_box_frac"], c["dup_box_iou"]
    issues = []

    def add(sev, code, stem, msg, line, **extra):
        issues.append(Issue("label_format", sev, code, stem, msg, line, extra))

    for p in ds.label_files():
        stem = p.stem
        kept = []                               # các box hợp lệ đã duyệt (để tìm DUP_BOX)
        for ln, text in ds.read_label_lines(stem) or []:
            try:
                cid, x, y, w, h = parse_yolo_line(text)
            except ValueError as e:
                add(ERROR, "BAD_FORMAT", stem, f"dòng không đúng định dạng: {e}", ln)
                continue
            if not 0 <= cid < len(ds.classes):
                add(ERROR, "BAD_CLASS_ID", stem, f"id lớp {cid} ngoài 0..{len(ds.classes) - 1}", ln, id=cid)
                continue
            if w <= 0 or h <= 0:
                add(ERROR, "BOX_ZERO", stem, "box rỗng (w hoặc h <= 0)", ln)
                continue
            over = max(0.0, -(x - w / 2), -(y - h / 2), (x + w / 2) - 1, (y + h / 2) - 1)
            if over > tol:
                add(ERROR, "BOX_OUT_OF_IMAGE", stem, f"box tràn ảnh {over:.4f}", ln, overflow=round(over, 4))
            box = (x, y, w, h)
            if any(k == cid and iou_xywh(box, b) > dup_iou for k, b in kept):
                add(ERROR, "DUP_BOX", stem, "box lặp với một dòng trước đó", ln)
            kept.append((cid, box))
            size = ds.image_size(stem)
            if size and min(w * size[0], h * size[1]) < min_px:
                add(WARN, "BOX_TINY", stem, f"box quá nhỏ ({min(w * size[0], h * size[1]):.1f}px)", ln)
            if w * h > max_frac:
                add(WARN, "BOX_HUGE", stem, f"box chiếm {w * h:.0%} ảnh", ln)
    return issues
