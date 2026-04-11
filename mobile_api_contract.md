# 📱 Tài liệu Tích hợp API chuẩn cho App Mobile (Kai Bill)

Để App Mobile có thể **Scale mạnh**, dễ mở rộng với hàng nghìn loại hoá đơn khác nhau (Cafe, Siêu thị, Chuyển khoản, Vé tàu, Hoá đơn đỏ...) mà **không cần Hardcode** giao diện, Backend được kiến trúc trả về một chuẩn JSON đồng nhất (Ideal Response).

Mọi kết quả trả về từ `/bills/extract` và `/bills/{bill_id}` đều dùng chung **duy nhất một mô hình JSON này**.

---

## 💎 Cấu trúc Lý tưởng (Ideal JSON Scale)

```json
{
  "bill_id": "59f8d0e8-dd53-42d6-a7f9-1347b4975f5b",
  "status": "completed",
  "failed_step": null,
  "message": "Chi tiêu 225,000đ tại nhà hàng Vĩnh Nguyên",
  
  "original_image_url": "https://<supabase_url>/.../59f8d0e8.jpg",
  "cropped_image_url": "https://<supabase_url>/.../59f8d0e8.jpg",
  
  "data": {
    "store_name": "Nhà hàng Sao Biển",
    "store_address": "123 Hoàng Diệu, Q4",
    "store_phone": "0901234567",
    "invoice_number": "HD-00123",
    "issued_at": "2024-05-12 19:30:00",
    
    "total_amount": 1250000,
    "subtotal": 1100000,
    "cash_tendered": null,
    "cash_change": null,
    "payment_method": "Credit Card",
    
    "category": "Ăn uống",
    "currency": "VND"
  },
  
  "items": [
    {
      "item_name": "Tôm hùm phô mai",
      "quantity": 1,
      "unit_price": 500000,
      "total_price": 500000
    },
    {
      "item_name": "Bia Heineken",
      "quantity": 6,
      "unit_price": 40000,
      "total_price": 240000
    }
  ],
  
  "meta": {
    "detect_confidence": 0.98,
    "processing_ms": 7500.5,
    "llm_error": null
  }
}
```

---

## 🛠️ Hướng dẫn dev Android (Kotlin / Gson) xử lý để không bị Hardcode

### 1. Root Level - UI và Định tuyến
- `status`: Chìa khoá định tuyến UI. Nếu `status == "failed"`, dev lôi cái `message` (chứa lỗi) để popup lên báo người dùng. Nếu `status == "completed"`, dev load thẳng object `data` lên màn hình.
- `message`: Chứa "Note" (ghi chú) hoặc "Summary" của bill do AI tự suy nghĩ. Rất tiện để gán thẳng vào cái ô `TextView` Ghi chú mà không cần code thêm rườm rà.
- `original_image_url`: Render thẳng vào thư viện ảnh Picasso, hoặc Glide để user chạm vào phóng to xem ảnh gốc.

### 2. Thuộc tính `meta` - Góc độ Kỹ thuật
Khối `meta` chứa các thông số Backend trả về:
- `detect_confidence`, `processing_ms`, `llm_error`

Góc độ Mobile App **KHÔNG CẦN QUAN TÂM** mấy số này lên UI (chỉ dùng bắn lên Crashlytics/Log nếu cần thiết).

### 3. Thuộc tính `data` - Thiết kế Giao diện Kháng Thay Đổi (Dynamic UI)
Object `data` chứa các trường cốt lõi của **mọi thể loại giao dịch Tài chính**. Bất kỳ bill gì (Tiền điện, nước, internet) cũng không thoát khỏi:
- Ai bán? (`store_name`, `store_address`)
- Bao giờ mua? Mã là gì? (`issued_at`, `invoice_number`)
- Chốt hết bao nhiêu tiền? (`total_amount`)
- Loại gì? (`category`)

**🌟 Android UI Tricks & Scale Tối Thượng**:
Thay vì code cứng 10 cái TextView (Text Tổng tiền, Text Địa chỉ, v.v.), Dev Mobile nên thiết kế màn hình Chi tiết bằng **RecyclerView** hoặc một **Dynamic LinearLayout**. 
Duyệt qua các thuộc tính của `data`, cái nào bị `null` (vd: bill cafe đéo có `cash_tendered`) => Ẩn row đó đi (`View.GONE`). Nhờ thế, mốt Backend có update trả về thêm 5 field mới, Data Object nở ra, nhưng App cũ đéo bao giờ vỡ giao diện!

### 3. Thuộc tính `items` - Rút gọn mảng hàng nghìn món
Dù là mua tivi tủ lạnh hay mâm cơm đầy bàn, cái list hàng nghìn món cũng rút vào một chuẩn 4 Field vô tư:
- `item_name`
- `quantity`
- `unit_price`
- `total_price`

Thiết kế chuẩn đúng 1 file Layout tái sử dụng (`item_bill_row.xml`). Quăng vào Apdater lặp qua cái List kia. Nếu có bill mới loại "Thanh toán hoá đơn tiền điện", thằng `items` này đơn giản trả đúng 1 object (`item_name`: Tiền điện t5, `quantity`: 1). Cực kì an toàn và dẻo dai.

---

## 🚀 Tối ưu hóa hiệu suất (Client-Side Optimization)

Để API đạt tốc độ xử lý nhanh nhất (**< 15s**) và phản hồi mượt mà cho trải nghiệm người dùng, Mobile Client **bắt buộc** thực hiện các bước sau:

### 1. Sử dụng Google ML Kit Document Scanner
* **Thực hiện**: Tích hợp [ML Kit Document Scanner](https://developers.google.com/ml-kit/vision/doc-scanner) thay cho Camera thường.
* **Lợi ích**: Tự động Crop, Deskew (bẻ thẳng), và Enhance ảnh. Giúp Backend OCR không tốn tài nguyên xử lý rác xung quanh.

### 2. Chuẩn hóa Định dạng & Kích thước
* **Định dạng**: Nén ảnh sang **WebP (Quality 80)**. Giảm 70% dung lượng file so với JPG.
* **Kích thước**: Resize ảnh về **Max Side = 1280px**. To hơn mức này sẽ làm OCR chạy chậm hơn mà không tăng chất lượng trích xuất.
* **Pre-processing**: Chuyển ảnh sang **Grayscale** trước khi gửi nếu có thể.

### 3. Workflow Chuẩn
`Chụp (ML Kit) -> Smart Crop -> Resize (1280px) -> Convert WebP -> POST /bills/extract`
