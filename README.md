# Sàn TMĐT Đồ Gia Dụng - 21DH114235 Hà Minh Trí

Website thương mại điện tử đa cửa hàng chuyên đồ gia dụng, xây dựng theo yêu cầu tuần 4-8 môn Thương mại điện tử.

## Công nghệ

- **Backend:** Python Flask
- **Database:** SQLite (với auto-migration)
- **Frontend:** HTML, CSS, JavaScript (Bootstrap-style custom CSS)
- **Maps:** Leaflet.js với OpenStreetMap
- **AI Chatbot:** Google Gemini API (gemini-1.5-flash)
- **SEO:** JSON-LD Schema, Sitemap.xml, Robots.txt, Open Graph
- **Image Storage:** Base64 Data URIs (persistent) với Cloudinary/Supabase fallback

## Cài đặt & Chạy Local

### Bước 1: Cài đặt dependencies
```powershell
cd "c:\WEB - Copy"
pip install -r requirements.txt
```

### Bước 2: Cấu hình Environment Variables (Tùy chọn)
Mở file `.env` trong thư mục dự án:

```env
# Gemini AI Chatbot (tùy chọn - fallback rule-based nếu không có)
GEMINI_API_KEY=your_gemini_api_key_here

# Cloud Storage (tùy chọn - fallback Base64 nếu không có)
CLOUDINARY_CLOUD_NAME=your_cloud_name
CLOUDINARY_API_KEY=your_api_key
CLOUDINARY_API_SECRET=your_api_secret
SUPABASE_URL=your_supabase_url
SUPABASE_KEY=your_supabase_key
SUPABASE_BUCKET=uploads

# Payment Webhooks (tùy chọn)
SEPAY_MERCHANT_ID=SP-LIVE-THA8BB58
SEPAY_SECRET_KEY=spsk_live_bxCWHJK8CMa17axvMbPWk3fmJKv66EXq
SEPAY_WEBHOOK_SECRET=your_webhook_secret_here
PAYMENT_WEBHOOK_SECRET=your_webhook_secret_here
```

### Bước 3: Chạy web
```powershell
python run.py
```

Hoặc chạy file `start.bat`

Mở trình duyệt: **http://localhost:5000`

## Tài khoản demo

| Vai trò | Email | Mật khẩu |
|---------|-------|----------|
| Admin | admin@ecommerce.vn | admin123 |
| Chủ cửa hàng | shop@ecommerce.vn | shop123 |
| Khách hàng | customer@ecommerce.vn | customer123 |
| Giao nhận | ship@ecommerce.vn | ship123 |

## Chức năng theo tuần

### Tuần 4 - Admin
- Quản lý danh mục sản phẩm
- Quản lý sản phẩm đồ gia dụng (CRUD)
- Quản lý giá bán + lịch sử thay đổi giá
- Quản lý khuyến mãi
- Upload hình ảnh sản phẩm (Base64 Data URIs)

### Tuần 5 - User
- Trang bán hàng hiển thị sản phẩm
- Tìm kiếm, lọc theo danh mục
- SEO meta tags

### Tuần 6-7
- Giỏ hàng
- Đặt hàng (COD / Online)
- Quản lý đơn hàng (Chờ xác nhận → Đã xác nhận → Đang xử lý → Đang giao → Đã giao / Đã hủy)
- Lịch sử đơn hàng + hủy đơn
- Đánh giá sản phẩm
- **Bản đồ GPS & Tính phí vận chuyển dựa trên khoảng cách**

### Tuần 8
- Thống kê doanh thu, top sản phẩm
- **Chatbot AI tư vấn khách hàng** (Google Gemini)

## Tính năng mới

### GPS & Bản đồ
- **Leaflet.js Map**: Tích hợp bản đồ tương tác với OpenStreetMap
- **Geolocation**: Auto-location GPS cho địa chỉ giao hàng
- **Reverse Geocoding**: Auto-fill địa chỉ từ tọa độ GPS
- **Tính phí vận chuyển động**: Dựa trên khoảng cách GPS (Haversine formula)
- **Phí vận chuyển tiered**:
  - ≤5km: 15,000đ
  - ≤15km: 30,000đ
  - ≤50km: 50,000đ
  - >50km: 80,000đ

### Image Storage
- **Base64 Data URIs**: Lưu ảnh trực tiếp trong database (persistent)
- **Cloud Storage Fallback**: Cloudinary/Supabase nếu credentials configured
- **No Filesystem Dependency**: Không bị mất ảnh khi redeploy
- **Auto Fallback**: Placeholder neutral khi load fail

### Database Auto-Migration
- **Auto-add columns**: TrangThai, NgayTao cho bảng DanhGia
- **Safe queries**: Fallback queries khi columns thiếu
- **No manual migration**: Tự động chạy khi init_db()

## Tính năng SEO

- **Sitemap.xml**: Tự động tạo tại `/sitemap.xml`
- **Robots.txt**: Cấu hình tại `/robots.txt`
- **Meta tags**: Tối ưu cho từng trang sản phẩm
- **Open Graph**: Hỗ trợ chia sẻ social media
- **Canonical URLs**: Tránh duplicate content
- **JSON-LD Schema**: Schema.org/Product cho trang chi tiết sản phẩm

## Dữ liệu mẫu (Seed Data)

