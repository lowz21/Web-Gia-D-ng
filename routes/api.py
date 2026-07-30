import os
from flask import Blueprint, request, jsonify, session
from database.db import query_all, query_one
from helpers import format_currency, get_effective_price, ORDER_STATUS
from dotenv import load_dotenv
from services.order_payment import (
    complete_order_payment,
    order_accessible,
    order_payment_payload,
    parse_order_id_from_transfer_content,
    cancel_expired_pending_orders,
)

load_dotenv()

api_bp = Blueprint("api", __name__)

WEBHOOK_SECRET = os.getenv("PAYMENT_WEBHOOK_SECRET", "")

# Rule-based fallback responses
CHATBOT_RESPONSES = {
    "xin chao": "Xin chào! Tôi là trợ lý TMĐT Gia Dụng Pro. Tôi có thể giúp bạn tìm sản phẩm, tra cứu đơn hàng, hoặc hướng dẫn mua hàng.",
    "chao": "Xin chào! Bạn cần hỗ trợ gì về đồ gia dụng hôm nay?",
    "gio hang": "Để xem giỏ hàng, bạn đăng nhập và nhấn biểu tượng giỏ hàng trên thanh menu. Bạn có thể cập nhật số lượng hoặc tiến hành đặt hàng.",
    "dat hang": "Quy trình đặt hàng: 1) Chọn sản phẩm → Thêm giỏ hàng  2) Vào Giỏ hàng → Đặt hàng  3) Nhập địa chỉ giao hàng  4) Chọn COD hoặc thanh toán online.",
    "thanh toan": "Hệ thống hỗ trợ 2 hình thức: Thanh toán khi nhận hàng (COD) và Thanh toán trực tuyến (mô phỏng).",
    "van chuyen": "Phí vận chuyển mặc định 30.000đ/đơn. Bạn có thể theo dõi trạng thái giao hàng trong mục 'Đơn hàng của tôi'.",
    "lien he": "Hotline: 1900 1234 | Email: support@giadungpro.vn | Địa chỉ: 123 Nguyễn Huệ, Q1, TP.HCM",
    "cam on": "Cảm ơn bạn! Chúc bạn mua sắm vui vẻ tại Gia Dụng Pro!",
}


def normalize(text):
    import unicodedata
    text = text.lower().strip()
    text = unicodedata.normalize("NFD", text)
    return "".join(c for c in text if unicodedata.category(c) != "Mn")


def get_product_context():
    """Lấy danh sách sản phẩm để đưa vào context cho AI"""
    products = query_all(
        """SELECT TenSanPham, GiaBan, SoLuongTon, dm.TenDanhMuc 
           FROM SanPham sp 
           JOIN DanhMuc dm ON sp.MaDanhMuc = dm.MaDanhMuc 
           WHERE sp.TrangThai='hoat_dong' 
           ORDER BY sp.MaSanPham DESC"""
    )
    
    context = "DANH SÁCH SẢN PHẨM ĐỒ GIA DỤNG HIỆN CÓ:\n\n"
    for p in products:
        price, disc = get_effective_price(p)
        stock_status = "Còn hàng" if p['SoLuongTon'] > 0 else "Hết hàng"
        context += f"- {p['TenSanPham']} ({p['TenDanhMuc']}) - Giá: {format_currency(price)} - Tồn kho: {p['SoLuongTon']} ({stock_status})\n"
    
    return context


