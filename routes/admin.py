from datetime import date
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from werkzeug.utils import secure_filename
import os
from database.db import query_one, query_all, execute, get_db, create_price_record, get_price_history
from helpers import login_required, slugify, ORDER_STATUS, format_currency, get_effective_price, ROLE_LABELS
from services.cloud_storage import upload_image, delete_image
import logging

# Configure logging
logging.basicConfig(level=logging.ERROR)
logger = logging.getLogger(__name__)

# Cấu hình upload hình ảnh
UPLOAD_FOLDER = 'static/img/products'
BANNER_UPLOAD_FOLDER = 'static/img/banners'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

admin_bp = Blueprint("admin", __name__)


def get_shop_id():
    user_id = session.get("user_id")
    if not user_id:
        return None
    row = query_one(
        "SELECT MaCuaHang FROM CuaHang WHERE MaNguoiDung = ?",
        (user_id,),
    )
    return row["MaCuaHang"] if row and "MaCuaHang" in row else None


@admin_bp.route("/")
@login_required(roles=["admin", "chu_cua_hang"])
def dashboard():
    user = session.get("user")
    if not user:
        flash("Phiên đăng nhập hết hạn", "warning")
        return redirect(url_for("auth.login"))
    
    role = user["VaiTro"]
    stats = {}

    if role == "admin":
        users_count = query_one("SELECT COUNT(*) as c FROM NguoiDung")
        products_count = query_one("SELECT COUNT(*) as c FROM SanPham")
        orders_count = query_one("SELECT COUNT(*) as c FROM DonHang")
        revenue = query_one(
            "SELECT COALESCE(SUM(TongTien), 0) as t FROM DonHang WHERE TrangThai NOT IN ('da_huy', 'cho_xac_nhan')"
        )
        stats = {
            "users": users_count["c"] if users_count else 0,
            "products": products_count["c"] if products_count else 0,
            "orders": orders_count["c"] if orders_count else 0,
            "revenue": revenue["t"] if revenue else 0,
        }
        recent_orders = query_all(
            """SELECT dh.*, nd.HoTen FROM DonHang dh
               JOIN NguoiDung nd ON dh.MaKhachHang = nd.MaNguoiDung
               ORDER BY dh.NgayDat DESC LIMIT 8"""
        )
    else:
        shop_id = get_shop_id()
        products_count = query_one("SELECT COUNT(*) as c FROM SanPham WHERE MaCuaHang = ?", (shop_id,))
        orders_count = query_one(
            """SELECT COUNT(DISTINCT dh.MaDonHang) as c FROM DonHang dh
               JOIN ChiTietDonHang ct ON dh.MaDonHang = ct.MaDonHang
               JOIN SanPham sp ON ct.MaSanPham = sp.MaSanPham
               WHERE sp.MaCuaHang = ?""",
            (shop_id,),
        )
        revenue = query_one(
            """SELECT COALESCE(SUM(ct.ThanhTien), 0) as t FROM ChiTietDonHang ct
               JOIN SanPham sp ON ct.MaSanPham = sp.MaSanPham
               JOIN DonHang dh ON ct.MaDonHang = dh.MaDonHang
               WHERE sp.MaCuaHang = ? AND dh.TrangThai NOT IN ('da_huy', 'cho_xac_nhan')""",
            (shop_id,),
        )
        stats = {
            "products": products_count["c"] if products_count else 0,
            "orders": orders_count["c"] if orders_count else 0,
            "revenue": revenue["t"] if revenue else 0,
        }
        recent_orders = query_all(
            """SELECT DISTINCT dh.*, nd.HoTen FROM DonHang dh
               JOIN ChiTietDonHang ct ON dh.MaDonHang = ct.MaDonHang
               JOIN SanPham sp ON ct.MaSanPham = sp.MaSanPham
               JOIN NguoiDung nd ON dh.MaKhachHang = nd.MaNguoiDung
               WHERE sp.MaCuaHang = ?
               ORDER BY dh.NgayDat DESC LIMIT 8""",
            (shop_id,),
        )

    return render_template(
        "admin/dashboard.html",
        stats=stats,
        recent_orders=recent_orders,
        order_status=ORDER_STATUS,
        format_currency=format_currency,
    )


# --- Danh mục ---
@admin_bp.route("/danh-muc")
@login_required(roles=["admin"])
def categories():
    cats = query_all("SELECT * FROM DanhMuc ORDER BY TenDanhMuc")
    return render_template("admin/categories.html", categories=cats)


@admin_bp.route("/danh-muc/them", methods=["GET", "POST"])
@login_required(roles=["admin"])
def category_add():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        desc = request.form.get("description", "").strip()
        slug = slugify(name)
        if not name:
            flash("Tên danh mục không được để trống.", "warning")
        else:
            try:
                execute("INSERT INTO DanhMuc (TenDanhMuc, Slug, MoTa) VALUES (?, ?, ?)", (name, slug, desc))
                flash("Thêm danh mục thành công.", "success")
                return redirect(url_for("admin.categories"))
            except Exception:
                flash("Slug đã tồn tại.", "danger")
    return render_template("admin/category_form.html", category=None)


