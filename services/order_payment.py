"""Thanh toán QR, hết hạn đơn và webhook."""
import os
import secrets
from datetime import datetime, timedelta

from database.db import get_db, query_one

PAYMENT_DEADLINE_MINUTES = int(os.getenv("PAYMENT_DEADLINE_MINUTES", "15"))

VIETQR_BANK_CODE = os.getenv("VIETQR_BANK_CODE", "MB")
VIETQR_ACCOUNT_NO = os.getenv("VIETQR_ACCOUNT_NO", "00931222")
VIETQR_ACCOUNT_NAME = os.getenv("VIETQR_ACCOUNT_NAME", "HA MINH TRI")


def payment_deadline_from_now():
    return datetime.now() + timedelta(minutes=PAYMENT_DEADLINE_MINUTES)


def new_guest_access_token():
    return secrets.token_urlsafe(32)


def build_vietqr_url(order_id, amount):
    amount_int = int(float(amount))
    add_info = f"DH{order_id}"
    return (
        f"https://img.vietqr.io/image/{VIETQR_BANK_CODE}-{VIETQR_ACCOUNT_NO}-compact2.png"
        f"?amount={amount_int}&addInfo={add_info}&accountName={VIETQR_ACCOUNT_NAME.replace(' ', '%20')}"
    )


def parse_order_id_from_transfer_content(content):
    if not content:
        return None
    text = str(content).upper().strip()
    if text.startswith("DH"):
        try:
            return int(text[2:].split()[0].strip(".,;"))
        except ValueError:
            return None
    return None


def order_accessible(order, user_id=None, guest_token=None):
    if not order:
        return False
    o = dict(order) if not isinstance(order, dict) else order
    if user_id and o.get("MaKhachHang") == user_id:
        return True
    if guest_token and o.get("MaTruyCapKhach") and secrets.compare_digest(
        o["MaTruyCapKhach"], guest_token
    ):
        return True
    return False


def restore_order_stock(conn, order_id):
    items = conn.execute(
        "SELECT MaSanPham, SoLuong FROM ChiTietDonHang WHERE MaDonHang = ?",
        (order_id,),
    ).fetchall()
    for item in items:
        conn.execute(
            "UPDATE SanPham SET SoLuongTon = SoLuongTon + ? WHERE MaSanPham = ?",
            (item["SoLuong"], item["MaSanPham"]),
        )


def cancel_pending_order(conn, order_id, old_status, note="Hết hạn thanh toán"):
    restore_order_stock(conn, order_id)
    conn.execute(
        "UPDATE DonHang SET TrangThai = 'cancelled' WHERE MaDonHang = ?",
        (order_id,),
    )
    conn.execute(
        "UPDATE ThanhToan SET TrangThai = 'da_huy' WHERE MaDonHang = ?",
        (order_id,),
    )
    conn.execute(
        """INSERT INTO LichSuDonHang (MaDonHang, TrangThaiCu, TrangThaiMoi, GhiChu)
           VALUES (?, ?, 'cancelled', ?)""",
        (order_id, old_status, note),
    )


def cancel_expired_pending_orders():
    """Hủy các đơn pending_payment quá hạn. Trả về số đơn đã hủy."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = get_db()
    try:
        rows = conn.execute(
            """SELECT MaDonHang, TrangThai FROM DonHang
               WHERE TrangThai = 'pending_payment'
               AND HanThanhToan IS NOT NULL
               AND datetime(HanThanhToan) <= datetime(?)""",
            (now,),
        ).fetchall()
        for row in rows:
            cancel_pending_order(conn, row["MaDonHang"], row["TrangThai"])
        conn.commit()
        return len(rows)
    finally:
        conn.close()


def complete_order_payment(order_id, note="Webhook xác nhận thanh toán"):
    order = query_one("SELECT * FROM DonHang WHERE MaDonHang = ?", (order_id,))
    if not order:
        return False, "Không tìm thấy đơn hàng"
    if order["TrangThai"] == "paid":
        return True, "already_paid"
    if order["TrangThai"] not in ("pending_payment",):
        return False, "Trạng thái đơn không hợp lệ để thanh toán"

    conn = get_db()
    try:
        old = order["TrangThai"]
        conn.execute(
            "UPDATE DonHang SET TrangThai = 'paid' WHERE MaDonHang = ?",
            (order_id,),
        )
        conn.execute(
            """UPDATE ThanhToan SET TrangThai = 'da_thanh_toan',
               NgayThanhToan = CURRENT_TIMESTAMP WHERE MaDonHang = ?""",
            (order_id,),
        )
        conn.execute(
            """INSERT INTO LichSuDonHang (MaDonHang, TrangThaiCu, TrangThaiMoi, GhiChu)
               VALUES (?, ?, 'paid', ?)""",
            (order_id, old, note),
        )
        if order["MaKhachHang"]:
            conn.execute(
                """INSERT INTO ThongBao (MaNguoiDung, TieuDe, NoiDung) VALUES (?, ?, ?)""",
                (
                    order["MaKhachHang"],
                    "Thanh toán thành công",
                    f"Đơn hàng #{order_id} đã được thanh toán qua QR.",
                ),
            )
        conn.commit()
        return True, "ok"
    finally:
        conn.close()


def order_payment_payload(order, items):
    o = dict(order) if not isinstance(order, dict) else order
    expires = o.get("HanThanhToan")
    expires_iso = None
    if expires:
        if isinstance(expires, str):
            expires_iso = expires.replace(" ", "T")
        else:
            expires_iso = expires.isoformat()
    return {
        "id": o["MaDonHang"],
        "total": float(o["TongTien"]),
        "total_formatted": None,
        "status": o["TrangThai"],
        "expires_at": expires_iso,
        "payment_method": o["PhuongThucThanhToan"],
        "guest_token": o.get("MaTruyCapKhach"),
        "qr_url": build_vietqr_url(o["MaDonHang"], o["TongTien"])
        if o["PhuongThucThanhToan"] == "chuyen_khoan"
        else None,
        "items": [
            {
                "name": i["TenSanPham"],
                "quantity": i["SoLuong"],
                "subtotal": float(i["ThanhTien"]),
            }
            for i in items
        ],
    }
