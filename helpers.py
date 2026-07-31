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


def get_effective_price(product_row, promotions=None):
    from database.db import get_current_price
    
    # Try to get current price from BangGia table first
    current_price = get_current_price(product_row["MaSanPham"])
    
    # Fallback to GiaBan if BangGia doesn't have price
    if current_price is None:
        price = float(product_row["GiaBan"])
    else:
        price = float(current_price)
    
    if promotions is None:
        from database.db import query_all
        today = __import__("datetime").date.today().isoformat()
        promotions = query_all(
            """SELECT * FROM KhuyenMai
               WHERE TrangThai = 'hoat_dong'
               AND date(NgayBatDau) <= date(?)
               AND date(NgayKetThuc) >= date(?)
               AND (MaSanPham IS NULL OR MaSanPham = ?)""",
            (today, today, product_row["MaSanPham"]),
        )
    discount = 0
    for promo in promotions:
        discount = max(discount, int(promo["PhanTramGiam"]))
    if discount:
        return round(price * (100 - discount) / 100, 0), discount
    return price, 0