def fallback_chatbot(message):
    """Fallback về rule-based khi AI lỗi"""
    if not message:
        return "Vui lòng nhập câu hỏi của bạn."

    if any(k in message for k in ["san pham", "do gia dung", "ban gi"]):
        products = query_all(
            "SELECT TenSanPham, GiaBan, Slug FROM SanPham WHERE TrangThai='hoat_dong' LIMIT 5"
        )
        lines = ["Các sản phẩm nổi bật:"]
        for p in products:
            price, disc = get_effective_price(p)
            lines.append(f"• {p['TenSanPham']} - {format_currency(price)}")
        lines.append("Bạn muốn xem chi tiết sản phẩm nào?")
        return "\n".join(lines)

    if any(k in message for k in ["khuyen mai", "giam gia", "sale"]):
        promos = query_all(
            """SELECT km.TenKhuyenMai, km.PhanTramGiam, sp.TenSanPham
               FROM KhuyenMai km LEFT JOIN SanPham sp ON km.MaSanPham = sp.MaSanPham
               WHERE km.TrangThai='hoat_dong' AND date(km.NgayKetThuc) >= date('now')"""
        )
        if not promos:
            return "Hiện chưa có chương trình khuyến mãi."
        lines = ["Chương trình khuyến mãi đang diễn ra:"]
        for pr in promos:
            target = pr["TenSanPham"] or "Toàn sàn"
            lines.append(f"• {pr['TenKhuyenMai']}: Giảm {pr['PhanTramGiam']}% ({target})")
        return "\n".join(lines)

    if "don hang" in message or "trang thai" in message:
        return "Các trạng thái đơn hàng: " + ", ".join(ORDER_STATUS.values()) + ". Bạn đăng nhập và vào 'Đơn hàng của tôi' để theo dõi chi tiết."

    for key, reply in CHATBOT_RESPONSES.items():
        if key in message and reply:
            return reply

    return "Tôi chưa hiểu câu hỏi. Bạn thử hỏi về: sản phẩm, khuyến mãi, đặt hàng, thanh toán, vận chuyển, liên hệ."


@api_bp.route("/chatbot", methods=["POST"])
def chatbot():
    data = request.get_json(silent=True) or {}
    message = data.get("message", "").strip()
    normalized_message = normalize(message)

    if not message:
        return jsonify({"reply": "Vui lòng nhập câu hỏi của bạn."})

    # Thử sử dụng Gemini AI
    gemini_api_key = os.getenv("GEMINI_API_KEY")
    
    if gemini_api_key and gemini_api_key != "your_gemini_api_key_here":
        try:
            import google.generativeai as genai
            
            genai.configure(api_key=gemini_api_key)
            model = genai.GenerativeModel('gemini-1.5-flash')
            
            # Lấy context sản phẩm
            product_context = get_product_context()
            
            # Tạo prompt với context
            prompt = f"""Bạn là trợ lý tư vấn khách hàng cho sàn TMĐT Gia Dụng Pro chuyên bán đồ gia dụng.

{product_context}

HƯỚNG DẪN:
- Trả lời ngắn gọn, thân thiện, dưới 200 từ
- Tư vấn dựa trên danh sách sản phẩm ở trên
- Nếu khách hỏi về sản phẩm cụ thể, hãy tư vấn đúng sản phẩm đó từ danh sách
- Nếu khách hỏi về giá, hãy báo giá từ danh sách
- Nếu khách hỏi về tồn kho, hãy kiểm tra từ danh sách
- Nếu không có sản phẩm khách hỏi, hãy gợi ý sản phẩm tương tự
- Luôn khuyến khích khách hàng đặt hàng

Câu hỏi khách hàng: {message}

Trả lời:"""
            
            response = model.generate_content(prompt)
            reply = response.text.strip()
            
            if reply:
                return jsonify({"reply": reply})
                
        except ImportError:
            print("google-generativeai package not installed, using fallback")
        except Exception as e:
            print(f"Gemini AI Error: {e}")
            # Fallback về rule-based
    
    # Fallback về rule-based
    reply = fallback_chatbot(normalized_message)
    return jsonify({"reply": reply})


@api_bp.route("/products/search")
def search_products():
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify([])
    products = query_all(
        """SELECT MaSanPham, TenSanPham, GiaBan, Slug FROM SanPham
           WHERE TrangThai='hoat_dong' AND TenSanPham LIKE ? LIMIT 10""",
        (f"%{q}%",),
    )
    result = []
    for p in products:
        price, disc = get_effective_price(p)
        result.append({
            "id": p["MaSanPham"],
            "name": p["TenSanPham"],
            "price": format_currency(price),
            "slug": p["Slug"],
            "discount": disc,
        })
    return jsonify(result)


