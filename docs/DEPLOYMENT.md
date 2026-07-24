# Hướng dẫn Deploy Website lên Render.com

## Tổng quan

Hướng dẫn này sẽ giúp bạn đưa website sàn TMĐT Gia Dụng Pro lên Render.com - một nền tảng hosting miễn phí cho Python/Flask.

## Bước 1: Chuẩn bị Repository

### 1.1. Đẩy code lên GitHub

Nếu chưa có repository trên GitHub:

```powershell
cd "c:\WEB - Copy"
git init
git add .
git commit -m "Initial commit"
```

Tạo repository mới trên GitHub, sau đó:

```powershell
git remote add origin https://github.com/username/your-repo.git
git branch -M main
git push -u origin main
```

### 1.2. Kiểm tra file cấu hình

Đảm bảo các file sau đã có trong repository:
- ✅ `Dockerfile` - Đã tạo
- ✅ `Procfile` - Đã tạo
- ✅ `requirements.txt` - Đã cập nhật
- ✅ `.env.example` - Đã tạo

## Bước 2: Đăng ký Render.com

### 2.1. Tạo tài khoản Render

1. Truy cập: https://render.com
2. Click "Sign Up"
3. Đăng ký bằng GitHub (khuyên dùng) hoặc Email
4. Xác nhận email

### 2.2. Kết nối GitHub với Render

1. Sau khi đăng nhập, click "New" → "Web Service"
2. Render sẽ yêu cầu quyền truy cập GitHub
3. Click "Connect" để cấp quyền
4. Chọn repository của bạn từ danh sách

## Bước 3: Tạo PostgreSQL Database

### 3.1. Tạo Database

1. Trong Dashboard Render, click "New" → "PostgreSQL"
2. Điền thông tin:
   - **Name**: `giadungpro-db` (hoặc tên bạn thích)
   - **Database**: `giadungpro`
   - **User**: `giadungpro_user`
   - **Region**: Singapore (để giảm latency cho Việt Nam)
3. Click "Create Database"
4. Chờ khoảng 2-3 phút để Render tạo database

### 3.2. Lấy Database URL

1. Vào tab "Connect" của database vừa tạo
2. Copy "Internal Database URL" có dạng:
   ```
   postgresql://giadungpro_user:password@dpg-xxxxx.oregon-postgres.render.com/giadungpro
   ```
3. Lưu lại URL này để dùng ở Bước 5

### 3.3. Seed dữ liệu

Vì PostgreSQL không tự động seed như SQLite, bạn cần chạy script seed:

```sql
-- Copy nội dung file database/schema.sql
-- Paste vào SQL Editor của Render PostgreSQL
-- Hoặc dùng pgAdmin để kết nối và chạy schema.sql
```

## Bước 4: Tạo Web Service

### 4.1. Cấu hình Web Service

1. Click "New" → "Web Service"
2. Chọn repository của bạn
3. Cấu hình như sau:

**Build & Deploy:**
- **Root Directory**: Để trống (hoặc `/` nếu code ở root)
- **Runtime**: Docker
- **Dockerfile Path**: `Dockerfile` (tự động detect)

**Environment:**
- **Name**: `giadungpro-web`
- **Region**: Singapore
- **Branch**: `main`

### 4.2. Cấu hình Environment Variables

Trong tab "Environment", thêm các biến sau:

| Key | Value | Description |
|-----|-------|-------------|
| `SECRET_KEY` | `your_random_secret_key_here` | Tạo random string dài |
| `FLASK_ENV` | `production` | Môi trường production |
| `DATABASE_URL` | `postgresql://...` | URL từ Bước 3.2 |
| `GEMINI_API_KEY` | `your_gemini_api_key` | API Key Gemini AI (tùy chọn) |
| `SEPAY_API_KEY` | `your_sepay_api_key` | API Key SePay (tùy chọn) |
| `SEPAY_WEBHOOK_SECRET` | `your_webhook_secret` | Secret cho SePay (tùy chọn) |
| `PAYMENT_WEBHOOK_SECRET` | `your_webhook_secret` | Secret cho webhook (tùy chọn) |

**Lưu ý:**
- `DATABASE_URL` là quan trọng nhất - copy từ Bước 3.2
- Các key SePay/PayOS có thể thêm sau khi tích hợp

### 4.3. Click "Create Web Service"

Render sẽ bắt đầu build và deploy. Quá trình mất khoảng 5-10 phút.

## Bước 5: Kiểm tra Deployment

### 5.1. Xem Logs

1. Vào tab "Logs" của Web Service
2. Kiểm tra xem có lỗi không
3. Nếu thấy "Server running on port 5000" → Thành công

### 5.2. Truy cập Website

