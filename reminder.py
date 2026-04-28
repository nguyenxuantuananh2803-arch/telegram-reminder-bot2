import requests
from datetime import datetime, timedelta
import os
import re

TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
SHEET_ID = os.getenv('SHEET_ID')

# URL sheet TRA_TRUOC (sử dụng sheet đầu tiên)
SHEET_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid=0"

def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {'chat_id': CHAT_ID, 'text': message, 'parse_mode': 'HTML'}
    try:
        requests.post(url, json=payload)
        print("✅ Đã gửi tin nhắn")
        return True
    except Exception as e:
        print(f"❌ Lỗi gửi tin nhắn: {e}")
        return False

def parse_date(date_str):
    """Chuyển đổi định dạng ngày tháng"""
    if not date_str or date_str.strip() == '':
        return None
    try:
        # Xử lý định dạng YYYY-MM-DD HH:MM:SS
        if ' ' in date_str:
            date_str = date_str.split(' ')[0]
        return datetime.strptime(date_str, '%Y-%m-%d').date()
    except:
        try:
            return datetime.strptime(date_str, '%d/%m/%Y').date()
        except:
            return None

def extract_phone(phone_str):
    """Trích xuất số điện thoại từ các định dạng khác nhau"""
    if not phone_str:
        return "Không có SDT"
    # Tìm số điện thoại (8-11 số)
    phone = re.sub(r'[^\d]', '', str(phone_str))
    if len(phone) >= 8:
        return phone[-8:]  # Lấy 8 số cuối
    return str(phone_str)

def parse_package(package_str):
    """Phân tích gói cước: 363*3, 363x2, 360*3, etc."""
    if not package_str:
        return None, None
    package_str = str(package_str).strip().upper()
    # Tìm pattern số*số hoặc sốxsố
    match = re.search(r'(\d+)[\*x](\d+)', package_str, re.IGNORECASE)
    if match:
        price = int(match.group(1))
        months = int(match.group(2))
        return price, months
    return None, None

