# 📱 Bill AI — Android App Documentation

> **Stack**: Kotlin · Retrofit2 · Supabase Android SDK · Google OAuth
> **Min SDK**: API 24 (Android 7.0) — 99.2% thiết bị

---

## 🏗️ Kiến trúc App

```
app/
├── ui/
│   ├── auth/          # Màn 1–2: Splash, Login
│   ├── main/          # Màn 3: Home/Dashboard
│   ├── scan/          # Màn 4–6: Camera, Preview, Processing
│   ├── bill/          # Màn 7: Chi tiết hóa đơn
│   ├── history/       # Màn 8: Lịch sử
│   └── profile/       # Màn 9: Cài đặt / Profile
├── data/
│   ├── api/           # Retrofit interfaces
│   ├── model/         # Data classes (Bill, BillItem...)
│   └── repository/    # BillRepository
└── utils/             # Formatters, Extensions...
```

**Pattern**: MVVM + LiveData + Repository

---

## 📐 Screens — 9 màn hình

---

### Màn 1: Splash Screen
**File**: `SplashActivity.kt`

**Mục đích**: Loading, kiểm tra trạng thái đăng nhập.

**Logic**:
```
App mở
  └─> Kiểm tra Supabase session còn hạn không?
        ├─ Có session → Home Screen
        └─ Không → Login Screen
```

**UI**:
- Logo Bill AI căn giữa
- Hiệu ứng fade-in → chuyển màn sau 1.5s

---

### Màn 2: Login Screen
**File**: `LoginActivity.kt`

**Mục đích**: Đăng nhập bằng Google qua Supabase OAuth.

**UI**:
- Logo + tên app
- Button "Đăng nhập bằng Google" (icon Google + text)
- Text nhỏ phía dưới: "Bằng việc đăng nhập, bạn đồng ý điều khoản sử dụng"

**Flow kỹ thuật**:
```kotlin
// Mở Google OAuth URL
val oauthUrl = "https://wnzwympdwnnvdzhsxcin.supabase.co/auth/v1/authorize?provider=google"
supabase.auth.signInWith(Google) { ... }

// Callback: nhận session
val user = supabase.auth.currentUserOrNull()
val userId = user?.id  // UUID — lưu và gửi kèm mọi API call
```

**Sau login**: Lưu `user.id` vào `SharedPreferences` → chuyển sang Màn 3.

---

### Màn 3: Home / Dashboard
**File**: `HomeFragment.kt` (trong `MainActivity`)

**Mục đích**: Trang chính — nhanh chóng scan bill hoặc xem lịch sử.

**UI**:
```
┌─────────────────────────────┐
│  Xin chào, [Tên user] 👋   │
│  [Avatar] ───────  [Bell]   │
├─────────────────────────────┤
│                             │
│   ╔═══════════════════╗     │
│   ║  📷 Quét hóa đơn ║     │  ← FAB Button lớn, nổi bật
│   ╚═══════════════════╝     │
│                             │
│  📋 Hóa đơn gần đây         │
│  ┌──────────────────────┐   │
│  │ 🏪 QUÁ ĐÃ BBQ        │   │
│  │    02/04 · 636,000đ  │   │
│  └──────────────────────┘   │
│  ┌──────────────────────┐   │
│  │ 🏪 VINH NGUYEN RES   │   │
│  │    29/03 · 225,000đ  │   │
│  └──────────────────────┘   │
└─────────────────────────────┘
│ Home │ History │ Profile │
```

**API call**: `GET /bills?user_id=...&limit=5` để lấy 5 bill gần nhất.

---

### Màn 4: Camera / Chọn ảnh
**File**: `ScanFragment.kt`

**Mục đích**: Cho phép user chụp hoặc chọn ảnh từ gallery.

**UI**:
```
┌─────────────────────────────┐
│       [X] Đóng              │
├─────────────────────────────┤
│                             │
│      [Camera Viewfinder]    │
│                             │
│   ┌──────────────────────┐  │
│   │  📄 Đặt hóa đơn vào  │  │  ← Overlay hướng dẫn
│   │     khung này        │  │
│   └──────────────────────┘  │
│                             │
│  [Gallery] · [📷 Chụp] · [Flash] │
└─────────────────────────────┘
```

**Kỹ thuật**:
```kotlin
// Chụp ảnh
registerForActivityResult(ActivityResultContracts.TakePicture()) { success ->
    if (success) navigateToPreview(photoUri)
}

// Chọn từ gallery
registerForActivityResult(ActivityResultContracts.GetContent()) { uri ->
    navigateToPreview(uri)
}
```

