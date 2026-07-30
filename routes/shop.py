from datetime import date
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from database.db import query_one, query_all, execute, get_db
from helpers import login_required, ORDER_STATUS, PAYMENT_METHODS, format_currency, get_effective_price
from services.order_payment import (
    PAYMENT_DEADLINE_MINUTES,
    build_vietqr_url,
    new_guest_access_token,
    payment_deadline_from_now,
    order_accessible,
    cancel_pending_order,
)

shop_bp = Blueprint("shop", __name__)


def ensure_cart(user_id):
    cart = query_one("SELECT * FROM GioHang WHERE MaNguoiDung = ?", (user_id,))
    if not cart:
        cid = execute("INSERT INTO GioHang (MaNguoiDung) VALUES (?)", (user_id,))
        return {"MaGioHang": cid}
    return cart


@shop_bp.route("/")
def index():
    """Homepage - Landing page với banners và featured categories"""
    # Banners for slider
    banners = query_all(
        """SELECT * FROM Banners 
           WHERE TrangThai = 'hoat_dong' 
           ORDER BY ThuTu ASC"""
    )
    
    # Featured categories
    categories = query_all("SELECT * FROM DanhMuc ORDER BY TenDanhMuc LIMIT 8")
    
    # Featured products (sản phẩm nổi bật)
    featured_products = query_all(
        """SELECT sp.*, dm.TenDanhMuc, dm.Slug as DanhMucSlug, ch.TenCuaHang,
           pi.URL as PrimaryImageURL
           FROM SanPham sp
           JOIN DanhMuc dm ON sp.MaDanhMuc = dm.MaDanhMuc
           JOIN CuaHang ch ON sp.MaCuaHang = ch.MaCuaHang
           LEFT JOIN Product_Images pi ON sp.MaSanPham = pi.MaSanPham AND pi.LaChinh = 1
           WHERE sp.TrangThai = 'hoat_dong'
           ORDER BY sp.MaSanPham DESC LIMIT 8"""
    )
    
    # Promotions
    promos = query_all(
        """SELECT * FROM KhuyenMai 
           WHERE TrangThai = 'hoat_dong' 
           AND date(NgayBatDau) <= date('now') AND date(NgayKetThuc) >= date('now')
           ORDER BY PhanTramGiam DESC LIMIT 4"""
    )
    
    return render_template(
        "shop/homepage.html",
        banners=banners,
        categories=categories,
        products=featured_products,
        promos=promos,
        format_currency=format_currency,
        get_effective_price=get_effective_price,
    )


