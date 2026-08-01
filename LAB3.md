# BÁO CÁO LAB 3 - 21DH114235 HÀ MINH TRÍ

## Thông tin sinh viên
- **Họ và tên:** Hà Minh Trí
- **Mã sinh viên:** 21DH114235
- **Môn học:** Thương mại điện tử
- **Đồ án:** Sàn TMĐT Đồ Gia Dụng

## Tổng quan dự án

Website thương mại điện tử đa cửa hàng chuyên đồ gia dụng, được phát triển theo yêu cầu tuần 4-8 môn Thương mại điện tử. Dự án tích hợp đầy đủ các tính năng từ quản lý sản phẩm, giỏ hàng, thanh toán đến chatbot AI.

## Công nghệ sử dụng

### Backend
- **Framework:** Python Flask
- **Database:** SQLite với auto-migration
- **ORM:** Native SQLite với helper functions
- **Authentication:** Session-based với role-based access control

### Frontend
- **HTML/CSS/JavaScript:** Bootstrap-style custom CSS
- **Maps:** Leaflet.js với OpenStreetMap
- **AJAX:** Fetch API cho dynamic content
- **Responsive:** Mobile-first design

### Tích hợp bên thứ ba
- **AI Chatbot:** Google Gemini API (gemini-1.5-flash)
- **Payment:** SePay webhook integration
- **Cloud Storage:** Cloudinary/Supabase với Base64 fallback
- **Maps:** OpenStreetMap với Leaflet.js

## Tính năng chính

### 1. Quản lý Admin (Tuần 4)
- **Quản lý danh mục sản phẩm:** CRUD danh mục
- **Quản lý sản phẩm:** CRUD sản phẩm với upload ảnh Base64
- **Quản lý giá bán:** Lịch sử thay đổi giá với BangGia
- **Quản lý khuyến mãi:** Tạo và quản lý chương trình khuyến mãi
- **Thống kê:** Dashboard với doanh thu, top sản phẩm

### 2. Giao diện khách hàng (Tuần 5)
- **Trang chủ:** Hiển thị sản phẩm nổi bật
- **Trang sản phẩm:** Danh sách sản phẩm với lọc theo danh mục
- **Tìm kiếm:** Search sản phẩm theo tên
- **SEO:** Meta tags, Open Graph, JSON-LD Schema
- **Sitemap.xml & Robots.txt:** Tự động tạo

### 3. Giỏ hàng & Đặt hàng (Tuần 6-7)
- **Giỏ hàng:** Thêm/xóa sản phẩm, cập nhật số lượng
- **Đặt hàng:** Form checkout với địa chỉ giao hàng
- **Phương thức thanh toán:** COD, Chuyển khoản QR
- **Quản lý đơn hàng:** Theo dõi trạng thái đơn hàng
- **Lịch sử đơn hàng:** Xem các đơn hàng đã đặt
- **Hủy đơn:** Hủy đơn hàng chưa xác nhận

### 4. GPS & Bản đồ (Tuần 6-7 - Tính năng mới)
- **Leaflet.js Map:** Bản đồ tương tác với OpenStreetMap
- **Geolocation:** Auto-location GPS cho địa chỉ giao hàng
- **Reverse Geocoding:** Auto-fill địa chỉ từ tọa độ GPS
- **Tính phí vận chuyển động:** Dựa trên khoảng cách GPS
- **Haversine Formula:** Tính khoảng cách giữa 2 điểm GPS
- **Phí vận chuyển tiered:**
  - ≤5km: 15,000đ
  - ≤15km: 30,000đ
  - ≤50km: 50,000đ
  - >50km: 80,000đ

### 5. Đánh giá sản phẩm (Tuần 6-7)
- **Đánh giá:** Khách hàng đánh giá sản phẩm đã mua
- **Rating:** Hệ thống đánh giá 1-5 sao
- **Hiển thị:** Hiển thị đánh giá trên trang chi tiết sản phẩm
- **Moderation:** Admin có thể ẩn/hiện đánh giá

### 6. Chatbot AI (Tuần 8)
- **Google Gemini API:** Chatbot AI thực sự
- **Rule-based Fallback:** Tự động fallback nếu không có API key
- **Product Knowledge:** AI tư vấn dựa trên dữ liệu sản phẩm
- **Natural Language:** Hiểu câu hỏi tự nhiên của khách hàng

### 7. Thanh toán QR (Tuần 8)
- **VietQR Integration:** Mã QR chuyển khoản
- **Countdown Timer:** Đếm ngược 5 phút
- **Polling Real-time:** Tự động kiểm tra trạng thái thanh toán
- **Webhook SePay:** Tự động cập nhật khi nhận tiền
- **Mock Payment:** API để test thanh toán

## Cấu trúc Database

### Các bảng chính
- **NguoiDung:** Người dùng với role-based access
- **CuaHang:** Cửa hàng đa cửa hàng
- **DanhMuc:** Danh mục sản phẩm
- **SanPham:** Sản phẩm với hình ảnh Base64
- **BangGia:** Lịch sử giá sản phẩm
- **KhuyenMai:** Khuyến mãi sản phẩm
- **GioHang & ChiTietGioHang:** Giỏ hàng
- **DonHang & ChiTietDonHang:** Đơn hàng
- **ThanhToan:** Thông tin thanh toán
- **DanhGia:** Đánh giá sản phẩm
- **DiaChiKhachHang:** Địa chỉ giao hàng với GPS