@admin_bp.route("/danh-muc/<int:cat_id>/sua", methods=["GET", "POST"])
@login_required(roles=["admin"])
def category_edit(cat_id):
    cat = query_one("SELECT * FROM DanhMuc WHERE MaDanhMuc = ?", (cat_id,))
    if not cat:
        flash("Danh mục không tồn tại.", "danger")
        return redirect(url_for("admin.categories"))

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        desc = request.form.get("description", "").strip()
        slug = request.form.get("slug", slugify(name)).strip()
        execute("UPDATE DanhMuc SET TenDanhMuc=?, Slug=?, MoTa=? WHERE MaDanhMuc=?", (name, slug, desc, cat_id))
        flash("Cập nhật danh mục thành công.", "success")
        return redirect(url_for("admin.categories"))

    return render_template("admin/category_form.html", category=cat)


@admin_bp.route("/danh-muc/<int:cat_id>/xoa", methods=["POST"])
@login_required(roles=["admin"])
def category_delete(cat_id):
    count_result = query_one("SELECT COUNT(*) as c FROM SanPham WHERE MaDanhMuc = ?", (cat_id,))
    count = count_result["c"] if count_result else 0
    if count:
        flash("Không thể xóa danh mục đang có sản phẩm.", "danger")
    else:
        execute("DELETE FROM DanhMuc WHERE MaDanhMuc = ?", (cat_id,))
        flash("Đã xóa danh mục.", "success")
    return redirect(url_for("admin.categories"))


# --- Sản phẩm ---
@admin_bp.route("/san-pham")
@login_required(roles=["admin", "chu_cua_hang"])
def products():
    user = session.get("user")
    if not user:
        flash("Phiên đăng nhập hết hạn", "warning")
        return redirect(url_for("auth.login"))
    
    role = user["VaiTro"]
    if role == "admin":
        items = query_all(
            """SELECT sp.*, dm.TenDanhMuc, ch.TenCuaHang FROM SanPham sp
               JOIN DanhMuc dm ON sp.MaDanhMuc = dm.MaDanhMuc
               JOIN CuaHang ch ON sp.MaCuaHang = ch.MaCuaHang
               ORDER BY sp.MaSanPham DESC"""
        )
    else:
        shop_id = get_shop_id()
        items = query_all(
            """SELECT sp.*, dm.TenDanhMuc, ch.TenCuaHang FROM SanPham sp
               JOIN DanhMuc dm ON sp.MaDanhMuc = dm.MaDanhMuc
               JOIN CuaHang ch ON sp.MaCuaHang = ch.MaCuaHang
               WHERE sp.MaCuaHang = ? ORDER BY sp.MaSanPham DESC""",
            (shop_id,),
        )

    enriched_items = []
    for item in items:
        price, discount = get_effective_price(item)
        item_dict = dict(item)
        item_dict["GiaHienTai"] = price
        item_dict["GiamGia"] = discount
        enriched_items.append(item_dict)
    items = enriched_items

    return render_template(
        "admin/products.html",
        products=items,
        format_currency=format_currency,
        get_effective_price=get_effective_price,
    )


