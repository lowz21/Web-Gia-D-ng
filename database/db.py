import os
import sqlite3
from werkzeug.security import generate_password_hash

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "database", "ecommerce.db")
SCHEMA_PATH = os.path.join(BASE_DIR, "database", "schema.sql")

# Database URL cho PostgreSQL (Production)
DATABASE_URL = os.getenv("DATABASE_URL")


def normalize_database_url(url):
    """Normalize database URL for psycopg2 compatibility."""
    if not url:
        return url
    
    # Convert postgres:// to postgresql://
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    
    # Add sslmode=require for serverless environments (Vercel, Supabase, Neon)
    if "sslmode" not in url.lower():
        # Add sslmode parameter
        separator = "&" if "?" in url else "?"
        url = f"{url}{separator}sslmode=require"
    
    return url


def get_db():
    if DATABASE_URL:
        # Sử dụng PostgreSQL cho production
        import psycopg2
        from psycopg2.extras import RealDictCursor
        
        # Normalize the database URL
        normalized_url = normalize_database_url(DATABASE_URL)
        
        conn = psycopg2.connect(normalized_url, cursor_factory=RealDictCursor)
        return conn
    else:
        # Sử dụng SQLite cho development
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn


def adapt_query_for_postgresql(sql, params):
    """
    Convert SQLite-style (?) placeholders to PostgreSQL-style (%s) placeholders.
    This allows the same SQL queries to work on both databases.
    """
    if not DATABASE_URL:
        return sql, params
    
    # Convert ? to %s for PostgreSQL
    # Count the number of placeholders
    placeholder_count = sql.count('?')
    
    if placeholder_count == 0:
        return sql, params
    
    # Replace all ? with %s
    postgres_sql = sql.replace('?', '%s')
    
    return postgres_sql, params


def query_one(sql, params=()):
    """Execute a query and return a single row."""
    conn = get_db()
    try:
        # Adapt query for PostgreSQL if needed
        adapted_sql, adapted_params = adapt_query_for_postgresql(sql, params)
        cur = conn.execute(adapted_sql, adapted_params)
        row = cur.fetchone()
        return row
    finally:
        conn.close()


def query_all(sql, params=()):
    """Execute a query and return all rows."""
    conn = get_db()
    try:
        # Adapt query for PostgreSQL if needed
        adapted_sql, adapted_params = adapt_query_for_postgresql(sql, params)
        cur = conn.execute(adapted_sql, adapted_params)
        rows = cur.fetchall()
        return rows
    finally:
        conn.close()


def execute(sql, params=()):
    """Execute a query and return the last row ID."""
    conn = get_db()
    try:
        # Adapt query for PostgreSQL if needed
        adapted_sql, adapted_params = adapt_query_for_postgresql(sql, params)
        cur = conn.execute(adapted_sql, adapted_params)
        conn.commit()
        last_id = cur.lastrowid if hasattr(cur, 'lastrowid') else None
        return last_id
    finally:
        conn.close()


def get_current_price(product_id):
    """Get the current active price for a product from BangGia table."""
    price_record = query_one(
        """SELECT GiaBan FROM BangGia 
           WHERE MaSanPham = ? AND IsActive = 1 
           AND (NgayKetThuc IS NULL OR NgayKetThuc > datetime('now'))
           ORDER BY NgayApDung DESC LIMIT 1""",
        (product_id,)
    )
    return price_record['GiaBan'] if price_record else None


def create_price_record(product_id, price, conn=None):
    """Create a new price record in BangGia table."""
    should_close = conn is None
    if conn is None:
        conn = get_db()
    
    try:
        # Deactivate previous active price
        conn.execute(
            """UPDATE BangGia SET NgayKetThuc = datetime('now'), IsActive = 0
               WHERE MaSanPham = ? AND IsActive = 1 AND NgayKetThuc IS NULL""",
            (product_id,)
        )
        
        # Insert new price record
        conn.execute(
            """INSERT INTO BangGia (MaSanPham, GiaBan, NgayApDung, IsActive, NgayTao)
               VALUES (?, ?, datetime('now'), 1, datetime('now'))""",
            (product_id, price)
        )
        
        if should_close:
            conn.commit()
    finally:
        if should_close:
            conn.close()


