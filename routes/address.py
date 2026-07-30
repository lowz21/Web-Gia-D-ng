"""Address management routes for customer shipping addresses."""
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from database.db import query_one, query_all, execute, get_db
from helpers import login_required

address_bp = Blueprint("address", __name__)


@login_required(roles=["khach_hang"])
@address_bp.route("/dia-chi", methods=["GET", "POST"])
def manage_addresses():
    """Quản lý địa chỉ giao hàng của khách hàng."""
    user_id = session["user_id"]
    
    if request.method == "POST":
        # Thêm địa chỉ mới
        ten_nhan = request.form.get("ten_nhan", "").strip()
        sdt = request.form.get("sdt", "").strip()
        dia_chi = request.form.get("dia_chi", "").strip()
        la_mac_dinh = request.form.get("la_mac_dinh") == "on"
        
        if not dia_chi:
            flash("Vui lòng nhập địa chỉ.", "warning")
            return redirect(url_for("address.manage_addresses"))
        
        conn = get_db()
        try:
            # Nếu chọn làm mặc định, hủy mặc định của các địa chỉ khác
            if la_mac_dinh:
                conn.execute(
                    "UPDATE DiaChiKhachHang SET LaMacDinh = 0 WHERE MaNguoiDung = ?",
                    (user_id,)
                )
            
            # Thêm địa chỉ mới
            conn.execute(
                """INSERT INTO DiaChiKhachHang (MaNguoiDung, TenNguoiNhan, SoDienThoai, DiaChi, LaMacDinh)
                   VALUES (?, ?, ?, ?, ?)""",
                (user_id, ten_nhan, sdt, dia_chi, 1 if la_mac_dinh else 0)
            )
            conn.commit()
            flash("Đã thêm địa chỉ mới.", "success")
        finally:
            conn.close()
        
        return redirect(url_for("address.manage_addresses"))
    
    # GET: Hiển thị danh sách địa chỉ
    addresses = query_all(
        "SELECT * FROM DiaChiKhachHang WHERE MaNguoiDung = ? ORDER BY LaMacDinh DESC, NgayTao DESC",
        (user_id,)
    )
    
    return render_template("address/manage_addresses.html", addresses=addresses)


@login_required(roles=["khach_hang"])
@address_bp.route("/dia-chi/<int:address_id>/mac-dinh", methods=["POST"])
def set_default_address(address_id):
    """Đặt địa chỉ làm mặc định."""
    user_id = session["user_id"]
    
    # Kiểm tra địa chỉ thuộc về user
    address = query_one(
        "SELECT * FROM DiaChiKhachHang WHERE MaDiaChi = ? AND MaNguoiDung = ?",
        (address_id, user_id)
    )
    
    if not address:
        flash("Không tìm thấy địa chỉ.", "danger")
        return redirect(url_for("address.manage_addresses"))
    
    conn = get_db()
    try:
        # Hủy mặc định của tất cả địa chỉ
        conn.execute(
            "UPDATE DiaChiKhachHang SET LaMacDinh = 0 WHERE MaNguoiDung = ?",
            (user_id,)
        )
        # Đặt địa chỉ này làm mặc định
        conn.execute(
            "UPDATE DiaChiKhachHang SET LaMacDinh = 1 WHERE MaDiaChi = ?",
            (address_id,)
        )
        conn.commit()
        flash("Đã đặt địa chỉ làm mặc định.", "success")
    finally:
        conn.close()
    
    return redirect(url_for("address.manage_addresses"))


@login_required(roles=["khach_hang"])
@address_bp.route("/dia-chi/<int:address_id>/xoa", methods=["POST"])
def delete_address(address_id):
    """Xóa địa chỉ."""
    user_id = session["user_id"]
    
    # Kiểm tra địa chỉ thuộc về user
    address = query_one(
        "SELECT * FROM DiaChiKhachHang WHERE MaDiaChi = ? AND MaNguoiDung = ?",
        (address_id, user_id)
    )
    
    if not address:
        flash("Không tìm thấy địa chỉ.", "danger")
        return redirect(url_for("address.manage_addresses"))
    
    conn = get_db()
    try:
        conn.execute("DELETE FROM DiaChiKhachHang WHERE MaDiaChi = ?", (address_id,))
        conn.commit()
        flash("Đã xóa địa chỉ.", "success")
    finally:
        conn.close()
    
    return redirect(url_for("address.manage_addresses"))


@login_required(roles=["khach_hang"])
@address_bp.route("/api/dia-chi", methods=["GET"])
def api_addresses():
    """API trả về danh sách địa chỉ của user."""
    user_id = session["user_id"]
    addresses = query_all(
        "SELECT * FROM DiaChiKhachHang WHERE MaNguoiDung = ? ORDER BY LaMacDinh DESC, NgayTao DESC",
        (user_id,)
    )
    
    addresses_list = []
    for addr in addresses:
        addresses_list.append({
            "id": addr["MaDiaChi"],
            "ten_nhan": addr["TenNguoiNhan"],
            "sdt": addr["SoDienThoai"],
            "dia_chi": addr["DiaChi"],
            "la_mac_dinh": bool(addr["LaMacDinh"])
        })
    
    return jsonify({"addresses": addresses_list})


@login_required(roles=["khach_hang"])
@address_bp.route("/api/dia-chi/mac-dinh", methods=["GET"])
def api_default_address():
    """API trả về địa chỉ mặc định của user."""
    user_id = session["user_id"]
    address = query_one(
        "SELECT * FROM DiaChiKhachHang WHERE MaNguoiDung = ? AND LaMacDinh = 1",
        (user_id,)
    )
    
    if address:
        return jsonify({
            "id": address["MaDiaChi"],
            "ten_nhan": address["TenNguoiNhan"],
            "sdt": address["SoDienThoai"],
            "dia_chi": address["DiaChi"]
        })
    
    return jsonify({"address": None})
