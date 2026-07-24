"""
SePay API & Webhook Integration
Dịch vụ theo dõi biến động số dư ngân hàng tự động
"""
import os
import requests
from datetime import datetime
from database.db import query_one, execute
from services.order_payment import complete_order_payment, parse_order_id_from_transfer_content

SEPAY_API_KEY = os.getenv("SEPAY_API_KEY")
SEPAY_WEBHOOK_SECRET = os.getenv("SEPAY_WEBHOOK_SECRET")


def verify_sepay_webhook(data, signature):
    """Xác thực webhook từ SePay"""
    if not SEPAY_WEBHOOK_SECRET:
        return False
    
    expected_signature = data.get("signature")
    if not expected_signature:
        return False
    
    # SePay sử dụng HMAC-SHA256 để xác thực webhook
    import hmac
    import hashlib
    
    # Tạo signature từ dữ liệu
    payload = f"{data.get('transaction_id')}{data.get('amount')}{data.get('content')}"
    calculated_signature = hmac.new(
        SEPAY_WEBHOOK_SECRET.encode(),
        payload.encode(),
        hashlib.sha256
    ).hexdigest()
    
    return hmac.compare_digest(calculated_signature, expected_signature)


def process_sepay_webhook(data):
    """Xử lý webhook từ SePay khi có giao dịch mới"""
    try:
        # Lấy thông tin giao dịch
        transaction_id = data.get("transaction_id")
        amount = float(data.get("amount", 0))
        content = data.get("content") or data.get("description") or ""
        account_number = data.get("account_number")
        
        # Parse order_id từ nội dung chuyển khoản
        order_id = parse_order_id_from_transfer_content(content)
        
        if not order_id:
            return {"status": "ignored", "message": "No order_id found in content"}
        
        # Kiểm tra đơn hàng
        order = query_one(
            "SELECT * FROM DonHang WHERE MaDonHang = ? AND TrangThai = 'pending_payment'",
            (order_id,)
        )
        
        if not order:
            return {"status": "ignored", "message": "Order not found or not pending"}
        
        # Kiểm tra số tiền (cho phép sai số nhỏ)
        if abs(amount - order["TongTien"]) > 1000:
            return {"status": "ignored", "message": "Amount mismatch"}
        
        # Xác nhận thanh toán
        success, message = complete_order_payment(order_id, f"SePay: {transaction_id}")
        
        if success:
            return {
                "status": "success",
                "order_id": order_id,
                "transaction_id": transaction_id,
                "amount": amount,
                "message": "Payment confirmed"
            }
        else:
            return {"status": "error", "message": message}
            
    except Exception as e:
        return {"status": "error", "message": str(e)}


def get_sepay_transactions(limit=10):
    """Lấy danh sách giao dịch gần đây từ SePay API"""
    if not SEPAY_API_KEY:
        return []
    
    try:
        url = "https://my.sepay.vn/userapi/transactions/list"
        headers = {
            "Authorization": f"Bearer {SEPAY_API_KEY}",
            "Content-Type": "application/json"
        }
        params = {
            "limit": limit
        }
        
        response = requests.get(url, headers=headers, params=params, timeout=10)
        
        if response.status_code == 200:
            return response.json().get("transactions", [])
        else:
            return []
            
    except Exception as e:
        print(f"SePay API Error: {e}")
        return []


def check_pending_payment_from_sepay():
    """Kiểm tra thanh toán từ SePay cho các đơn hàng đang chờ"""
    transactions = get_sepay_transactions(limit=50)
    
    for tx in transactions:
        content = tx.get("content") or tx.get("description") or ""
        order_id = parse_order_id_from_transfer_content(content)
        
        if order_id:
            order = query_one(
                "SELECT * FROM DonHang WHERE MaDonHang = ? AND TrangThai = 'pending_payment'",
                (order_id,)
            )
            
            if order:
                amount = float(tx.get("amount", 0))
                if abs(amount - order["TongTien"]) <= 1000:
                    complete_order_payment(order_id, f"SePay: {tx.get('transaction_id')}")
