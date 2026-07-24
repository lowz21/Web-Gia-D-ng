from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from werkzeug.security import check_password_hash, generate_password_hash
from database.db import query_one, execute
from helpers import login_required, ROLE_LABELS

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/dang-nhap", methods=["GET", "POST"])
def login():
    if session.get("user_id"):
        return redirect(url_for("shop.index"))

    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        user = query_one("SELECT * FROM NguoiDung WHERE Email = ?", (email,))

        if not user or not check_password_hash(user["MatKhau"], password):
            flash("Email hoặc mật khẩu không đúng.", "danger")
            return render_template("auth/login.html")

        if user["TrangThai"] != "hoat_dong":
            flash("Tài khoản đã bị khóa.", "danger")
            return render_template("auth/login.html")

        session["user_id"] = user["MaNguoiDung"]
        session["user"] = {
            "MaNguoiDung": user["MaNguoiDung"],
            "HoTen": user["HoTen"],
            "Email": user["Email"],
            "VaiTro": user["VaiTro"],
        }
        flash(f"Xin chào {user['HoTen']}!", "success")

        next_url = request.args.get("next")
        if user["VaiTro"] == "admin":
            return redirect(next_url or url_for("admin.dashboard"))
        if user["VaiTro"] == "chu_cua_hang":
            return redirect(next_url or url_for("admin.products"))
        return redirect(next_url or url_for("shop.index"))

    return render_template("auth/login.html")


@auth_bp.route("/dang-ky", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        phone = request.form.get("phone", "").strip()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm", "")

        if not all([name, email, password]):
            flash("Vui lòng điền đầy đủ thông tin.", "warning")
        elif password != confirm:
            flash("Mật khẩu xác nhận không khớp.", "danger")
        elif query_one("SELECT 1 FROM NguoiDung WHERE Email = ?", (email,)):
            flash("Email đã được sử dụng.", "danger")
        else:
            uid = execute(
                "INSERT INTO NguoiDung (HoTen, Email, MatKhau, SoDienThoai, VaiTro) VALUES (?, ?, ?, ?, 'khach_hang')",
                (name, email, generate_password_hash(password), phone),
            )
            execute("INSERT INTO GioHang (MaNguoiDung) VALUES (?)", (uid,))
            flash("Đăng ký thành công! Vui lòng đăng nhập.", "success")
            return redirect(url_for("auth.login"))

    return render_template("auth/register.html")


@auth_bp.route("/dang-xuat")
def logout():
    session.clear()
    flash("Đã đăng xuất.", "info")
    return redirect(url_for("shop.index"))