@shop_bp.route("/san-pham")
def shop():
    """Shop page - Product listings với filters và pagination"""
    keyword = request.args.get("q", "").strip()
    category_slug = request.args.get("danh_muc", "").strip()
    min_price = request.args.get("min_price")
    max_price = request.args.get("max_price")
    sort_by = request.args.get("sort", "newest")  # newest, price_asc, price_desc
    page = int(request.args.get("page", 1))
    per_page = 12

    sql = """
        SELECT sp.*, dm.TenDanhMuc, dm.Slug as DanhMucSlug, ch.TenCuaHang, pi.URL as PrimaryImageURL
        FROM SanPham sp
        JOIN DanhMuc dm ON sp.MaDanhMuc = dm.MaDanhMuc
        JOIN CuaHang ch ON sp.MaCuaHang = ch.MaCuaHang
        LEFT JOIN Product_Images pi ON sp.MaSanPham = pi.MaSanPham AND pi.LaChinh = 1
        WHERE sp.TrangThai = 'hoat_dong'"""
    params = []

    if keyword:
        sql += " AND (sp.TenSanPham LIKE ? OR sp.MoTa LIKE ? OR sp.MetaKeyword LIKE ?)"
        like = f"%{keyword}%"
        params.extend([like, like, like])
    if category_slug:
        sql += " AND dm.Slug = ?"
        params.append(category_slug)
    if min_price:
        try:
            min_price_val = float(min_price)
            sql += " AND sp.GiaBan >= ?"
            params.append(min_price_val)
        except ValueError:
            pass
    if max_price:
        try:
            max_price_val = float(max_price)
            sql += " AND sp.GiaBan <= ?"
            params.append(max_price_val)
        except ValueError:
            pass

    # Sorting
    if sort_by == "price_asc":
        sql += " ORDER BY sp.GiaBan ASC"
    elif sort_by == "price_desc":
        sql += " ORDER BY sp.GiaBan DESC"
    else:  # newest
        sql += " ORDER BY sp.MaSanPham DESC"

    count_sql = sql.replace(
        "SELECT sp.*, dm.TenDanhMuc, dm.Slug as DanhMucSlug, ch.TenCuaHang, pi.URL as PrimaryImageURL",
        "SELECT COUNT(*) as c",
    )
    # Remove ORDER BY clause from count query
    if "ORDER BY" in count_sql:
        count_sql = count_sql[:count_sql.index("ORDER BY")]
    
    count_result = query_one(count_sql, params)
    total = count_result["c"] if count_result and "c" in count_result else 0

    sql += " LIMIT ? OFFSET ?"
    params.extend([per_page, (page - 1) * per_page])
    products = query_all(sql, params)

    categories = query_all("SELECT * FROM DanhMuc ORDER BY TenDanhMuc")
    promos = query_all(
        """SELECT * FROM KhuyenMai WHERE TrangThai='hoat_dong'
           AND date(NgayBatDau) <= date('now') AND date(NgayKetThuc) >= date('now')
           AND MaSanPham IS NULL LIMIT 1"""
    )

    return render_template(
        "shop/shop.html",
        products=products,
        categories=categories,
        keyword=keyword,
        cat_slug=cat_slug,
        page=page,
        per_page=per_page,
        total_pages=max(1, (total + per_page - 1) // per_page),
        total=total,
        global_promo=promos[0] if promos else None,
        format_currency=format_currency,
        get_effective_price=get_effective_price,
    )


@shop_bp.route("/san-pham/<slug>")
def product_detail(slug):
    product = query_one(
        """SELECT sp.*, dm.TenDanhMuc, ch.TenCuaHang, ch.DiaChi as DiaChiCuaHang
           FROM SanPham sp
           JOIN DanhMuc dm ON sp.MaDanhMuc = dm.MaDanhMuc
           JOIN CuaHang ch ON sp.MaCuaHang = ch.MaCuaHang
           WHERE sp.Slug = ? AND sp.TrangThai = 'hoat_dong'""",
        (slug,),
    )
    if not product:
        flash("Sản phẩm không tồn tại hoặc đã bị gỡ khỏi hệ thống.", "warning")
        return redirect(url_for("shop.index"))

    reviews = query_all(
        """SELECT dg.*, nd.HoTen FROM DanhGia dg
           JOIN NguoiDung nd ON dg.MaNguoiDung = nd.MaNguoiDung
           WHERE dg.MaSanPham = ? ORDER BY dg.NgayDanhGia DESC""",
        (product["MaSanPham"],),
    )
    avg_rating = query_one(
        "SELECT AVG(SoSao) as avg, COUNT(*) as cnt FROM DanhGia WHERE MaSanPham = ?",
        (product["MaSanPham"],),
    )
    price, discount = get_effective_price(product)
    related = query_all(
        """SELECT sp.* FROM SanPham sp
           WHERE sp.MaDanhMuc = ? AND sp.MaSanPham != ? AND sp.TrangThai = 'hoat_dong'
           LIMIT 4""",
        (product["MaDanhMuc"], product["MaSanPham"]),
    )

    can_review = False
    if session.get("user_id"):
        bought = query_one(
            """SELECT 1 FROM ChiTietDonHang ct
               JOIN DonHang dh ON ct.MaDonHang = dh.MaDonHang
               WHERE ct.MaSanPham = ? AND dh.MaKhachHang = ? AND dh.TrangThai = 'da_giao'""",
            (product["MaSanPham"], session["user_id"]),
        )
        reviewed = query_one(
            "SELECT 1 FROM DanhGia WHERE MaSanPham = ? AND MaNguoiDung = ?",
            (product["MaSanPham"], session["user_id"]),
        )
        can_review = bought and not reviewed

    # Lịch sử đổi giá
    price_history = query_all(
        """SELECT * FROM LichSuGia WHERE MaSanPham = ? ORDER BY NgayThayDoi DESC LIMIT 10""",
        (product["MaSanPham"],),
    )

    # Product images from gallery
    product_images = query_all(
        """SELECT * FROM Product_Images 
           WHERE MaSanPham = ? 
           ORDER BY LaChinh DESC, ThuTu ASC""",
        (product["MaSanPham"],),
    )

    return render_template(
        "shop/product_detail.html",
        product=product,
        reviews=reviews,
        avg_rating=avg_rating,
        effective_price=price,
        discount=discount,
        related=related,
        can_review=can_review,
        price_history=price_history,
        product_images=product_images,
        format_currency=format_currency,
        get_effective_price=get_effective_price,
    )


@shop_bp.route("/gio-hang")
@login_required(roles=["khach_hang"])
def cart():
    cart_row = ensure_cart(session["user_id"])
    items = query_all(
        """SELECT ct.*, sp.TenSanPham, sp.Slug, sp.SoLuongTon, sp.GiaBan, sp.GiaGoc, ch.TenCuaHang
           FROM ChiTietGioHang ct
           JOIN SanPham sp ON ct.MaSanPham = sp.MaSanPham
           JOIN CuaHang ch ON sp.MaCuaHang = ch.MaCuaHang
           WHERE ct.MaGioHang = ?""",
        (cart_row["MaGioHang"],),
    )

    total = 0
    enriched = []
    for item in items:
        price, _ = get_effective_price(item)
        subtotal = price * item["SoLuong"]
        total += subtotal
        d = dict(item)
        d["DonGia"] = price
        d["ThanhTien"] = subtotal
        enriched.append(d)

    return render_template("shop/cart.html", items=enriched, total=total, format_currency=format_currency)


@shop_bp.route("/gio-hang/them", methods=["POST"])
@login_required(roles=["khach_hang"])
def cart_add():
    product_id = int(request.form.get("product_id"))
    qty = max(int(request.form.get("quantity", 1) or 1), 1)

    product = query_one("SELECT * FROM SanPham WHERE MaSanPham = ? AND TrangThai = 'hoat_dong'", (product_id,))
    if not product:
        flash("Sản phẩm không tồn tại.", "danger")
        return redirect(url_for("shop.index"))
    if product["SoLuongTon"] < qty:
        flash("Sản phẩm đã hết hàng hoặc không đủ số lượng.", "warning")
        return redirect(request.referrer or url_for("shop.index"))

    cart_row = ensure_cart(session["user_id"])
    existing = query_one(
        "SELECT * FROM ChiTietGioHang WHERE MaGioHang = ? AND MaSanPham = ?",
        (cart_row["MaGioHang"], product_id),
    )
    if existing:
        new_qty = existing["SoLuong"] + qty
        if new_qty > product["SoLuongTon"]:
            flash("Không đủ hàng trong kho.", "warning")
        else:
            execute(
                "UPDATE ChiTietGioHang SET SoLuong = ? WHERE MaGioHang = ? AND MaSanPham = ?",
                (new_qty, cart_row["MaGioHang"], product_id),
            )
            flash("Đã cập nhật giỏ hàng.", "success")
    else:
        execute(
            "INSERT INTO ChiTietGioHang (MaGioHang, MaSanPham, SoLuong) VALUES (?, ?, ?)",
            (cart_row["MaGioHang"], product_id, qty),
        )
        flash("Đã thêm vào giỏ hàng.", "success")

    return redirect(request.referrer or url_for("shop.cart"))


@shop_bp.route("/gio-hang/cap-nhat", methods=["POST"])
@login_required(roles=["khach_hang"])
def cart_update():
    cart_row = ensure_cart(session["user_id"])
    for key, val in request.form.items():
        if key.startswith("qty_"):
            pid = int(key.replace("qty_", ""))
            qty = max(int(val or 0), 0)
            product = query_one("SELECT * FROM SanPham WHERE MaSanPham = ?", (pid,))
            if qty == 0:
                execute(
                    "DELETE FROM ChiTietGioHang WHERE MaGioHang = ? AND MaSanPham = ?",
                    (cart_row["MaGioHang"], pid),
                )
            elif product:
                if qty > product["SoLuongTon"]:
                    flash(f"Sản phẩm không đủ hàng trong kho.", "warning")
                else:
                    execute(
                        "UPDATE ChiTietGioHang SET SoLuong = ? WHERE MaGioHang = ? AND MaSanPham = ?",
                        (qty, cart_row["MaGioHang"], pid),
                    )
    flash("Cập nhật giỏ hàng thành công.", "success")
    return redirect(url_for("shop.cart"))


@shop_bp.route("/gio-hang/xoa/<int:product_id>", methods=["POST"])
@login_required(roles=["khach_hang"])
def cart_remove(product_id):
    cart_row = ensure_cart(session["user_id"])
    execute(
        "DELETE FROM ChiTietGioHang WHERE MaGioHang = ? AND MaSanPham = ?",
        (cart_row["MaGioHang"], product_id),
    )
    flash("Đã xóa sản phẩm khỏi giỏ hàng.", "info")
    return redirect(url_for("shop.cart"))


def _guest_cart_dict():
    return session.setdefault("guest_cart", {})


def _guest_cart_line_items():
    cart = _guest_cart_dict()
    if not cart:
        return []
    ids = [int(pid) for pid in cart.keys()]
    placeholders = ",".join("?" * len(ids))
    products = query_all(
        f"""SELECT sp.* FROM SanPham sp
            WHERE sp.MaSanPham IN ({placeholders}) AND sp.TrangThai = 'hoat_dong'""",
        ids,
    )
    by_id = {p["MaSanPham"]: p for p in products}
    items = []
    for pid_str, qty in cart.items():
        pid = int(pid_str)
        if pid not in by_id:
            continue
        p = dict(by_id[pid])
        p["SoLuong"] = int(qty)
        items.append(p)
    return items


@shop_bp.route("/khach/gio-hang/them", methods=["POST"])
def guest_cart_add():
    if session.get("user_id"):
        flash("Bạn đã đăng nhập — dùng giỏ hàng tài khoản.", "info")
        return redirect(url_for("shop.cart"))
    product_id = int(request.form.get("product_id"))
    qty = max(int(request.form.get("quantity", 1) or 1), 1)
    product = query_one(
        "SELECT * FROM SanPham WHERE MaSanPham = ? AND TrangThai = 'hoat_dong'", (product_id,)
    )
    if not product or product["SoLuongTon"] < qty:
        flash("Sản phẩm không khả dụng hoặc không đủ số lượng.", "warning")
        return redirect(request.referrer or url_for("shop.index"))
    cart = _guest_cart_dict()
    cart[str(product_id)] = cart.get(str(product_id), 0) + qty
    session["guest_cart"] = cart
    session.modified = True
    flash("Đã thêm vào giỏ khách. Tiếp tục đặt hàng QR.", "success")
    return redirect(url_for("shop.guest_checkout"))


@shop_bp.route("/dat-hang-khach", methods=["GET", "POST"])
def guest_checkout():
    if session.get("user_id"):
        return redirect(url_for("shop.checkout"))
    items = _guest_cart_line_items()
    if not items:
        flash("Giỏ khách trống. Chọn sản phẩm và thêm vào giỏ.", "warning")
        return redirect(url_for("shop.index"))

    if request.method == "POST":
        address = request.form.get("address", "").strip()
        payment = request.form.get("payment", "chuyen_khoan")
        if payment != "chuyen_khoan":
            flash("Khách vãng lai chỉ hỗ trợ thanh toán QR.", "warning")
            payment = "chuyen_khoan"
        if not address:
            flash("Vui lòng nhập địa chỉ giao hàng.", "warning")
            total = sum(get_effective_price(i)[0] * i["SoLuong"] for i in items)
            return render_template(
                "shop/guest_checkout.html",
                items=items,
                total=total,
                payment_methods=PAYMENT_METHODS,
                format_currency=format_currency,
                get_effective_price=get_effective_price,
            )

        line_items = []
        total = 0
        for item in items:
            if item["SoLuong"] > item["SoLuongTon"]:
                flash(f"Sản phẩm '{item['TenSanPham']}' không đủ hàng.", "danger")
                return redirect(url_for("shop.guest_checkout"))
            price, _ = get_effective_price(item)
            subtotal = price * item["SoLuong"]
            total += subtotal
            line_items.append((item["MaSanPham"], item["SoLuong"], price, subtotal))

        guest_token = new_guest_access_token()
        deadline = payment_deadline_from_now()
        conn = get_db()
        try:
            cur = conn.execute(
                """INSERT INTO DonHang
                   (TongTien, DiaChiGiao, TrangThai, PhuongThucThanhToan, MaKhachHang, HanThanhToan, MaTruyCapKhach)
                   VALUES (?, ?, 'pending_payment', 'chuyen_khoan', NULL, ?, ?)""",
                (total, address, deadline.strftime("%Y-%m-%d %H:%M:%S"), guest_token),
            )
            order_id = cur.lastrowid
            for pid, qty, price, subtotal in line_items:
                conn.execute(
                    "INSERT INTO ChiTietDonHang (MaDonHang, MaSanPham, SoLuong, DonGia, ThanhTien) VALUES (?, ?, ?, ?, ?)",
                    (order_id, pid, qty, price, subtotal),
                )
                conn.execute(
                    "UPDATE SanPham SET SoLuongTon = SoLuongTon - ? WHERE MaSanPham = ?",
                    (qty, pid),
                )
            conn.execute(
                "INSERT INTO ThanhToan (PhuongThuc, SoTien, TrangThai, MaDonHang) VALUES (?, ?, ?, ?)",
                ("chuyen_khoan", total, "cho_thanh_toan", order_id),
            )
            conn.execute(
                "INSERT INTO LichSuDonHang (MaDonHang, TrangThaiCu, TrangThaiMoi, GhiChu) VALUES (?, NULL, 'pending_payment', 'Khách vãng lai tạo đơn QR')",
                (order_id,),
            )
            conn.commit()
        finally:
            conn.close()

        session.pop("guest_cart", None)
        session.modified = True
        flash(f"Đơn #{order_id} chờ thanh toán QR ({PAYMENT_DEADLINE_MINUTES} phút).", "warning")
        return redirect(url_for("shop.order_confirmation", order_id=order_id, token=guest_token))

    total = sum(get_effective_price(i)[0] * i["SoLuong"] for i in items)
    return render_template(
        "shop/guest_checkout.html",
        items=items,
        total=total,
        payment_methods=PAYMENT_METHODS,
        format_currency=format_currency,
        get_effective_price=get_effective_price,
    )


@shop_bp.route("/dat-hang", methods=["GET", "POST"])
@login_required(roles=["khach_hang"])
def checkout():
    cart_row = ensure_cart(session["user_id"])
    items = query_all(
        """SELECT ct.*, sp.TenSanPham, sp.SoLuongTon, sp.GiaBan, sp.MaSanPham
           FROM ChiTietGioHang ct JOIN SanPham sp ON ct.MaSanPham = sp.MaSanPham
           WHERE ct.MaGioHang = ?""",
        (cart_row["MaGioHang"],),
    )
    if not items:
        flash("Giỏ hàng trống.", "warning")
        return redirect(url_for("shop.cart"))

    user = query_one("SELECT * FROM NguoiDung WHERE MaNguoiDung = ?", (session["user_id"],))

    if request.method == "POST":
        address_type = request.form.get("address_type", "manual")
        payment = request.form.get("payment", "COD")
        voucher_code = request.form.get("voucher", "").strip().upper()
        
        # Xử lý địa chỉ
        address = ""
        if address_type == "manual":
            address = request.form.get("address", "").strip()
        else:
            # Lấy địa chỉ từ database
            try:
                address_id = int(address_type)
                saved_address = query_one(
                    "SELECT * FROM DiaChiKhachHang WHERE MaDiaChi = ? AND MaNguoiDung = ?",
                    (address_id, session["user_id"])
                )
                if saved_address:
                    # Format địa chỉ
                    parts = []
                    if saved_address["TenNguoiNhan"]:
                        parts.append(saved_address["TenNguoiNhan"])
                    if saved_address["SoDienThoai"]:
                        parts.append(saved_address["SoDienThoai"])
                    parts.append(saved_address["DiaChi"])
                    address = " | ".join(parts)
            except (ValueError, TypeError):
                address = request.form.get("address", "").strip()

        if not address:
            flash("Vui lòng nhập hoặc chọn địa chỉ giao hàng.", "warning")
            return render_template(
                "shop/checkout.html",
                items=items,
                user=user,
                payment_methods=PAYMENT_METHODS,
                format_currency=format_currency,
                get_effective_price=get_effective_price,
            )

        for item in items:
            if item["SoLuong"] > item["SoLuongTon"]:
                flash(f"Sản phẩm '{item['TenSanPham']}' không đủ hàng.", "danger")
                return redirect(url_for("shop.cart"))

        total = 0
        line_items = []
        for item in items:
            price, _ = get_effective_price(item)
            subtotal = price * item["SoLuong"]
            total += subtotal
            line_items.append((item["MaSanPham"], item["SoLuong"], price, subtotal))

        # Áp dụng Voucher
        voucher_discount = 0
        voucher_info = None
        if voucher_code:
            voucher = query_one(
                """SELECT * FROM Voucher 
                   WHERE MaVoucher = ? AND TrangThai = 'hoat_dong'
                   AND date(NgayBatDau) <= date('now') AND date(NgayKetThuc) >= date('now')""",
                (voucher_code,),
            )
            if voucher:
                if voucher["SoLuong"] > 0 or voucher["SoLuong"] == -1:
                    if total >= voucher["DonToiThieu"]:
                        if voucher["LoaiGiam"] == "tien_mat":
                            voucher_discount = voucher["GiaTriGiam"]
                        else:  # phan_tram
                            voucher_discount = total * voucher["GiaTriGiam"] / 100
                        voucher_info = voucher
                    else:
                        flash(f"Đơn hàng tối thiểu {format_currency(voucher['DonToiThieu'])} để áp dụng voucher.", "warning")
                else:
                    flash("Voucher đã hết lượt sử dụng.", "warning")
            else:
                flash("Mã voucher không hợp lệ hoặc đã hết hạn.", "warning")

        final_total = total - voucher_discount
        is_qr = payment == "chuyen_khoan"
        guest_token = new_guest_access_token() if is_qr else None
        deadline = payment_deadline_from_now() if is_qr else None
        initial_status = "pending_payment" if is_qr else "cho_xac_nhan"

        conn = get_db()
        try:
            cur = conn.execute(
                """INSERT INTO DonHang
                   (TongTien, DiaChiGiao, TrangThai, PhuongThucThanhToan, MaKhachHang, HanThanhToan, MaTruyCapKhach)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    final_total,
                    address,
                    initial_status,
                    payment,
                    session["user_id"],
                    deadline.strftime("%Y-%m-%d %H:%M:%S") if deadline else None,
                    guest_token,
                ),
            )
            order_id = cur.lastrowid

            for pid, qty, price, subtotal in line_items:
                conn.execute(
                    "INSERT INTO ChiTietDonHang (MaDonHang, MaSanPham, SoLuong, DonGia, ThanhTien) VALUES (?, ?, ?, ?, ?)",
                    (order_id, pid, qty, price, subtotal),
                )

            # Cập nhật số lượng voucher đã sử dụng
            if voucher_info:
                if voucher_info["SoLuong"] > 0:
                    conn.execute("UPDATE Voucher SET DaSuDung = DaSuDung + 1 WHERE MaVoucher = ?", (voucher_code,))

            # Cập nhật tồn kho
            for pid, qty, price, subtotal in line_items:
                conn.execute(
                    "UPDATE SanPham SET SoLuongTon = SoLuongTon - ? WHERE MaSanPham = ?",
                    (qty, pid),
                )

            pay_status = "cho_thanh_toan" if is_qr else "cho_thanh_toan"
            if payment == "COD":
                pay_status = "cho_thanh_toan"
            conn.execute(
                "INSERT INTO ThanhToan (PhuongThuc, SoTien, TrangThai, MaDonHang) VALUES (?, ?, ?, ?)",
                (payment, final_total, pay_status, order_id),
            )
            if not is_qr:
                conn.execute(
                    "UPDATE DonHang SET TrangThai = ? WHERE MaDonHang = ?",
                    ("cho_xac_nhan", order_id),
                )
            conn.execute(
                "INSERT INTO LichSuDonHang (MaDonHang, TrangThaiCu, TrangThaiMoi, GhiChu) VALUES (?, NULL, ?, 'Tạo đơn hàng')",
                (order_id, initial_status if is_qr else "cho_xac_nhan"),
            )
            # Wrap notification in try-except to prevent checkout failure
            try:
                conn.execute(
                    "INSERT INTO ThongBao (MaNguoiDung, TieuDe, NoiDung) VALUES (?, ?, ?)",
                    (
                        session["user_id"],
                        "Đặt hàng thành công" if not is_qr else "Đơn chờ thanh toán QR",
                        f"Đơn hàng #{order_id} {'đang chờ quét QR trong ' + str(PAYMENT_DEADLINE_MINUTES) + ' phút.' if is_qr else 'đã được tạo.'}",
                    ),
                )
            except Exception as e:
                # Log error but don't fail checkout
                pass
            conn.execute("DELETE FROM ChiTietGioHang WHERE MaGioHang = ?", (cart_row["MaGioHang"],))
            conn.commit()
        except Exception as e:
            conn.rollback()
            flash(f"Có lỗi xảy ra khi đặt hàng: {str(e)}", "danger")
            return redirect(url_for("shop.cart"))
        finally:
            conn.close()

        if is_qr:
            flash(
                f"Đơn #{order_id} đã tạo. Vui lòng thanh toán QR trong {PAYMENT_DEADLINE_MINUTES} phút.",
                "warning",
            )
        else:
            flash("Đặt hàng thành công!", "success")
        
        # Clear cart session
        session.pop("cart", None)
        
        return redirect(url_for("shop.order_confirmation", order_id=order_id))

    total = sum(get_effective_price(i)[0] * i["SoLuong"] for i in items)
    return render_template(
        "shop/checkout.html",
        items=items,
        user=user,
        total=total,
        payment_methods=PAYMENT_METHODS,
        format_currency=format_currency,
        get_effective_price=get_effective_price,
    )


@shop_bp.route("/don-hang-cua-toi")
@login_required(roles=["khach_hang"])
def my_orders():
    orders = query_all(
        """SELECT * FROM DonHang WHERE MaKhachHang = ? ORDER BY NgayDat DESC""",
        (session["user_id"],),
    )
    return render_template(
        "shop/my_orders.html",
        orders=orders,
        order_status=ORDER_STATUS,
        format_currency=format_currency,
    )


@shop_bp.route("/don-hang/<int:order_id>")
@login_required(roles=["khach_hang"])
def order_detail(order_id):
    order = query_one(
        "SELECT * FROM DonHang WHERE MaDonHang = ? AND MaKhachHang = ?",
        (order_id, session["user_id"]),
    )
    if not order:
        flash("Không tìm thấy đơn hàng.", "danger")
        return redirect(url_for("shop.my_orders"))
    
    # Chuyển đổi Row sang dict để sử dụng .get()
    order = dict(order)

    items = query_all(
        """SELECT ct.*, sp.TenSanPham, sp.Slug FROM ChiTietDonHang ct
           JOIN SanPham sp ON ct.MaSanPham = sp.MaSanPham WHERE ct.MaDonHang = ?""",
        (order_id,),
    )
    history = query_all(
        "SELECT * FROM LichSuDonHang WHERE MaDonHang = ? ORDER BY NgayCapNhat DESC",
        (order_id,),
    )
    shipping = query_one(
        """SELECT vc.*, dv.TenDonVi FROM VanChuyen vc
           LEFT JOIN DonViGiaoNhan dv ON vc.MaDonVi = dv.MaDonVi WHERE vc.MaDonHang = ?""",
        (order_id,),
    )
    
    # Tạo QR URL nếu đơn đang chờ thanh toán
    qr_url = None
    expires_at = None
    if order["TrangThai"] == "pending_payment" and order["PhuongThucThanhToan"] == "chuyen_khoan":
        qr_url = build_vietqr_url(order["MaDonHang"], order["TongTien"])
        # Chuyển expires_at sang ISO format với timezone
        if order.get("HanThanhToan"):
            from datetime import datetime, timezone, timedelta
            try:
                dt = datetime.strptime(order["HanThanhToan"], "%Y-%m-%d %H:%M:%S")
                vn_tz = timezone(timedelta(hours=7))
                dt = dt.replace(tzinfo=vn_tz)
                expires_at = dt.isoformat()
            except ValueError:
                expires_at = order["HanThanhToan"].replace(" ", "T")

    return render_template(
        "shop/order_detail.html",
        order=order,
        items=items,
        history=history,
        shipping=shipping,
        order_status=ORDER_STATUS,
        format_currency=format_currency,
        qr_url=qr_url,
        expires_at=expires_at,
    )


@shop_bp.route("/don-hang/<int:order_id>/xac-nhan")
def order_confirmation(order_id):
    guest_token = request.args.get("token", "")
    user_id = session.get("user_id")

    if user_id:
        order = query_one(
            "SELECT * FROM DonHang WHERE MaDonHang = ? AND MaKhachHang = ?",
            (order_id, user_id),
        )
    else:
        order = query_one("SELECT * FROM DonHang WHERE MaDonHang = ?", (order_id,))

    if not order or not order_accessible(order, user_id=user_id, guest_token=guest_token or None):
        flash("Không tìm thấy đơn hàng.", "danger")
        if user_id:
            return redirect(url_for("shop.my_orders"))
        return redirect(url_for("shop.index"))
    
    # Chuyển đổi Row sang dict để sử dụng .get()
    order = dict(order)

    items = query_all(
        """SELECT ct.*, sp.TenSanPham FROM ChiTietDonHang ct
           JOIN SanPham sp ON ct.MaSanPham = sp.MaSanPham
           WHERE ct.MaDonHang = ?""",
        (order_id,),
    )

    qr_url = None
    expires_at = None
    if order["PhuongThucThanhToan"] == "chuyen_khoan" and order["TrangThai"] == "pending_payment":
        qr_url = build_vietqr_url(order_id, order["TongTien"])
        # Chuyển expires_at sang ISO format với timezone
        if order.get("HanThanhToan"):
            from datetime import datetime, timezone, timedelta
            try:
                dt = datetime.strptime(order["HanThanhToan"], "%Y-%m-%d %H:%M:%S")
                vn_tz = timezone(timedelta(hours=7))
                dt = dt.replace(tzinfo=vn_tz)
                expires_at = dt.isoformat()
            except (ValueError, TypeError, Exception):
                expires_at = order["HanThanhToan"].replace(" ", "T") if order["HanThanhToan"] else None

    return render_template(
        "shop/order_confirmation.html",
        order=order,
        items=items,
        qr_url=qr_url,
        guest_token=order["MaTruyCapKhach"] if order["MaTruyCapKhach"] else guest_token,
        payment_deadline_minutes=PAYMENT_DEADLINE_MINUTES,
        format_currency=format_currency,
        payment_methods=PAYMENT_METHODS,
        order_status=ORDER_STATUS,
        expires_at=expires_at,
    )


@shop_bp.route("/api/pending-orders")
@login_required(roles=["khach_hang"])
def api_pending_orders():
    """API trả về danh sách đơn hàng chờ thanh toán của user"""
    from datetime import datetime, timedelta
    
    pending_orders = query_all(
        """SELECT * FROM DonHang 
           WHERE MaKhachHang = ? AND TrangThai = 'pending_payment'
           AND HanThanhToan > datetime('now')
           ORDER BY NgayDat DESC""",
        (session["user_id"],),
    )
    
    result = []
    for order in pending_orders:
        items = query_all(
            """SELECT ct.*, sp.TenSanPham FROM ChiTietDonHang ct
               JOIN SanPham sp ON ct.MaSanPham = sp.MaSanPham
               WHERE ct.MaDonHang = ?""",
            (order["MaDonHang"],),
        )
        
        # Tính thời gian còn lại
        deadline = datetime.strptime(order["HanThanhToan"], "%Y-%m-%d %H:%M:%S")
        remaining_seconds = (deadline - datetime.now()).total_seconds()
        remaining_minutes = max(0, int(remaining_seconds / 60))
        
        # Chuyển đổi Row thành dict
        items_dict = []
        for item in items:
            items_dict.append({
                "TenSanPham": item["TenSanPham"],
                "SoLuong": item["SoLuong"],
                "DonGia": item["DonGia"],
                "ThanhTien": item["ThanhTien"]
            })
        
        result.append({
            "order_id": order["MaDonHang"],
            "total": order["TongTien"],
            "deadline": order["HanThanhToan"],
            "remaining_minutes": remaining_minutes,
            "items": items_dict,
        })
    
    return jsonify({"pending_orders": result})


@shop_bp.route("/don-hang-cho-thanh-toan")
@login_required(roles=["khach_hang"])
def pending_orders_page():
    """Trang hiển thị danh sách đơn hàng chờ thanh toán"""
    from datetime import datetime
    
    pending_orders = query_all(
        """SELECT * FROM DonHang 
           WHERE MaKhachHang = ? AND TrangThai = 'pending_payment'
           AND HanThanhToan > datetime('now')
           ORDER BY NgayDat DESC""",
        (session["user_id"],),
    )
    
    orders_with_items = []
    for order in pending_orders:
        items = query_all(
            """SELECT ct.*, sp.TenSanPham FROM ChiTietDonHang ct
               JOIN SanPham sp ON ct.MaSanPham = sp.MaSanPham
               WHERE ct.MaDonHang = ?""",
            (order["MaDonHang"],),
        )
        
        # Tính thời gian còn lại
        deadline = datetime.strptime(order["HanThanhToan"], "%Y-%m-%d %H:%M:%S")
        remaining_seconds = (deadline - datetime.now()).total_seconds()
        
        orders_with_items.append({
            **order,
            "items": items,
            "remaining_seconds": remaining_seconds,
        })
    
    return render_template(
        "shop/pending_orders.html",
        orders=orders_with_items,
        format_currency=format_currency,
    )


@shop_bp.route("/don-hang/<int:order_id>/huy", methods=["POST"])
@login_required(roles=["khach_hang"])
def order_cancel(order_id):
    order = query_one(
        "SELECT * FROM DonHang WHERE MaDonHang = ? AND MaKhachHang = ?",
        (order_id, session["user_id"]),
    )
    if not order:
        flash("Không tìm thấy đơn hàng.", "danger")
        return redirect(url_for("shop.my_orders"))

    if order["TrangThai"] not in ("cho_xac_nhan", "da_xac_nhan", "pending_payment"):
        flash("Không thể hủy đơn hàng ở trạng thái hiện tại.", "warning")
        return redirect(url_for("shop.order_detail", order_id=order_id))

    conn = get_db()
    try:
        if order["TrangThai"] == "pending_payment":
            cancel_pending_order(conn, order_id, order["TrangThai"], "Khách hàng hủy")
        else:
            items = conn.execute(
                "SELECT * FROM ChiTietDonHang WHERE MaDonHang = ?", (order_id,)
            ).fetchall()
            for item in items:
                conn.execute(
                    "UPDATE SanPham SET SoLuongTon = SoLuongTon + ? WHERE MaSanPham = ?",
                    (item["SoLuong"], item["MaSanPham"]),
                )
            conn.execute("UPDATE DonHang SET TrangThai = 'da_huy' WHERE MaDonHang = ?", (order_id,))
            conn.execute(
                "INSERT INTO LichSuDonHang (MaDonHang, TrangThaiCu, TrangThaiMoi, GhiChu) VALUES (?, ?, 'da_huy', 'Khách hàng hủy')",
                (order_id, order["TrangThai"]),
            )
        conn.commit()
    finally:
        conn.close()
    flash("Đã hủy đơn hàng.", "info")
    return redirect(url_for("shop.my_orders"))


@shop_bp.route("/san-pham/<slug>/danh-gia", methods=["POST"])
@login_required(roles=["khach_hang"])
def add_review(slug):
    product = query_one("SELECT * FROM SanPham WHERE Slug = ?", (slug,))
    if not product:
        flash("Sản phẩm không tồn tại.", "danger")
        return redirect(url_for("shop.index"))

    stars = int(request.form.get("stars", 0) or 0)
    content = request.form.get("content", "").strip()

    if stars < 1 or stars > 5:
        flash("Số sao phải từ 1 đến 5.", "warning")
        return redirect(url_for("shop.product_detail", slug=slug))

    bought = query_one(
        """SELECT dh.MaDonHang FROM ChiTietDonHang ct
           JOIN DonHang dh ON ct.MaDonHang = dh.MaDonHang
           WHERE ct.MaSanPham = ? AND dh.MaKhachHang = ? AND dh.TrangThai = 'da_giao'""",
        (product["MaSanPham"], session["user_id"]),
    )
    if not bought:
        flash("Bạn chưa mua sản phẩm này.", "warning")
        return redirect(url_for("shop.product_detail", slug=slug))

    existing = query_one(
        "SELECT 1 FROM DanhGia WHERE MaSanPham = ? AND MaNguoiDung = ?",
        (product["MaSanPham"], session["user_id"]),
    )
    if existing:
        flash("Bạn đã đánh giá sản phẩm này.", "info")
        return redirect(url_for("shop.product_detail", slug=slug))

    execute(
        "INSERT INTO DanhGia (MaSanPham, MaNguoiDung, MaDonHang, SoSao, NoiDung) VALUES (?, ?, ?, ?, ?)",
        (product["MaSanPham"], session["user_id"], bought["MaDonHang"], stars, content),
    )
    flash("Gửi đánh giá thành công.", "success")
    return redirect(url_for("shop.product_detail", slug=slug))


@shop_bp.route("/thong-bao")
@login_required()
def notifications():
    notes = query_all(
        "SELECT * FROM ThongBao WHERE MaNguoiDung = ? ORDER BY NgayTao DESC LIMIT 50",
        (session["user_id"],),
    )
    execute("UPDATE ThongBao SET DaDoc = 1 WHERE MaNguoiDung = ?", (session["user_id"],))
    return render_template("shop/notifications.html", notifications=notes)


@shop_bp.route("/robots.txt")
def robots_txt():
    return """User-agent: *
Allow: /
Disallow: /admin/
Disallow: /dang-nhap
Disallow: /dang-ky
Disallow: /gio-hang
Disallow: /dat-hang
Disallow: /don-hang-cua-toi
Disallow: /thong-bao

Sitemap: /sitemap.xml
""", 200, {"Content-Type": "text/plain"}


@shop_bp.route("/sitemap.xml")
def sitemap_xml():
    from flask import Response
    import datetime

    base_url = request.host_url.rstrip("/")
    products = query_all(
        "SELECT Slug FROM SanPham WHERE TrangThai = 'hoat_dong'"
    )
    categories = query_all("SELECT Slug FROM DanhMuc")

    xml = '<?xml version="1.0" encoding="UTF-8"?>\n'
    xml += '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'

    # Homepage
    xml += f"""  <url>
    <loc>{base_url}/</loc>
    <lastmod>{datetime.date.today().isoformat()}</lastmod>
    <changefreq>daily</changefreq>
    <priority>1.0</priority>
  </url>\n"""

    # Categories
    for cat in categories:
        xml += f"""  <url>
    <loc>{base_url}/?danh-muc={cat['Slug']}</loc>
    <changefreq>weekly</changefreq>
    <priority>0.8</priority>
  </url>\n"""

    # Products
    for prod in products:
        lastmod = datetime.date.today().isoformat()  # Use today's date since NgayCapNhat column doesn't exist
        xml += f"""  <url>
    <loc>{base_url}/san-pham/{prod['Slug']}</loc>
    <lastmod>{lastmod}</lastmod>
    <changefreq>weekly</changefreq>
    <priority>0.7</priority>
  </url>\n"""

    xml += '</urlset>'
    return Response(xml, mimetype="application/xml")