---

### Màn 5: Preview & Confirm
**File**: `PreviewFragment.kt`

**Mục đích**: Xem lại ảnh trước khi gửi lên backend.

**UI**:
```
┌─────────────────────────────┐
│  ← Chụp lại                │
├─────────────────────────────┤
│                             │
│   [Preview ảnh hóa đơn]     │
│                             │
├─────────────────────────────┤
│   💡 Đảm bảo ảnh rõ nét     │
│      và không bị cắt        │
├─────────────────────────────┤
│                             │
│   [Chụp lại] [✅ Xử lý →]   │
└─────────────────────────────┘
```

**Action "Xử lý"**: Compress ảnh → chuyển sang Màn 6.

---

### Màn 6: Processing (Upload & Wait)
**File**: `ProcessingFragment.kt`

**Mục đích**: Upload ảnh, chờ backend xử lý, hiển thị tiến trình.

**UI**:
```
┌─────────────────────────────┐
│                             │
│      🔄 Đang xử lý...       │
│                             │
│   ████████░░░░░░  60%       │
│                             │
│   ✅ Đã upload ảnh          │
│   ✅ Phát hiện hóa đơn      │
│   🔄 Đang đọc văn bản...    │
│   ⬜ Phân tích AI           │
│                             │
│   Thường mất 10–20 giây     │
└─────────────────────────────┘
```

**Kỹ thuật**:
```kotlin
// Gửi multipart request
val result = billRepository.extractBill(imageFile, userId)
// result.status: completed | failed
```

**Kết quả**:
- `completed` → Chuyển sang Màn 7
- `failed` → Hiển thị dialog lỗi + nút "Thử lại"

---

### Màn 7: Bill Detail (Kết quả)
**File**: `BillDetailFragment.kt`

**Mục đích**: Hiển thị toàn bộ thông tin hóa đơn đã trích xuất.

**UI**:
```
┌─────────────────────────────┐
│  ← Back        [Share] [⋮]  │
├─────────────────────────────┤
│                             │
│  [Ảnh crop hóa đơn]         │
│                             │
├─────────────────────────────┤
│  🏪 QUÁ ĐÃ BBQ              │
│  📍 171 Cao Thắng, P.12     │
│  📅 21/10/2019 · 10:43      │
│  🧾 HD: 2.1-191021-000002   │
├─────────────────────────────┤
│  CÁC MÓN                   │
│  ─────────────────────────  │
│  Vếu sườn lớn  x2  556,000  │
│  Khăn lạnh     x2    6,000  │
│  ─────────────────────────  │
│  Tổng cộng        636,000đ  │
│  Khách đưa      1,000,000đ  │
│  Tiền thối        364,000đ  │
│  Thanh toán: CASH           │
├─────────────────────────────┤
│  [🗑 Xóa]  [📄 Export CSV]  │
└─────────────────────────────┘
```

> Nếu `needs_review: true` → hiển thị banner vàng "⚠️ Kết quả cần kiểm tra lại"

---

### Màn 8: History / Lịch sử
**File**: `HistoryFragment.kt` (tab trong bottom nav)

**Mục đích**: Xem toàn bộ lịch sử hóa đơn đã scan.

**UI**:
```
┌─────────────────────────────┐
│  📋 Lịch sử hóa đơn   [🔍] │
├─────────────────────────────┤
│  [All] [✅ Hoàn tất] [❌ Lỗi] │  ← Filter chips
├─────────────────────────────┤
│  Tháng 4, 2026              │
│  ┌──────────────────────┐   │
│  │🖼 [crop] │ QUÁ ĐÃ BBQ │   │
│  │         │ 636,000đ   │   │
│  │         │ 02/04 CASH │   │
│  └──────────────────────┘   │
│  ┌──────────────────────┐   │
│  │🖼 [crop] │ VINH NR   │   │
│  │         │ 225,000đ   │   │
│  │         │ 29/03      │   │
│  └──────────────────────┘   │
│         [Load more...]      │
└─────────────────────────────┘
│ Home │ History │ Profile │
```

**API call**: `GET /bills?user_id=...&page=1` với infinite scroll.

**Nhấn vào 1 item**: Chuyển sang Màn 7 (detail từ history).

---

### Màn 9: Profile / Settings
**File**: `ProfileFragment.kt` (tab trong bottom nav)

**Mục đích**: Thông tin tài khoản, cài đặt, đăng xuất.

