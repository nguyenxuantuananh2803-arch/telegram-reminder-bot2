import requests
from datetime import datetime, timedelta
import os
import re

# ==================== CẤU HÌNH ====================
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
SHEET_ID = os.getenv('SHEET_ID')

# URL sheet TRA TRUOC (gid=0 là sheet đầu tiên)
SHEET_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid=0"

def send_telegram_message(message):
    """Gửi tin nhắn Telegram"""
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {'chat_id': CHAT_ID, 'text': message, 'parse_mode': 'HTML'}
    try:
        response = requests.post(url, json=payload, timeout=10)
        return response.status_code == 200
    except Exception as e:
        print(f"Lỗi gửi tin nhắn: {e}")
        return False

def parse_date(date_str):
    """Chuyển đổi định dạng ngày tháng"""
    if not date_str or date_str.strip() == '':
        return None
    try:
        if ' ' in date_str:
            date_str = date_str.split(' ')[0]
        return datetime.strptime(date_str, '%Y-%m-%d').date()
    except:
        return None

def extract_phone(phone_str):
    """Trích xuất số điện thoại (lấy 8 số cuối)"""
    if not phone_str or phone_str.strip() == '':
        return "Không có SDT"
    phone = re.sub(r'[^\d]', '', str(phone_str))
    if len(phone) >= 8:
        return phone[-8:]
    return str(phone_str)

def parse_package(package_str):
    """Phân tích gói cước: 363*3, 363x2, 360*3..."""
    if not package_str or package_str.strip() == '':
        return None, None
    package_str = str(package_str).strip().upper()
    match = re.search(r'(\d+)[\*x](\d+)', package_str, re.IGNORECASE)
    if match:
        price = int(match.group(1))
        months = int(match.group(2))
        return price, months
    return None, None

