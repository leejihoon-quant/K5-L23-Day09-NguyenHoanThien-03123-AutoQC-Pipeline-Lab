# Báo cáo Day 09 — Nguyễn Hoàn Thiện, 03123

## 1. Kết luận trước
Pipeline kết luận **Release**. Vào 224 ảnh, cửa vào loại 22 (3 BAD_SIZE, 2 CORRUPT_IMAGE, 8 DUP_IMAGE_EXACT, 4 DUP_IMAGE_NEAR, 5 LEAK_TEST), còn **202 ảnh** và xuất đủ 202 ảnh vào `export/clean_v1`. Sau autofix và 80 ảnh người duyệt (mô phỏng) không còn lỗi bắt buộc; còn 16/202 ảnh (7,9%) có cảnh báo chưa duyệt, thấp hơn ngưỡng Hold 10%. Release này phụ thuộc vào việc chọn `second_opinion.conf = 0,8` (mục 3): ở `conf = 0,5` cùng pipeline ra **Hold** (44/202 = 21,8%).

## 2. Lỗi và phân việc
Lấy từ `02_error_list_v1` (202 ảnh quét; số dòng lỗi theo mã).

| Mã lỗi | Số dòng/ảnh | Ai sửa | Vì sao |
|---|---:|---|---|
| DUP_IMAGE_EXACT / NEAR, LEAK_TEST, BAD_SIZE, CORRUPT_IMAGE | 8 / 4 / 5 / 3 / 2 | máy (xoá ảnh ở cửa vào) | quy tắc rõ ràng, xoá ảnh không cần hiểu nội dung |
| BAD_CLASS_ID, BAD_FORMAT, BOX_ZERO, DUP_BOX | 6 / 3 / 4 / 7 | máy (`drop_line`) | dòng sai cú pháp/vô nghĩa; xoá là an toàn |
| BOX_OUT_OF_IMAGE | 8 | máy (`clip_box`) | cắt về trong ảnh, giữ lớp |
| BAD_CLASS_NAME | 2 | máy (`rename_classes`) | ghi lại tên lớp theo cấu hình |
| MISSING_LABEL_FILE | 6 | **người** (`needs_label`) | máy không được bịa nhãn |
| POSSIBLE_MISSING / FALSE_POS / WRONG_CLASS / LOOSE_BOX | 32 / 29 / 14 / 12 | **người** | cần hiểu nội dung ảnh; model chỉ nghi ngờ |
| EMPTY_LABEL, BOX_TINY, BOX_HUGE | 12 / 6 / 3 | người | không phân biệt được ảnh nền với thiếu nhãn, box nhỏ thật với vẽ sai |

`05_review_queue.csv` (102 ảnh) xếp theo trọng số `review.weights`: 6 ảnh `NEEDS_LABEL` (trọng số 10) lên đầu vì chưa có nhãn nào; tiếp đến ảnh có `WRONG_CLASS` (3), `MISSING`/`FALSE_POS`/`FIXED_DROP_LINE` (2), rồi `LOOSE_BOX` (1,5); `BOX_TINY`, `BOX_HUGE` (0,3–0,5) xuống cuối. Ngân sách 80 ảnh bao phủ 80/102 ảnh trong hàng đợi, gồm cả 6 ảnh thiếu nhãn và toàn bộ nhóm nghi nhầm lớp/thiếu box có ưu tiên cao. Lỗi cảnh báo còn lại sau duyệt giảm từ 113 dòng (`04_error_list_v2`) xuống 31 dòng (`07_error_list_v3`).

## 3. Calibration (2 ngưỡng)
Nguồn: `submission/calibration/calibration_report.md` (bộ calib 39 ảnh có đáp án).