def get_price_history(product_id):
    """Get all price history for a product."""
    return query_all(
        """SELECT * FROM BangGia 
           WHERE MaSanPham = ? 
           ORDER BY NgayApDung DESC""",
        (product_id,)
    )


def init_db():
    # Skip SQLite initialization on Vercel (serverless environment)
    # Vercel requires external PostgreSQL, not local SQLite
    if os.getenv("VERCEL"):
        print("Skipping SQLite initialization on Vercel (requires external PostgreSQL)")
        return
    
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    with open(SCHEMA_PATH, encoding="utf-8") as f:
        schema = f.read()

    conn = get_db()
    conn.executescript(schema)
    _migrate_donhang_columns(conn)
    _migrate_price_history(conn)
    _migrate_dia_chi_khach_hang(conn)
    _migrate_product_images(conn)
    _migrate_banners(conn)
    _migrate_bang_gia(conn)
    _migrate_user_profile_fields(conn)
    conn.commit()

    count = conn.execute("SELECT COUNT(*) FROM NguoiDung").fetchone()[0]
    if count == 0:
        seed_data(conn)
    conn.close()


def _migrate_donhang_columns(conn):
    """Thêm cột cho luồng pending_payment trên DB đã tồn tại."""
    cols = {row[1] for row in conn.execute("PRAGMA table_info(DonHang)").fetchall()}
    if "HanThanhToan" not in cols:
        conn.execute("ALTER TABLE DonHang ADD COLUMN HanThanhToan DATETIME")
    if "MaTruyCapKhach" not in cols:
        conn.execute("ALTER TABLE DonHang ADD COLUMN MaTruyCapKhach VARCHAR(64)")


def _migrate_price_history(conn):
    """Migrate LichSuGia to Price_History with valid_from/valid_to."""
    # Check if Price_History table exists
    tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    if "Price_History" not in tables:
        return
    
    # Check if migration already done
    if conn.execute("SELECT COUNT(*) FROM Price_History").fetchone()[0] > 0:
        return
    
    # Migrate data from LichSuGia to Price_History
    old_records = conn.execute("SELECT * FROM LichSuGia ORDER BY NgayThayDoi").fetchall()
    
    for record in old_records:
        ma_sp = record[1]
        gia_moi = record[3]
        ngay_thay_doi = record[4]
        ghi_chu = record[5]
        
        # Insert into Price_History
        conn.execute(
            """INSERT INTO Price_History (MaSanPham, GiaTri, Valid_From, Valid_To, GhiChu)
               VALUES (?, ?, ?, ?, ?)""",
            (ma_sp, gia_moi, ngay_thay_doi, None, ghi_chu or "Migrated from LichSuGia")
        )
    
    conn.commit()


def _migrate_dia_chi_khach_hang(conn):
    """Create DiaChiKhachHang table if not exists."""
    tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    if "DiaChiKhachHang" in tables:
        return
    
    conn.execute("""
        CREATE TABLE IF NOT EXISTS DiaChiKhachHang (
            MaDiaChi INTEGER PRIMARY KEY AUTOINCREMENT,
            MaNguoiDung INTEGER NOT NULL,
            TenNguoiNhan VARCHAR(100),
            SoDienThoai VARCHAR(15),
            DiaChi VARCHAR(255) NOT NULL,
            LaMacDinh INTEGER DEFAULT 0,
            NgayTao DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (MaNguoiDung) REFERENCES NguoiDung(MaNguoiDung)
        )
    """)
    conn.commit()


def _migrate_product_images(conn):
    """Create Product_Images table if not exists."""
    tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    if "Product_Images" in tables:
        return
    
    conn.execute("""
        CREATE TABLE IF NOT EXISTS Product_Images (
            MaAnh INTEGER PRIMARY KEY AUTOINCREMENT,
            MaSanPham INTEGER NOT NULL,
            URL VARCHAR(500) NOT NULL,
            LaChinh INTEGER DEFAULT 0,
            ThuTu INTEGER DEFAULT 0,
            NgayTao DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (MaSanPham) REFERENCES SanPham(MaSanPham)
        )
    """)
    conn.commit()