def _fetch_pending_order(order_id, user_id=None, guest_token=None):
    order = query_one("SELECT * FROM DonHang WHERE MaDonHang = ?", (order_id,))
    if not order or order["TrangThai"] != "pending_payment":
        return None
    if not order_accessible(order, user_id=user_id, guest_token=guest_token):
        return None
    items = query_all(
        """SELECT ct.*, sp.TenSanPham FROM ChiTietDonHang ct
           JOIN SanPham sp ON ct.MaSanPham = sp.MaSanPham WHERE ct.MaDonHang = ?""",
        (order_id,),
    )
    payload = order_payment_payload(order, items)
    payload["total_formatted"] = format_currency(order["TongTien"])
    return payload


@api_bp.route("/orders/pending", methods=["GET", "POST"])
def api_pending_orders():
    """Danh sách đơn PENDING_PAYMENT của user đăng nhập hoặc guest (localStorage)."""
    cancel_expired_pending_orders()

    user_id = session.get("user_id")
    guest_refs = []

    if request.method == "POST":
        data = request.get_json(silent=True) or {}
        guest_refs = data.get("order_refs") or []
    else:
        raw = request.args.get("order_refs", "")
        if raw:
            import json

            try:
                guest_refs = json.loads(raw)
            except json.JSONDecodeError:
                guest_refs = []

    seen = set()
    results = []

    if user_id:
        rows = query_all(
            """SELECT MaDonHang FROM DonHang
               WHERE MaKhachHang = ? AND TrangThai = 'pending_payment'
               ORDER BY NgayDat DESC""",
            (user_id,),
        )
        for row in rows:
            oid = row["MaDonHang"]
            if oid in seen:
                continue
            seen.add(oid)
            item = _fetch_pending_order(oid, user_id=user_id)
            if item:
                results.append(item)

    for ref in guest_refs:
        try:
            oid = int(ref.get("id"))
        except (TypeError, ValueError):
            continue
        token = ref.get("token") or ""
        if oid in seen:
            continue
        item = _fetch_pending_order(oid, guest_token=token or None)
        if item:
            seen.add(oid)
            results.append(item)

    return jsonify({"orders": results, "count": len(results)})


@api_bp.route("/orders/<int:order_id>/status")
def api_order_status(order_id):
    token = request.args.get("token", "")
    user_id = session.get("user_id")
    order = query_one("SELECT TrangThai, MaKhachHang, MaTruyCapKhach FROM DonHang WHERE MaDonHang = ?", (order_id,))
    if not order or not order_accessible(order, user_id=user_id, guest_token=token or None):
        return jsonify({"error": "not_found"}), 404
    return jsonify(
        {
            "order_id": order_id,
            "status": order["TrangThai"],
            "is_paid": order["TrangThai"] in ("paid", "cho_xac_nhan", "da_xac_nhan"),
            "is_pending": order["TrangThai"] == "pending_payment",
            "is_cancelled": order["TrangThai"] in ("cancelled", "da_huy"),
        }
    )


@api_bp.route("/orders/<int:order_id>/payment-qr")
def api_order_payment_qr(order_id):
    token = request.args.get("token", "")
    user_id = session.get("user_id")
    order = query_one("SELECT * FROM DonHang WHERE MaDonHang = ?", (order_id,))
    if not order or not order_accessible(order, user_id=user_id, guest_token=token or None):
        return jsonify({"error": "not_found"}), 404
    if order["TrangThai"] != "pending_payment":
        return jsonify({"error": "not_pending", "status": order["TrangThai"]}), 400
    items = query_all(
        """SELECT ct.*, sp.TenSanPham FROM ChiTietDonHang ct
           JOIN SanPham sp ON ct.MaSanPham = sp.MaSanPham WHERE ct.MaDonHang = ?""",
        (order_id,),
    )
    payload = order_payment_payload(order, items)
    payload["total_formatted"] = format_currency(order["TongTien"])
    return jsonify(payload)


@api_bp.route("/orders/<int:order_id>/mock-payment-success", methods=["POST"])
def mock_payment_success(order_id):
    """API test để giả lập thanh toán thành công (chỉ dùng cho development)"""
    from services.order_payment import complete_order_payment
    
    success, message = complete_order_payment(order_id, "Mock payment success (dev only)")
    
    if success:
        return jsonify({
            "status": "success",
            "order_id": order_id,
            "message": "Đã giả lập thanh toán thành công"
        })
    else:
        return jsonify({
            "status": "error",
            "message": message
        }), 400