# ==================== HÀM CHÍNH ====================
def check_reminders():
    """Kiểm tra và gửi thông báo"""
    try:
        print("🔄 Đang đọc dữ liệu từ Google Sheets...")
        response = requests.get(SHEET_URL, timeout=30)
        
        if response.status_code != 200:
            send_telegram_message(f"❌ Lỗi: Không đọc được sheet (Mã: {response.status_code})")
            return
        
        lines = response.text.strip().split('\n')
        if len(lines) < 2:
            send_telegram_message("⚠️ Không có dữ liệu trong sheet")
            return
        
        today = datetime.now().date()
        print(f"📅 Hôm nay: {today}")
        
        # Danh sách phân loại
        overdue_2x = []      # Quá hạn 2 lần (>= 14 ngày)
        overdue_1x = []      # Quá hạn 1 lần (1-13 ngày)
        upcoming_7days = []  # Sắp đến hạn trong 7 ngày tới
        
        # Bỏ qua dòng header
        data_rows = lines[1:]
        
        for idx, row in enumerate(data_rows, start=2):
            if not row.strip():
                continue
            
            cols = row.split(',')
            if len(cols) < 13:
                continue
            
            try:
                # Lấy dữ liệu theo index
                ten_kh = cols[7].strip() if len(cols) > 7 else ''
                ngay_89_str = cols[2].strip() if len(cols) > 2 else ''
                sdt_raw = cols[11].strip() if len(cols) > 11 else ''
                goi_cuoc_raw = cols[12].strip() if len(cols) > 12 else ''
                
                if not ten_kh or not ngay_89_str:
                    continue
                
                # Parse dữ liệu
                due_date = parse_date(ngay_89_str)
                if not due_date:
                    continue
                
                phone = extract_phone(sdt_raw)
                price, months = parse_package(goi_cuoc_raw)
                
                # Tính số ngày đến hạn
                days_until_due = (due_date - today).days
                
                # === PHÂN LOẠI THEO YÊU CẦU ===
                
                # 1. QUÁ HẠN 2 LẦN (quá hạn >= 14 ngày)
                if days_until_due <= -14:
                    overdue_2x.append({
                        'name': ten_kh.upper(),
                        'phone': phone,
                        'due_date': due_date,
                        'days_overdue': abs(days_until_due),
                        'package': goi_cuoc_raw,
                        'months': months
                    })
                    print(f"🔥🔥 Quá hạn 2 lần: {ten_kh} - {abs(days_until_due)} ngày")
                
                # 2. QUÁ HẠN 1 LẦN (quá hạn 1-13 ngày)
                elif days_until_due < 0:
                    overdue_1x.append({
                        'name': ten_kh.upper(),
                        'phone': phone,
                        'due_date': due_date,
                        'days_overdue': abs(days_until_due),
                        'package': goi_cuoc_raw,
                        'months': months
                    })
                    print(f"🔥 Quá hạn: {ten_kh} - {abs(days_until_due)} ngày")
                
                # 3. SẮP ĐẾN HẠN (trong vòng 7 ngày tới)
                elif 0 <= days_until_due <= 7:
                    upcoming_7days.append({
                        'name': ten_kh.upper(),
                        'phone': phone,
                        'due_date': due_date,
                        'days_left': days_until_due,
                        'package': goi_cuoc_raw,
                        'months': months
                    })
                    print(f"⏰ Sắp đến hạn: {ten_kh} - còn {days_until_due} ngày")
                
            except Exception as e:
                print(f"⚠️ Lỗi dòng {idx}: {e}")
                continue
        
        # ==================== TẠO TIN NHẮN ====================
        message = "🔔 <b>BÁO CÁO CÔNG VIỆC SIM</b> 🔔\n"
        message += f"📅 {today.strftime('%d/%m/%Y')}\n"
        message += "━" * 35 + "\n\n"
        
        # 1. QUÁ HẠN 2 LẦN (ưu tiên cao nhất)
        if overdue_2x:
            message += "🚨🚨 <b>KHẨN CẤP - QUÁ HẠN 2 LẦN (≥14 NGÀY)</b> 🚨🚨\n\n"
            for item in overdue_2x:
                message += f"🔥🔥 <b>{item['name']}</b>\n"
                message += f"   📱 {item['phone']}\n"
                message += f"   📅 Hết hạn: {item['due_date']}\n"
                message += f"   ⚠️ QUÁ HẠN {item['days_overdue']} NGÀY\n"
                if item['months'] == 2:
                    message += f"   📦 {item['package']} - SIM 2 THÁNG (CẦN THAY NGAY)\n"
                else:
                    message += f"   📦 {item['package']}\n"
                message += "\n"
        
        # 2. QUÁ HẠN 1 LẦN
        if overdue_1x:
            message += "🚨 <b>QUÁ HẠN (CẦN XỬ LÝ NGAY)</b> 🚨\n\n"
            for item in overdue_1x:
                message += f"🔥 <b>{item['name']}</b>\n"
                message += f"   📱 {item['phone']}\n"
                message += f"   📅 Hết hạn: {item['due_date']}\n"
                message += f"   ⚠️ QUÁ HẠN {item['days_overdue']} NGÀY\n"
                if item['months'] == 2:
                    message += f"   📦 {item['package']} - SIM 2 THÁNG\n"
                else:
                    message += f"   📦 {item['package']}\n"
                message += "\n"
        
        # 3. SẮP ĐẾN HẠN (trong 7 ngày)
        if upcoming_7days:
            message += "⏰ <b>CÔNG VIỆC SẮP ĐẾN HẠN (TRONG 7 NGÀY TỚI)</b> ⏰\n\n"
            for item in upcoming_7days:
                if item['days_left'] == 0:
                    message += f"📌 <b>{item['name']}</b> - <b>HÔM NAY</b>\n"
                else:
                    message += f"📌 <b>{item['name']}</b> - Còn {item['days_left']} ngày\n"
                message += f"   📱 {item['phone']}\n"
                message += f"   📅 Đến hạn: {item['due_date']}\n"
                message += f"   📦 {item['package']}\n\n"
        
        # 4. KHÔNG CÓ VIỆC
        if not overdue_2x and not overdue_1x and not upcoming_7days:
            message += "✅ Hôm nay không có công việc cần xử lý.\n"
            message += "   - Sim 2 tháng sẽ được nhắc trước 30 ngày\n"
            message += "   - Sim 3 tháng được nhắc trước 7 ngày\n"
        
        # Gửi tin nhắn
        send_telegram_message(message)
        
        print(f"\n📊 KẾT QUẢ:")
        print(f"   - Quá hạn 2 lần: {len(overdue_2x)}")
        print(f"   - Quá hạn 1 lần: {len(overdue_1x)}")
        print(f"   - Sắp đến hạn (7 ngày): {len(upcoming_7days)}")
        
    except Exception as e:
        error_msg = f"❌ Lỗi hệ thống: {str(e)}"
        print(error_msg)
        send_telegram_message(error_msg)

# ==================== CHẠY CHÍNH ====================
if __name__ == "__main__":
    print("🚀 Bot nhắc việc khởi động...")
    check_reminders()
    print("🏁 Kết thúc")