def _migrate_banners(conn):
    """Create Banners table if not exists."""
    tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    if "Banners" in tables:
        return
    
    conn.execute("""
        CREATE TABLE IF NOT EXISTS Banners (
            MaBanner INTEGER PRIMARY KEY AUTOINCREMENT,
            TieuDe VARCHAR(255),
            MoTa TEXT,
            URL VARCHAR(500) NOT NULL,
            Link VARCHAR(500),
            TrangThai VARCHAR(20) DEFAULT 'hoat_dong',
            ThuTu INTEGER DEFAULT 0,
            NgayTao DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()


def _migrate_bang_gia(conn):
    """Create BangGia table if not exists."""
    tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    if "BangGia" in tables:
        return
    
    conn.execute("""
        CREATE TABLE IF NOT EXISTS BangGia (
            MaBangGia INTEGER PRIMARY KEY AUTOINCREMENT,
            MaSanPham INTEGER NOT NULL,
            GiaBan DECIMAL(15,2) NOT NULL,
            NgayApDung DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            NgayKetThuc DATETIME,
            IsActive INTEGER DEFAULT 1,
            NgayTao DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (MaSanPham) REFERENCES SanPham(MaSanPham)
        )
    """)
    conn.commit()


def _migrate_user_profile_fields(conn):
    """Add profile fields to NguoiDung table if not exists."""
    cols = {row[1] for row in conn.execute("PRAGMA table_info(NguoiDung)").fetchall()}
    if "Avatar" not in cols:
        conn.execute("ALTER TABLE NguoiDung ADD COLUMN Avatar VARCHAR(255) DEFAULT 'default-avatar.png'")
    if "GioiTinh" not in cols:
        conn.execute("ALTER TABLE NguoiDung ADD COLUMN GioiTinh VARCHAR(10) DEFAULT 'Khác'")
    if "NgaySinh" not in cols:
        conn.execute("ALTER TABLE NguoiDung ADD COLUMN NgaySinh DATE")
    conn.commit()


def seed_data(conn):
    users = [
        ("Quản trị viên", "admin@ecommerce.vn", "admin123", "0901000001", "admin"),
        ("Nguyễn Văn Bán", "shop@ecommerce.vn", "shop123", "0902000002", "chu_cua_hang"),
        ("Trần Thị Mua", "customer@ecommerce.vn", "customer123", "0903000003", "khach_hang"),
        ("Giao Hàng Nhanh", "ship@ecommerce.vn", "ship123", "0904000004", "giao_nhan"),
        ("Chủ cửa hàng 2", "shop2@ecommerce.vn", "shop123", "0905000005", "chu_cua_hang"),
    ]
    
    for name, email, pwd, phone, role in users:
        conn.execute(
            "INSERT INTO NguoiDung (HoTen, Email, MatKhau, SoDienThoai, VaiTro) VALUES (?, ?, ?, ?, ?)",
            (name, email, generate_password_hash(pwd), phone, role),
        )

    conn.execute(
        "INSERT INTO CuaHang (TenCuaHang, DiaChi, MoTa, MaNguoiDung) VALUES (?, ?, ?, ?)",
        ("Gia Dụng Pro", "123 Nguyễn Huệ, Q1, TP.HCM", "Chuyên đồ gia dụng cao cấp", 2),
    )
    conn.execute(
        "INSERT INTO CuaHang (TenCuaHang, DiaChi, MoTa, MaNguoiDung) VALUES (?, ?, ?, ?)",
        ("Nhà Xinh Store", "456 Lê Lợi, Q3, TP.HCM", "Đồ gia dụng giá tốt", 5),
    )

    conn.execute(
        "INSERT INTO DonViGiaoNhan (TenDonVi, DiaChi, SoDienThoai, Email, MaNguoiDung) VALUES (?, ?, ?, ?, ?)",
        ("Giao Hàng Nhanh", "789 Võ Văn Tần, Q3, TP.HCM", "19001234", "ship@ecommerce.vn", 4),
    )

    categories = [
        ("Nồi & Chảo", "noi-chao", "Nồi, chảo các loại"),
        ("Bình & Ly", "binh-ly", "Bình nước, ly uống"),
        ("Dụng cụ nhà bếp", "dung-cu-nha-bep", "Dao, thớt, xẻng..."),
        ("Đồ dùng phòng tắm", "phong-tam", "Khăn, kệ, phụ kiện"),
        ("Đồ trang trí", "trang-tri", "Trang trí nhà cửa"),
        ("Nồi chiên không dầu", "noi-chien-khong-dau", "Nồi chiên không dầu đa năng"),
        ("Bếp từ", "bep-tu", "Bếp từ hiện đại"),
        ("Máy hút bụi", "may-hut-bui", "Máy hút bụi gia đình"),
        ("Quạt hơi nước", "quat-hoi-nuoc", "Quạt hơi nước làm mát"),
    ]
    for name, slug, desc in categories:
        conn.execute(
            "INSERT INTO DanhMuc (TenDanhMuc, Slug, MoTa) VALUES (?, ?, ?)",
            (name, slug, desc),
        )

    products = [
        # Nồi & Chảo
        ("Nồi inox 3 đáy Sunhouse", "Nồi inox cao cấp, chống dính, dùng được mọi loại bếp", 450000, 500000, 50, "noi-inox-sunhouse", 1, 1),
        ("Chảo chống dính Elmich", "Chảo chống dính 28cm, tay cầm chống nóng", 320000, 380000, 80, "chao-chong-dinh-elmich", 1, 1),
        
        # Bình & Ly
        ("Bình giữ nhiệt Lock&Lock 1L", "Giữ nhiệt 12 giờ, inox 304", 280000, 350000, 100, "binh-giu-nhiet-locklock", 2, 1),
        ("Ly thủy tinh cao cấp 6 cái", "Ly uống nước, thiết kế sang trọng", 89000, 120000, 120, "ly-thuy-tinh-6-cai", 2, 2),
        
        # Dụng cụ nhà bếp
        ("Bộ dao thớt 5 món", "Dao inox, thớt gỗ tre, đủ dụng cụ nhà bếp", 199000, 250000, 60, "bo-dao-thot-5-mon", 3, 1),
        ("Bộ hộp thủy tinh 5 chiếc", "Hộp đựng thực phẩm, vào lò vi sóng được", 220000, 260000, 70, "bo-hop-thuy-tinh", 3, 1),
        
        # Đồ dùng phòng tắm
        ("Kệ treo nhà tắm inox", "Kệ 2 tầng chống gỉ, lắp không cần khoan", 150000, 180000, 40, "ke-treo-nha-tam", 4, 1),
        ("Khăn tắm cotton cao cấp", "Khăn bông mềm, thấm hút tốt", 180000, 220000, 90, "khan-tam-cotton", 4, 2),
        
        # Đồ trang trí
        ("Đèn trang trí phòng khách", "Đèn LED trang trí, 3 chế độ sáng", 350000, 420000, 25, "den-trang-tri-phong-khach", 5, 2),
        
        # Nồi chiên không dầu
        ("Nồi chiên không dầu Philips HD9650", "Nồi chiên không dầu 4.2L, công suất 2225W", 2890000, 3200000, 30, "noi-chien-philips-hd9650", 6, 1),
        ("Nồi chiên không dầu Xiaomi Mi Smart Air Fryer", "Nồi chiên không dầu 3.5L, điều khiển qua app", 1590000, 1800000, 45, "noi-chien-xiaomi-smart", 6, 1),
        ("Nồi chiên không dầu Sharp KS-72T", "Nồi chiên không dầu 2.4L, giá rẻ", 890000, 1100000, 60, "noi-chien-sharp-ks72t", 6, 2),
        
        # Bếp từ
        ("Bếp từ đôi Sunhouse SHD8606", "Bếp từ đôi, điều khiển cảm ứng", 1290000, 1500000, 25, "bep-tu-doi-sunhouse", 7, 1),
        ("Bếp từ đơn Midea MI-T21", "Bếp từ đơn, công suất 2000W", 690000, 850000, 40, "bep-tu-don-midea", 7, 1),
        ("Bếp từ 3 vùng nấu Bosch PPI82560", "Bếp từ 3 vùng, cao cấp", 8900000, 9500000, 15, "bep-tu-3-vung-bosch", 7, 2),
        
        # Máy hút bụi
        ("Máy hút bụi cầm tay Xiaomi Deerma", "Máy hút bụi cầm tay, hút ẩm được", 890000, 1100000, 35, "may-hut-bui-xiaomi-deerma", 8, 1),
        ("Máy hút bụi robot Ecovacs Deebot N79", "Robot hút bụi tự động", 3500000, 4000000, 20, "robot-hut-bui-ecovacs", 8, 1),
        ("Máy hút bụi Electrolux ZB3230P", "Máy hút bụi gia đình, công suất 1800W", 2200000, 2600000, 30, "may-hut-bui-electrolux", 8, 2),
        
        # Quạt hơi nước
        ("Quạt hơi nước Sunhouse SHD7720", "Quạt hơi nước 3 chế độ gió", 890000, 1100000, 50, "quat-hoi-nuoc-sunhouse", 9, 1),
        ("Quạt hơi nước Sharp PJ-A36MY", "Quạt hơi nước ion lọc không khí", 2500000, 2900000, 25, "quat-hoi-nuoc-sharp", 9, 1),
        ("Quạt hơi nước Kangaroo KG77", "Quạt hơi nước làm mát nhanh", 1200000, 1500000, 40, "quat-hoi-nuoc-kangaroo", 9, 2),
    ]
    
    for name, desc, price, orig, stock, slug, cat, shop in products:
        conn.execute(
            """INSERT INTO SanPham (TenSanPham, MoTa, GiaBan, GiaGoc, SoLuongTon, Slug,
               MetaTitle, MetaDescription, MaDanhMuc, MaCuaHang)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (name, desc, price, orig, stock, slug, name, desc, cat, shop),
        )

    conn.execute(
        """INSERT INTO KhuyenMai (TenKhuyenMai, PhanTramGiam, NgayBatDau, NgayKetThuc, MaSanPham)
           VALUES (?, ?, date('now', '-7 days'), date('now', '+30 days'), NULL)""",
        ("Khuyến mãi mùa hè", 10),
    )
    conn.execute(
        """INSERT INTO KhuyenMai (TenKhuyenMai, PhanTramGiam, NgayBatDau, NgayKetThuc, MaSanPham)
           VALUES (?, ?, date('now'), date('now', '+14 days'), ?)""",
        ("Flash sale nồi chiên Philips", 15, 11),
    )
    conn.execute(
        """INSERT INTO KhuyenMai (TenKhuyenMai, PhanTramGiam, NgayBatDau, NgayKetThuc, MaSanPham)
           VALUES (?, ?, date('now'), date('now', '+21 days'), ?)""",
        ("Giảm giá máy hút bụi Xiaomi", 20, 14),
    )

    # Vouchers
    conn.execute(
        """INSERT INTO Voucher (MaVoucher, TenVoucher, LoaiGiam, GiaTriGiam, DonToiThieu, SoLuong, NgayBatDau, NgayKetThuc)
           VALUES (?, ?, ?, ?, ?, ?, date('now'), date('now', '+30 days'))""",
        ("GIAM50K", "Giảm 50.000đ cho đơn trên 500k", "tien_mat", 50000, 500000, 100),
    )
    conn.execute(
        """INSERT INTO Voucher (MaVoucher, TenVoucher, LoaiGiam, GiaTriGiam, DonToiThieu, SoLuong, NgayBatDau, NgayKetThuc)
           VALUES (?, ?, ?, ?, ?, ?, date('now'), date('now', '+30 days'))""",
        ("GIAM10", "Giảm 10% cho đơn trên 1 triệu", "phan_tram", 10, 1000000, 50),
    )
    conn.execute(
        """INSERT INTO Voucher (MaVoucher, TenVoucher, LoaiGiam, GiaTriGiam, DonToiThieu, SoLuong, NgayBatDau, NgayKetThuc)
           VALUES (?, ?, ?, ?, ?, ?, date('now'), date('now', '+30 days'))""",
        ("FREESHIP", "Miễn phí vận chuyển", "tien_mat", 30000, 0, -1),
    )

    conn.commit()
