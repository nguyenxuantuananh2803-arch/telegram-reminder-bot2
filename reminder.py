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
        print(f"📤 Đã gửi tin nhắn (status: {response.status_code})")
        return response.status_code == 200
    except Exception as e:
        print(f"❌ Lỗi gửi tin nhắn: {e}")
        return False

def parse_date(date_str):
    """Chuyển đổi định dạng ngày tháng"""
    if not date_str or date_str.strip() == '':
        return None
    try:
        # Xử lý định dạng YYYY-MM-DD
        if ' ' in date_str:
            date_str = date_str.split(' ')[0]
        return datetime.strptime(date_str, '%Y-%m-%d').date()
    except:
        try:
            # Thử định dạng DD/MM/YYYY
            return datetime.strptime(date_str, '%d/%m/%Y').date()
        except:
            print(f"   ⚠️ Không parse được ngày: '{date_str}'")
            return None

def extract_phone(phone_str):
    """Trích xuất số điện thoại"""
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
        print(f"📊 URL: {SHEET_URL}")
        
        response = requests.get(SHEET_URL, timeout=30)
        
        if response.status_code != 200:
            send_telegram_message(f"❌ Lỗi: Không đọc được sheet (Mã: {response.status_code})")
            print(f"❌ HTTP Error: {response.status_code}")
            return
        
        # Lấy nội dung CSV
        content = response.text
        print(f"📄 Đã đọc được {len(content)} bytes")
        
        lines = content.strip().split('\n')
        print(f"📋 Tổng số dòng: {len(lines)}")
        
        if len(lines) < 2:
            print("⚠️ Không có dữ liệu (chỉ có header hoặc file rỗng)")
            send_telegram_message("⚠️ Không có dữ liệu trong sheet")
            return
        
        # In ra header để debug
        header_line = lines[0]
        headers = header_line.split(',')
        print(f"📌 HEADER ({len(headers)} cột):")
        for i, h in enumerate(headers):
            print(f"   Cột {i}: '{h}'")
        
        today = datetime.now().date()
        print(f"📅 Hôm nay: {today}")
        
        # Danh sách các loại task
        urgent_overdue = []
        normal_overdue = []
        due_soon = []
        birthday_alerts = []
        
        # Bỏ qua dòng header, xử lý từ dòng 2
        data_rows = lines[1:]
        
        print(f"\n🔍 Bắt đầu xử lý {len(data_rows)} dòng dữ liệu...")
        
        for idx, row in enumerate(data_rows, start=2):
            if not row.strip():
                continue
            
            # Tách các cột (xử lý CSV có dấu phẩy)
            cols = row.split(',')
            
            # DEBUG: In ra 15 dòng đầu để kiểm tra
            if idx <= 15:
                print(f"\n--- Dòng {idx} ---")
                print(f"   Số cột: {len(cols)}")
                for i, col in enumerate(cols[:15]):  # Chỉ in 15 cột đầu
                    print(f"   Cột {i}: '{col[:50]}'")  # Chỉ in 50 ký tự đầu
            
            if len(cols) < 13:
                print(f"⚠️ Dòng {idx}: Thiếu cột (chỉ có {len(cols)}/13 cột)")
                continue
            
            try:
                # === MAP CỘT THEO HEADER ===
                # Dựa vào header mẫu từ file Excel:
                # Cột 0: STT
                # Cột 1: NGAY
                # Cột 2: 89.0 (Due Date quan trọng!)
                # Cột 7: TEN KHACH HANG
                # Cột 8: NGAY SINH
                # Cột 11: SDT
                # Cột 12: GOI CUOC
                
                ten_kh = cols[7].strip() if len(cols) > 7 else ''
                ngay_89_str = cols[2].strip() if len(cols) > 2 else ''
                sdt_raw = cols[11].strip() if len(cols) > 11 else ''
                goi_cuoc_raw = cols[12].strip() if len(cols) > 12 else ''
                ngay_sinh_str = cols[8].strip() if len(cols) > 8 else ''
                
                if not ten_kh:
                    print(f"⚠️ Dòng {idx}: Không có tên khách hàng")
                    continue
                
                if not ngay_89_str:
                    print(f"⚠️ Dòng {idx}: Không có ngày 89")
                    continue
                
                print(f"\n✅ Dòng {idx}: {ten_kh}")
                print(f"   Ngày 89: '{ngay_89_str}'")
                print(f"   SDT: '{sdt_raw}'")
                print(f"   Gói cước: '{goi_cuoc_raw}'")
                
                # Parse dữ liệu
                due_date = parse_date(ngay_89_str)
                if not due_date:
                    print(f"   ❌ Không parse được ngày")
                    continue
                
                print(f"   ✅ Due date: {due_date}")
                
                phone = extract_phone(sdt_raw)
                price, months = parse_package(goi_cuoc_raw)
                
                print(f"   📱 Phone: {phone}")
                print(f"   📦 Months: {months}")
                
                # Xác định số ngày báo trước
                if months == 2:
                    remind_days = 30
                    sim_type = "SIM 2 THÁNG"
                else:
                    remind_days = 7
                    sim_type = "SIM 3 THÁNG"
                
                remind_date = due_date - timedelta(days=remind_days)
                days_diff = (today - remind_date).days
                
                print(f"   ⏰ Remind date: {remind_date}")
                print(f"   📊 Days diff: {days_diff}")
                
                # Tạo task description
                task_desc = f"Làm sim {ten_kh.upper()} {phone}"
                
                # === PHÂN LOẠI THEO MỨC ĐỘ KHẨN CẤP ===
                if months == 2 and due_date < today:
                    days_overdue = (today - due_date).days
                    print(f"   🔥 SIM 2 THÁNG - QUÁ HẠN {days_overdue} ngày")
                    urgent_overdue.append({
                        'name': ten_kh.upper(),
                        'phone': phone,
                        'due_date': due_date,
                        'days_overdue': days_overdue,
                        'package': goi_cuoc_raw,
                        'sim_type': sim_type
                    })
                elif remind_date <= today <= due_date:
                    days_left = (due_date - today).days
                    print(f"   ⚠️ Quá hạn hoặc sắp hết hạn")
                    normal_overdue.append({
                        'name': ten_kh.upper(),
                        'phone': phone,
                        'due_date': due_date,
                        'days_left': days_left,
                        'package': goi_cuoc_raw,
                        'sim_type': sim_type
                    })
                elif today <= remind_date <= today + timedelta(days=7):
                    days_to = (remind_date - today).days
                    print(f"   📌 Sắp đến hạn nhắc")
                    due_soon.append({
                        'name': ten_kh.upper(),
                        'phone': phone,
                        'due_date': due_date,
                        'days_to': days_to,
                        'package': goi_cuoc_raw,
                        'sim_type': sim_type
                    })
                else:
                    print(f"   ℹ️ Chưa đến lúc nhắc")
                
                # === XỬ LÝ SINH NHẬT ===
                if ngay_sinh_str:
                    birth_date = parse_date(ngay_sinh_str)
                    if birth_date:
                        age_19_date = birth_date.replace(year=birth_date.year + 19)
                        days_until = (age_19_date - today).days
                        if days_until <= 30:
                            birthday_alerts.append({
                                'name': ten_kh.upper(),
                                'phone': phone,
                                'birth_date': birth_date,
                                'days_until': days_until
                            })
                            print(f"   🎂 Sinh nhật 19 tuổi: {days_until} ngày nữa")
                
            except Exception as e:
                print(f"❌ Lỗi xử lý dòng {idx}: {e}")
                continue
        
        # ==================== TẠO TIN NHẮN ====================
        print(f"\n📊 KẾT QUẢ XỬ LÝ:")
        print(f"   - Khẩn cấp (sim 2 tháng quá hạn): {len(urgent_overdue)}")
        print(f"   - Quá hạn thông thường: {len(normal_overdue)}")
        print(f"   - Sắp đến hạn: {len(due_soon)}")
        print(f"   - Sinh nhật: {len(birthday_alerts)}")
        
        message = "🔔 <b>BÁO CÁO CÔNG VIỆC SIM</b> 🔔\n"
        message += f"📅 {today.strftime('%d/%m/%Y')}\n"
        message += "━" * 35 + "\n\n"
        
        if urgent_overdue:
            message += "🚨 <b>KHẨN CẤP - SIM 2 THÁNG QUÁ HẠN</b> 🚨\n\n"
            for item in urgent_overdue:
                message += f"🔥 {item['name']}\n"
                message += f"   📱 {item['phone']}\n"
                message += f"   📅 Hết hạn: {item['due_date']}\n"
                message += f"   ⚠️ QUÁ HẠN {item['days_overdue']} NGÀY\n"
                message += f"   📦 {item['package']}\n\n"
        
        if normal_overdue:
            message += "⚠️ <b>CÔNG VIỆC QUÁ HẠN</b> ⚠️\n\n"
            for item in normal_overdue:
                if item['days_left'] < 0:
                    message += f"❗ {item['name']}\n"
                    message += f"   📱 {item['phone']}\n"
                    message += f"   📅 Hết hạn: {item['due_date']}\n"
                    message += f"   ⚠️ QUÁ HẠN {abs(item['days_left'])} NGÀY\n\n"
                else:
                    message += f"⏰ {item['name']}\n"
                    message += f"   📱 {item['phone']}\n"
                    message += f"   📅 Đến hạn: {item['due_date']}\n"
                    message += f"   ⏰ Còn {item['days_left']} ngày\n\n"
        
        if due_soon:
            message += "📌 <b>CÔNG VIỆC SẮP ĐẾN HẠN</b> 📌\n\n"
            for item in due_soon:
                message += f"📋 {item['name']}\n"
                message += f"   📱 {item['phone']}\n"
                message += f"   📅 Đến hạn: {item['due_date']}\n"
                message += f"   ⏰ Nhắc sau {item['days_to']} ngày\n\n"
        
        if birthday_alerts:
            message += "🎂 <b>SINH NHẬT 19 TUỔI</b> 🎂\n\n"
            for item in birthday_alerts:
                if item['days_until'] < 0:
                    message += f"🔥 {item['name']} - ĐÃ ĐỦ 19 TUỔI (quá {abs(item['days_until'])} ngày)\n"
                else:
                    message += f"🎂 {item['name']} - Sắp đủ 19 tuổi (còn {item['days_until']} ngày)\n"
                message += f"   📱 {item['phone']}\n"
                message += f"   📅 SN: {item['birth_date']}\n\n"
        
        if not urgent_overdue and not normal_overdue and not due_soon and not birthday_alerts:
            message += "✅ Hôm nay không có công việc cần xử lý.\n"
            message += "\n💡 Kiểm tra lại dữ liệu trong Google Sheets:\n"
            message += "   - Cột 2 (89.0) phải có ngày dạng YYYY-MM-DD\n"
            message += "   - Cột 7 (TEN KHACH HANG) không được trống\n"
            message += "   - Đảm bảo sheet được chia sẻ công khai\n"
        
        send_telegram_message(message)
        print("\n✅ Đã gửi báo cáo Telegram")
        
    except Exception as e:
        error_msg = f"❌ Lỗi hệ thống: {str(e)}"
        print(error_msg)
        send_telegram_message(error_msg)

# ==================== CHẠY CHÍNH ====================
if __name__ == "__main__":
    print("🚀 Bot nhắc việc khởi động...")
    check_reminders()
    print("🏁 Kết thúc")