def check_reminders():
    try:
        print("🔄 Đang đọc dữ liệu từ sheet TRA_TRUOC...")
        response = requests.get(SHEET_URL, timeout=30)
        if response.status_code != 200:
            send_telegram_message(f"❌ Lỗi: Không đọc được sheet (Mã lỗi: {response.status_code})")
            return
        
        lines = response.text.strip().split('\n')
        if len(lines) < 2:
            print("⚠️ Không có dữ liệu")
            return
        
        # Bỏ qua dòng header
        data_rows = lines[1:]
        today = datetime.now().date()
        reminders = []
        birthday_reminders = []
        warning_reminders = []
        
        # Thời gian nhắc làm sim (cho cột 89)
        remind_before_days = 7
        
        print(f"📅 Hôm nay: {today}")
        print(f"🔍 Đang kiểm tra {len(data_rows)} khách hàng...")
        
        for idx, row in enumerate(data_rows, start=2):
            if not row.strip():
                continue
            
            cols = row.split(',')
            if len(cols) < 10:
                continue
            
            # Lấy dữ liệu theo index từ file Excel
            # Index cần điều chỉnh theo cột thực tế
            try:
                # Giả sử cấu trúc: STT(0), NGAY(1), NGAY_89(2), NGAY_94(3), TRUNG_TAM(4), FB(5), NHA_MANG(6), TEN(7), NGAY_SINH(8), ... SDT(11), GOI_CUOC(12)
                stt = cols[0].strip()
                ngay_89_str = cols[2].strip() if len(cols) > 2 else ''
                ten_kh = cols[7].strip() if len(cols) > 7 else ''
                ngay_sinh_str = cols[8].strip() if len(cols) > 8 else ''
                sdt_raw = cols[11].strip() if len(cols) > 11 else ''
                goi_cuoc_raw = cols[12].strip() if len(cols) > 12 else ''
                
                if not ten_kh:
                    continue
                
                # Xử lý ngày 89
                due_date = parse_date(ngay_89_str)
                if not due_date:
                    continue
                
                # Xử lý số điện thoại
                phone = extract_phone(sdt_raw)
                
                # Xử lý gói cước
                price, months = parse_package(goi_cuoc_raw)
                
                # Tạo task description
                task_desc = f"Làm sim {ten_kh.upper()} {phone}"
                if months:
                    task_desc += f" (gói {price}*{months} - {months} tháng)"
                    if months == 2:
                        warning_reminders.append({
                            'task': task_desc,
                            'due_date': due_date,
                            'phone': phone,
                            'name': ten_kh,
                            'note': '⚠️ GÓI 2 THÁNG - CẦN THAY SIM SAU 2 THÁNG'
                        })
                
                # 1. Báo trước 7 ngày cột 89
                remind_date = due_date - timedelta(days=remind_before_days)
                if remind_date <= today <= due_date:
                    if today > due_date:
                        status = "🔥 ĐÃ QUÁ HẠN"
                    else:
                        days_left = (due_date - today).days
                        status = f"⏰ Còn {days_left} ngày"
                    
                    reminders.append({
                        'task': task_desc,
                        'due_date': due_date,
                        'status': status,
                        'urgent': today >= due_date
                    })
                    print(f"📌 [{idx}] {ten_kh} - Hạn: {due_date} ({status})")
                
                # 2. Xử lý sinh nhật 19 tuổi
                if ngay_sinh_str:
                    birth_date = parse_date(ngay_sinh_str)
                    if birth_date:
                        age_19_date = birth_date.replace(year=birth_date.year + 19)
                        days_until_19 = (age_19_date - today).days
                        
                        if days_until_19 <= 14:  # Báo trong vòng 14 ngày
                            if days_until_19 <= 0:
                                birth_status = "🔥 ĐÃ ĐỦ 19 TUỔI"
                            else:
                                birth_status = f"⏰ Còn {days_until_19} ngày nữa đủ 19 tuổi"
                            
                            birthday_reminders.append({
                                'name': ten_kh.upper(),
                                'phone': phone,
                                'birth_date': birth_date,
                                'age_19_date': age_19_date,
                                'status': birth_status,
                                'due_date': due_date
                            })
                            print(f"🎂 [{idx}] {ten_kh} - {birth_status} (SN: {birth_date})")
                
            except Exception as e:
                print(f"⚠️ Lỗi dòng {idx}: {e}")
                continue
        
        # Gửi thông báo tổng hợp
        message = "🔔 <b>BÁO CÁO CÔNG VIỆC HÀNG NGÀY</b> 🔔\n"
        message += f"📅 {today.strftime('%d/%m/%Y')} (Giờ Hàn Quốc 10:00)\n"
        message += "━" * 20 + "\n\n"
        
        if reminders:
            message += "📌 <b>NHẮC LÀM SIM (TRƯỚC 7 NGÀY):</b>\n"
            for r in reminders:
                emoji = "✅" if not r['urgent'] else "🔥"
                message += f"{emoji} {r['task']}\n"
                message += f"   📅 Đến hạn: {r['due_date']}\n"
                message += f"   📍 {r['status']}\n\n"
        else:
            message += "✅ Không có sim cần làm trong tuần này.\n\n"
        
        if birthday_reminders:
            message += "🎂 <b>NHẮC SINH NHẬT 19 TUỔI:</b>\n"
            for b in birthday_reminders:
                message += f"🎂 {b['name']} - {b['phone']}\n"
                message += f"   📅 SN: {b['birth_date']}\n"
                message += f"   📍 {b['status']}\n"
                if b.get('due_date'):
                    message += f"   📌 Hạn sim: {b['due_date']}\n"
                message += "\n"
        
        if warning_reminders:
            message += "⚠️ <b>CẢNH BÁO GÓI CƯỚC 2 THÁNG:</b>\n"
            for w in warning_reminders:
                message += f"⚠️ {w['task']}\n"
                message += f"   📅 Hết hạn: {w['due_date']}\n"
                message += f"   📍 {w['note']}\n\n"
        
        if not reminders and not birthday_reminders and not warning_reminders:
            message += "✨ Hôm nay không có việc gì cần xử lý.\n"
        
        message += "\n━" * 20 + "\n"
        message += "💡 <i>Vui lòng kiểm tra và xử lý kịp thời.</i>"
        
        send_telegram_message(message)
        print(f"✅ Đã gửi báo cáo với {len(reminders)} sim, {len(birthday_reminders)} sinh nhật, {len(warning_reminders)} cảnh báo")
        
    except Exception as e:
        error_msg = f"❌ Lỗi hệ thống: {str(e)}"
        print(error_msg)
        send_telegram_message(error_msg)

if __name__ == "__main__":
    print("🚀 Bot nhắc việc khởi động...")
    check_reminders()
    print("🏁 Kết thúc")