| Tham số | Khởi đầu | Đã chọn | Precision / Recall (trước → sau) | Lý do (đánh đổi) |
|---|---|---|---|---|
| `duplicates.phash_dist` | 2 | **10** | DUP_IMAGE_NEAR: 1,00 / 0,50 → 1,00 / 0,67 | Precision giữ 1,00 ở mọi mức ≤ 16; recall tăng từ 4. Chọn 10 thay vì 16 (F1 0,91) vì 16 loại 31 ảnh trên lô raw so với 22 ở mức 10 (9 ảnh thêm, chưa kiểm). Mức 20 làm hỏng cả ảnh trùng hệt (recall EXACT 0,33). |
| `second_opinion.conf` | 0,25 | **0,8** | WRONG_CLASS 0,56/0,83 → 1,00/0,83; MISSING 0,50/1,00 → 0,67/0,75; LOOSE_BOX 0,29/0,40 → 0,50/0,20; FALSE_POS 0,31/1,00 (không đổi) | F1 trung bình 4 loại: 0,52 (ở 0,5) → 0,60 (ở 0,8). Đánh đổi: precision tăng, **recall thiếu box giảm 1,00 → 0,75**, tức có thể bỏ sót ~1/4 ảnh thiếu box. Số ảnh cần duyệt cũng giảm (hàng đợi 130 → 102), nên cổng Release được. |

**Một chỗ calibration có thể đánh lừa:** calib chỉ 39 ảnh, mỗi loại lỗi chỉ 5–8 ca (LOOSE_BOX có 5, WRONG_CLASS 6), nên một ca đổi chiều là F1 nhảy ~0,1–0,2; chênh 0,52 → 0,60 có thể là nhiễu. Ngoài ra `conf = 0,8` được chọn một phần vì nó làm cổng ra Release (chưa chắc tốt hơn cho dữ liệu thật). Với `phash_dist`, mở xem các cặp ảnh bị gộp (img_0186 ↔ img_0061, phash 10: cùng cảnh, bản crop; img_0223 ↔ img_0077, phash 6: cùng ảnh khác tông màu) thì đều là trùng thật, nên 10 hợp lý; nhưng cặp img_0186 nằm sát ngưỡng, và mức 6 sẽ bỏ sót nó.

## 4. Cửa chặn và điều pipeline KHÔNG bắt được
(a) Chạy `python -m pipeline.run --budget 0 --reports work/rep_nb --export-dir work/exp_nb`: kết luận **REWORK** ("còn 6 lỗi bắt buộc chưa sửa được"), mã thoát **20**, log ghi "KHÔNG xuất: còn lỗi bắt buộc"; thư mục `work/exp_nb` không được tạo. 6 lỗi này là 6 ảnh `MISSING_LABEL_FILE`. Cổng chặn đúng: lỗi bắt buộc không bị che bởi bất kỳ ngưỡng nào.

(b) Điểm mù có bằng chứng:
1. **Box lỏng nhẹ:** trên calib, recall `POSSIBLE_LOOSE_BOX` chỉ 0,20 ở `conf = 0,8` (0,40 ở 0,25), vì ngưỡng `iou_loose = 0,5` bỏ qua box lệch vừa phải (IoU 0,5–0,7).
2. **Báo động giả của FALSE_POS:** precision 0,31 ở mọi `conf` (5 TP, 11 FP trên calib); hơn nữa tham số `conf` không tác động tới cờ này (dùng `fp_conf = 0,1` cố định). Trong lô raw còn 13 dòng FALSE_POS sau duyệt (`07_error_list_v3`), tức ảnh Release vẫn có thể chứa box thừa.
3. **Vật nhỏ bị bỏ qua theo thiết kế:** `min_area_px = 600` loại dự đoán nhỏ hơn cỡ đó, nên thiếu nhãn ở vật nhỏ không bao giờ bị cờ.
4. **Ảnh nền hay thiếu nhãn:** 12 ảnh `EMPTY_LABEL` chỉ được cảnh báo, máy không phân biệt được.

## 5. Train: raw vs clean (tùy chọn, chấm riêng)
Cấu hình: yolo26n, 20 epoch, batch 16, imgsz 640, seed 0 và 1, chạy trên Colab T4 (device 0). Raw = 224 ảnh, clean = 202 ảnh (`clean_v1`). Kết quả trong `submission/results/` (`comparison.md`, `comparison.png`).

| biến thể | mAP50 (TB ± độ lệch) | mAP50-95 | precision | recall |
|---|---|---|---|---|
| raw | 0,726 ± 0,000 | 0,512 ± 0,004 | 0,764 ± 0,061 | 0,649 ± 0,028 |
| clean | 0,715 ± 0,019 | 0,492 ± 0,014 | 0,795 ± 0,018 | 0,606 ± 0,004 |

