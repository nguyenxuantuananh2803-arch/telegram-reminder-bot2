import requests
from datetime import datetime, timedelta
import os
import re

# ==================== CẤU HÌNH ====================
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
SHEET_ID = os.getenv('SHEET_ID')

# URL sheet TRA TRUOC
SHEET_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid=0"

# ==================== HÀM HỖ TRỢ ====================
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
    """Trích xuất số điện thoại"""
    if not phone_str:
        return "Không có SDT"
    # Lấy 8 số cuối
    phone = re.sub(r'[^\d]', '', str(phone_str))
    if len(phone) >= 8:
        return phone[-8:]
    # Nếu có 010-xxxx-xxxx format
    match = re.search(r'010[-]?(\d{4})[-]?(\d{4})', str(phone_str))
    if match:
        return match.group(1) + match.group(2)
    return str(phone_str)

def parse_package(package_str):
    """Phân tích gói cước: 363*3, 363x2, 360*3..."""
    if not package_str:
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
            print("⚠️ Không có dữ liệu")
            return
        
        today = datetime.now().date()
        print(f"📅 Hôm nay: {today}")
        
        # Danh sách các loại task
        urgent_overdue = []    # Quá hạn > 7 ngày (sim 2 tháng)
        normal_overdue = []    # Quá hạn 1-7 ngày
        due_soon = []          # Sắp đến hạn (trong 7 ngày tới)
        birthday_alerts = []   # Sinh nhật 19 tuổi
        
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
                ngay_sinh_str = cols[8].strip() if len(cols) > 8 else ''
                
                if not ten_kh or not ngay_89_str:
                    continue
                
                # Parse dữ liệu
                due_date = parse_date(ngay_89_str)
                if not due_date:
                    continue
                
                phone = extract_phone(sdt_raw)
                price, months = parse_package(goi_cuoc_raw)
                
                # Xác định số ngày báo trước và loại sim
                if months == 2:
                    remind_days = 30
                    sim_type = "SIM 2 THÁNG"
                else:
                    remind_days = 7
                    sim_type = "SIM 3 THÁNG"
                
                remind_date = due_date - timedelta(days=remind_days)
                days_diff = (today - remind_date).days
                
                # Tạo task description
                task_desc = f"Làm sim {ten_kh.upper()} {phone}"
                
                # === PHÂN LOẠI THEO MỨC ĐỘ KHẨN CẤP ===
                
                # 1. QUÁ HẠN NGHIÊM TRỌNG (sim 2 tháng quá hạn > 7 ngày)
                if months == 2 and due_date < today:
                    days_overdue = (today - due_date).days
                    if days_overdue >= 14:  # Quá hạn 2 lần (14 ngày)
                        urgent_overdue.append({
                            'name': ten_kh.upper(),
                            'phone': phone,
                            'due_date': due_date,
                            'remind_date': remind_date,
                            'days_overdue': days_overdue,
                            'package': goi_cuoc_raw,
                            'sim_type': sim_type,
                            'level': 'CRITICAL'
                        })
                    elif days_overdue >= 7:
                        urgent_overdue.append({
                            'name': ten_kh.upper(),
                            'phone': phone,
                            'due_date': due_date,
                            'remind_date': remind_date,
                            'days_overdue': days_overdue,
                            'package': goi_cuoc_raw,
                            'sim_type': sim_type,
                            'level': 'HIGH'
                        })
                    else:
                        normal_overdue.append({
                            'name': ten_kh.upper(),
                            'phone': phone,
                            'due_date': due_date,
                            'days_left': -days_overdue,
                            'package': goi_cuoc_raw,
                            'sim_type': sim_type
                        })
                
                # 2. QUÁ HẠN THÔNG THƯỜNG (1-7 ngày)
                elif remind_date < today <= due_date:
                    days_left = (due_date - today).days
                    normal_overdue.append({
                        'name': ten_kh.upper(),
                        'phone': phone,
                        'due_date': due_date,
                        'days_left': days_left,
                        'package': goi_cuoc_raw,
                        'sim_type': sim_type
                    })
                
                # 3. SẮP ĐẾN HẠN (trong vòng 7 ngày tới)
                elif today <= remind_date <= today + timedelta(days=7):
                    days_to_remind = (remind_date - today).days
                    due_soon.append({
                        'name': ten_kh.upper(),
                        'phone': phone,
                        'due_date': due_date,
                        'remind_date': remind_date,
                        'days_to': days_to_remind,
                        'package': goi_cuoc_raw,
                        'sim_type': sim_type
                    })
                
                # === XỬ LÝ SINH NHẬT 19 TUỔI ===
                if ngay_sinh_str:
                    birth_date = parse_date(ngay_sinh_str)
                    if birth_date:
                        age_19_date = birth_date.replace(year=birth_date.year + 19)
                        days_until_19 = (age_19_date - today).days
                        
                        if days_until_19 <= 30:  # Trong vòng 30 ngày
                            if days_until_19 < 0:
                                status = f"🔥 ĐÃ ĐỦ 19 TUỔI (quá {abs(days_until_19)} ngày)"
                            else:
                                status = f"⏰ Sắp đủ 19 tuổi (còn {days_until_19} ngày)"
                            
                            birthday_alerts.append({
                                'name': ten_kh.upper(),
                                'phone': phone,
                                'birth_date': birth_date,
                                'age_19_date': age_19_date,
                                'status': status
                            })
                
            except Exception as e:
                print(f"⚠️ Lỗi dòng {idx}: {e}")
                continue
        
        # ==================== TẠO TIN NHẮN ====================
        message = "🔔 <b>BÁO CÁO CÔNG VIỆC SIM</b> 🔔\n"
        message += f"📅 {today.strftime('%d/%m/%Y')}\n"
        message += "━" * 35 + "\n\n"
        
        # 1. QUÁ HẠN NGHIÊM TRỌNG (Sim 2 tháng quá hạn 2 lần)
        if urgent_overdue:
            message += "🚨 <b>KHẨN CẤP - QUÁ HẠN 14 NGÀY TRỞ LÊN</b> 🚨\n\n"
            for item in urgent_overdue:
                if item['level'] == 'CRITICAL':
                    message += f"🔥🔥 {item['name']}\n"
                    message += f"   📱 {item['phone']}\n"
                    message += f"   📅 Hết hạn: {item['due_date']}\n"
                    message += f"   ⚠️ QUÁ HẠN {item['days_overdue']} NGÀY\n"
                    message += f"   📦 {item['package']} - {item['sim_type']}\n"
                    message += f"   🎯 <b>CẦN XỬ LÝ NGAY LẬP TỨC</b>\n\n"
                else:
                    message += f"🔥 {item['name']}\n"
                    message += f"   📱 {item['phone']}\n"
                    message += f"   📅 Hết hạn: {item['due_date']}\n"
                    message += f"   ⚠️ QUÁ HẠN {item['days_overdue']} NGÀY\n"
                    message += f"   📦 {item['package']} - {item['sim_type']}\n\n"
        
        # 2. QUÁ HẠN THÔNG THƯỜNG
        if normal_overdue:
            message += "⚠️ <b>CÔNG VIỆC QUÁ HẠN</b> ⚠️\n\n"
            for item in normal_overdue:
                if item['days_left'] < 0:
                    message += f"❗ {item['name']}\n"
                    message += f"   📱 {item['phone']}\n"
                    message += f"   📅 Hết hạn: {item['due_date']}\n"
                    message += f"   ⚠️ QUÁ HẠN {abs(item['days_left'])} NGÀY\n"
                    message += f"   📦 {item['package']} - {item['sim_type']}\n\n"
                else:
                    message += f"⏰ {item['name']}\n"
                    message += f"   📱 {item['phone']}\n"
                    message += f"   📅 Đến hạn: {item['due_date']}\n"
                    message += f"   ⏰ Còn {item['days_left']} ngày\n"
                    message += f"   📦 {item['package']} - {item['sim_type']}\n\n"
        
        # 3. SẮP ĐẾN HẠN
        if due_soon:
            message += "📌 <b>CÔNG VIỆC SẮP ĐẾN HẠN</b> 📌\n\n"
            for item in due_soon:
                message += f"📋 {item['name']}\n"
                message += f"   📱 {item['phone']}\n"
                message += f"   📅 Đến hạn: {item['due_date']}\n"
                message += f"   ⏰ Nhắc sau {item['days_to']} ngày\n"
                message += f"   📦 {item['package']} - {item['sim_type']}\n\n"
        
        # 4. SINH NHẬT 19 TUỔI
        if birthday_alerts:
            message += "🎂 <b>SINH NHẬT 19 TUỔI</b> 🎂\n\n"
            for item in birthday_alerts:
                message += f"{item['status']}\n"
                message += f"   👤 {item['name']}\n"
                message += f"   📱 {item['phone']}\n"
                message += f"   📅 SN: {item['birth_date']}\n\n"
        
        # 5. KHÔNG CÓ VIỆC
        if not urgent_overdue and not normal_overdue and not due_soon and not birthday_alerts:
            message += "✅ Hôm nay không có công việc cần xử lý.\n"
        
        # Gửi tin nhắn
        send_telegram_message(message)
        print(f"✅ Đã gửi báo cáo: {len(urgent_overdue)} khẩn cấp, {len(normal_overdue)} quá hạn, {len(due_soon)} sắp đến hạn")
        
    except Exception as e:
        error_msg = f"❌ Lỗi hệ thống: {str(e)}"
        print(error_msg)
        send_telegram_message(error_msg)

# ==================== CHẠY CHÍNH ====================
if __name__ == "__main__":
    print("🚀 Bot nhắc việc khởi động...")
    check_reminders()
    print("🏁 Kết thúc")