**UI**:
```
┌─────────────────────────────┐
│  [Avatar]                   │
│  Tên: [Google Display Name] │
│  Email: user@gmail.com      │
├─────────────────────────────┤
│  THỐNG KÊ                  │
│  Tổng bill: 42              │
│  Tháng này: 8               │
├─────────────────────────────┤
│  CÀI ĐẶT                   │
│  > Ngôn ngữ         Tiếng Việt │
│  > Export toàn bộ CSV       │
│  > Về ứng dụng      v1.0.0  │
├─────────────────────────────┤
│  [🚪 Đăng xuất]             │
└─────────────────────────────┘
│ Home │ History │ Profile │
```

---

## 🔌 API Integration (Retrofit)

### Setup
```kotlin
// build.gradle
implementation("com.squareup.retrofit2:retrofit:2.9.0")
implementation("com.squareup.retrofit2:converter-gson:2.9.0")
implementation("com.squareup.okhttp3:logging-interceptor:4.12.0")
implementation("io.github.jan-tennert.supabase:gotrue-kt:2.x.x")
```

### BillApiService.kt
```kotlin
interface BillApiService {
    @Multipart
    @POST("bills/extract")
    suspend fun extractBill(
        @Header("X-API-Key") apiKey: String,
        @Part image: MultipartBody.Part,
        @Part("user_id") userId: RequestBody,
    ): BillResponse

    @GET("bills")
    suspend fun listBills(
        @Header("X-API-Key") apiKey: String,
        @Query("user_id") userId: String,
        @Query("page") page: Int = 1,
        @Query("limit") limit: Int = 20,
    ): ListBillsResponse

    @GET("bills/{id}")
    suspend fun getBill(
        @Header("X-API-Key") apiKey: String,
        @Path("id") billId: String,
    ): BillResponse

    @DELETE("bills/{id}")
    suspend fun deleteBill(
        @Header("X-API-Key") apiKey: String,
        @Path("id") billId: String,
    ): DeleteResponse
}
```

### Google Login (Supabase SDK)
```kotlin
// Khởi tạo Supabase client
val supabase = createSupabaseClient(
    supabaseUrl = "https://wnzwympdwnnvdzhsxcin.supabase.co",
    supabaseKey = "<SUPABASE_ANON_KEY>"  // Không phải service key!
) {
    install(GoTrue)
}

// Đăng nhập Google
supabase.auth.signInWith(Google)

// Lấy user ID
val userId = supabase.auth.currentUserOrNull()?.id ?: ""
```

---

## 📊 Data Models (Kotlin)

```kotlin
data class BillResponse(
    val bill_id: String,
    val status: String,          // completed | failed
    val failed_step: String?,
    val message: String?,
    val original_image_url: String?,
    val cropped_image_url: String?,
    val data: BillData?,
    val items: List<BillItem>,
    val meta: BillMeta,
)

data class BillData(
    val store_name: String?,
    val address: String?,
    val phone: String?,
    val invoice_id: String?,
    val datetime: String?,
    val total: Long,
    val subtotal: Long?,
    val cash_given: Long?,
    val cash_change: Long?,
    val payment_method: String?,
    val currency: String,
)

data class BillItem(
    val name: String,
    val quantity: Int,
    val unit_price: Long,
    val total_price: Long,
)

data class BillMeta(
    val needs_review: Boolean,
    val detect_confidence: Double,
    val processing_ms: Double,
    val llm_error: String?,
)
```

---

## 🔐 Security

| Bí mật | Lưu ở đâu | Ai dùng |
|--------|-----------|---------|
| `API_SECRET_KEY` (64 chars) | Backend `.env` only | Android → Backend |
| `SUPABASE_SERVICE_KEY` | Backend `.env` only | Backend → Supabase |
| `SUPABASE_ANON_KEY` | Android app config | Android → Supabase Auth |
| Google Token | Android memory (Supabase SDK) | Supabase Auth |

> **Android KHÔNG lưu `SUPABASE_SERVICE_KEY`** — key này chỉ nằm ở server.

---

## 🗺️ Navigation Map

```
SplashActivity
    ├─> LoginActivity ──Google─> Supabase Auth
    │                               └─> MainActivity
    └─> MainActivity
            ├─ HomeFragment       (bottom tab 1)
            │       └─> ScanFragment
            │               └─> PreviewFragment
            │                       └─> ProcessingFragment
            │                               └─> BillDetailFragment
            │
            ├─ HistoryFragment    (bottom tab 2)
            │       └─> BillDetailFragment
            │
            └─ ProfileFragment    (bottom tab 3)
```

**Tổng cộng: 9 màn hình** (2 Activity + 7 Fragment)

---

*Bill AI Mobile v1.0 — Nhóm 2*
