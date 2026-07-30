import os
from flask import Flask, session

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def create_app():
    app = Flask(__name__)
    app.config["SECRET_KEY"] = "21DH114235-Ha-Minh-Tri-ecommerce-2026"
    app.config["UPLOAD_FOLDER"] = os.path.join(BASE_DIR, "static", "uploads")
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    from database.db import init_db
    init_db()

    from routes.auth import auth_bp
    from routes.admin import admin_bp
    from routes.shop import shop_bp
    from routes.api import api_bp
    from routes.address import address_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp, url_prefix="/admin")
    app.register_blueprint(shop_bp)
    app.register_blueprint(api_bp, url_prefix="/api")
    app.register_blueprint(address_bp)

    from jobs.scheduler import start_scheduler
    start_scheduler(app)

    @app.context_processor
    def inject_globals():
        from database.db import query_one
        cart_count = 0
        if session.get("user_id"):
            row = query_one(
                """SELECT COALESCE(SUM(ct.SoLuong), 0) as cnt
                   FROM GioHang gh
                   LEFT JOIN ChiTietGioHang ct ON gh.MaGioHang = ct.MaGioHang
                   WHERE gh.MaNguoiDung = ?""",
                (session["user_id"],),
            )
            cart_count = row["cnt"] if row else 0
        return {
            "current_user": session.get("user"),
            "cart_count": cart_count,
        }

    return app
