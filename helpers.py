import re
import unicodedata
from functools import wraps
from flask import session, redirect, url_for, flash, request

ORDER_STATUS = {
    "pending_payment": "Chờ thanh toán QR (PENDING_PAYMENT)",
    "paid": "Đã thanh toán (PAID)",
    "cancelled": "Đã hủy — hết hạn (CANCELLED)",
    "cho_xac_nhan": "Chờ xác nhận",
    "da_xac_nhan": "Đã xác nhận",
    "dang_xu_ly": "Đang xử lý (PROCESSING)",
    "dang_chuan_bi": "Đang chuẩn bị (PREPARING)",
    "dang_giao": "Đang giao (SHIPPING)",
    "da_giao": "Đã giao (DELIVERED)",
    "da_huy": "Đã hủy",
    "cho_thanh_toan": "Chờ thanh toán",
    "da_thanh_toan": "Đã thanh toán",
}

PAYMENT_METHODS = {
    "COD": "Thanh toán khi nhận hàng (COD)",
    "chuyen_khoan": "Chuyển khoản qua QR",
}

ROLE_LABELS = {
    "admin": "Quản trị viên",
    "chu_cua_hang": "Chủ cửa hàng",
    "khach_hang": "Khách hàng",
    "giao_nhan": "Đơn vị giao nhận",
}


def slugify(text):
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^\w\s-]", "", text.lower())
    return re.sub(r"[-\s]+", "-", text).strip("-")


def login_required(roles=None):
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            if not session.get("user_id"):
                flash("Vui lòng đăng nhập để tiếp tục.", "warning")
                return redirect(url_for("auth.login", next=request.url))
            if roles and session.get("user", {}).get("VaiTro") not in roles:
                flash("Bạn không có quyền truy cập chức năng này.", "danger")
                return redirect(url_for("shop.index"))
            return f(*args, **kwargs)
        return wrapped
    return decorator


def vendor_required(f):
    """Decorator to ensure vendor can only access their own store data."""
    @wraps(f)
    def wrapped(*args, **kwargs):
        if not session.get("user_id"):
            flash("Vui lòng đăng nhập để tiếp tục.", "warning")
            return redirect(url_for("auth.login", next=request.url))
        
        if session.get("user", {}).get("VaiTro") != "chu_cua_hang":
            flash("Chỉ chủ cửa hàng mới có quyền truy cập.", "danger")
            return redirect(url_for("shop.index"))
        
        return f(*args, **kwargs)
    return wrapped


def format_currency(value):
    try:
        return f"{int(float(value)):,}".replace(",", ".") + "đ"
    except (TypeError, ValueError):
        return "0đ"


def to_dict_safe(row):
    """Safely converts sqlite3.Row or dict-like object into a standard Python dict."""
    if row is None:
        return {}
    if isinstance(row, dict):
        return row
    if hasattr(row, 'keys'): # Handles sqlite3.Row
        return dict(row)
    return {}

def get_product_id_safe(product_row):
    """Safely extract product ID from dict, sqlite3.Row, or model instance."""
    if not product_row:
        return None
        
    p_dict = to_dict_safe(product_row)
    if p_dict:
        for key in ['MaSanPham', 'id', 'san_pham_id', 'id_san_pham', 'masanpham', 'ID']:
            if key in p_dict and p_dict[key] is not None:
                return p_dict[key]

    # If it's an object/model instance
    for attr in ['MaSanPham', 'id', 'san_pham_id', 'id_san_pham']:
        if hasattr(product_row, attr):
            val = getattr(product_row, attr)
            if val is not None:
                return val

    # Fallback to index access if available
    try:
        return product_row[0]
    except Exception:
        return None

def get_effective_price(product_row, promotions=None):
    """Safely calculate product price without throwing AttributeError on sqlite3.Row."""
    try:
        p_dict = to_dict_safe(product_row)
        
        # 1. Extract base price safely
        price = 0.0
        if p_dict:
            price = (p_dict.get('Gia') or 
                     p_dict.get('gia_ban') or 
                     p_dict.get('gia') or 
                     p_dict.get('GiaBan') or 0.0)
        elif hasattr(product_row, 'gia_ban'):
            price = getattr(product_row, 'gia_ban', 0.0)
        elif hasattr(product_row, 'gia'):
            price = getattr(product_row, 'gia', 0.0)

        # 2. Extract product ID
        product_id = get_product_id_safe(product_row)
        if not product_id:
            return float(price or 0.0), 0.0

        # 3. Get current price from database function if available
        try:
            from database.db import get_current_price
            current_price = get_current_price(product_id)
            final_price = float(current_price) if current_price else float(price or 0.0)
        except Exception:
            final_price = float(price or 0.0)

        # 4. Handle promotions if provided
        if promotions is None:
            try:
                from database.db import query_all
                today = __import__("datetime").date.today().isoformat()
                promotions = query_all(
                    """SELECT * FROM KhuyenMai
                       WHERE TrangThai = 'hoat_dong'
                       AND date(NgayBatDau) <= date(?)
                       AND date(NgayKetThuc) >= date(?)
                       AND (MaSanPham IS NULL OR MaSanPham = ?)""",
                    (today, today, product_id),
                )
            except Exception:
                promotions = []
        
        discount = 0
        for promo in promotions:
            promo_dict = to_dict_safe(promo)
            promo_discount = promo_dict.get('PhanTramGiam', 0) if promo_dict else 0
            discount = max(discount, int(promo_discount) if promo_discount else 0)
        
        if discount:
            return round(final_price * (100 - discount) / 100, 0), discount
        return final_price, 0

    except Exception as e:
        print(f"Error in get_effective_price: {str(e)}")
        return 0.0, 0