Chênh mAP50 (clean − raw) = **−0,011**, nhỏ hơn độ lệch giữa các seed của clean (0,019). Kết luận trung thực: **không chứng minh được dữ liệu sạch giúp mAP tốt hơn**; với 2 seed, chênh này nằm trong nhiễu. Clean cho precision cao hơn và ổn định hơn (0,795 so với 0,764) nhưng recall thấp hơn (0,606 so với 0,649).

Giả thuyết giải thích:
1. Clean bỏ 22 ảnh (10%) nên ít dữ liệu hơn; 20 epoch với model nhỏ thì mất dữ liệu có thể bù lại phần lợi từ bỏ nhãn xấu.
2. Tập đánh giá có thể chứa chính những lỗi nhãn mà pipeline đã sửa ở tập train, nên model train trên nhãn "sạch" bị lệch so với nhãn val còn lỗi. Ngoài ra, người duyệt chỉ là mô phỏng (80/102 ảnh trong hàng đợi) và còn 16 ảnh cảnh báo chưa duyệt, nên nhãn clean chưa thật sự sạch.

Hạn chế: chỉ 2 seed, độ lệch raw (0,0002) có thể thấp do tình cờ; cần ≥ 5 seed mới kết luận được.

## 6. Quyết định và ghi chú AI
(a) **Quyết định cuối: Release** (`clean_v1`, 202 ảnh). Điều kiện cần lưu ý: "người duyệt" là mô phỏng (`scripts/human_review_sim.py`, 80 ảnh); trong thực tế phải có người thật duyệt, và nếu hạ `conf` về 0,5 thì pipeline ra Hold (44/202 ảnh cảnh báo chưa duyệt, cần thêm khoảng 40 ảnh duyệt hoặc ngân sách lớn hơn để về Release).

(b) **Dùng AI (Claude Code) để viết 4 module.**
- Prompt chính: "đọc hướng dẫn, viết 4 module (label_format, gate, autofix, second_opinion)", kèm docstring/test của từng stub.
- Cách kiểm: chạy `pytest` (79 passed), chạy `python -m pipeline.run` đủ 5 bước, đọc lại `03_fixes.csv` và báo cáo lỗi; mở xem các cặp ảnh trùng; kiểm cổng bằng `--budget 0`. Chưa tự thử thêm ba ca biên ngoài bộ test (dòng dính 2 lỗi, dòng trống giữa file, ảnh nhiều dự đoán) ngoài những gì test đã phủ.
- Lần AI sai: lần đầu ghi 4 file bằng lệnh shell bị lỗi cú pháp (không file nào bị sửa), phải ghi lại bằng công cụ Edit; khi tạo task CVAT, các lần upload ảnh đầu bị lỗi (chỉ nhận 1 ảnh), phải xoá task và gửi bằng zip.

*(Thưởng +2)* **CVAT:** project `AutoQC-Day09` (id 6), task 31 gồm 20 ảnh (5 ảnh có `BOX_TINY` + 15 ảnh đầu hàng đợi) và 95 box; tạo và import nhãn YOLO 1.1 qua API. Lọc `width < 20` khớp **19 box trên 6 ảnh**: img_0020 (3), img_0026 (6), img_0030 (3), img_0051 (3), img_0069 (1), img_0161 (3). Cả 5 ảnh `BOX_TINY` của pipeline (img_0026, 0030, 0051, 0069, 0161) đều có trong tập này; img_0020 chỉ CVAT thấy (box hẹp 16–17 px nhưng cạnh ngắn ≥ 12 px). Khác biệt do ngưỡng: CVAT lọc theo chiều rộng < 20 px, pipeline theo cạnh ngắn < 12 px. Bộ lọc tính bằng API từ tọa độ box, chưa chụp ảnh màn hình bộ lọc trên giao diện. `can_review`: người gán đánh dấu ca khó cần xem lại; pipeline dùng thông tin tương tự ở hàng đợi duyệt (trọng số ưu tiên `NEEDS_LABEL`, `POSSIBLE_*`).