1. Render sẽ cung cấp URL dạng: `https://giadungpro-web.onrender.com`
2. Click vào URL để truy cập website
3. Test các chức năng cơ bản

## Bước 6: Tích hợp SePay (Tùy chọn)

### 6.1. Đăng ký SePay

1. Truy cập: https://sepay.vn
2. Đăng ký tài khoản miễn phí
3. Kết nối tài khoản ngân hàng của bạn

### 6.2. Lấy API Key

1. Vào Dashboard SePay
2. Settings → API Keys
3. Copy API Key và Webhook Secret

### 6.3. Cấu hình Webhook SePay

1. Trong SePay, thêm Webhook URL:
   ```
   https://giadungpro-web.onrender.com/api/webhooks/payment
   ```
2. Copy API Key và Webhook Secret
3. Thêm vào Environment Variables của Render:
   - `SEPAY_API_KEY`: `your_api_key`
   - `SEPAY_WEBHOOK_SECRET`: `your_webhook_secret`

### 6.4. Test Webhook

1. Đặt hàng QR trên website
2. Chuyển khoản thật vào tài khoản đã kết nối SePay
3. SePay sẽ gửi webhook → Website tự động cập nhật trạng thái

## Bước 7: Cấu hình Domain (Tùy chọn)

### 7.1. Mua Domain

Mua domain từ các nhà cung cấp:
- Namecheap
- GoDaddy
- Cloudflare (miễn phí với Cloudflare Registrar)

### 7.2. Cấu hình DNS

1. Vào DNS provider của bạn
2. Thêm CNAME record:
   - **Name**: `www` (hoặc để trống)
   - **Value**: `giadungpro-web.onrender.com`
   - **TTL**: 3600

### 7.3. Thêm Domain vào Render

1. Vào Web Service → Settings → Custom Domains
2. Click "Add Custom Domain"
3. Nhập domain của bạn
4. Render sẽ cung cấp DNS records để cấu hình

## Bước 8: Monitor & Maintenance

### 8.1. Xem Logs

Vào tab "Logs" để xem:
- Error logs
- Access logs
- Performance metrics

### 8.2. Auto-deploy

Render sẽ tự động deploy khi bạn push code mới vào GitHub:
- Push code → Auto build → Auto deploy

### 8.3. Backup Database

Render PostgreSQL tự động backup hàng ngày. Bạn có thể:
- Export thủ công từ Dashboard
- Kết nối bằng pgAdmin để backup

## Troubleshooting

### Lỗi: Database connection failed

**Nguyên nhân:** DATABASE_URL sai hoặc database chưa sẵn sàng

**Giải pháp:**
1. Kiểm tra DATABASE_URL trong Environment Variables
2. Đảm bảo database đã chạy (Status = Available)
3. Test kết nối bằng pgAdmin

### Lỗi: Build failed

**Nguyên nhân:** Dockerfile hoặc requirements.txt sai

**Giải pháp:**
1. Xem Logs để biết lỗi cụ thể
2. Kiểm tra Dockerfile syntax
3. Đảm bảo tất cả dependencies trong requirements.txt

### Lỗi: Webhook không hoạt động

**Nguyên nhân:** Webhook URL sai hoặc secret không khớp

**Giải pháp:**
1. Kiểm tra Webhook URL trong SePay
2. Đảm bảo SEPAY_WEBHOOK_SECRET khớp
3. Test webhook bằng Postman

### Lỗi: Website không phản hồi

**Nguyên nhân:** Web service bị crash hoặc timeout

**Giải pháp:**
1. Xem Logs để biết lỗi
2. Kiểm tra memory limit (Render free tier: 512MB)
3. Restart web service

## Chi phí

### Render Free Tier

- **Web Service**: Miễn phí (với giới hạn)
  - 512MB RAM
  - 0.1 CPU
  - Sleep sau 15 phút không hoạt động

- **PostgreSQL**: Miễn phí (với giới hạn)
  - 90 days retention
  - 1GB storage
  - 90 connections

### Khi cần nâng cấp

Nếu website có nhiều traffic:
- **Web Service**: $7/tháng (512MB RAM, always on)
- **PostgreSQL**: $7/tháng (1GB storage, 90 days retention)

## Tổng kết

Sau khi hoàn thành các bước trên:
- ✅ Website chạy 24/7 trên Render.com
- ✅ Database PostgreSQL online
- ✅ Tự động deploy khi push code
- ✅ Tích hợp SePay cho thanh toán thật
- ✅ Domain tùy chỉnh (nếu muốn)

## Hỗ trợ

- Render Documentation: https://render.com/docs
- SePay Documentation: https://sepay.vn/docs
- Flask Deployment: https://flask.palletsprojects.com/en/latest/deploying/
