import requests
from datetime import datetime, timedelta
import os
import re

TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
SHEET_ID = os.getenv('SHEET_ID')

SHEET_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid=0"

def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {'chat_id': CHAT_ID, 'text': message, 'parse_mode': 'HTML'}
    try:
        requests.post(url, json=payload)
        return True
    except Exception as e:
        print(f"Lỗi: {e}")
        return False

def parse_date(date_str):
    if not date_str or date_str.strip() == '':
        return None
    try:
        if ' ' in date_str:
            date_str = date_str.split(' ')[0]
        return datetime.strptime(date_str, '%Y-%m-%d').date()
    except:
        return None

def extract_phone(phone_str):
    if not phone_str:
        return "Không có SDT"
    phone = re.sub(r'[^\d]', '', str(phone_str))
    if len(phone) >= 8:
        return phone[-8:]
    return str(phone_str)

def parse_package(package_str):
    if not package_str:
        return None, None
    package_str = str(package_str).strip().upper()
    match = re.search(r'(\d+)[\*x](\d+)', package_str, re.IGNORECASE)
    if match:
        price = int(match.group(1))
        months = int(match.group(2))
        return price, months
    return None, None

def check_reminders():
    try:
        response = requests.get(SHEET_URL, timeout=30)
        if response.status_code != 200:
            send_telegram_message("❌ Lỗi: Không đọc được sheet")
            return
        
        lines = response.text.strip().split('\n')
        if len(lines) < 2:
            return
        
        data_rows = lines[1:]
        today = datetime.now().date()
        reminders_2month = []  # Sim 2 tháng
        reminders_3month = []  # Sim 3 tháng
        birthday_alerts = []
        
        for idx, row in enumerate(data_rows, start=2):
            if not row.strip():
                continue
            cols = row.split(',')
            if len(cols) < 13:
                continue
            
            try:
                ten_kh = cols[7].strip() if len(cols) > 7 else ''
                ngay_89_str = cols[2].strip() if len(cols) > 2 else ''
                sdt_raw = cols[11].strip() if len(cols) > 11 else ''
                goi_cuoc_raw = cols[12].strip() if len(cols) > 12 else ''
                ngay_sinh_str = cols[8].strip() if len(cols) > 8 else ''
                
                if not ten_kh or not ngay_89_str:
                    continue
                
                due_date = parse_date(ngay_89_str)
                if not due_date:
                    continue
                
                phone = extract_phone(sdt_raw)
                price, months = parse_package(goi_cuoc_raw)
                
                # Xác định số ngày báo trước
                if months == 2:
                    remind_days = 30
                    sim_type = "⚠️ SIM 2 THÁNG"
                    target_list = reminders_2month
                else:
                    remind_days = 7
                    sim_type = "SIM 3 THÁNG"
                    target_list = reminders_3month
                
                remind_date = due_date - timedelta(days=remind_days)
                
                # Chỉ nhắc nếu chưa quá hạn quá 7 ngày
                if remind_date <= today <= due_date + timedelta(days=7):
                    days_left = (due_date - today).days
                    if days_left < 0:
                        status = f"🔥 QUÁ HẠN {abs(days_left)} NGÀY"
                    else:
                        status = f"⏰ Còn {days_left} ngày"
                    
                    target_list.append({
                        'name': ten_kh.upper(),
                        'phone': phone,
                        'due_date': due_date,
                        'status': status,
                        'sim_type': sim_type,
                        'package': goi_cuoc_raw
                    })
                
                # Xử lý sinh nhật 19 tuổi
                if ngay_sinh_str:
                    birth_date = parse_date(ngay_sinh_str)
                    if birth_date:
                        age_19 = birth_date.replace(year=birth_date.year + 19)
                        days_until = (age_19 - today).days
                        if -7 <= days_until <= 30:  # Trong vòng 30 ngày hoặc quá 7 ngày
                            birthday_alerts.append({
                                'name': ten_kh.upper(),
                                'phone': phone,
                                'birth_date': birth_date,
                                'age_19_date': age_19,
                                'days': days_until
                            })
            except Exception as e:
                print(f"Lỗi dòng {idx}: {e}")
                continue
        
        # Tạo tin nhắn
        message = "🔔 <b>BÁO CÁO CÔNG VIỆC SIM</b> 🔔\n"
        message += f"📅 {today.strftime('%d/%m/%Y')}\n"
        message += "━" * 30 + "\n\n"
        
        if reminders_2month:
            message += "🚨 <b>SIM 2 THÁNG - KHẨN CẤP (Báo trước 30 ngày):</b>\n\n"
            for r in reminders_2month:
                message += f"🔥 {r['name']}\n"
                message += f"   📱 {r['phone']}\n"
                message += f"   📅 Hết hạn: {r['due_date']}\n"
                message += f"   📍 {r['status']}\n"
                message += f"   📦 Gói: {r['package']}\n\n"
        
        if reminders_3month:
            message += "✅ <b>SIM 3 THÁNG (Báo trước 7 ngày):</b>\n\n"
            for r in reminders_3month:
                message += f"📌 {r['name']}\n"
                message += f"   📱 {r['phone']}\n"
                message += f"   📅 Hết hạn: {r['due_date']}\n"
                message += f"   📍 {r['status']}\n\n"
        
        if birthday_alerts:
            message += "🎂 <b>SINH NHẬT 19 TUỔI:</b>\n\n"
            for b in birthday_alerts:
                if b['days'] < 0:
                    message += f"🔥 {b['name']} - ĐÃ ĐỦ 19 TUỔI (quá {abs(b['days'])} ngày)\n"
                else:
                    message += f"🎂 {b['name']} - Sắp đủ 19 tuổi (còn {b['days']} ngày)\n"
                message += f"   📱 {b['phone']}\n"
                message += f"   📅 SN: {b['birth_date']}\n\n"
        
        if not reminders_2month and not reminders_3month and not birthday_alerts:
            message += "✨ Hôm nay không có việc cần xử lý.\n"
        
        send_telegram_message(message)
        
    except Exception as e:
        send_telegram_message(f"❌ Lỗi hệ thống: {str(e)}")

if __name__ == "__main__":
    check_reminders()
