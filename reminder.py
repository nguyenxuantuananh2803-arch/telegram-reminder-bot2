import requests
from datetime import datetime, timedelta
import os
import re

# ==================== CẤU HÌNH ====================
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
SHEET_ID = os.getenv('SHEET_ID')

SHEET_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid=0"

def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {'chat_id': CHAT_ID, 'text': message, 'parse_mode': 'HTML'}
    try:
        requests.post(url, json=payload, timeout=10)
        return True
    except Exception as e:
        print(f"Lỗi gửi tin nhắn: {e}")
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
    if not phone_str or phone_str.strip() == '':
        return "Không có SDT"
    phone = re.sub(r'[^\d]', '', str(phone_str))
    if len(phone) >= 8:
        return phone[-8:]
    return str(phone_str)

def parse_package(package_str):
    if not package_str or package_str.strip() == '':
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
        print("🔄 Đang đọc dữ liệu từ Google Sheets...")
        response = requests.get(SHEET_URL, timeout=30)
        
        if response.status_code != 200:
            send_telegram_message(f"❌ Lỗi: Không đọc được sheet")
            return
        
        lines = response.text.strip().split('\n')
        if len(lines) < 2:
            send_telegram_message("⚠️ Không có dữ liệu")
            return
        
        today = datetime.now().date()
        print(f"📅 Hôm nay: {today}")
        
        # Danh sách phân loại ĐÚNG
        overdue = []      # QUÁ HẠN (due_date < today)
        today_due = []    # HÔM NAY ĐẾN HẠN (due_date == today)
        upcoming_7days = []  # SẮP ĐẾN HẠN (trong 7 ngày tới, chưa kể hôm nay)
        
        data_rows = lines[1:]
        
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
                
                if not ten_kh or not ngay_89_str:
                    continue
                
                due_date = parse_date(ngay_89_str)
                if not due_date:
                    continue
                
                phone = extract_phone(sdt_raw)
                price, months = parse_package(goi_cuoc_raw)
                
                # Tính số ngày đến hạn
                days_until_due = (due_date - today).days
                
                # === PHÂN LOẠI THEO NGÀY ===
                
                # 1. QUÁ HẠN (due_date < today)
                if days_until_due < 0:
                    overdue.append({
                        'name': ten_kh.upper(),
                        'phone': phone,
                        'due_date': due_date,
                        'days_overdue': abs(days_until_due),
                        'package': goi_cuoc_raw,
                        'months': months
                    })
                    print(f"❌ QUÁ HẠN: {ten_kh} - {abs(days_until_due)} ngày")
                
                # 2. HÔM NAY ĐẾN HẠN (due_date == today)
                elif days_until_due == 0:
                    today_due.append({
                        'name': ten_kh.upper(),
                        'phone': phone,
                        'due_date': due_date,
                        'package': goi_cuoc_raw,
                        'months': months
                    })
                    print(f"📅 HÔM NAY: {ten_kh}")
                
                # 3. SẮP ĐẾN HẠN (1-7 ngày tới)
                elif 1 <= days_until_due <= 7:
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
        
        # 1. QUÁ HẠN (quan trọng nhất)
        if overdue:
            message += "🚨 <b>QUÁ HẠN - CẦN XỬ LÝ NGAY</b> 🚨\n\n"
            for item in overdue:
                message += f"🔥 <b>{item['name']}</b>\n"
                message += f"   📱 {item['phone']}\n"
                message += f"   📅 Hết hạn: {item['due_date']}\n"
                message += f"   ⚠️ QUÁ HẠN {item['days_overdue']} NGÀY\n"
                if item['months'] == 2:
                    message += f"   📦 {item['package']} - SIM 2 THÁNG\n"
                else:
                    message += f"   📦 {item['package']}\n"
                message += "\n"
        
        # 2. HÔM NAY ĐẾN HẠN
        if today_due:
            message += "📅 <b>HÔM NAY ĐẾN HẠN</b> 📅\n\n"
            for item in today_due:
                message += f"📌 <b>{item['name']}</b>\n"
                message += f"   📱 {item['phone']}\n"
                message += f"   📅 Đến hạn: {item['due_date']} - HÔM NAY\n"
                message += f"   📦 {item['package']}\n\n"
        
        # 3. SẮP ĐẾN HẠN (trong 7 ngày tới)
        if upcoming_7days:
            message += "⏰ <b>CÔNG VIỆC SẮP ĐẾN HẠN (TRONG 7 NGÀY TỚI)</b> ⏰\n\n"
            for item in upcoming_7days:
                message += f"📋 <b>{item['name']}</b>\n"
                message += f"   📱 {item['phone']}\n"
                message += f"   📅 Đến hạn: {item['due_date']}\n"
                message += f"   ⏰ Còn {item['days_left']} ngày\n"
                if item['months'] == 2:
                    message += f"   📦 {item['package']} - SIM 2 THÁNG (NHẮC TRƯỚC 30 NGÀY)\n"
                else:
                    message += f"   📦 {item['package']}\n"
                message += "\n"
        
        # 4. KHÔNG CÓ VIỆC
        if not overdue and not today_due and not upcoming_7days:
            message += "✅ Hôm nay không có công việc cần xử lý.\n"
            message += "\n💡 Lưu ý:\n"
            message += "   - Sim 2 tháng (363*2): nhắc trước 30 ngày\n"
            message += "   - Sim 3 tháng (363*3, 360*3): nhắc trước 7 ngày\n"
            message += "   - Quá hạn: sẽ hiển thị ở mục QUÁ HẠN\n"
        
        # Gửi tin nhắn
        send_telegram_message(message)
        
        print(f"\n📊 KẾT QUẢ XỬ LÝ:")
        print(f"   - Quá hạn: {len(overdue)}")
        print(f"   - Hôm nay đến hạn: {len(today_due)}")
        print(f"   - Sắp đến hạn (7 ngày): {len(upcoming_7days)}")
        
    except Exception as e:
        error_msg = f"❌ Lỗi hệ thống: {str(e)}"
        print(error_msg)
        send_telegram_message(error_msg)

if __name__ == "__main__":
    print("🚀 Bot nhắc việc khởi động...")
    check_reminders()
    print("🏁 Kết thúc")
