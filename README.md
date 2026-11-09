# TIKTOK AFFILIATE AI STUDIO PRO

> **Phần mềm chuyên nghiệp chạy LOCAL trên Windows giúp tự động hóa 100% quy trình sản xuất video TikTok Affiliate từ ảnh sản phẩm gốc đến video hoàn chỉnh sẵn sàng đăng kênh.**

---

## 1. QUY TRÌNH SẢN XUẤT 5 BƯỚC KHÉP KÍN

1. **Nạp sản phẩm**: Tải ảnh sản phẩm gốc (tìm trên TikTok) và nhập thông tin (công dụng, ưu đãi, giá bán).
2. **Tạo nhân vật AI (Gemini)**: Tool tự động gửi ảnh sản phẩm và prompt sang Gemini để tạo ảnh nhân vật nữ bán hàng thương mại (chuẩn dọc 9:16), giữ nguyên 100% nhận diện bao bì sản phẩm.
3. **Tạo 3 phương án kịch bản (Gemini)**:
   - **Phương án A**: Đánh vào nhu cầu / Nỗi đau khách hàng.
   - **Phương án B**: Tạo sự tò mò / Khám phá bí mật.
   - **Phương án C**: Thuyết phục bằng lợi ích thực tế & Niềm tin.
   - **QUY ĐỊNH BẮT BUỘC**: Mỗi phương án gồm 2 cảnh video riêng biệt. Mỗi cảnh có lời thoại **chính xác 42 từ tiếng Việt** cho thời lượng mục tiêu **10 giây** (nhịp đọc nhanh liền mạch ~4.2 từ/giây, giọng nữ miền Bắc Hà Nội xưng "em", gọi "các bác"). Kèm theo Prompt Veo 3 chi tiết.
4. **Sản xuất video (Google Flow / Veo 3)**: Tự động đưa ảnh nhân vật AI và Prompt Cảnh 1 vào Flow tạo video 1, sau đó đưa Prompt Cảnh 2 tạo video 2 và tải về máy.
5. **Ghép video (FFmpeg Engine)**: Nối Video 1 và Video 2 thành một video TikTok hoàn chỉnh 1080x1920 @ 30fps, âm thanh đồng bộ, không giật lag.

---

## 2. CÔNG NGHỆ & KIẾN TRÚC HỆ THỐNG

- **Backend**: Python 3.12, FastAPI, SQLite, Playwright (Chromium Headed Persistent Context), FFmpeg (H.264/AAC Engine).
- **Frontend**: React 19, TypeScript, Vite, Tailwind CSS v4, Lucide React Icons.
- **Lưu trữ Cục Bộ**:
  - Dữ liệu dự án: `data/projects/{project_id}/` (product, character, scripts, prompts, videos, exports).
  - Phiên đăng nhập trình duyệt: `data/browser_profiles/gemini` và `data/browser_profiles/flow`.
  - Cơ sở dữ liệu: `data/studio.db`.

---

## 3. HƯỚNG DẪN KHỞI ĐỘNG VÀ SỬ DỤNG

### Cách 1: Khởi động tự động bằng file .bat (Khuyên dùng)

1. Nhấp đúp chuột vào file **`start.bat`** (hoặc gõ `.\start.bat` trong PowerShell/CMD).
2. Hệ thống sẽ tự động kiểm tra Python, Node.js, thư viện và FFmpeg, sau đó khởi động Backend và Frontend.
3. Trình duyệt sẽ tự động mở địa chỉ: **`http://127.0.0.1:5173`**.
4. Khi muốn đóng hệ thống, chạy file **`stop.bat`** (hoặc gõ `.\stop.bat`).

### Cách 2: Khởi động thủ công trong PowerShell hoặc CMD

**Khởi động Backend:**
```powershell
.\venv\Scripts\python.exe backend/run.py
```
*(Hoặc đơn giản gõ: `python backend/run.py`)*
Backend chạy tại: `http://127.0.0.1:8000`

**Khởi động Frontend:**
```powershell
cd frontend
npm run dev
```
Frontend chạy tại: `http://127.0.0.1:5173`

---

## 4. KẾT NỐI GEMINI & GOOGLE FLOW

1. Tại thanh Header hoặc trang **Gemini Automation** / **Google Flow Studio**, bấm nút **"Kết nối"**.
2. Cửa sổ trình duyệt Chromium sẽ mở ra.
3. Bạn đăng nhập tài khoản Google của mình và hoàn tất xác minh 2 bước (nếu có).
4. Tool sẽ tự động ghi nhớ phiên đăng nhập vào thư mục `data/browser_profiles/` trên máy tính của bạn.
5. Những lần sau sử dụng, bạn không cần phải đăng nhập lại.

> **Bảo mật tuyệt đối**: Ứng dụng KHÔNG lưu mật khẩu, KHÔNG gửi cookie ra bên ngoài, và khi xuất file ZIP sao lưu dự án, dữ liệu đăng nhập sẽ được loại trừ hoàn toàn.

---

## 5. BA CHẾ ĐỘ HOẠT ĐỘNG LINH HOẠT

Bạn có thể chuyển đổi giữa 3 chế độ ở góc trên bên phải màn hình bất kỳ lúc nào:

1. **TỰ ĐỘNG (Auto)**: Tool thực hiện tuần tự mọi thao tác điền prompt, upload ảnh và tải kết quả. Người dùng chỉ quan sát hoặc xử lý khi có CAPTCHA.
2. **BÁN TỰ ĐỘNG (Semi-Auto)**: Tool tự động chuẩn bị ảnh và điền sẵn prompt vào giao diện web, dừng lại để người dùng xem lại và bấm xác nhận trước khi gửi.
3. **THỦ CÔNG (Manual)**: Dành cho trường hợp Google cập nhật giao diện web bất ngờ. Tool cung cấp sẵn nút sao chép prompt, xem ảnh tham chiếu và cho phép kéo thả file video tải về trực tiếp vào ô tương ứng.

---

## 6. BỘ ĐẾM CHUẨN 42 TỪ & QUÉT CHÍNH SÁCH

- **Bộ đếm thời gian thực**: Khi chỉnh sửa lời thoại, hệ thống tự động đếm từng từ tiếng Việt:
  - `< 42 từ`: Huy hiệu màu vàng cảnh báo thiếu từ.
  - `= 42 từ`: Huy hiệu màu xanh ngọc xác nhận chuẩn 10 giây.
  - `> 42 từ`: Huy hiệu màu đỏ cảnh báo thừa từ.
- **Quét rủi ro chính sách**: Tự động cảnh báo các cụm từ dễ vi phạm chính sách quảng cáo TikTok như tuyên bố chữa khỏi ("trị dứt điểm", "cam kết 100%", "thần dược").