@admin_bp.route("/san-pham/them", methods=["GET", "POST"])
@login_required(roles=["admin", "chu_cua_hang"])
def product_add():
    cats = query_all("SELECT * FROM DanhMuc ORDER BY TenDanhMuc")
    shops = query_all("SELECT * FROM CuaHang ORDER BY TenCuaHang")
    shop_id = get_shop_id()

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        desc = request.form.get("description", "").strip()
        price = float(request.form.get("price", 0) or 0)
        orig = float(request.form.get("original_price", 0) or price)
        stock = int(request.form.get("stock", 0) or 0)
        cat_id = int(request.form.get("category_id"))
        store_id = int(request.form.get("shop_id") or shop_id or 0)
        meta_title = request.form.get("meta_title", name)
        meta_desc = request.form.get("meta_description", desc)
        meta_kw = request.form.get("meta_keyword", "")
        slug = slugify(name)
        
        # Xử lý upload hình ảnh với cloud storage fallback
        image_file = request.files.get('image')
        image_path = None
        
        if image_file and image_file.filename:
            if not allowed_file(image_file.filename):
                flash("Chỉ chấp nhận file hình ảnh (png, jpg, jpeg, gif, webp).", "danger")
            else:
                try:
                    # Use cloud storage service with fallback
                    upload_result = upload_image(image_file, folder="products", public_id=f"products/{slug}")
                    image_path = upload_result.get("url", "")
                    logger.info(f"Image uploaded successfully: {image_path}")
                except Exception as e:
                    logger.error(f"Error uploading image: {str(e)}")
                    flash(f"Lỗi khi tải lên hình ảnh: {str(e)}", "warning")
                    # Fallback to local storage if cloud upload fails
                    try:
                        os.makedirs(UPLOAD_FOLDER, exist_ok=True)
                        filename = secure_filename(f"{slug}_{image_file.filename}")
                        image_path = os.path.join(UPLOAD_FOLDER, filename)
                        image_file.save(image_path)
                        image_path = f"img/products/{filename}"
                    except Exception as local_error:
                        logger.error(f"Error saving image locally: {str(local_error)}")
                        image_path = None

        if price <= 0:
            flash("Giá sản phẩm phải lớn hơn 0.", "warning")
        elif stock < 0:
            flash("Tồn kho không được âm.", "warning")
        elif session.get("user", {}).get("VaiTro") == "chu_cua_hang" and store_id != shop_id:
            flash("Bạn chỉ được thêm sản phẩm cho cửa hàng của mình.", "danger")
        else:
            dup = query_one(
                "SELECT 1 FROM SanPham WHERE TenSanPham = ? AND MaCuaHang = ?",
                (name, store_id),
            )
            if dup:
                flash("Tên sản phẩm đã tồn tại trong cửa hàng.", "danger")
            else:
                # Use a single transaction for both product creation and price history
                conn = get_db()
                try:
                    # Insert SanPham
                    cur = conn.execute(
                        """INSERT INTO SanPham (TenSanPham, MoTa, GiaBan, GiaGoc, SoLuongTon, Slug,
                           MetaTitle, MetaDescription, MetaKeyword, HinhAnh, MaDanhMuc, MaCuaHang)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (name, desc, price, orig, stock, slug, meta_title, meta_desc, meta_kw, image_path, cat_id, store_id),
                    )
                    pid = cur.lastrowid if hasattr(cur, 'lastrowid') else cur.lastrowid
                    
                    # Create initial BangGia record
                    conn.execute(
                        """INSERT INTO BangGia (MaSanPham, GiaBan, NgayApDung, IsActive, NgayTao)
                           VALUES (?, ?, datetime('now'), 1, datetime('now'))""",
                        (pid, price)
                    )
                    
                    conn.commit()
                    flash("Thêm sản phẩm thành công.", "success")
                    return redirect(url_for("admin.products"))
                    
                except Exception as e:
                    conn.rollback()
                    logger.error(f"Error creating product: {str(e)}")
                    flash(f"Lỗi khi tạo sản phẩm: {str(e)}", "danger")
                    return redirect(url_for("admin.product_add"))
                finally:
                    conn.close()

    return render_template("admin/product_form.html", product=None, categories=cats, shops=shops, shop_id=shop_id)


@admin_bp.route("/san-pham/<int:pid>/sua", methods=["GET", "POST"])
@login_required(roles=["admin", "chu_cua_hang"])
def product_edit(pid):
    product = query_one("SELECT * FROM SanPham WHERE MaSanPham = ?", (pid,))
    if not product:
        flash("Sản phẩm không tồn tại.", "danger")
        return redirect(url_for("admin.products"))

    shop_id = get_shop_id()
    if session.get("user", {}).get("VaiTro") == "chu_cua_hang" and product["MaCuaHang"] != shop_id:
        flash("Không có quyền sửa sản phẩm này.", "danger")
        return redirect(url_for("admin.products"))

    cats = query_all("SELECT * FROM DanhMuc ORDER BY TenDanhMuc")
    shops = query_all("SELECT * FROM CuaHang ORDER BY TenCuaHang")

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        desc = request.form.get("description", "").strip()
        price = float(request.form.get("price", 0) or 0)
        orig = float(request.form.get("original_price", 0) or price)
        stock = int(request.form.get("stock", 0) or 0)
        cat_id = int(request.form.get("category_id"))
        status = request.form.get("status", "hoat_dong")
        meta_title = request.form.get("meta_title", name)
        meta_desc = request.form.get("meta_description", desc)
        meta_kw = request.form.get("meta_keyword", "")

        # Xử lý upload hình ảnh với cloud storage fallback
        image_file = request.files.get('image')
        image_path = product.get("HinhAnh")  # Keep existing image if no new upload
        
        if image_file and image_file.filename:
            if not allowed_file(image_file.filename):
                flash("Chỉ chấp nhận file hình ảnh (png, jpg, jpeg, gif, webp).", "danger")
            else:
                try:
                    # Use cloud storage service with fallback
                    upload_result = upload_image(image_file, folder="products", public_id=f"products/{slugify(name)}")
                    image_path = upload_result.get("url", "")
                    logger.info(f"Image uploaded successfully: {image_path}")
                except Exception as e:
                    logger.error(f"Error uploading image: {str(e)}")
                    flash(f"Lỗi khi tải lên hình ảnh: {str(e)}", "warning")
                    # Fallback to local storage if cloud upload fails
                    try:
                        os.makedirs(UPLOAD_FOLDER, exist_ok=True)
                        filename = secure_filename(f"{slugify(name)}_{image_file.filename}")
                        image_path = os.path.join(UPLOAD_FOLDER, filename)
                        image_file.save(image_path)
                        image_path = f"img/products/{filename}"
                    except Exception as local_error:
                        logger.error(f"Error saving image locally: {str(local_error)}")
                        image_path = product.get("HinhAnh")  # Keep old image on error

        old_price = float(product["GiaBan"])
        
        # Use a single transaction for both price history and product update
        conn = get_db()
        try:
            if price != old_price:
                # Deactivate previous active price records
                conn.execute(
                    """UPDATE BangGia 
                       SET NgayKetThuc = datetime('now'), IsActive = 0
                       WHERE MaSanPham = ? AND IsActive = 1 AND NgayKetThuc IS NULL""",
                    (pid,)
                )
                
                # Insert new price record
                conn.execute(
                    """INSERT INTO BangGia (MaSanPham, GiaBan, NgayApDung, IsActive, NgayTao)
                       VALUES (?, ?, datetime('now'), 1, datetime('now'))""",
                    (pid, price)
                )
            
            # Update SanPham with new price and other fields including image
            conn.execute(
                """UPDATE SanPham SET TenSanPham=?, MoTa=?, GiaBan=?, GiaGoc=?, SoLuongTon=?,
                   MetaTitle=?, MetaDescription=?, MetaKeyword=?, TrangThai=?, MaDanhMuc=?, HinhAnh=? WHERE MaSanPham=?""",
                (name, desc, price, orig, stock, meta_title, meta_desc, meta_kw, status, cat_id, image_path, pid),
            )
            
            conn.commit()
            flash("Cập nhật sản phẩm thành công.", "success")
            return redirect(url_for("admin.products"))
            
        except Exception as e:
            conn.rollback()
            logger.error(f"Error updating product {pid}: {str(e)}")
            flash(f"Lỗi khi cập nhật sản phẩm: {str(e)}", "danger")
            return redirect(url_for("admin.product_edit", pid=pid))
        finally:
            conn.close()

    price_history = get_price_history(pid)
    return render_template(
        "admin/product_form.html",
        product=product,
        categories=cats,
        shops=shops,
        shop_id=shop_id,
        price_history=price_history,
        format_currency=format_currency,
    )


@admin_bp.route("/san-pham/<int:pid>/xoa", methods=["POST"])
@login_required(roles=["admin", "chu_cua_hang"])
def product_delete(pid):
    product = query_one("SELECT * FROM SanPham WHERE MaSanPham = ?", (pid,))
    if not product:
        flash("Sản phẩm không tồn tại.", "danger")
        return redirect(url_for("admin.products"))

    shop_id = get_shop_id()
    if session.get("user", {}).get("VaiTro") == "chu_cua_hang" and product["MaCuaHang"] != shop_id:
        flash("Không có quyền xóa sản phẩm này.", "danger")
        return redirect(url_for("admin.products"))

    execute("UPDATE SanPham SET TrangThai = 'ngung_ban' WHERE MaSanPham = ?", (pid,))
    flash("Đã ngừng bán sản phẩm.", "success")
    return redirect(url_for("admin.products"))


# --- Khuyến mãi ---
@admin_bp.route("/khuyen-mai")
@login_required(roles=["admin", "chu_cua_hang"])
def promotions():
    promos = query_all(
        """SELECT km.*, sp.TenSanPham FROM KhuyenMai km
           LEFT JOIN SanPham sp ON km.MaSanPham = sp.MaSanPham
           ORDER BY km.MaKhuyenMai DESC"""
    )
    return render_template("admin/promotions.html", promotions=promos)


@admin_bp.route("/khuyen-mai/them", methods=["GET", "POST"])
@login_required(roles=["admin", "chu_cua_hang"])
def promotion_add():
    products = query_all("SELECT MaSanPham, TenSanPham FROM SanPham WHERE TrangThai = 'hoat_dong'")
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        percent = int(request.form.get("percent", 0) or 0)
        start = request.form.get("start_date")
        end = request.form.get("end_date")
        product_id = request.form.get("product_id")
        product_id = int(product_id) if product_id else None

        if not name or percent <= 0 or percent > 100:
            flash("Dữ liệu khuyến mãi không hợp lệ.", "warning")
        else:
            execute(
                "INSERT INTO KhuyenMai (TenKhuyenMai, PhanTramGiam, NgayBatDau, NgayKetThuc, MaSanPham) VALUES (?, ?, ?, ?, ?)",
                (name, percent, start, end, product_id),
            )
            flash("Thêm khuyến mãi thành công.", "success")
            return redirect(url_for("admin.promotions"))

    return render_template("admin/promotion_form.html", promotion=None, products=products)


@admin_bp.route("/khuyen-mai/<int:promo_id>/xoa", methods=["POST"])
@login_required(roles=["admin"])
def promotion_delete(promo_id):
    execute("DELETE FROM KhuyenMai WHERE MaKhuyenMai = ?", (promo_id,))
    flash("Đã xóa khuyến mãi.", "success")
    return redirect(url_for("admin.promotions"))


# --- Đơn hàng ---
@admin_bp.route("/don-hang")
@login_required(roles=["admin", "chu_cua_hang", "giao_nhan"])
def orders():
    role = session.get("user", {}).get("VaiTro")
    status_filter = request.args.get("status", "")

    sql = """SELECT dh.*, nd.HoTen, nd.SoDienThoai FROM DonHang dh
             JOIN NguoiDung nd ON dh.MaKhachHang = nd.MaNguoiDung WHERE 1=1"""
    params = []

    if role == "chu_cua_hang":
        shop_id = get_shop_id()
        sql += """ AND dh.MaDonHang IN (
            SELECT ct.MaDonHang FROM ChiTietDonHang ct
            JOIN SanPham sp ON ct.MaSanPham = sp.MaSanPham WHERE sp.MaCuaHang = ?)"""
        params.append(shop_id)

    if status_filter:
        sql += " AND dh.TrangThai = ?"
        params.append(status_filter)

    sql += " ORDER BY dh.NgayDat DESC"
    orders_list = query_all(sql, params)
    shippers = query_all("SELECT * FROM DonViGiaoNhan")

    return render_template(
        "admin/orders.html",
        orders=orders_list,
        order_status=ORDER_STATUS,
        shippers=shippers,
        format_currency=format_currency,
        current_status=status_filter,
    )


@admin_bp.route("/don-hang/<int:order_id>")
@login_required(roles=["admin", "chu_cua_hang", "giao_nhan"])
def order_detail(order_id):
    order = query_one(
        """SELECT dh.*, nd.HoTen, nd.Email, nd.SoDienThoai FROM DonHang dh
           JOIN NguoiDung nd ON dh.MaKhachHang = nd.MaNguoiDung
           WHERE dh.MaDonHang = ?""",
        (order_id,),
    )
    if not order:
        flash("Không tìm thấy đơn hàng.", "danger")
        return redirect(url_for("admin.orders"))

    items = query_all(
        """SELECT ct.*, sp.TenSanPham, sp.HinhAnh, ch.TenCuaHang FROM ChiTietDonHang ct
           JOIN SanPham sp ON ct.MaSanPham = sp.MaSanPham
           JOIN CuaHang ch ON sp.MaCuaHang = ch.MaCuaHang
           WHERE ct.MaDonHang = ?""",
        (order_id,),
    )
    history = query_all(
        "SELECT * FROM LichSuDonHang WHERE MaDonHang = ? ORDER BY NgayCapNhat DESC",
        (order_id,),
    )
    shipping = query_one("SELECT * FROM VanChuyen WHERE MaDonHang = ?", (order_id,))
    payment = query_one("SELECT * FROM ThanhToan WHERE MaDonHang = ?", (order_id,))
    shippers = query_all("SELECT * FROM DonViGiaoNhan")

    return render_template(
        "admin/order_detail.html",
        order=order,
        items=items,
        history=history,
        shipping=shipping,
        payment=payment,
        shippers=shippers,
        order_status=ORDER_STATUS,
        format_currency=format_currency,
    )


def update_order_status(order_id, new_status, note=""):
    order = query_one("SELECT * FROM DonHang WHERE MaDonHang = ?", (order_id,))
    if not order:
        return False
    old = order["TrangThai"]
    execute("UPDATE DonHang SET TrangThai = ? WHERE MaDonHang = ?", (new_status, order_id))
    execute(
        "INSERT INTO LichSuDonHang (MaDonHang, TrangThaiCu, TrangThaiMoi, GhiChu) VALUES (?, ?, ?, ?)",
        (order_id, old, new_status, note),
    )
    execute(
        "INSERT INTO ThongBao (MaNguoiDung, TieuDe, NoiDung) VALUES (?, ?, ?)",
        (
            order["MaKhachHang"],
            f"Cập nhật đơn hàng #{order_id}",
            f"Đơn hàng của bạn đã chuyển sang: {ORDER_STATUS.get(new_status, new_status)}",
        ),
    )
    return True


@admin_bp.route("/don-hang/<int:order_id>/cap-nhat", methods=["POST"])
@login_required(roles=["admin", "chu_cua_hang"])
def order_update_status(order_id):
    new_status = request.form.get("status")
    shipper_id = request.form.get("shipper_id")

    if new_status not in ORDER_STATUS:
        flash("Trạng thái không hợp lệ.", "danger")
        return redirect(url_for("admin.order_detail", order_id=order_id))

    if new_status == "dang_giao" and shipper_id:
        existing = query_one("SELECT * FROM VanChuyen WHERE MaDonHang = ?", (order_id,))
        if existing:
            execute(
                "UPDATE VanChuyen SET MaDonVi=?, TrangThai='dang_giao' WHERE MaDonHang=?",
                (shipper_id, order_id),
            )
        else:
            execute(
                "INSERT INTO VanChuyen (MaDonHang, MaDonVi, TrangThai, PhiVanChuyen) VALUES (?, ?, 'dang_giao', 30000)",
                (order_id, shipper_id),
            )

    update_order_status(order_id, new_status)
    flash("Cập nhật trạng thái đơn hàng thành công.", "success")
    return redirect(url_for("admin.order_detail", order_id=order_id))


@admin_bp.route("/don-hang/<int:order_id>/da-thanh-toan", methods=["POST"])
@login_required(roles=["admin", "chu_cua_hang"])
def order_mark_paid(order_id):
    """Mark VietQR payment as paid and update order status"""
    order = query_one("SELECT * FROM DonHang WHERE MaDonHang = ?", (order_id,))
    if not order:
        flash("Không tìm thấy đơn hàng.", "danger")
        return redirect(url_for("admin.orders"))
    
    if order["PhuongThucThanhToan"] != "chuyen_khoan":
        flash("Đơn hàng này không phải thanh toán QR.", "warning")
        return redirect(url_for("admin.order_detail", order_id=order_id))
    
    conn = get_db()
    try:
        # Update payment status
        conn.execute(
            "UPDATE ThanhToan SET TrangThai = 'da_thanh_toan' WHERE MaDonHang = ?",
            (order_id,)
        )
        
        # Update order status if still pending
        if order["TrangThai"] in ["pending_payment", "cho_xac_nhan"]:
            old_status = order["TrangThai"]
            conn.execute(
                "UPDATE DonHang SET TrangThai = 'da_xac_nhan' WHERE MaDonHang = ?",
                (order_id,)
            )
            conn.execute(
                "INSERT INTO LichSuDonHang (MaDonHang, TrangThaiCu, TrangThaiMoi, GhiChu) VALUES (?, ?, ?, ?)",
                (order_id, old_status, "da_xac_nhan", "Admin xác nhận đã thanh toán QR")
            )
        
        conn.commit()
        flash("Đã đánh dấu đơn hàng thanh toán thành công.", "success")
    except Exception as e:
        conn.rollback()
        flash(f"Có lỗi xảy ra: {str(e)}", "danger")
    finally:
        conn.close()
    
    return redirect(url_for("admin.order_detail", order_id=order_id))


@admin_bp.route("/don-hang/<int:order_id>/nhan-giao", methods=["POST"])
@login_required(roles=["giao_nhan", "admin"])
def order_accept_ship(order_id):
    shipper = query_one("SELECT MaDonVi FROM DonViGiaoNhan WHERE MaNguoiDung = ?", (session.get("user_id"),))
    shipper_id = shipper["MaDonVi"] if shipper and "MaDonVi" in shipper else request.form.get("shipper_id")

    existing = query_one("SELECT * FROM VanChuyen WHERE MaDonHang = ? AND MaDonVi IS NOT NULL", (order_id,))
    if existing and existing["MaDonVi"] != shipper_id:
        flash("Đơn hàng đã được đơn vị khác tiếp nhận.", "danger")
        return redirect(url_for("admin.orders"))

    if not query_one("SELECT * FROM VanChuyen WHERE MaDonHang = ?", (order_id,)):
        execute(
            "INSERT INTO VanChuyen (MaDonHang, MaDonVi, TrangThai, PhiVanChuyen) VALUES (?, ?, 'dang_giao', 30000)",
            (order_id, shipper_id),
        )
    else:
        execute("UPDATE VanChuyen SET MaDonVi=?, TrangThai='dang_giao' WHERE MaDonHang=?", (shipper_id, order_id))

    update_order_status(order_id, "dang_giao", "Đơn vị giao nhận đã tiếp nhận")
    flash("Nhận đơn vận chuyển thành công.", "success")
    return redirect(url_for("admin.orders"))


@admin_bp.route("/don-hang/<int:order_id>/giao-xong", methods=["POST"])
@login_required(roles=["giao_nhan", "admin"])
def order_delivered(order_id):
    execute(
        "UPDATE VanChuyen SET TrangThai='da_giao', NgayGiaoThucTe=date('now') WHERE MaDonHang=?",
        (order_id,),
    )
    update_order_status(order_id, "da_giao", "Giao hàng thành công")
    flash("Cập nhật giao hàng thành công.", "success")
    return redirect(url_for("admin.orders"))


# --- Người dùng ---
@admin_bp.route("/nguoi-dung")
@login_required(roles=["admin"])
def users():
    users_list = query_all("SELECT * FROM NguoiDung ORDER BY MaNguoiDung")
    return render_template("admin/users.html", users=users_list, role_labels=ROLE_LABELS)


@admin_bp.route("/nguoi-dung/<int:uid>/khoa", methods=["POST"])
@login_required(roles=["admin"])
def user_toggle(uid):
    user = query_one("SELECT * FROM NguoiDung WHERE MaNguoiDung = ?", (uid,))
    if user:
        new_status = "khoa" if user["TrangThai"] == "hoat_dong" else "hoat_dong"
        execute("UPDATE NguoiDung SET TrangThai = ? WHERE MaNguoiDung = ?", (new_status, uid))
        flash("Cập nhật trạng thái người dùng thành công.", "success")
    return redirect(url_for("admin.users"))


# --- Thống kê ---
@admin_bp.route("/thong-ke")
@login_required(roles=["admin", "chu_cua_hang"])
def statistics():
    role = session.get("user", {}).get("VaiTro")
    shop_filter = ""
    params = []
    if role == "chu_cua_hang":
        shop_filter = " AND sp.MaCuaHang = ?"
        params.append(get_shop_id())

    revenue_by_month = query_all(
        f"""SELECT strftime('%Y-%m', dh.NgayDat) as thang, SUM(ct.ThanhTien) as doanh_thu
            FROM ChiTietDonHang ct
            JOIN DonHang dh ON ct.MaDonHang = dh.MaDonHang
            JOIN SanPham sp ON ct.MaSanPham = sp.MaSanPham
            WHERE dh.TrangThai NOT IN ('da_huy') {shop_filter}
            GROUP BY thang ORDER BY thang DESC LIMIT 12""",
        params,
    )

    top_products = query_all(
        f"""SELECT sp.TenSanPham, SUM(ct.SoLuong) as sold, SUM(ct.ThanhTien) as revenue
            FROM ChiTietDonHang ct
            JOIN SanPham sp ON ct.MaSanPham = sp.MaSanPham
            JOIN DonHang dh ON ct.MaDonHang = dh.MaDonHang
            WHERE dh.TrangThai NOT IN ('da_huy') {shop_filter}
            GROUP BY sp.MaSanPham ORDER BY sold DESC LIMIT 10""",
        params,
    )

    status_stats = query_all(
        f"""SELECT dh.TrangThai, COUNT(DISTINCT dh.MaDonHang) as cnt
            FROM DonHang dh
            JOIN ChiTietDonHang ct ON dh.MaDonHang = ct.MaDonHang
            JOIN SanPham sp ON ct.MaSanPham = sp.MaSanPham
            WHERE 1=1 {shop_filter}
            GROUP BY dh.TrangThai""",
        params,
    )

    total_revenue = sum(r["doanh_thu"] or 0 for r in revenue_by_month)
    total_orders_result = query_one(
        f"""SELECT COUNT(DISTINCT dh.MaDonHang) as c FROM DonHang dh
            JOIN ChiTietDonHang ct ON dh.MaDonHang = ct.MaDonHang
            JOIN SanPham sp ON ct.MaSanPham = sp.MaSanPham
            WHERE 1=1 {shop_filter}""",
        params,
    )
    total_orders = total_orders_result["c"] if total_orders_result else 0

    total_products_result = query_one(
        f"""SELECT COUNT(*) as c FROM SanPham sp WHERE 1=1 {shop_filter.replace('sp.', '')}""",
        params if role == "chu_cua_hang" else []
    )
    total_products = total_products_result["c"] if total_products_result else 0

    # Prepare Chart.js data
    months_labels = [f"T{r['thang'][5:]}/{r['thang'][:4]}" for r in reversed(revenue_by_month)]
    revenue_data = [float(r["doanh_thu"] or 0) for r in reversed(revenue_by_month)]
    
    status_labels = [ORDER_STATUS.get(r["TrangThai"], r["TrangThai"]) for r in status_stats]
    status_counts = [int(r["cnt"] or 0) for r in status_stats]

    return render_template(
        "admin/statistics.html",
        months_labels=months_labels,
        revenue_data=revenue_data,
        status_labels=status_labels,
        status_counts=status_counts,
        top_products=top_products,
        total_revenue=total_revenue,
        total_orders=total_orders,
        total_products=total_products,
        order_status=ORDER_STATUS,
        format_currency=format_currency,
    )


# --- Banner Management ---
@admin_bp.route("/banners")
@login_required(roles=["admin"])
def banners():
    banners = query_all(
        "SELECT * FROM Banners ORDER BY ThuTu ASC"
    )
    return render_template("admin/banners.html", banners=banners)


@admin_bp.route("/banners/them", methods=["GET", "POST"])
@login_required(roles=["admin"])
def banner_add():
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        link = request.form.get("link", "").strip()
        order = int(request.form.get("order", 0) or 0)
        
        # Handle image upload
        image_file = request.files.get('image')
        image_path = None
        public_id = None
        
        if image_file and image_file.filename:
            if not allowed_file(image_file.filename):
                flash("Chỉ chấp nhận file hình ảnh (png, jpg, jpeg, gif, webp).", "danger")
            else:
                try:
                    # Use cloud storage service
                    upload_result = upload_image(image_file, folder="banners", public_id=f"banner_{title}")
                    image_path = upload_result['url']
                    public_id = upload_result['public_id']
                except Exception as e:
                    # Fallback to local storage if cloud upload fails or not on Vercel
                    if os.getenv("VERCEL"):
                        flash("Cloud storage không khả dụng. Vui lòng cấu hình Cloudinary hoặc Supabase trên Vercel.", "danger")
                    else:
                        os.makedirs(BANNER_UPLOAD_FOLDER, exist_ok=True)
                        filename = secure_filename(f"banner_{title}_{image_file.filename}")
                        image_path_local = os.path.join(BANNER_UPLOAD_FOLDER, filename)
                        image_file.save(image_path_local)
                        image_path = f"img/banners/{filename}"
                        public_id = f"banners/{filename}"
        
        if not image_path:
            flash("Vui lòng tải lên hình ảnh banner.", "danger")
        else:
            execute(
                """INSERT INTO Banners (TieuDe, MoTa, URL, Link, TrangThai, ThuTu)
                   VALUES (?, ?, ?, ?, 'hoat_dong', ?)""",
                (title, description, image_path, link, order)
            )
            flash("Đã thêm banner thành công.", "success")
            return redirect(url_for("admin.banners"))
    
    return render_template("admin/banner_form.html", banner=None)


@admin_bp.route("/banners/<int:banner_id>/sua", methods=["GET", "POST"])
@login_required(roles=["admin"])
def banner_edit(banner_id):
    banner = query_one("SELECT * FROM Banners WHERE MaBanner = ?", (banner_id,))
    if not banner:
        flash("Banner không tồn tại.", "danger")
        return redirect(url_for("admin.banners"))
    
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        link = request.form.get("link", "").strip()
        order = int(request.form.get("order", 0) or 0)
        status = request.form.get("status", "hoat_dong")
        
        # Handle image upload
        image_file = request.files.get('image')
        image_path = banner["URL"]
        
        if image_file and image_file.filename:
            if not allowed_file(image_file.filename):
                flash("Chỉ chấp nhận file hình ảnh (png, jpg, jpeg, gif, webp).", "danger")
            else:
                try:
                    # Use cloud storage service
                    upload_result = upload_image(image_file, folder="banners", public_id=f"banner_{title}")
                    image_path = upload_result['url']
                except Exception as e:
                    # Fallback to local storage if cloud upload fails or not on Vercel
                    if os.getenv("VERCEL"):
                        flash("Cloud storage không khả dụng. Vui lòng cấu hình Cloudinary hoặc Supabase trên Vercel.", "danger")
                    else:
                        os.makedirs(BANNER_UPLOAD_FOLDER, exist_ok=True)
                        filename = secure_filename(f"banner_{title}_{image_file.filename}")
                        image_path_local = os.path.join(BANNER_UPLOAD_FOLDER, filename)
                        image_file.save(image_path_local)
                        image_path = f"img/banners/{filename}"
        
        execute(
            """UPDATE Banners SET TieuDe = ?, MoTa = ?, URL = ?, Link = ?, TrangThai = ?, ThuTu = ?
               WHERE MaBanner = ?""",
            (title, description, image_path, link, status, order, banner_id)
        )
        flash("Đã cập nhật banner thành công.", "success")
        return redirect(url_for("admin.banners"))
    
    return render_template("admin/banner_form.html", banner=banner)


@admin_bp.route("/banners/<int:banner_id>/xoa", methods=["POST"])
@login_required(roles=["admin"])
def banner_delete(banner_id):
    banner = query_one("SELECT * FROM Banners WHERE MaBanner = ?", (banner_id,))
    if not banner:
        flash("Banner không tồn tại.", "danger")
        return redirect(url_for("admin.banners"))
    
    execute("DELETE FROM Banners WHERE MaBanner = ?", (banner_id,))
    flash("Đã xóa banner thành công.", "success")
    return redirect(url_for("admin.banners"))


# --- Product Image Management ---
@admin_bp.route("/san-pham/<int:product_id>/hinh-anh", methods=["GET", "POST"])
@login_required(roles=["admin", "chu_cua_hang"])
def product_images(product_id):
    product = query_one("SELECT * FROM SanPham WHERE MaSanPham = ?", (product_id,))
    if not product:
        flash("Sản phẩm không tồn tại.", "danger")
        return redirect(url_for("admin.products"))
    
    shop_id = get_shop_id()
    if session.get("user", {}).get("VaiTro") == "chu_cua_hang" and product["MaCuaHang"] != shop_id:
        flash("Không có quyền quản lý hình ảnh sản phẩm này.", "danger")
        return redirect(url_for("admin.products"))
    
    images = query_all(
        "SELECT * FROM Product_Images WHERE MaSanPham = ? ORDER BY LaChinh DESC, ThuTu ASC",
        (product_id,)
    )
    
    if request.method == "POST":
        # Handle multiple image uploads
        image_files = request.files.getlist('images')
        
        if image_files:
            for image_file in image_files:
                if image_file and image_file.filename and allowed_file(image_file.filename):
                    try:
                        # Use cloud storage service
                        upload_result = upload_image(image_file, folder="products", public_id=f"{product['Slug']}_{image_file.filename}")
                        image_path = upload_result['url']
                    except Exception as e:
                        # Fallback to local storage if cloud upload fails or not on Vercel
                        if os.getenv("VERCEL"):
                            flash("Cloud storage không khả dụng. Vui lòng cấu hình Cloudinary hoặc Supabase trên Vercel.", "danger")
                            return redirect(url_for("admin.product_images", product_id=product_id))
                        else:
                            os.makedirs(UPLOAD_FOLDER, exist_ok=True)
                            filename = secure_filename(f"{product['Slug']}_{image_file.filename}")
                            image_path_local = os.path.join(UPLOAD_FOLDER, filename)
                            image_file.save(image_path_local)
                            image_path = f"img/products/{filename}"
                    
                    # Check if this is the first image (make it primary)
                    existing_count_result = query_one(
                        "SELECT COUNT(*) as c FROM Product_Images WHERE MaSanPham = ?",
                        (product_id,)
                    )
                    existing_count = existing_count_result["c"] if existing_count_result else 0
                    is_primary = 1 if existing_count == 0 else 0
                    
                    execute(
                        """INSERT INTO Product_Images (MaSanPham, URL, LaChinh, ThuTu)
                           VALUES (?, ?, ?, ?)""",
                        (product_id, image_path, is_primary, existing_count)
                    )
            
            flash("Đã thêm hình ảnh thành công.", "success")
            return redirect(url_for("admin.product_images", product_id=product_id))
        else:
            flash("Vui lòng chọn ít nhất một hình ảnh.", "warning")
    
    return render_template("admin/product_images.html", product=product, images=images)


@admin_bp.route("/san-pham/<int:product_id>/hinh-anh/<int:image_id>/mac-dinh", methods=["POST"])
@login_required(roles=["admin", "chu_cua_hang"])
def set_primary_image(product_id, image_id):
    product = query_one("SELECT * FROM SanPham WHERE MaSanPham = ?", (product_id,))
    if not product:
        flash("Sản phẩm không tồn tại.", "danger")
        return redirect(url_for("admin.products"))
    
    shop_id = get_shop_id()
    if session.get("user", {}).get("VaiTro") == "chu_cua_hang" and product["MaCuaHang"] != shop_id:
        flash("Không có quyền quản lý hình ảnh sản phẩm này.", "danger")
        return redirect(url_for("admin.products"))
    
    conn = get_db()
    try:
        # Remove primary flag from all images of this product
        conn.execute(
            "UPDATE Product_Images SET LaChinh = 0 WHERE MaSanPham = ?",
            (product_id,)
        )
        # Set primary flag to selected image
        conn.execute(
            "UPDATE Product_Images SET LaChinh = 1 WHERE MaAnh = ?",
            (image_id,)
        )
        conn.commit()
        flash("Đã đặt hình ảnh làm chính.", "success")
    finally:
        conn.close()
    
    return redirect(url_for("admin.product_images", product_id=product_id))


@admin_bp.route("/san-pham/<int:product_id>/hinh-anh/<int:image_id>/xoa", methods=["POST"])
@login_required(roles=["admin", "chu_cua_hang"])
def delete_product_image(product_id, image_id):
    product = query_one("SELECT * FROM SanPham WHERE MaSanPham = ?", (product_id,))
    if not product:
        flash("Sản phẩm không tồn tại.", "danger")
        return redirect(url_for("admin.products"))
    
    shop_id = get_shop_id()
    if session.get("user", {}).get("VaiTro") == "chu_cua_hang" and product["MaCuaHang"] != shop_id:
        flash("Không có quyền quản lý hình ảnh sản phẩm này.", "danger")
        return redirect(url_for("admin.products"))
    
    image = query_one(
        "SELECT * FROM Product_Images WHERE MaAnh = ? AND MaSanPham = ?",
        (image_id, product_id)
    )
    
    if not image:
        flash("Hình ảnh không tồn tại.", "danger")
        return redirect(url_for("admin.product_images", product_id=product_id))
    
    # If deleting primary image, set another image as primary if available
    if image["LaChinh"]:
        remaining = query_one(
            "SELECT * FROM Product_Images WHERE MaSanPham = ? AND MaAnh != ? LIMIT 1",
            (product_id, image_id)
        )
        if remaining:
            execute("UPDATE Product_Images SET LaChinh = 1 WHERE MaAnh = ?", (remaining["MaAnh"],))
    
    execute("DELETE FROM Product_Images WHERE MaAnh = ?", (image_id,))
    flash("Đã xóa hình ảnh thành công.", "success")
    return redirect(url_for("admin.product_images", product_id=product_id))