### Bảng DiaChiKhachHang (Mới)
```sql
CREATE TABLE DiaChiKhachHang (
    MaDiaChiKhachHang INTEGER PRIMARY KEY AUTOINCREMENT,
    MaKhachHang INTEGER NOT NULL,
    TenNguoiNhan TEXT NOT NULL,
    SoDienThoai TEXT NOT NULL,
    TinhThanh TEXT NOT NULL,
    QuanHuyen TEXT NOT NULL,
    PhuongXa TEXT NOT NULL,
    DiaChiCuThe TEXT NOT NULL,
    Lat REAL,  -- Latitude GPS
    Lng REAL,  -- Longitude GPS
    LaMacDinh INTEGER DEFAULT 0,
    FOREIGN KEY (MaKhachHang) REFERENCES NguoiDung(MaNguoiDung)
)
```

## Tính năng kỹ thuật đặc biệt

### 1. Base64 Data URIs cho Images
- **Persistent Storage:** Lưu ảnh trực tiếp trong database
- **No Filesystem Dependency:** Không bị mất ảnh khi redeploy
- **Cloud Storage Fallback:** Cloudinary/Supabase nếu credentials configured
- **Auto Fallback:** Placeholder neutral khi load fail

### 2. Database Auto-Migration
- **Auto-add Columns:** TrangThai, NgayTao cho bảng DanhGia
- **Safe Queries:** Fallback queries khi columns thiếu
- **No Manual Migration:** Tự động chạy khi init_db()
- **Error Handling:** Graceful degradation khi schema khác nhau

### 3. GPS Distance Calculation
```python
def calculate_distance_km(lat1, lon1, lat2, lon2):
    """Haversine formula để tính khoảng cách GPS"""
    from math import radians, cos, sin, asin, sqrt
    
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a))
    km = 6371 * c
    return km
```

### 4. Dynamic Shipping Fee
```python
def calculate_shipping_fee(distance_km):
    """Tính phí vận chuyển dựa trên khoảng cách"""
    if distance_km <= 5:
        return 15000
    elif distance_km <= 15:
        return 30000
    elif distance_km <= 50:
        return 50000
    else:
        return 80000
```

## Cấu hình Environment

```env
# Flask
SECRET_KEY=your_secret_key_here
FLASK_ENV=production

# Gemini AI (Tùy chọn)
GEMINI_API_KEY=your_gemini_api_key

# Cloud Storage (Tùy chọn)
CLOUDINARY_CLOUD_NAME=your_cloud_name
CLOUDINARY_API_KEY=your_api_key
CLOUDINARY_API_SECRET=your_api_secret

# Payment Webhooks (Tùy chọn)
SEPAY_MERCHANT_ID=SP-LIVE-THA8BB58
SEPAY_SECRET_KEY=spsk_live_bxCWHJK8CMa17axvMbPWk3fmJKv66EXq
SEPAY_WEBHOOK_SECRET=your_webhook_secret
PAYMENT_WEBHOOK_SECRET=your_webhook_secret
```

## Tài khoản demo

| Vai trò | Email | Mật khẩu |
|---------|-------|----------|
| Admin | admin@ecommerce.vn | admin123 |
| Chủ cửa hàng | shop@ecommerce.vn | shop123 |
| Khách hàng | customer@ecommerce.vn | customer123 |
| Giao nhận | ship@ecommerce.vn | ship123 |

## Deployment

### Local Development
```bash
cd "c:\WEB - Copy"
pip install -r requirements.txt
python run.py
```

### Render Deployment
- **Platform:** Render.com
- **Database:** SQLite với auto-migration (PostgreSQL tùy chọn)
- **Image Storage:** Base64 Data URIs (persistent)
- **Auto-deploy:** Tự động deploy khi push code
- **Free Tier:** Web service + PostgreSQL miễn phí

## SEO Optimization

- **Sitemap.xml:** Tự động tạo tại `/sitemap.xml`
- **Robots.txt:** Cấu hình tại `/robots.txt`
- **Meta Tags:** Tối ưu cho từng trang sản phẩm
- **Open Graph:** Hỗ trợ chia sẻ social media
- **Canonical URLs:** Tránh duplicate content
- **JSON-LD Schema:** Schema.org/Product cho trang chi tiết sản phẩm

## Kết quả đạt được

### Tuần 4
- ✅ Quản lý danh mục sản phẩm
- ✅ Quản lý sản phẩm CRUD
- ✅ Quản lý giá bán với lịch sử
- ✅ Quản lý khuyến mãi
- ✅ Upload hình ảnh Base64

### Tuần 5
- ✅ Trang bán hàng responsive
- ✅ Tìm kiếm và lọc sản phẩm
- ✅ SEO meta tags tối ưu
- ✅ Sitemap và Robots.txt

### Tuần 6-7
- ✅ Giỏ hàng đầy đủ
- ✅ Đặt hàng COD và QR
- ✅ Quản lý đơn hàng
- ✅ Lịch sử đơn hàng
- ✅ Đánh giá sản phẩm
- ✅ **Bản đồ GPS auto-location**
- ✅ **Tính phí vận chuyển động**

### Tuần 8
- ✅ Thống kê doanh thu
- ✅ Chatbot AI Gemini
- ✅ Thanh toán QR với webhook
- ✅ Real-time payment polling

## Kết luận

Dự án sàn TMĐT Đồ Gia Dụng đã hoàn thành đầy đủ các yêu cầu từ tuần 4-8, với các tính năng nâng cao như:
- GPS Maps & Dynamic Shipping
- Base64 Image Storage (persistent)
- Database Auto-Migration
- AI Chatbot Integration
- Real-time Payment Processing

Dự án sẵn sàng để deploy lên production với Render.com hoặc các platform tương tự.