Dự án đã được cài đặt sẵn 18 sản phẩm đồ gia dụng đa dạng:
- **Nồi & Chảo**: Nồi inox Sunhouse, Chảo Elmich
- **Bình & Ly**: Bình giữ nhiệt Lock&Lock, Ly thủy tinh
- **Dụng cụ nhà bếp**: Bộ dao thớt, Hộp thủy tinh
- **Đồ dùng phòng tắm**: Kệ treo, Khăn tắm
- **Đồ trang trí**: Đèn LED
- **Nồi chiên không dầu**: Philips, Xiaomi, Sharp
- **Bếp từ**: Sunhouse, Midea, Bosch
- **Máy hút bụi**: Xiaomi, Ecovacs, Electrolux
- **Quạt hơi nước**: Sunhouse, Sharp, Kangaroo

## Cấu trúc CSDL

Xem `database/schema.sql` — gồm các bảng: NguoiDung, CuaHang, DanhMuc, SanPham, LichSuGia, KhuyenMai, GioHang, ChiTietGioHang, DonHang, ChiTietDonHang, ThanhToan, DonViGiaoNhan, VanChuyen, DanhGia, ThongBao, LichSuDonHang, DiaChiKhachHang.

**Bảng DiaChiKhachHang**:
- MaDiaChiKhachHang (PK)
- MaKhachHang (FK)
- TenNguoiNhan
- SoDienThoai
- TinhThanh
- QuanHuyen
- PhuongXa
- DiaChiCuThe
- Lat (Latitude - GPS)
- Lng (Longitude - GPS)
- LaMacDinh

## Lưu ý cho Demo Giảng Viên

1. **Database**: SQLite sẽ tự động tạo và seed dữ liệu khi chạy lần đầu
2. **Tài khoản**: Sử dụng tài khoản demo ở trên để test các chức năng
3. **Bán hàng**: Chức năng đặt hàng, giỏ hàng hoạt động đầy đủ
4. **GPS Map**: Test tính năng GPS auto-location và tính phí vận chuyển động
5. **SEO**: Kiểm tra `/sitemap.xml` và `/robots.txt` sau khi chạy
6. **Chatbot AI**:
   - Có API Key: Chatbot AI thực sự với Google Gemini
   - Không API Key: Tự động fallback về rule-based
   - AI sẽ tự động tư vấn dựa trên dữ liệu sản phẩm trong CSDL
7. **JSON-LD**: Kiểm tra source trang sản phẩm để xem Schema.org/Product
8. **Image Storage**: Images được lưu dưới Base64 Data URIs trong DB (persistent)

## Test Thanh Toán QR (Development)

Hệ thống hỗ trợ thanh toán QR với các tính năng:
- **Countdown Timer**: Đếm ngược 5 phút khi đặt hàng QR
- **Polling Real-time**: Tự động kiểm tra trạng thái thanh toán mỗi 4 giây
- **Webhook**: Đã tích hợp sẵn endpoint `/api/webhooks/payment`

### Cách Test Thanh Toán (Localhost)

**Cách 1: Sử dụng API Mock (Đơn giản nhất)**
```powershell
# Giả lập thanh toán thành công cho đơn hàng #8
curl -X POST http://localhost:5000/api/orders/8/mock-payment-success
```

Hoặc sử dụng Postman/Thunder Client:
- Method: POST
- URL: `http://localhost:5000/api/orders/<order_id>/mock-payment-success`
- Response: `{"status": "success", "order_id": 8, "message": "Đã giả lập thanh toán thành công"}`

**Cách 2: Test Polling Real-time**
1. Đặt hàng với phương thức "Chuyển khoản qua QR"
2. Mở trang xác nhận đơn hàng hoặc trang chi tiết đơn hàng
3. Quan sát countdown timer đếm ngược
4. Gọi API mock thanh toán thành công
5. Trang sẽ tự động cập nhật thành "Đã thanh toán" (không cần reload)

**Cách 3: Tích hợp Webhook thật (Production)**
Để hệ thống tự động nhận biết khi khách chuyển khoản thật, cần tích hợp với:
- **SePay**: Dịch vụ theo dõi biến động số dư ngân hàng (Đã tích hợp sẵn)
- **PayOS**: Cổng thanh toán Việt Nam với webhook
- **VietQR Webhook**: Webhook từ VietQR

Cấu hình trong `.env`:
```env
SEPAY_MERCHANT_ID=SP-LIVE-THA8BB58
SEPAY_SECRET_KEY=spsk_live_bxCWHJK8CMa17axvMbPWk3fmJKv66EXq
SEPAY_WEBHOOK_SECRET=your_webhook_secret_here
PAYMENT_WEBHOOK_SECRET=your_webhook_secret_here
```

### Luồng Thanh Toán QR

1. **Đặt hàng** → Trạng thái `PENDING_PAYMENT` + Countdown 5 phút
2. **Hiển thị QR** → Mã QR VietQR với thông tin chuyển khoản
3. **Polling 4s** → Frontend kiểm tra trạng thái đơn hàng
4. **Webhook nhận tiền** → Backend cập nhật trạng thái `PAID`
5. **UI cập nhật real-time** → Ẩn QR, hiển thị "Thanh toán thành công"
6. **Hết hạn** → Cronjob tự động hủy đơn sau 5 phút
