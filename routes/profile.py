import os
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from werkzeug.utils import secure_filename
from database.db import query_one, query_all, execute, get_db
from helpers import login_required

profile_bp = Blueprint("profile", __name__)

# Avatar upload configuration
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}
MAX_FILE_SIZE = 2 * 1024 * 1024  # 2MB

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@profile_bp.route("/ho-so", methods=["GET", "POST"])
@login_required()
def profile():
    """User profile edit page"""
    user_id = session.get("user_id")
    if not user_id:
        flash("Vui lòng đăng nhập để xem hồ sơ", "warning")
        return redirect(url_for("auth.login"))
    
    user = query_one("SELECT * FROM NguoiDung WHERE MaNguoiDung = ?", (user_id,))
    if not user:
        flash("Không tìm thấy thông tin người dùng", "danger")
        return redirect(url_for("auth.login"))
    
    if request.method == "POST":
        try:
            ho_ten = request.form.get("ho_ten", "").strip()
            email = request.form.get("email", "").strip()
            sdt = request.form.get("sdt", "").strip()
            gioi_tinh = request.form.get("gioi_tinh", "Khác")
            
            # Handle date of birth from dropdowns
            ngay_sinh = None
            ngay = request.form.get("ngay_sinh_ngay", "")
            thang = request.form.get("ngay_sinh_thang", "")
            nam = request.form.get("ngay_sinh_nam", "")
            if ngay and thang and nam:
                ngay_sinh = f"{nam}-{thang.zfill(2)}-{ngay.zfill(2)}"
            
            # Handle avatar upload
            avatar = user.get("Avatar", "default-avatar.png")
            if "avatar" in request.files:
                file = request.files["avatar"]
                if file and file.filename and allowed_file(file.filename):
                    # Check file size
                    file.seek(0, os.SEEK_END)
                    file_size = file.tell()
                    file.seek(0)
                    
                    if file_size > MAX_FILE_SIZE:
                        flash("Kích thước file không được vượt quá 2MB", "danger")
                        return render_template("profile/profile.html", user=user)
                    
                    # Create upload directory if not exists
                    upload_dir = os.path.join("static", "uploads", "avatars")
                    os.makedirs(upload_dir, exist_ok=True)
                    
                    # Generate unique filename
                    filename = secure_filename(file.filename)
                    unique_filename = f"{user_id}_{filename}"
                    filepath = os.path.join(upload_dir, unique_filename)
                    
                    # Save file
                    file.save(filepath)
                    avatar = unique_filename
            
            # Update user profile
            execute(
                """UPDATE NguoiDung SET HoTen=?, Email=?, SoDienThoai=?, GioiTinh=?, NgaySinh=?, Avatar=?
                   WHERE MaNguoiDung=?""",
                (ho_ten, email, sdt, gioi_tinh, ngay_sinh or None, avatar, user_id)
            )
            
            # Update session
            session["user"] = query_one("SELECT * FROM NguoiDung WHERE MaNguoiDung = ?", (user_id,))
            
            flash("Cập nhật hồ sơ thành công!", "success")
            return redirect(url_for("profile.profile"))
            
        except Exception as e:
            flash(f"Có lỗi xảy ra: {str(e)}", "danger")
            return render_template("profile/profile.html", user=user)
    
    return render_template("profile/profile.html", user=user)


@profile_bp.route("/dia-chi")
@login_required()
def addresses():
    """User address book page"""
    user_id = session.get("user_id")
    if not user_id:
        flash("Vui lòng đăng nhập để xem sổ địa chỉ", "warning")
        return redirect(url_for("auth.login"))
    
    addresses = query_all(
        "SELECT * FROM DiaChiKhachHang WHERE MaNguoiDung = ? ORDER BY LaMacDinh DESC, NgayTao DESC",
        (user_id,)
    )
    return render_template("profile/addresses.html", addresses=addresses)


@profile_bp.route("/doi-mat-khau", methods=["GET", "POST"])
@login_required()
def change_password():
    """Change password page"""
    user_id = session.get("user_id")
    if not user_id:
        flash("Vui lòng đăng nhập để đổi mật khẩu", "warning")
        return redirect(url_for("auth.login"))
    
    if request.method == "POST":
        old_password = request.form.get("old_password", "")
        new_password = request.form.get("new_password", "")
        confirm_password = request.form.get("confirm_password", "")
        
        user = query_one("SELECT * FROM NguoiDung WHERE MaNguoiDung = ?", (user_id,))
        if not user:
            flash("Không tìm thấy thông tin người dùng", "danger")
            return redirect(url_for("auth.login"))
        
        # Verify old password
        from werkzeug.security import check_password_hash
        if not check_password_hash(user["MatKhau"], old_password):
            flash("Mật khẩu cũ không đúng", "danger")
            return render_template("profile/change_password.html")
        
        # Validate new password
        if len(new_password) < 6:
            flash("Mật khẩu mới phải có ít nhất 6 ký tự", "danger")
            return render_template("profile/change_password.html")
        
        if new_password != confirm_password:
            flash("Mật khẩu mới không khớp", "danger")
            return render_template("profile/change_password.html")
        
        # Update password
        from werkzeug.security import generate_password_hash
        execute(
            "UPDATE NguoiDung SET MatKhau=? WHERE MaNguoiDung=?",
            (generate_password_hash(new_password), user_id)
        )
        
        flash("Đổi mật khẩu thành công!", "success")
        return redirect(url_for("profile.change_password"))
    
    return render_template("profile/change_password.html")
