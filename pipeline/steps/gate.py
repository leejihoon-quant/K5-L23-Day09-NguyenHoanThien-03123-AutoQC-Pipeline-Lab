"""BƯỚC 4 — Cửa chặn: quyết định Release / Hold / Rework.   ★

Test:  pytest tests/test_gate.py -q

Cây quyết định Day 07 (slide Day 09: "Lỗi bắt buộc chặn pipeline; lỗi cảnh báo chuyển người xem"):

  còn ≥ 1 lỗi bắt buộc (severity ERROR)                          -> "Rework"
  không còn lỗi bắt buộc, nhưng tỉ lệ ẢNH còn cảnh báo
      >= cfg["gate"]["warn_ratio_hold"]                          -> "Hold"
  còn lại                                                        -> "Release"

Tỉ lệ cảnh báo = (số ẢNH khác nhau có ≥ 1 cảnh báo) / (tổng số ảnh).  Chú ý:
- chỉ đếm issue có `image` nằm trong `image_stems` (bỏ "<dataset>", "data.yaml");
- bỏ qua ảnh nằm trong `reviewed` (người đã xem, cảnh báo của ảnh đó coi như đã xử lý) — nhưng LỖI BẮT BUỘC thì không bao giờ được bỏ qua;
- mẫu số là số ảnh, không phải số issue.

Trả về dict: decision, n_errors, n_warn_images, n_images, warn_ratio (làm tròn 4 chữ số), reasons (list[str], giải thích bằng tiếng Việt, có số liệu).
"""
from ..common import ERROR, WARN  # noqa: F401


def decide(issues, image_stems, cfg, reviewed=frozenset()):
    stems = set(image_stems)
    n = len(stems)
    n_err = sum(1 for i in issues if i.severity == ERROR)
    warn_imgs = {i.image for i in issues if i.severity == WARN and i.image in stems and i.image not in reviewed}
    ratio = round(len(warn_imgs) / n, 4) if n else 0.0
    thr = cfg["gate"]["warn_ratio_hold"]
    if n_err:
        decision = "Rework"
        reason = f"còn {n_err} lỗi bắt buộc chưa sửa được: phải làm lại"
    elif n and len(warn_imgs) / n >= thr:
        decision = "Hold"
        reason = f"{len(warn_imgs)}/{n} ảnh ({ratio:.1%}) còn cảnh báo chưa duyệt, >= ngưỡng {thr:.0%}: giữ lại"
    else:
        decision = "Release"
        reason = f"không còn lỗi bắt buộc; {len(warn_imgs)}/{n} ảnh ({ratio:.1%}) còn cảnh báo, < ngưỡng {thr:.0%}"
    return {"decision": decision, "n_errors": n_err, "n_warn_images": len(warn_imgs), "n_images": n,
            "warn_ratio": ratio, "reasons": [reason]}