@api_bp.route("/webhooks/payment", methods=["POST"])
def payment_webhook():
    """Webhook từ SePay hoặc cổng thanh toán báo đã nhận tiền."""
    data = request.get_json(silent=True) or {}
    
    # Xử lý webhook từ SePay (format mới)
    if data.get("gateway") or "code" in data or "transferAmount" in data:
        # Parse order_id từ code hoặc content
        order_id = None
        if data.get("code"):
            # Code có dạng DH1641337 -> tách số
            code = data.get("code", "")
            if code.startswith("DH"):
                try:
                    order_id = int(code.replace("DH", ""))
                except (TypeError, ValueError):
                    pass
        
        if not order_id:
            content = data.get("content") or ""
            order_id = parse_order_id_from_transfer_content(content)
        
        if not order_id:
            return jsonify({"status": "success", "message": "Webhook received but no order_id found"}), 200
        
        try:
            order_id = int(order_id)
        except (TypeError, ValueError):
            return jsonify({"status": "success", "message": "Invalid order_id format"}), 200
        
        # Kiểm tra đơn hàng
        order = query_one("SELECT * FROM DonHang WHERE MaDonHang = ?", (order_id,))
        if not order:
            return jsonify({"status": "success", "message": f"Order {order_id} not found"}), 200
        
        # Kiểm tra số tiền
        amount = data.get("transferAmount") or data.get("amount")
        if amount is not None:
            try:
                if abs(float(amount) - float(order["TongTien"])) > 1000:
                    return jsonify({"status": "success", "message": "Amount mismatch"}), 200
            except (TypeError, ValueError):
                pass
        
        # Xác nhận thanh toán
        ok, msg = complete_order_payment(order_id, f"SePay: {data.get('transactionDate')}")
        if ok:
            return jsonify({"status": "success", "order_id": order_id, "message": "Payment confirmed"}), 200
        else:
            return jsonify({"status": "success", "message": msg}), 200
    
    # Xử lý webhook từ cổng thanh toán khác (format cũ)
    order_id = data.get("order_id")
    content = data.get("content") or data.get("addInfo") or data.get("description")
    status = (data.get("status") or "success").lower()
    amount = data.get("amount")

    if not order_id and content:
        order_id = parse_order_id_from_transfer_content(content)
    try:
        order_id = int(order_id)
    except (TypeError, ValueError):
        return jsonify({"status": "success", "message": "Invalid order_id"}), 200

    if status not in ("success", "paid", "ok"):
        return jsonify({"status": "success", "message": "Ignored status"}), 200

    order = query_one("SELECT * FROM DonHang WHERE MaDonHang = ?", (order_id,))
    if not order:
        return jsonify({"status": "success", "message": f"Order {order_id} not found"}), 200

    if amount is not None:
        try:
            if abs(float(amount) - float(order["TongTien"])) > 1:
                return jsonify({"status": "success", "message": "Amount mismatch"}), 200
        except (TypeError, ValueError):
            pass

    ok, msg = complete_order_payment(order_id)
    if not ok:
        return jsonify({"error": msg}), 400
    return jsonify({"success": True, "order_id": order_id, "status": "paid", "message": msg})


@api_bp.route("/cron/cancel-expired-orders", methods=["POST"])
def cron_cancel_expired_orders():
    """
    Vercel Cron Job Endpoint for cancelling expired pending orders.
    Protected by CRON_SECRET_KEY environment variable.
    """
    cron_secret = os.getenv("CRON_SECRET_KEY", "")
    
    # Verify secret key
    provided_secret = request.headers.get("X-Cron-Secret") or request.args.get("secret")
    
    if not cron_secret or not provided_secret or provided_secret != cron_secret:
        return jsonify({"error": "Unauthorized"}), 401
    
    try:
        n = cancel_expired_pending_orders()
        return jsonify({
            "status": "success",
            "cancelled_orders": n,
            "message": f"Cancelled {n} expired pending orders"
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500
