import re
import unicodedata
import logging
import math
from functools import wraps
from flask import session, redirect, url_for, flash, request

logger = logging.getLogger(__name__)

# Store coordinates (Ho Chi Minh City center)
STORE_LAT = 10.7769
STORE_LNG = 106.7009

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
    """Safely converts sqlite3.Row, dict, or tuple-like object into a pure Python dict."""
    if row is None:
        return {}
    if isinstance(row, dict):
        return row
    try:
        # Convert sqlite3.Row to standard dict
        return dict(row)
    except (TypeError, ValueError):
        return {}

def get_effective_price(product_row):
    """Safely computes price without ever calling .get() directly on sqlite3.Row."""
    try:
        if not product_row:
            return 0.0, 0.0

        # 1. Safely convert to dictionary first
        p_dict = to_dict_safe(product_row)

        # 2. Extract price if dictionary conversion succeeded
        if p_dict:
            # Check known price column names
            price_keys = ['gia_ban', 'Gia', 'gia', 'GiaBan', 'DonGia', 'GiaNiemYet', 'GiaKhuyenMai', 'price']
            for key in price_keys:
                if key in p_dict and p_dict[key] is not None:
                    try:
                        val = float(p_dict[key])
                        if val > 0:
                            return val, 0.0
                    except (ValueError, TypeError):
                        continue

            # Fallback search for any key containing 'gia' or 'price'
            for key, val in p_dict.items():
                if any(k in str(key).lower() for k in ['gia', 'price']):
                    if val is not None:
                        try:
                            val_float = float(val)
                            if val_float > 0:
                                return val_float, 0.0
                        except (ValueError, TypeError):
                            continue

        # 3. Extract price if it is an ORM Model / Object with attributes
        for attr in ['gia_ban', 'Gia', 'gia', 'GiaBan', 'DonGia', 'price']:
            if hasattr(product_row, attr):
                val = getattr(product_row, attr)
                if val is not None:
                    try:
                        val_float = float(val)
                        if val_float > 0:
                            return val_float, 0.0
                    except (ValueError, TypeError):
                        continue

        return 0.0, 0.0

    except Exception as e:
        logger.error(f"Error in get_effective_price: {str(e)}")
        return 0.0, 0.0


def calculate_distance_km(lat1, lon1, lat2, lon2):
    """Calculates distance in KM between two geographic coordinates using Haversine formula."""
    try:
        if None in (lat1, lon1, lat2, lon2):
            return 0.0
        R = 6371.0  # Earth radius in km
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = (math.sin(dlat / 2) ** 2 +
             math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2)
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        return R * c
    except Exception:
        return 0.0


def calculate_shipping_fee(distance_km):
    """Calculates shipping fee based on distance tier."""
    if distance_km <= 5.0:
        return 15000  # Under 5km: 15.000đ
    elif distance_km <= 15.0:
        return 30000  # 5-15km: 30.000đ
    elif distance_km <= 50.0:
        return 50000  # 15-50km: 50.000đ
    else:
        return 80000  # Inter-provincial / long distance: 80.000đ
