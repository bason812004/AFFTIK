import os
import re
import sys
import logging
import asyncio
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


def extract_text_via_windows_ocr(image_path: str) -> str:
    """
    Extracts text from an image file using Windows 10/11 native OCR (Windows.Media.Ocr).
    Extremely fast (~0.3s) and runs entirely locally without any external API or heavy dependencies.
    """
    if not image_path or not os.path.exists(image_path):
        return ""

    script_path = Path(__file__).resolve().parent / "win_ocr.ps1"
    if not script_path.exists():
        return ""

    try:
        res = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-ExecutionPolicy", "Bypass",
                "-File", str(script_path),
                "-ImagePath", str(Path(image_path).resolve())
            ],
            capture_output=True,
            timeout=8
        )
        return res.stdout.decode("utf-8", errors="ignore").strip()
    except Exception as e:
        logger.debug(f"Windows native OCR extraction error: {e}")
        return ""


def _normalize_text(text: str) -> str:
    import unicodedata
    t = text.lower().replace('đ', 'd').replace('$', 'e')
    nfkd = unicodedata.normalize('NFKD', t)
    cleaned = ''.join([c for c in nfkd if not unicodedata.combining(c)])
    cleaned = cleaned.replace('ö', 'o').replace('ä', 'a').replace('ë', 'e')
    return cleaned


def parse_product_from_ocr_text(ocr_text: str, original_filename: str = "") -> Optional[Dict[str, Any]]:
    """
    Parses OCR text extracted from e-commerce screenshots / product photos into:
    - product_name
    - category
    - benefits
    - highlights
    """
    if not ocr_text or len(ocr_text.strip()) < 3:
        return None

    raw_lines = [l.strip() for l in ocr_text.splitlines() if len(l.strip()) > 1]
    norm_lines = [_normalize_text(l) for l in raw_lines]

    # Filter out common mobile screenshot UI noise
    noise_patterns = [
        r'^\d{1,2}:\d{2}$', r'^\d+/\d+$', r'tim\s*san\s*pham', r'tuong\s*tu', r'tddng\s*tv',
        r'q\s*tim', r'uy\s*tin', r'tu\s*van', r'van\s*chuyen', r'mien\s*phi', r'shopee', r'tiktok', r'lazada',
        r'^zalo$', r'zalo', r'^messenger$', r'^facebook$'
    ]
    meaningful_lines = []
    meaningful_norm = []
    for raw_l, norm_l in zip(raw_lines, norm_lines):
        if any(re.search(pat, norm_l) for pat in noise_patterns):
            continue
        meaningful_lines.append(raw_l)
        meaningful_norm.append(norm_l)

    combined_norm = " ".join(meaningful_norm)

    # Rule 0: Demolition Hammers / Concrete Drills / Power Tools (Máy đục bê tông, máy đục tường, máy khoan)
    if any(k in combined_norm for k in ["duc be tong", "may duc", "duc tuong", "khoan duc", "be tong", "khoan be tong", "duc cam tay", "khoan"]):
        p_name = "Máy Đục Tường Bê Tông Cầm Tay Chuyên Dụng (Kèm 2 Mũi Đục)"
        from backend.app.services.pipeline_runner import ensure_42_words
        s1 = ensure_42_words(
            "Các bác thợ đang tìm máy đục bê tông siêu khỏe, bền bỉ cho công trình của mình? Dòng máy đục cầm tay công suất lớn này là trợ thủ đắc lực, lực đập cực mạnh giúp phá dỡ bê tông nhanh chóng!",
            filler="cho cả gia đình mình yên tâm sử dụng mỗi ngày luôn nhé các bác ơi"
        )
        s2 = ensure_42_words(
            "Thân máy bọc kim loại chịu lực cao, tay cầm phụ chống rung êm ái kèm tặng sẵn hai mũi đục thép tôi siêu bền. Hôm nay shop đang trợ giá cực sâu và miễn phí giao hàng toàn quốc, bấm vào giỏ hàng!",
            filler="vào giỏ hàng bên dưới để chốt đơn nhận ngay ưu đãi đặc biệt hôm nay nhé"
        )
        return {
            "product_name": p_name,
            "category": "Dụng cụ cầm tay & Máy xây dựng",
            "benefits": "động cơ công suất lớn đục phá bê tông siêu khỏe, lực đập mạnh mẽ phá vỡ bê tông tường gạch nhanh chóng, đi kèm tay cầm phụ chống rung và 2 mũi đục dẹt nhọn thép tôi siêu bền",
            "highlights": "mô tơ dây đồng 100%, thân máy hợp kim chịu va đập, tay cầm cao su êm ái chống trượt kèm 2 mũi đục dẹt nhọn tiện lợi",
            "target_customer": "Thợ xây dựng, thợ cơ khí, công trình và gia đình cần sửa chữa nhà cửa",
            "scene1_dialogue": s1,
            "scene2_dialogue": s2
        }

    # Rule 1: Kids Electric Vehicles (Xe điện trẻ em, ATV, Ô tô điện)
    if any(k in combined_norm for k in ["xe dien", "xe may", "atv", "4 cho", "9199", "dia hinh"]):
        p_name = "Xe Máy Điện ATV 4 Bánh Địa Hình Trẻ Em (Mã 9199)"
        s1 = "Ba mẹ tìm xe điện ATV địa hình cho bé? Xe bốn bánh chín một chín chín sở hữu thiết kế thể thao hầm hố, khung chắc chắn chịu lực tốt giúp bé thỏa sức vận động vui chơi mỗi ngày nhé!"
        s2 = "Bánh xe địa hình ma sát bám đường chống trượt kèm đèn pha LED sáng. Hôm nay shop trợ giá cực hời và miễn phí giao hàng, ba mẹ nhanh tay bấm ngay vào giỏ hàng bên dưới để đặt mua nhé!"
        return {
            "product_name": p_name,
            "category": "Đồ chơi & Xe điện trẻ em",
            "benefits": "xe máy điện địa hình 4 bánh thể thao hầm hố, bánh ma sát bám đường chống trượt an toàn, thân máy chắc chắn chịu lực tốt giúp bé thỏa sức vận động",
            "highlights": "bánh xe địa hình ma sát tốt, thiết kế hầm hố thể thao, thân máy chắc chắn chịu lực tốt kèm đèn pha LED siêu sáng",
            "target_customer": "Các bậc phụ huynh có con nhỏ muốn tìm xe điện an toàn, bền bỉ cho bé",
            "scene1_dialogue": s1,
            "scene2_dialogue": s2
        }

    # Rule 2: Pressure Washers (Máy rửa xe)
    if any(k in combined_norm for k in ["rua xe", "sakura", "3800w", "ap luc", "xit rua"]):
        p_name = "Máy Rửa Xe Nhật Bản Sakura 3800W"
        return {
            "product_name": p_name,
            "category": "Thiết bị điện & Dụng cụ rửa xe",
            "benefits": "công suất cực mạnh 3800W xịt rửa áp lực cao đánh bay bùn đất rong rêu nhanh chóng, đi kèm dây cao áp 15 mét và bình tạo bọt tuyết tiện lợi",
            "highlights": "mô tơ cảm ứng từ bền bỉ, lõi đồng nguyên chất 100%, tự ngắt thông minh khi nhả cò súng",
            "target_customer": "Chủ xe máy, ô tô và các gia đình cần vệ sinh sân vườn, nhà cửa",
            "scene1_dialogue": "Cả nhà đang tìm máy rửa xe áp lực cao công suất mạnh mẽ, bền bỉ cho gia đình mình? Máy rửa xe Sakura ba nghìn tám trăm oát từ Nhật Bản chính là lựa chọn số một, đánh bay mọi vết bẩn cứng đầu chỉ trong chớp mắt!",
            "scene2_dialogue": "Mô tơ cảm ứng từ êm ái, lõi đồng nguyên chất bền bỉ kèm dây cao áp mười lăm mét và bình bọt tuyết tiện lợi. Hôm nay shop trợ giá cực sâu và miễn phí giao hàng, các bác nhanh tay bấm ngay vào giỏ hàng đặt mua nhé!"
        }

    # Rule 3: Electric Kettles (Ấm siêu tốc)
    if any(k in combined_norm for k in ["am dun", "sieu toc", "kettle", "1.8l", "dun sieu toc", "am sieu toc"]):
        p_name = "Ấm Đun Siêu Tốc Inox 1.8L"
        return {
            "product_name": p_name,
            "category": "Điện gia dụng & Nhà bếp",
            "benefits": "công suất lớn đun sôi nước siêu tốc chỉ trong 3-5 phút, ruột inox 304 nguyên khối an toàn cho sức khỏe và tự ngắt điện khi nước sôi",
            "highlights": "ruột inox 304 sáng bóng chống bám cặn, vỏ cách nhiệt an toàn, tự ngắt khi cạn nước",
            "target_customer": "Gia đình, văn phòng, sinh viên cần pha trà, cà phê, nấu mì nhanh chóng",
            "scene1_dialogue": "Cả nhà đang tìm ấm đun siêu tốc bền đẹp, đun nước nhanh và an toàn cho gia đình mình? Chiếc ấm siêu tốc inox một chấm tám lít này chính là giải pháp hoàn hảo, đun sôi nước chỉ trong ba phút cực kỳ tiện lợi mỗi ngày!",
            "scene2_dialogue": "Ruột bình làm bằng inox ba linh tư sáng bóng, chống rỉ sét và tuyệt đối an toàn cho sức khỏe. Hôm nay shop đang trợ giá cực hời kèm miễn phí giao hàng, cả nhà nhanh tay bấm ngay vào giỏ hàng bên dưới để sở hữu nhé!"
        }

    # Rule 4: Baby Food Trays (Khay ăn dặm)
    if any(k in combined_norm for k in ["an dam", "khay an", "cho be", "chia ngan"]):
        p_name = "Khay Ăn Dặm Inox 304 Chia Ngăn Cho Bé"
        return {
            "product_name": p_name,
            "category": "Mẹ & Bé",
            "benefits": "chất liệu inox 304 kháng khuẩn cao cấp không lo rơi vỡ, chia ngăn khoa học giúp bé hào hứng ăn ngon miệng mỗi bữa",
            "highlights": "inox 304 kháng khuẩn, bo viền mịn chống xước, nắp đậy khít chống tràn và chịu nhiệt tiệt trùng tốt",
            "target_customer": "Các mẹ bỉm sữa đang trong giai đoạn cho bé ăn dặm khoa học",
            "scene1_dialogue": "Ba mẹ tìm khay ăn dặm an toàn, bền bỉ cho con? Khay inox ba linh tư này là lựa chọn tuyệt vời. Chất liệu kháng khuẩn, rơi không vỡ, chia ngăn khoa học giúp bé hào hứng ăn ngon mỗi ngày.",
            "scene2_dialogue": "Khay bo viền mịn chống xước, chịu nhiệt tiệt trùng tốt và dễ lau rửa. Hôm nay trợ giá cực hời kèm tặng thìa nĩa, ba mẹ nhanh tay bấm vào giỏ hàng bên dưới để sở hữu cho bé yêu nhé!"
        }

    # Rule 5: Leather Bags / Briefcases (Cặp da, túi xách công sở)
    if any(k in combined_norm for k in ["cap da", "tui xach", "lecos", "cong so", "da nam", "laptop"]):
        p_name = "Cặp Da Nam Công Sở Cao Cấp LECOS"
        return {
            "product_name": p_name,
            "category": "Thời trang & Phụ kiện công sở",
            "benefits": "chất liệu da cao cấp chống thấm nước, chống bong tróc, form đứng sang trọng đựng vừa laptop và tài liệu A4 cực kỳ lịch lãm",
            "highlights": "da cao cấp mềm mịn, khóa kéo kim loại chống gỉ, ngăn chia khoa học, dây đeo chéo tháo rời tiện lợi",
            "target_customer": "Nhân viên văn phòng, doanh nhân, quý ông công sở",
            "scene1_dialogue": "Các anh đang tìm kiếm chiếc cặp da nam sang trọng và tiện lợi? Cặp da LECOS cao cấp này chính là sự lựa chọn hoàn hảo nhất. Da chống thấm nước tuyệt đối, form chuẩn đứng tôn dáng sang trọng hơn khi gặp đối tác!",
            "scene2_dialogue": "Thiết kế lịch lãm, đường may tinh tế cùng quai đeo êm ái làm điểm tựa phong thái thành đạt. Hôm nay giảm giá mạnh kèm quà tặng ví da, các anh nhanh tay bấm vào giỏ hàng bên dưới nhận ưu đãi nhé!"
        }

    from backend.app.services.pipeline_runner import ensure_42_words

    # Rule 6: Laser Leveling / Cross-line lasers (Máy cân mực laser, máy bắn cốt laser)
    if any(k in combined_norm for k in ["laser", "can muc", "ban cot", "do hieng", "can bang", "tia laser", "215 tia", "5 tia", "12 tia"]):
        p_name = "Máy Cân Mực Laser Siêu Sáng (Bắn Cốt Tự Động Cân Bằng)"
        s1 = "Bác thợ tìm máy cân mực laser siêu sáng cho công trình? Máy bắn cốt cân bằng tự động là trợ thủ đắc lực, tia sáng cực nét hỗ trợ thi công ốp lát cho các bác yên tâm sử dụng nhé!"
        s2 = "Bóng laser siêu bền, tự cân bằng cùng pin dung lượng cao dùng cả ngày. Hôm nay shop trợ giá sâu kèm miễn phí vận chuyển, các bác hãy bấm vào giỏ hàng bên dưới để chốt đơn nhận ưu đãi nhé!"
        return {
            "product_name": p_name,
            "category": "Dụng cụ đo lường & Thiết bị xây dựng",
            "benefits": "chùm tia laser siêu sáng nhìn rõ ngoài trời nắng và trong nhà, cơ chế tự động cân bằng chuẩn xác báo động khi nghiêng, hỗ trợ đo đạc thi công ốp lát nhanh chóng",
            "highlights": "bóng đèn laser nhập khẩu siêu bền, pin sạc dung lượng cao dùng cả ngày, kèm chân xoay 360 độ và hộp chống sốc tiện lợi",
            "target_customer": "Thợ xây dựng, thợ ốp lát gạch, thợ thạch cao, thợ nội thất và gia đình sửa chữa",
            "scene1_dialogue": s1,
            "scene2_dialogue": s2
        }

    # Rule 7: Vacuum Sealer Machines (Máy hút chân không thực phẩm)
    if any(k in combined_norm for k in ["chan khong", "may hut", "star ker", "sk-x20", "may thoi"]):
        p_name = "Máy Hút Chân Không Thực Phẩm STAR KER (Model SK-X20 Có Hút & Thổi)"
        s1 = "Cả nhà tìm máy hút chân không thực phẩm cho gia đình? Máy hút chân không Star Ker là giải pháp số một, giữ thực phẩm tươi ngon gấp năm lần cực kỳ tiện lợi cho cả nhà yên tâm sử dụng!"
        s2 = "Thiết kế nhỏ gọn, lực hút mạnh mẽ tích hợp cả hút và thổi khí. Hôm nay shop trợ giá hời kèm tặng cuộn túi, cả nhà nhanh tay bấm vào giỏ hàng bên dưới để chốt đơn nhận ưu đãi nhé!"
        return {
            "product_name": p_name,
            "category": "Thiết bị gia dụng & Bảo quản thực phẩm",
            "benefits": "lực hút chân không cực mạnh bảo quản thực phẩm tươi ngon gấp 5 lần, ngăn ngừa ẩm mốc và vi khuẩn, tích hợp 2 chế độ hút chân không và thổi khí thông minh",
            "highlights": "đường hàn miệng túi rộng 30cm dán kín miệng túi, lực hút mạnh mẽ, nhỏ gọn dễ vệ sinh lau chùi",
            "target_customer": "Các bà nội trợ, gia đình, quán ăn và hộ kinh doanh đóng gói thực phẩm",
            "scene1_dialogue": s1,
            "scene2_dialogue": s2
        }

    # Rule 8: Poultry Veterinary Medicine (Thuốc thú y gia cầm QIN YI PIAN)
    if any(k in combined_norm for k in ["thu6c", "thuoc", "gia cam", "qin yi pian", "ga vit", "chim bo cau", "duong ruot", "100 vien", "diieu hoa", "chudng dieu"]):
        p_name = "Thuốc Thú Y Cho Gia Cầm QIN YI PIAN (Hộp 100 Viên Đặc Trị Đường Ruột)"
        s1 = "Bà con tìm thuốc đặc trị đường ruột cho gà vịt? Thuốc thú y gia cầm Qin Yi Pian dạng viên là giải pháp cứu cánh, dứt điểm phân xanh phân trắng cho đàn vật nuôi khỏe mạnh và mau lớn nhé!"
        s2 = "Thành phần thảo dược lành tính, điều hòa tiêu hóa dùng cho gà con lẫn gà lớn. Hôm nay shop trợ giá tốt kèm miễn phí giao hàng, bà con hãy bấm ngay vào giỏ hàng bên dưới nhận ưu đãi nhé!"
        return {
            "product_name": p_name,
            "category": "Thuốc thú y & Chăn nuôi gia cầm",
            "benefits": "đặc trị tiêu chảy, phân xanh phân trắng, chướng diều và rối loạn tiêu hóa ở gà vịt chim bồ câu, giúp vật nuôi phục hồi đường ruột khỏe mạnh nhanh chóng",
            "highlights": "dạng viên tiện lợi dễ cho uống trực tiếp hoặc hòa nước, thành phần thảo dược an toàn lành tính, dùng được cho cả gà con và gia cầm lớn",
            "target_customer": "Chủ trang trại, hộ chăn nuôi gà vịt, người nuôi chim cảnh và gia cầm",
            "scene1_dialogue": s1,
            "scene2_dialogue": s2
        }

    # Rule 8B: Livestock Probiotics & Herbal Bedding Powder (Men vi sinh và thảo dược rắc chuồng BIOFARM GOLDENVET)
    if any(k in combined_norm for k in ["biofarm", "goldenvet", "men visinh", "men vi sinh", "rac chuong", "thao duoc rac chuong", "khu mui chuong"]):
        is_combo = any(k in combined_norm for k in ["combo", "3kg", "3 kg", "3 tui", "tiet kiem hon"])
        p_name = (
            "Men Vi Sinh Và Thảo Dược Rắc Chuồng BIOFARM GOLDENVET (Combo 3 Túi 3KG)"
            if is_combo else
            "Men Vi Sinh Và Thảo Dược Rắc Chuồng BIOFARM GOLDENVET (Túi 1KG)"
        )
        s1 = "Bà con chăn nuôi đau đầu vì mùi hôi chuồng trại và dịch bệnh? Men vi sinh thảo dược rắc chuồng Biofarm Goldenvet xử lý triệt để khí độc, giữ nền chuồng khô ráo sạch sẽ giúp đàn vật nuôi khỏe mạnh!"
        s2 = "Kết hợp men vi sinh hoạt lực cao cùng thảo dược tự nhiên, phân hủy phân thải nhanh và ngừa tiêu chảy hiệu quả. Combo ba túi ba ký siêu tiết kiệm đang trợ giá hời, bà con bấm giỏ hàng ngay!"
        return {
            "product_name": p_name,
            "category": "Chế phẩm sinh học & Thú y chăn nuôi",
            "benefits": "khử mùi hôi và khí độc chuồng trại cực mạnh, phân hủy nhanh chất thải chăn nuôi, ức chế vi khuẩn gây bệnh hô hấp và tiêu chảy cho heo gà vịt",
            "highlights": "kết hợp đa chủng men vi sinh hoạt lực cao và thảo dược tự nhiên, an toàn lành tính cho vật nuôi, giữ nền chuồng luôn khô ráo sạch sẽ",
            "target_customer": "Trang trại và hộ chăn nuôi heo, gà, vịt, gia súc gia cầm",
            "scene1_dialogue": s1,
            "scene2_dialogue": s2
        }

    # Rule 9: Organic 3-in-1 Bio Fertilizer (Phân bón hữu cơ vi sinh Organic 3 Trong 1)
    if any(k in combined_norm for k in ["organic", "3 trong 1", "cai teo dat", "cai tao dat", "kich re", "cong nghe neb", "cuu dat cuu cay", "huu co vi sinh"]):
        p_name = "Phân Bón Hữu Cơ Vi Sinh Organic 3 Trong 1 (Cải Tạo Đất & Kích Rễ Cây)"
        s1 = "Bà con tìm phân bón hữu cơ cải tạo đất, kích rễ cây? Chế phẩm vi sinh Organic ba trong một công nghệ NEB là giải pháp vàng giúp cây bung rễ xanh lá vượt trội cho mùa màng luôn bội thu!"
        s2 = "Công thức đa chủng vi sinh có lợi, phục hồi đất bạc màu chống rửa trôi phân bón. Hôm nay shop trợ giá hời kèm miễn phí vận chuyển, bà con hãy bấm vào giỏ hàng bên dưới nhận ưu đãi nhé!"
        return {
            "product_name": p_name,
            "category": "Vật tư nông nghiệp & Phân bón cây trồng",
            "benefits": "phục hồi và cải tạo đất cằn cỗi bạc màu bằng vi sinh vật có lợi, kích thích bộ rễ phát triển cực mạnh, ứng dụng công nghệ NEB chống rửa trôi phân bón hiệu quả",
            "highlights": "100% hữu cơ sinh học an toàn thân thiện môi trường, đa chủng vi sinh có lợi, đậm đặc tiết kiệm chi phí bón cây",
            "target_customer": "Nhà vườn, bà con trồng cây ăn trái, hoa kiểng, rau màu và cây nông nghiệp",
            "scene1_dialogue": s1,
            "scene2_dialogue": s2
        }

    # Rule 10: Foliar Fertilizer SUN 30-10-10 (Phân bón lá cao cấp SUN 30-10-10 Vua Bật Chồi)
    if any(k in combined_norm for k in ["phan bon la", "30 - 10", "30-10", "vua bat choi", "vija bat choi", "bung dot", "map choi", "400 lit"]):
        p_name = "Phân Bón Lá Cao Cấp SUN 30-10-10 Vua Bật Chồi (Hộp Pha 400 Lít)"
        s1 = ensure_42_words(
            "Bà con nhà vườn muốn cây trồng bung đọt nhanh, mập chồi và xanh dày lá? Phân bón lá cao cấp SUN ba mươi mười mười Vua Bật Chồi giúp cây bật mầm khỏe mạnh, phát triển vượt trội mỗi ngày!",
            filler="cho bà con nhà vườn yên tâm canh tác đạt năng suất cao nhất nhé"
        )
        s2 = ensure_42_words(
            "Một hũ đậm đặc pha được tới bốn trăm lít nước, tan nhanh hoàn toàn giúp lá hấp thụ dinh dưỡng tối đa. Hôm nay shop trợ giá hời kèm miễn phí giao hàng, bà con bấm giỏ hàng chốt đơn ngay!",
            filler="vào giỏ hàng bên dưới để chốt đơn nhận ngay ưu đãi đặc biệt hôm nay nhé"
        )
        return {
            "product_name": p_name,
            "category": "Vật tư nông nghiệp & Phân bón lá",
            "benefits": "kích thích cây trồng bung đọt cực mạnh, mập chồi, to lá xanh dày bóng mượt, phục hồi cây suy yếu nhanh chóng sau thu hoạch",
            "highlights": "hàm lượng NPK 30-10-10 giàu đạm chuyên biệt cho giai đoạn phát triển thân lá, 1 hũ pha được 400 lít nước siêu tiết kiệm",
            "target_customer": "Bà con nông dân, nhà vườn trồng cây ăn trái, rau màu, hoa kiểng và cây công nghiệp",
            "scene1_dialogue": s1,
            "scene2_dialogue": s2
        }

    # Rule 11: 2-in-1 Electric Milk Frother & Egg Beater Y7 (Máy khuấy điện 2 in 1 Y7 đánh bọt cà phê & đánh trứng)
    if any(k in combined_norm for k in ["may khuay", "khuay dien", "khuay dlen", "2 in 1", "ba toc do", "sac nhanh type-c", "danh trung", "danh bot"]):
        p_name = "Máy Khuấy Điện Cầm Tay 2 In 1 Y7 (Đánh Bọt Cà Phê & Đánh Trứng 3 Tốc Độ)"
        s1 = ensure_42_words(
            "Cả nhà thích tự pha cà phê bọt biển hay đánh trứng làm bánh tại nhà? Máy khuấy điện cầm tay hai trong một Y bảy giúp đánh bông bọt sữa và trứng siêu mịn chỉ trong vài chục giây cực nhanh!",
            filler="cho cả gia đình mình yên tâm sử dụng mỗi ngày luôn nhé các bác ơi"
        )
        s2 = ensure_42_words(
            "Máy đi kèm hai đầu khuấy inox ba linh tư an toàn, điều chỉnh ba mức tốc độ mạnh mẽ và sạc nhanh Type-C tiện lợi. Hôm nay shop trợ giá cực hời, cả nhà bấm ngay giỏ hàng đặt mua nhé!",
            filler="vào giỏ hàng bên dưới để chốt đơn nhận ngay ưu đãi đặc biệt hôm nay nhé"
        )
        return {
            "product_name": p_name,
            "category": "Thiết bị nhà bếp & Dụng cụ pha chế",
            "benefits": "đánh bông bọt sữa cà phê và đánh trứng kem tươi cực nhanh chỉ trong vài chục giây, điều chỉnh linh hoạt 3 mức tốc độ mạnh mẽ",
            "highlights": "tặng kèm 2 đầu khuấy inox 304 an toàn thực phẩm dễ tháo lắp vệ sinh, pin sạc nhanh cổng Type-C tiện lợi dùng không dây",
            "target_customer": "Người yêu thích pha chế cà phê tại nhà, làm bánh, nội trợ gia đình và văn phòng",
            "scene1_dialogue": s1,
            "scene2_dialogue": s2
        }

    # Rule 12: Cat Creamy Treats Silver Spoon (Hộp 50 Thanh Súp Thưởng Cho Mèo Silver Spoon 50 x 14g)
    if any(k in combined_norm for k in ["silver spoon", "versp00", "sup thuong", "thijdng cho meo", "50 thanh", "50 x 14g"]):
        p_name = "Hộp 50 Thanh Súp Thưởng Cho Mèo Silver Spoon (50 x 14g)"
        s1 = ensure_42_words(
            "Các sen đang tìm súp thưởng thơm ngon bổ dưỡng cho hoàng thượng nhà mình? Hộp năm mươi thanh súp thưởng cho mèo Silver Spoon sánh mịn, thơm lừng giúp kích thích vị giác cho bé mèo ăn ngon miệng mỗi ngày!",
            filler="cho các bé mèo cưng luôn khỏe mạnh và mượt lông mỗi ngày nhé"
        )
        s2 = ensure_42_words(
            "Hộp lớn năm mươi thanh mười bốn gam đủ sáu hương vị cá biển và thịt gà giàu dinh dưỡng, bổ sung nước tốt cho thận. Hôm nay shop trợ giá cực hời, các sen bấm ngay giỏ hàng chốt đơn nhé!",
            filler="vào giỏ hàng bên dưới để chốt đơn nhận ngay ưu đãi đặc biệt hôm nay nhé"
        )
        return {
            "product_name": p_name,
            "category": "Thức ăn & Phụ kiện thú cưng",
            "benefits": "súp thưởng dạng thanh sánh mịn thơm ngon kích thích vị giác cho mèo biếng ăn, bổ sung nước và dưỡng chất thiết yếu tốt cho hệ tiêu hóa",
            "highlights": "hộp lớn 50 thanh x 14g siêu tiết kiệm, đa dạng 6 hương vị cá ngừ cá hồi thịt gà thơm ngon chuẩn Nhật Bản",
            "target_customer": "Người nuôi mèo, người yêu thú cưng muốn chăm sóc bữa phụ dinh dưỡng cho mèo",
            "scene1_dialogue": s1,
            "scene2_dialogue": s2
        }

    # Rule 13: Super 888 Rice Grain Filling Fertilizer (Combo 5 Chai Phân Bón Sinh Học Super 888 Vô Gạo Chắc Hạt Nặng Ký 250ml Tặng 1)
    if any(k in combined_norm for k in ["super 888", "super888", "vo gao", "chac hat", "nang ky", "sinh hoc chau a", "5 chai 250ml"]):
        p_name = "Combo 5 Chai Phân Bón Sinh Học Super 888 Vô Gạo Chắc Hạt Nặng Ký (250ml Tặng 1)"
        s1 = ensure_42_words(
            "Bà con trồng lúa muốn lúa trổ thoát nhanh, vô gạo siêu tốc, chắc hạt tới cậy thì dùng ngay bộ Super tám tám tám Sinh Học Châu Á này nhé! Giúp xanh ba lá đòng, đứng lá, hạt sáng mẩy nặng ký!",
            filler="cho vụ mùa lúa trúng lớn năng suất vượt trội luôn nhé bà con ơi"
        )
        s2 = ensure_42_words(
            "Đặc biệt mua combo năm chai hai trăm năm mươi mi li lít hôm nay được tặng thêm một chai cực kỳ tiết kiệm. Đang có trợ giá ưu đãi miễn phí vận chuyển, bà con bấm ngay giỏ hàng góc trái nhé!",
            filler="vào giỏ hàng bên dưới để chốt đơn nhận ngay ưu đãi đặc biệt hôm nay nhé"
        )
        return {
            "product_name": p_name,
            "category": "Vật tư nông nghiệp & Phân bón lúa",
            "benefits": "công nghệ vô gạo siêu tốc giúp xanh 3 lá đòng, đứng lá, lúa trổ thoát đều, vô gạo nhanh, sáng hạt no hạt nặng ký",
            "highlights": "combo 5 chai 250ml tặng thêm 1 chai chính hãng Sinh Học Châu Á ASIA siêu tiết kiệm cho nhà nông",
            "target_customer": "Bà con nông dân trồng lúa, đại lý vật tư nông nghiệp",
            "scene1_dialogue": s1,
            "scene2_dialogue": s2
        }

    # Rule 14: Organic NPK 10-10-10 Fertilizer Combo 3 Bags 30KG (Phân Bón Hữu Cơ Combo 3 Bao NPK 10-10-10 Tổng 30KG)
    if any(k in combined_norm for k in ["combo 3 bao npk", "10 10 10", "101010", "tong 30kg", "npk 10"]):
        p_name = "Phân Bón Hữu Cơ Combo 3 Bao NPK 10-10-10 (Tổng 30KG)"
        s1 = ensure_42_words(
            "Bà con làm vườn tìm phân bón cân đối dinh dưỡng cho cây trồng? Combo ba bao phân bón hữu cơ NPK mười mười mười tổng ba mươi ký giúp cây ra rễ khỏe, xanh lá, bung chồi và nuôi trái cực tốt!",
            filler="cho bà con nhà vườn yên tâm canh tác đạt năng suất cao nhất nhé"
        )
        s2 = ensure_42_words(
            "Hạt phân giàu hữu cơ kết hợp đạm lân kali cân bằng mười mười mười, cải tạo đất tơi xốp bền vững. Combo ba bao ba mươi ký đang trợ giá miễn phí giao hàng, bà con bấm ngay giỏ hàng nhé!",
            filler="vào giỏ hàng bên dưới để chốt đơn nhận ngay ưu đãi đặc biệt hôm nay nhé"
        )
        return {
            "product_name": p_name,
            "category": "Vật tư nông nghiệp & Phân bón hữu cơ NPK",
            "benefits": "cung cấp dinh dưỡng NPK 10-10-10 cân đối kết hợp hữu cơ giúp cây bung rễ khỏe, xanh dày lá, phát triển chồi và nuôi dưỡng hoa trái đồng đều",
            "highlights": "combo 3 bao lớn tổng 30kg siêu tiết kiệm, hạt phân tan đều dễ hấp thu, cải tạo đất tơi xốp màu mỡ",
            "target_customer": "Bà con nông dân, nhà vườn trồng cây ăn trái, rau màu, hoa kiểng và cây công nghiệp",
            "scene1_dialogue": s1,
            "scene2_dialogue": s2
        }

    # Rule 15: SUN Flower Blooming Booster Fertilizer (Phân Bón Cao Cấp SUN Kích Hoa Cực Mạnh Ra Hoa Đồng Loạt)
    if any(k in combined_norm for k in ["kich hoa", "ra hoa dong loat", "kich hoa cuc manh", "ich hoa"]):
        p_name = "Phân Bón Cao Cấp SUN Kích Hoa Cực Mạnh (Ra Hoa Đồng Loạt)"
        s1 = ensure_42_words(
            "Bà con trồng hoa kiểng, cây ăn trái muốn cây phân hóa mầm hoa mạnh và ra hoa đồng loạt? Phân bón cao cấp SUN Kích Hoa Cực Mạnh giúp đánh thức mầm ngủ, thúc bông bung đều rực rỡ!",
            filler="cho nhà vườn yên tâm mùa hoa trái rộ đẹp năng suất vượt trội nhé"
        )
        s2 = ensure_42_words(
            "Công thức giàu lân và vi lượng dễ hấp thu giúp cuống hoa mập khỏe, hạn chế rụng nụ và tăng đậu trái tối đa. Hôm nay shop trợ giá kèm miễn phí giao hàng, bà con bấm ngay giỏ hàng nhé!",
            filler="vào giỏ hàng bên dưới để chốt đơn nhận ngay ưu đãi đặc biệt hôm nay nhé"
        )
        return {
            "product_name": p_name,
            "category": "Vật tư nông nghiệp & Phân bón kích hoa",
            "benefits": "kích thích phân hóa mầm hoa cực mạnh, đánh thức mầm ngủ giúp cây ra hoa đồng loạt, bông to màu sắc rực rỡ và hạn chế rụng hoa",
            "highlights": "công thức cao cấp SUN tan nhanh 100%, hấp thụ nhanh qua lá và rễ, tăng tỷ lệ đậu quả và dưỡng hoa bền đẹp",
            "target_customer": "Bà con nhà vườn trồng hoa kiểng, cây cảnh, cây ăn trái",
            "scene1_dialogue": s1,
            "scene2_dialogue": s2
        }

    # Rule 16: Aquaculture Water Treatment Probiotics (Vi sinh xử lý nước ao nuôi OPS Hanbio)
    if any(k in combined_norm for k in ["ao nuoi", "lam sach nuoc", "giam nh3", "no2", "hanbio", "227g"]):
        p_name = "Vi Sinh Xử Lý Nước Ao Nuôi OPS HANBIO (Làm Sạch Nước Giảm Khí Độc)"
        s1 = ensure_42_words(
            "Bà con nuôi tôm cá đang đau đầu vì nước ao ô nhiễm, đáy ao nhiều mùn bã và khí độc NH3, NO2 tăng cao? Vi sinh xử lý nước ao nuôi OPS Hanbio giúp làm sạch nước nhanh chóng và ổn định môi trường ao nuôi!"
        )
        s2 = ensure_42_words(
            "Gói vi sinh đậm đặc hai trăm hai mươi bảy gam chứa mật độ lợi khuẩn cao giúp phân hủy bùn đáy, cho tôm cá khỏe mạnh lớn nhanh. Hôm nay shop trợ giá ưu đãi kèm miễn phí ship, bà con bấm ngay giỏ hàng nhé!"
        )
        return {
            "product_name": p_name,
            "category": "Nông nghiệp & Chăn nuôi",
            "benefits": "làm sạch nước ao nuôi tôm cá nhanh chóng, hấp thụ và giảm nhanh khí độc NH3, NO2, phân hủy mùn bã hữu cơ tích tụ đáy ao giúp ổn định màu nước",
            "highlights": "mật độ bào tử vi sinh có lợi đậm đặc đóng gói 227g tiết kiệm chi phí, 100% sinh học an toàn giúp tôm cá khỏe mạnh, ăn khỏe và lớn nhanh",
            "target_customer": "Bà con nuôi trồng thủy sản, nuôi tôm cá thương phẩm",
            "scene1_dialogue": s1,
            "scene2_dialogue": s2,
            "scene1_action": "Nhân vật tươi cười, đặt tay và chỉ trực tiếp vào gói vi sinh xử lý nước ao nuôi OPS Hanbio trong ảnh tham chiếu, thuyết trình rõ giải pháp làm sạch nước ao nuôi tôm cá, giảm khí độc NH3 NO2 và phân hủy mùn bã đáy ao",
            "scene2_action": "Máy quay tiến nhẹ cận cảnh làm nổi bật bao bì gói vi sinh OPS Hanbio 227g với mật độ lợi khuẩn đậm đặc an toàn cho tôm cá phát triển khỏe mạnh, nhân vật mỉm cười chỉ tay vào sản phẩm rồi chỉ xuống góc trái kêu gọi bà con đặt mua",
            "needs_product_name": False
        }

    # Rule 17: Smart Car Tire Inflator (Máy bơm lốp xe hơi tự ngắt)
    if any(k in combined_norm for k in ["ap suat lop", "bom lop", "van lop", "16p day", "lop day", "may bom lop"]):
        p_name = "Máy Bơm Lốp Xe Hơi Điện Tử Tự Ngắt Thông Minh"
        s1 = ensure_42_words(
            "Các bác tài lái xe đi đường xa lo lắng lốp xe non hơi hay xẹp lốp bất ngờ giữa đường? Trang bị ngay máy bơm lốp xe hơi điện tử thông minh này, giúp bơm căng lốp nhanh chóng chỉ trong vài phút cực kỳ an tâm!"
        )
        s2 = ensure_42_words(
            "Máy có màn hình LED hiển thị áp suất sắc nét, chỉ cần cài mức hơi mong muốn là bơm tự động ngắt chuẩn xác khi lốp đầy. Đang có ưu đãi trợ giá kèm miễn phí giao hàng, các bác bấm ngay giỏ hàng góc trái nhé!"
        )
        return {
            "product_name": p_name,
            "category": "Thiết bị & Dụng cụ chuyên dụng",
            "benefits": "cài đặt thông số áp suất lốp mong muốn và tự động ngắt chuẩn xác khi lốp đầy hơi, giúp bơm căng lốp ô tô, xe máy nhanh chóng ngay tại chỗ chỉ trong vài phút",
            "highlights": "màn hình LED kỹ thuật số hiển thị áp suất rõ nét ban đêm, xi lanh công suất mạnh mẽ, thiết kế nhỏ gọn bỏ cốp xe cứu hộ khẩn cấp mọi lúc mọi nơi",
            "target_customer": "Chủ xe ô tô, tài xế lái xe đường dài và gia đình",
            "scene1_dialogue": s1,
            "scene2_dialogue": s2,
            "scene1_action": "Nhân vật tươi cười, đặt tay và chỉ trực tiếp vào thân máy bơm lốp xe hơi điện tử trong ảnh tham chiếu, giới thiệu tính năng cài đặt áp suất thông minh giúp bơm căng lốp ô tô nhanh chóng ngay tại chỗ",
            "scene2_action": "Máy quay tiến nhẹ cận cảnh làm nổi bật màn hình LED hiển thị áp suất sắc nét, cụm nút cài đặt tự ngắt và đầu van bơm chắc chắn của máy bơm lốp xe hơi, nhân vật mỉm cười chỉ vào máy rồi chỉ xuống góc trái kêu gọi chốt đơn",
            "needs_product_name": False
        }

    # Rule 18: Yellow Leaf & Root Rot Recovery Bio-Fertilizer (Phục hồi vàng lá, thối rễ)
    if any(k in combined_norm for k in ["vang la", "thoi re", "vang l6", "vung re", "phuc hoi vang la"]):
        p_name = "Chế Phẩm Sinh Học Phục Hồi Vàng Lá, Thối Rễ Cây Trồng"
        s1 = ensure_42_words(
            "Bà con làm vườn đang xót xa vì cây ăn trái, cây cảnh bị vàng lá, thối rễ, héo rũ chậm phát triển? Dùng ngay chế phẩm sinh học Phục Hồi Vàng Lá, Thối Rễ này để tái tạo bộ rễ tơ trắng khỏe mạnh giúp cây xanh tốt trở lại!"
        )
        s2 = ensure_42_words(
            "Hoạt chất sinh học thẩm thấu sâu giúp khoanh vùng nấm hại, cải tạo đất vùng rễ và kích thích cây bung đọt mới cực nhanh. Đang có ưu đãi trợ giá kèm miễn phí giao hàng toàn quốc, bà con bấm ngay giỏ hàng góc trái nhé!"
        )
        return {
            "product_name": p_name,
            "category": "Nông nghiệp & Chăn nuôi",
            "benefits": "đặc trị và phục hồi nhanh tình trạng cây trồng bị vàng lá, thối rễ, ngủ ngày do nấm khuẩn và ngập úng, kích thích tái tạo bộ rễ tơ trắng khỏe mạnh",
            "highlights": "chế phẩm sinh học thẩm thấu sâu vào vùng rễ, cải tạo đất tơi xốp, giải độc phèn mặn và giúp cây đâm chồi xanh tốt trở lại nhanh chóng",
            "target_customer": "Bà con nhà vườn trồng cây ăn trái, cây công nghiệp, hoa kiểng",
            "scene1_dialogue": s1,
            "scene2_dialogue": s2,
            "scene1_action": "Nhân vật tươi cười, đặt tay và chỉ trực tiếp vào sản phẩm chế phẩm sinh học Phục Hồi Vàng Lá, Thối Rễ trong ảnh tham chiếu, thuyết trình rõ công dụng đặc trị vàng lá thối rễ và tái tạo bộ rễ tơ trắng khỏe mạnh cho cây trồng",
            "scene2_action": "Máy quay tiến nhẹ cận cảnh làm nổi bật bao bì nhãn mác chế phẩm Phục Hồi Vàng Lá, Thối Rễ với hoạt chất sinh học cải tạo vùng rễ và phục hồi cây suy yếu, nhân vật chỉ tay vào sản phẩm rồi chỉ xuống góc trái kêu gọi bà con đặt mua",
            "needs_product_name": False
        }

    # Rule 19: 304 Stainless Steel Rice Spoon with Walnut Handle (Muỗng cơm inox 304 cán gỗ óc chó)
    if any(k in combined_norm for k in ["muong com", "mu6ng cum", "mü6ng cüm", "go oc cho", "g6 6c ch6", "imox 304"]):
        p_name = "Muỗng Cơm Inox 304 Cán Gỗ Óc Chó Cao Cấp"
        s1 = ensure_42_words(
            "Chị em nội trợ đang tìm chiếc muỗng xới cơm vừa sang trọng vừa hạn chế dính cơm và không làm trầy lòng nồi? Muỗng cơm inox ba linh tư cán gỗ óc chó cao cấp giúp xới cơm êm tay và an toàn sức khỏe mỗi ngày!"
        )
        s2 = ensure_42_words(
            "Lòng muỗng bằng inox ba linh tư dày dặn bo viền mịn màng, kết hợp cán gỗ óc chó tự nhiên cách nhiệt cầm cực kỳ đầm tay. Hôm nay shop đang trợ giá ưu đãi kèm giao hàng nhanh, cả nhà bấm ngay giỏ hàng chốt đơn nhé!"
        )
        return {
            "product_name": p_name,
            "category": "Điện gia dụng & Nhà bếp",
            "benefits": "xới cơm êm tay hạn chế bám dính hạt cơm, bề mặt inox 304 sáng bóng an toàn thực phẩm kết hợp cán gỗ óc chó tự nhiên cách nhiệt chống nóng sang trọng",
            "highlights": "chất liệu inox 304 đúc dày dặn không gỉ sét, viền muỗng bo tròn mịn màng không trầy nồi chống dính, cán gỗ cầm đầm tay bền đẹp theo năm tháng",
            "target_customer": "Chị em nội trợ, gia đình yêu thích đồ bếp cao cấp",
            "scene1_dialogue": s1,
            "scene2_dialogue": s2,
            "scene1_action": "Nhân vật tươi cười, đặt tay và chỉ trực tiếp vào chiếc muỗng cơm inox 304 cán gỗ óc chó trong ảnh tham chiếu, giới thiệu lòng muỗng inox sáng bóng chống dính cơm và phần cán gỗ cách nhiệt sang trọng",
            "scene2_action": "Máy quay tiến nhẹ cận cảnh làm nổi bật bề mặt inox 304 dày dặn bo viền tròn mịn màng và vân gỗ óc chó tự nhiên cầm đầm tay của muỗng cơm, nhân vật mỉm cười chỉ vào sản phẩm rồi chỉ xuống góc trái kêu gọi chốt đơn",
            "needs_product_name": False
        }

    # Rule 20: Combi Chelated Micronutrient Fertilizer (Phân bón trung vi lượng Combi)
    if any(k in combined_norm for k in ["trung vi luong", "trung w luong", "combi", "tao phuc", "kich thich phat trien re"]):
        p_name = "Phân Bón Trung Vi Lượng Cao Cấp COMBI (Hữu Cơ Tạo Phức)"
        s1 = ensure_42_words(
            "Bà con nhà vườn thấy cây trồng có dấu hiệu xoăn đọt, vàng lá gân xanh hay còi cọc kém phát triển? Phân bón trung vi lượng cao cấp Combi hữu cơ tạo phức giúp bổ sung dưỡng chất thiết yếu cho cây bung rễ mạnh và xanh dày lá!"
        )
        s2 = ensure_42_words(
            "Ứng dụng công nghệ Chelate hòa tan hoàn toàn một trăm phần trăm giúp lá và rễ hấp thu tức thì, ngừa rụng bông trái non hiệu quả. Hôm nay shop trợ giá ưu đãi kèm giao hàng tận vườn, bà con bấm ngay giỏ hàng nhé!"
        )
        return {
            "product_name": p_name,
            "category": "Nông nghiệp & Chăn nuôi",
            "benefits": "bổ sung đầy đủ các nguyên tố trung vi lượng hữu cơ tạo phức giúp cây hấp thu tối đa, kích thích bộ rễ phát triển mạnh, thân mập và lá xanh dày bóng mượt",
            "highlights": "công nghệ Chelate hòa tan hoàn toàn 100% không lắng cặn, khắc phục nhanh hiện tượng xoăn đọt, vàng lá gân xanh, rụng bông rụng trái non",
            "target_customer": "Bà con nông dân, nhà vườn trồng cây ăn trái, rau màu, hoa kiểng",
            "scene1_dialogue": s1,
            "scene2_dialogue": s2,
            "scene1_action": "Nhân vật tươi cười, đặt tay và chỉ trực tiếp vào sản phẩm phân bón trung vi lượng Combi trong ảnh tham chiếu, thuyết trình rõ công dụng bổ sung trung vi lượng hữu cơ giúp cây bung rễ mạnh, mập thân và xanh dày lá",
            "scene2_action": "Máy quay tiến nhẹ cận cảnh làm nổi bật bao bì phân bón trung vi lượng Combi hữu cơ tạo phức công nghệ Chelate hòa tan 100% ngừa xoăn đọt vàng lá, nhân vật chỉ tay vào sản phẩm rồi chỉ xuống góc trái kêu gọi bà con chốt đơn",
            "needs_product_name": False
        }

    # Rule 21: SIK Liquid Asphalt Waterproofing Coating (Nhựa đường dầu hắc dạng lỏng chống thấm SIK)
    if any(k in combined_norm for k in ["dau hac", "dru hac", "chong tham", "ch6ng tham", "nhua duong", "do ben 20 nam"]):
        p_name = "Nhựa Đường Dầu Hắc Dạng Lỏng Siêu Chống Thấm SIK Cao Cấp"
        s1 = ensure_42_words(
            "Mùa mưa bão khiến trần nhà, sân thượng, tường nứt hay mái tôn gia đình bạn bị thấm dột ẩm mốc khó chịu? Nhựa đường dầu hắc dạng lỏng siêu chống thấm SIK giúp bịt kín mọi khe nứt và ngăn nước thấm dột triệt để ngay tại nhà!"
        )
        s2 = ensure_42_words(
            "Dạng lỏng cải tiến chỉ cần mở nắp quét trực tiếp không cần đun nấu, màng phủ đàn hồi siêu bám dính bền bỉ tới hai mươi năm. Hôm nay shop trợ giá ưu đãi kèm miễn phí giao hàng, các bác bấm ngay giỏ hàng chốt đơn nhé!"
        )
        return {
            "product_name": p_name,
            "category": "Thiết bị & Dụng cụ chuyên dụng",
            "benefits": "thẩm thấu và bịt kín mọi vết nứt tường, sàn bê tông, sân thượng, mái tôn, máng xối, tạo lớp màng cao su đàn hồi ngăn nước thấm dột triệt để ngay sau khi khô",
            "highlights": "nhựa đường cải tiến dạng lỏng dễ dàng tự quét trực tiếp bằng chổi cọ mà không cần đun nóng, độ bám dính siêu cao chịu nắng mưa bền bỉ tới 20 năm",
            "target_customer": "Chủ nhà, thợ xây dựng sửa chữa chống thấm nhà cửa",
            "scene1_dialogue": s1,
            "scene2_dialogue": s2,
            "scene1_action": "Nhân vật tươi cười, đặt tay và chỉ trực tiếp vào thùng nhựa đường dầu hắc dạng lỏng chống thấm SIK trong ảnh tham chiếu, thuyết trình rõ công dụng quét trực tiếp bịt kín vết nứt sân thượng, tường nhà và mái tôn chống dột",
            "scene2_action": "Máy quay tiến nhẹ cận cảnh làm nổi bật bao bì thùng nhựa đường dầu hắc dạng lỏng SIK với đặc tính siêu bám dính đàn hồi và độ bền chống thấm lên tới 20 năm, nhân vật chỉ vào sản phẩm rồi chỉ xuống góc trái kêu gọi đặt mua",
            "needs_product_name": False
        }

    # Rule 22: 3-Tier Multi-purpose Storage Rack (Kệ 3 tầng đa năng)
    if any(k in combined_norm for k in ["ke 3 tang", "43cm", "ke da nang"]):
        p_name = "Kệ 3 Tầng Đa Năng Có Bánh Xe Tiện Lợi"
        s1 = ensure_42_words(
            "Góc bếp, phòng tắm hay phòng khách nhà mình đang bừa bộn nhiều chai lọ đồ đạc chưa biết sắp xếp vào đâu? Chiếc kệ ba tầng đa năng này giúp gom gọn mọi vật dụng ngăn nắp và tiết kiệm tối đa không gian sống cho gia đình!"
        )
        s2 = ensure_42_words(
            "Thiết kế khung chịu lực dày dặn, ba khay đựng sâu lòng thoáng khí kèm bốn bánh xe xoay ba trăm sáu mươi độ đẩy đi cực nhẹ. Hôm nay shop đang trợ giá ưu đãi kèm giao hàng nhanh, cả nhà bấm ngay giỏ hàng chốt đơn nhé!"
        )
        return {
            "product_name": p_name,
            "category": "Gia dụng & Đời sống",
            "benefits": "sắp xếp gọn gàng chai lọ gia vị nhà bếp, đồ dùng phòng tắm, bỉm sữa cho bé hay sách vở phòng khách, giúp tối ưu diện tích và giữ nhà cửa luôn ngăn nắp",
            "highlights": "khung chịu lực chắc chắn chống rung lắc, khay 3 tầng sâu lòng có lỗ thoát nước thoáng khí, tích hợp 4 bánh xe xoay 360 độ di chuyển êm ái mọi góc nhà",
            "target_customer": "Chị em nội trợ, gia đình, căn hộ chung cư, tiệm spa",
            "scene1_dialogue": s1,
            "scene2_dialogue": s2,
            "scene1_action": "Nhân vật tươi cười, đặt tay và chỉ trực tiếp vào chiếc kệ 3 tầng đa năng trong ảnh tham chiếu, giới thiệu kết cấu 3 tầng rộng rãi giúp sắp xếp gọn gàng chai lọ nhà bếp, phòng tắm và phòng khách",
            "scene2_action": "Máy quay tiến nhẹ cận cảnh làm nổi bật khung kệ chịu lực chắc chắn, khay đựng 3 tầng sâu lòng thoáng khí và hệ bánh xe xoay 360 độ di chuyển nhẹ nhàng của kệ 3 tầng, nhân vật chỉ vào kệ rồi chỉ xuống góc trái kêu gọi chốt đơn",
            "needs_product_name": False
        }

    # Rule 23: Keepo K2 Cat Food with Hairball Care (Hạt cho mèo Keepo K2)
    if any(k in combined_norm for k in ["keepo", "keepb", "hairball", "tieu bui long", "5 goi k2", "hat cho meo"]):
        p_name = "Hạt Cho Mèo KEEPO K2 Hỗ Trợ Tiêu Búi Lông & Chăm Sóc Mắt"
        s1 = ensure_42_words(
            "Các sen đang tìm dòng hạt khô vừa thơm ngon vừa hỗ trợ tiêu búi lông hiệu quả cho hoàng thượng nhà mình? Hạt cho mèo Keepo K2 giàu dinh dưỡng giúp bé mèo ăn ngon miệng, sáng mắt mượt lông và khỏe mạnh mỗi ngày nhé!"
        )
        s2 = ensure_42_words(
            "Hạt giòn thơm kích thích vị giác kể cả mèo kén ăn, đóng gói combo năm túi chia nhỏ bảo quản cực kỳ tiện lợi. Hôm nay shop đang trợ giá ưu đãi kèm quà tặng và miễn phí ship, các sen bấm ngay giỏ hàng chốt đơn nhé!"
        )
        return {
            "product_name": p_name,
            "category": "Thức ăn & Phụ kiện thú cưng",
            "benefits": "cung cấp dinh dưỡng đạm và vitamin toàn diện, hỗ trợ đào thải tiêu búi lông tự nhiên trong ruột, chăm sóc mắt sáng khỏe và dưỡng lông bóng mượt cho mèo cưng",
            "highlights": "hạt khô giòn rụm thơm ngon kích thích vị giác cho cả mèo kén ăn, combo 5 gói K2 chia nhỏ tiện bảo quản chống ẩm mốc kèm quà tặng hấp dẫn",
            "target_customer": "Các sen nuôi mèo, người yêu thú cưng",
            "scene1_dialogue": s1,
            "scene2_dialogue": s2,
            "scene1_action": "Nhân vật tươi cười, đặt tay và chỉ trực tiếp vào bộ gói hạt cho mèo Keepo K2 trong ảnh tham chiếu, giới thiệu công dụng cung cấp dinh dưỡng, hỗ trợ tiêu búi lông và chăm sóc mắt sáng khỏe cho mèo cưng",
            "scene2_action": "Máy quay tiến nhẹ cận cảnh làm nổi bật bao bì combo 5 gói hạt cho mèo Keepo K2 chia nhỏ bảo quản tiện lợi kèm quà tặng, nhân vật mỉm cười chỉ vào sản phẩm rồi chỉ xuống góc trái kêu gọi các sen đặt mua",
            "needs_product_name": False
        }

    # Rule 24: Premium Gamefowl Grain Feed (Ngũ cốc gà đá)
    if any(k in combined_norm for k in ["ngu coc", "ngo coc", "ngo cöc", "ga da", "10kg tang", "11kg"]):
        p_name = "Ngũ Cốc Gà Đá Dinh Dưỡng Cao Cấp (Mua 10KG Tặng 1KG)"
        s1 = ensure_42_words(
            "Anh em nuôi chiến kê muốn gà sung sức, đỏ khỏe, cơ bắp săn chắc và bền lực suốt trận đấu? Ngũ cốc gà đá dinh dưỡng cao cấp giúp bồi bổ thể lực dẻo dai, bóng mượt lông và tiêu hóa cực tốt mỗi ngày nhé!"
        )
        s2 = ensure_42_words(
            "Hạt ngũ cốc sạch tuyển chọn kỹ lưỡng, không bụi mốc, giúp chiến kê hấp thu nhanh và lên bo cực chuẩn. Đặc biệt mua mười ký được tặng thêm một ký kèm miễn phí giao hàng, anh em bấm ngay giỏ hàng góc trái chốt đơn nhé!"
        )
        return {
            "product_name": p_name,
            "category": "Nông nghiệp & Chăn nuôi",
            "benefits": "bổ sung nguồn năng lượng dồi dào giúp gà đá sung sức, đỏ khỏe, săn chắc cơ bắp, bóng mượt lông và tăng thể lực bền bỉ suốt trận đấu",
            "highlights": "phối trộn chuẩn tỷ lệ từ các loại hạt ngũ cốc sạch tuyển chọn không bụi mốc, giàu đạm và vitamin, ưu đãi mua 10kg tặng thêm 1kg tổng 11kg cực hời",
            "target_customer": "Anh em nuôi gà đá, sư kê, trang trại gia cầm chiến kê",
            "scene1_dialogue": s1,
            "scene2_dialogue": s2,
            "scene1_action": "Nhân vật tươi cười, đặt tay và chỉ trực tiếp vào bao ngũ cốc gà đá trong ảnh tham chiếu, thuyết trình rõ công dụng bổ sung năng lượng giúp chiến kê sung sức, săn chắc cơ bắp và bóng mượt lông",
            "scene2_action": "Máy quay tiến nhẹ cận cảnh làm nổi bật bao bì ngũ cốc gà đá phối trộn các loại hạt sạch chất lượng cao (ưu đãi mua 10kg tặng 1kg tổng 11kg), nhân vật mỉm cười chỉ vào sản phẩm rồi chỉ xuống góc trái kêu gọi anh em chốt đơn",
            "needs_product_name": False
        }

    # Rule 25: Crossbody Bag / Shoulder Bag (Túi đeo chéo thời trang)
    if any(k in combined_norm for k in ["tui deo cheo", "tui xach", "balo", "cap da"]):
        p_name = "Túi Đeo Chéo Thời Trang Cao Cấp Đa Ngăn Tiện Dụng"
        s1 = ensure_42_words(
            "Cả nhà đang tìm một chiếc túi đeo chéo vừa thời trang vừa đựng gọn điện thoại, ví tiền và phụ kiện khi ra ngoài? Mẫu túi đeo chéo này giúp tôn dáng năng động, dễ dàng phối đồ đi làm hay đi chơi suốt cả ngày!"
        )
        s2 = ensure_42_words(
            "Túi được may tỉ mỉ từ chất liệu cao cấp bền đẹp chống thấm nhẹ, nhiều ngăn chứa rộng rãi và khóa kéo cực kỳ mượt mà. Hôm nay shop đang trợ giá ưu đãi kèm giao hàng nhanh, cả nhà bấm ngay giỏ hàng góc trái nhé!"
        )
        return {
            "product_name": p_name,
            "category": "Thời trang & Phụ kiện",
            "benefits": "đựng gọn điện thoại, ví tiền, sạc dự phòng và đồ dùng cá nhân ngăn nắp khi ra ngoài, thiết kế ôm sát người tôn dáng năng động và dễ phối mọi trang phục",
            "highlights": "chất liệu vải da cao cấp trượt nước bền đẹp, khóa kéo mượt mà chắc chắn, nhiều ngăn khoa học và dây đeo êm vai tùy chỉnh linh hoạt",
            "target_customer": "Khách hàng yêu thích thời trang, phụ kiện túi đeo chéo đi làm, đi chơi",
            "scene1_dialogue": s1,
            "scene2_dialogue": s2,
            "scene1_action": "Nhân vật tươi cười, đặt tay và chỉ trực tiếp vào chiếc túi đeo chéo trong ảnh tham chiếu, giới thiệu phom dáng hiện đại và các ngăn chứa tiện dụng giúp đựng gọn điện thoại, ví tiền khi ra ngoài",
            "scene2_action": "Máy quay tiến nhẹ cận cảnh làm nổi bật chất liệu bề mặt bền đẹp, đường may tỉ mỉ, khóa kéo mượt mà và dây đeo chắc chắn của chiếc túi đeo chéo, nhân vật chỉ vào túi rồi chỉ xuống góc trái kêu gọi mua hàng",
            "needs_product_name": False
        }

    # Return None so that analyze_product_image_hybrid falls back to GEMINI FLASH VISION first for any unfamiliar product
    return None


def generate_smart_product_profile_from_name_direct(
    p_name: str,
    category: str,
    benefits: str,
    highlights: str
) -> Dict[str, Any]:
    from backend.app.services.pipeline_runner import ensure_42_words
    s1 = ensure_42_words(
        f"Cả nhà đang tìm {p_name} chuẩn chất lượng? Sản phẩm giúp {benefits}!",
        filler="cho cả gia đình mình yên tâm sử dụng tiện lợi mỗi ngày nhé"
    )
    s2 = ensure_42_words(
        f"Đặc biệt {p_name} sở hữu {highlights}. Hôm nay shop đang trợ giá ưu đãi kèm giao hàng nhanh, các bác bấm ngay giỏ hàng góc trái chốt đơn nhé!",
        filler="vào giỏ hàng góc trái bên dưới để chốt đơn nhận ưu đãi hôm nay nhé"
    )
    return {
        "product_name": p_name,
        "category": category,
        "benefits": benefits,
        "highlights": highlights,
        "target_customer": "Khách hàng mua sắm trực tuyến trên TikTok",
        "scene1_dialogue": s1,
        "scene2_dialogue": s2,
        "needs_product_name": False
    }


def is_valid_recognized_product_name(name: str) -> bool:
    """
    Validates whether a candidate product name is a real, meaningful product title
    and NOT generic filler, OCR gibberish, or chat/UI noise.
    """
    if not name or not isinstance(name, str):
        return False
    clean = name.strip()
    if len(clean) < 4 or len(clean) > 120:
        return False
    low = clean.lower()
    norm = _normalize_text(clean)

    # Reject placeholder / generic names
    generic_bad = [
        "san pham tien ich", "san pham thuong mai", "san pham nay",
        "can nhap ten", "chua nhan dien", "unknown", "product", "image", "screenshot",
        "zalo", "messenger", "facebook", "shopee", "tiktok", "lazada", "tim san pham"
    ]
    if any(g in norm for g in generic_bad):
        return False

    # Reject OCR gibberish characters or broken tokens
    if any(bad in low for bad in ['6c', 'ä', 'ö', 'ë', 'å', 'ü', 'ø', 'hiéng', 'tdong', 'tddng', 'phåi', 'versp00', 'khuåy', 'dlen']):
        return False

    words = clean.split()
    if len(words) < 2:
        return False
    # Reject if too many single-character tokens (like "S I V E R")
    single_char_tokens = sum(1 for w in words if len(re.sub(r'[^a-zA-ZÀ-ỹ0-9]', '', w)) <= 1)
    if single_char_tokens >= 2 and single_char_tokens / max(1, len(words)) > 0.35:
        return False

    return True


def is_generic_benefits(text: str) -> bool:
    if not text or not isinstance(text, str):
        return True
    low = text.strip().lower()
    if len(low) < 12:
        return True
    generic_phrases = [
        "sản phẩm tiện ích",
        "công dụng vượt trội",
        "công năng vượt trội",
        "giải quyết nhanh gọn nhu cầu sử dụng hằng ngày",
        "giải quyết hiệu quả nhu cầu sử dụng hằng ngày",
        "tiết kiệm thời gian và công sức với",
        "thiết kế thông minh, chất liệu bền bỉ, dễ sử dụng",
        "thiết kế cao cấp, chất liệu bền bỉ",
        "chính hãng cao cấp, thiết kế hiện đại",
    ]
    return any(g in low for g in generic_phrases)


def _extract_packaging_clues_from_ocr(ocr_text: str) -> Dict[str, str]:
    """
    Extracts real product name candidates, benefit phrases, and spec/highlight phrases
    directly from Windows OCR text on any unfamiliar product image/banner.
    """
    if not ocr_text or len(ocr_text.strip()) < 4:
        return {}
    raw_lines = [re.sub(r'\s+', ' ', l).strip() for l in ocr_text.splitlines() if len(l.strip()) >= 3]
    noise_words = [
        "tìm sản phẩm", "tương tự", "shopee", "tiktok", "lazada", "zalo", "messenger",
        "facebook", "giỏ hàng", "mua ngay", "chat ngay", "thêm vào", "đánh giá", "đã bán"
    ]
    clean_lines = []
    for line in raw_lines:
        low = line.lower()
        if any(nw in low for nw in noise_words):
            continue
        if re.match(r'^[\d\s:./%-]+$', line):
            continue
        # Skip lines with heavy OCR gibberish symbols
        if sum(1 for c in line if c in "@#$^*~`|\\<>[]{}") > 1:
            continue
        clean_lines.append(line)

    if not clean_lines:
        return {}

    benefit_keywords = [
        "giúp", "hỗ trợ", "đặc trị", "phục hồi", "ngăn", "chống", "bổ sung", "tăng",
        "giảm", "làm sạch", "khử", "bảo vệ", "dưỡng", "tiết kiệm", "nhanh", "hiệu quả",
        "an toàn", "bền", "sáng", "mượt", "chắc", "khỏe", "thơm", "tiêu", "kích thích"
    ]
    spec_keywords = [
        "ml", "lít", "kg", "gam", "gói", "hộp", "chai", "túi", "viên", "thanh", "combo",
        "tặng", "inox", "nhựa", "gỗ", "da", "pin", "w", "v", "led", "tầng", "ngăn",
        "100%", "chính hãng", "cao cấp", "nhật bản", "hàn quốc", "công nghệ", "bảo hành"
    ]

    benefit_parts = []
    spec_parts = []
    title_candidates = []

    for line in clean_lines:
        low = line.lower()
        words = line.split()
        if 2 <= len(words) <= 12 and is_valid_recognized_product_name(line):
            title_candidates.append(line)
        if any(bk in low for bk in benefit_keywords) and 3 <= len(words) <= 18:
            benefit_parts.append(line.rstrip(".,;!"))
        elif any(sk in low for sk in spec_keywords) and 2 <= len(words) <= 16:
            spec_parts.append(line.rstrip(".,;!"))

    return {
        "ocr_title": title_candidates[0] if title_candidates else "",
        "ocr_benefits": ", ".join(benefit_parts[:3]) if benefit_parts else "",
        "ocr_highlights": ", ".join(spec_parts[:3]) if spec_parts else ""
    }


def generate_smart_product_profile_from_name(
    product_name: str,
    benefits_hint: str = "",
    ocr_context: str = ""
) -> Dict[str, Any]:
    """
    Builds a concise, accurate, non-rambling product profile (category, benefits, highlights,
    Scene 1 & Scene 2 dialogues >= 42 words, and scene1_action / scene2_action / store_context)
    strictly tailored to the specific function (công dụng) of the product.
    Works for both known products AND any future unfamiliar product uploaded by the user.
    """
    from backend.app.services.pipeline_runner import ensure_42_words
    p_name = product_name.strip()
    custom_ben = "" if is_generic_benefits(benefits_hint) else benefits_hint.strip()

    # Check if the name or OCR context matches any of our specialized OCR rules first
    combined_lookup = f"{p_name}\n{ocr_context}".strip()
    matched = parse_product_from_ocr_text(combined_lookup, p_name)
    if matched and is_valid_recognized_product_name(matched.get("product_name", "")):
        if is_valid_recognized_product_name(p_name) and "đang nhận diện" not in p_name.lower():
            matched["product_name"] = p_name
        if custom_ben and custom_ben.lower() != (matched.get("benefits") or "").lower():
            matched["benefits"] = custom_ben
        return matched

    # Extract any real packaging clues from OCR text of unfamiliar products
    clues = _extract_packaging_clues_from_ocr(ocr_context) if ocr_context else {}
    if (not is_valid_recognized_product_name(p_name) or "đang nhận diện" in p_name.lower()) and clues.get("ocr_title"):
        p_name = clues["ocr_title"]

    ocr_ben = clues.get("ocr_benefits") or ""
    ocr_high = clues.get("ocr_highlights") or ""
    effective_ben_hint = custom_ben or ocr_ben

    norm = _normalize_text(f"{p_name} {ocr_context}")

    if any(k in norm for k in ["ga da", "chien ke", "ngu coc ga", "chim canh", "bo cau"]):
        category = "Nông nghiệp & Chăn nuôi"
        store_context = "cửa hàng thức ăn và phụ kiện chăn nuôi chiến kê chuyên nghiệp"
        benefits = effective_ben_hint or f"bổ sung nguồn năng lượng và dưỡng chất dồi dào từ {p_name} giúp chiến kê sung sức, đỏ khỏe, săn chắc cơ bắp và bền lực"
        highlights = ocr_high or "nguyên liệu sạch tuyển chọn kỹ lưỡng, không bụi mốc, giàu đạm và vitamin giúp hấp thu tiêu hóa nhanh"
        s1_raw = f"Anh em nuôi chiến kê đang tìm {p_name} giúp gà sung sức, đỏ khỏe, cơ bắp săn chắc và bền lực suốt trận đấu? Sản phẩm giúp {benefits} mỗi ngày nhé!"
        s2_raw = f"Đặc biệt {p_name} có {highlights}. Hôm nay shop đang trợ giá ưu đãi kèm miễn phí giao hàng, anh em bấm ngay giỏ hàng góc trái chốt đơn nhé!"
        s1_action = f"Nhân vật tươi cười tự tin trong {store_context}, đặt tay và chỉ trực tiếp vào sản phẩm {p_name} trong ảnh tham chiếu để giới thiệu công dụng {benefits}"
        s2_action = f"Máy quay tiến nhẹ cận cảnh làm nổi bật bao bì và chi tiết của {p_name} ({highlights}), nhân vật mỉm cười chỉ vào sản phẩm rồi chỉ xuống góc trái kêu gọi anh em chốt đơn"
    elif any(k in norm for k in ["meo", "cho", "thu cung", "sup thuong", "pate", "hat cho", "cat", "dog", "keepo"]):
        category = "Thức ăn & Phụ kiện thú cưng"
        store_context = "cửa hàng pet shop thức ăn và phụ kiện thú cưng hiện đại"
        benefits = effective_ben_hint or f"cung cấp dinh dưỡng đạm và vitamin toàn diện, kích thích vị giác ăn ngon miệng, hỗ trợ tiêu hóa và dưỡng lông bóng mượt cho thú cưng"
        highlights = ocr_high or "nguyên liệu an toàn lành tính, hương vị thơm ngon dễ ăn, đóng gói chia nhỏ tiện lợi bảo quản chống ẩm mốc"
        s1_raw = f"Các sen đang tìm {p_name} vừa thơm ngon vừa giàu dinh dưỡng cho thú cưng nhà mình? Sản phẩm giúp {benefits} mỗi ngày nhé!"
        s2_raw = f"Đặc biệt {p_name} sở hữu {highlights}. Hôm nay shop đang trợ giá ưu đãi kèm quà tặng và miễn phí giao hàng, các sen bấm ngay giỏ hàng góc trái chốt đơn nhé!"
        s1_action = f"Nhân vật tươi cười trong {store_context}, đặt tay và chỉ trực tiếp vào sản phẩm {p_name} trong ảnh tham chiếu để giới thiệu công dụng {benefits}"
        s2_action = f"Máy quay tiến nhẹ cận cảnh làm nổi bật bao bì và quy cách đóng gói của {p_name} ({highlights}), nhân vật mỉm cười chỉ vào sản phẩm rồi chỉ xuống góc trái kêu gọi các sen đặt mua"
    elif any(k in norm for k in ["ao nuoi", "tom ca", "thuy san", "nh3", "no2", "day ao", "men vi sinh nuoc"]):
        category = "Nông nghiệp & Thủy sản"
        store_context = "cửa hàng vật tư và chế phẩm sinh học nuôi trồng thủy sản"
        benefits = effective_ben_hint or "làm sạch nước ao nuôi tôm cá nhanh chóng, hấp thụ khí độc NH3, NO2 và phân hủy mùn bã hữu cơ đáy ao hiệu quả"
        highlights = ocr_high or "mật độ vi sinh có lợi đậm đặc, hoạt lực mạnh, an toàn sinh học giúp tôm cá khỏe mạnh ăn khỏe lớn nhanh"
        s1_raw = f"Bà con nuôi thủy sản đang lo lắng nước ao ô nhiễm và khí độc tăng cao? {p_name} giúp {benefits} cực kỳ nhanh chóng nhé!"
        s2_raw = f"Với {highlights}, {p_name} giúp tiết kiệm chi phí xử lý nước tối đa. Hôm nay shop trợ giá ưu đãi kèm miễn phí ship, bà con bấm ngay giỏ hàng góc trái nhé!"
        s1_action = f"Nhân vật tươi cười trong {store_context}, chỉ tay trực tiếp vào sản phẩm {p_name} trong ảnh tham chiếu để thuyết trình giải pháp {benefits}"
        s2_action = f"Máy quay tiến nhẹ cận cảnh làm nổi bật nhãn mác và thành phần vi sinh đậm đặc của {p_name} ({highlights}), nhân vật chỉ vào sản phẩm rồi chỉ xuống góc trái kêu gọi bà con đặt mua"
    elif any(k in norm for k in ["vang la", "thoi re", "nam benh", "sau benh", "thuoc tru", "kich re", "phan bon", "combi", "trung vi luong", "npk", "huu co", "cay trong", "nha vuon", "kich hoa", "vo gao"]):
        category = "Nông nghiệp & Chăn nuôi"
        store_context = "cửa hàng vật tư nông nghiệp và phân bón cây trồng chuyên nghiệp"
        benefits = effective_ben_hint or f"bổ sung dinh dưỡng chuyên sâu, phục hồi bộ rễ tơ khỏe mạnh, giúp cây trồng bung đọt xanh dày lá và tăng năng suất vượt trội"
        highlights = ocr_high or "công thức sinh học hòa tan thẩm thấu nhanh qua lá và rễ, an toàn cho đất và cây trồng, tiết kiệm chi phí nhà nông"
        s1_raw = f"Bà con nhà vườn đang tìm {p_name} giúp cây trồng phát triển khỏe mạnh, xanh dày lá và phục hồi rễ cực nhanh? Sản phẩm giúp {benefits}!"
        s2_raw = f"Nhờ {highlights}, {p_name} được rất nhiều nhà vườn tin dùng. Hôm nay shop trợ giá ưu đãi kèm giao hàng tận vườn, bà con bấm ngay giỏ hàng góc trái chốt đơn nhé!"
        s1_action = f"Nhân vật tươi cười trong {store_context}, đặt tay và chỉ trực tiếp vào sản phẩm {p_name} trong ảnh tham chiếu để giới thiệu công dụng {benefits}"
        s2_action = f"Máy quay tiến nhẹ cận cảnh làm nổi bật bao bì, nhãn hiệu và thành phần công thức của {p_name} ({highlights}), nhân vật chỉ vào sản phẩm rồi chỉ xuống góc trái kêu gọi bà con nhà vườn chốt đơn"
    elif any(k in norm for k in ["chong tham", "nhua duong", "dau hac", "keo dan", "son", "vet nut", "tham dot", "mai ton", "san thuong"]):
        category = "Thiết bị & Vật liệu chống thấm"
        store_context = "cửa hàng vật liệu xây dựng và phụ gia chống thấm chuyên dụng"
        benefits = effective_ben_hint or "thẩm thấu sâu và bịt kín mọi vết nứt tường, trần nhà, sân thượng, mái tôn và máng xối, ngăn nước thấm dột triệt để ngay sau khi thi công"
        highlights = ocr_high or "dạng lỏng cải tiến dễ dàng tự quét trực tiếp tại nhà, độ bám dính đàn hồi siêu cao và chịu nắng mưa bền bỉ nhiều năm"
        s1_raw = f"Mùa mưa tới khiến tường nhà, sân thượng hay mái tôn bị thấm dột ẩm mốc? Dùng ngay {p_name} giúp {benefits} cực kỳ hiệu quả tại nhà!"
        s2_raw = f"Đặc biệt {p_name} sở hữu {highlights}. Hôm nay shop đang trợ giá ưu đãi kèm miễn phí giao hàng, các bác bấm ngay giỏ hàng góc trái chốt đơn nhé!"
        s1_action = f"Nhân vật tươi cười trong {store_context}, chỉ tay trực tiếp vào sản phẩm {p_name} trong ảnh tham chiếu để thuyết trình rõ công dụng {benefits}"
        s2_action = f"Máy quay tiến nhẹ cận cảnh làm nổi bật bao bì và thông số độ bền chống thấm của {p_name} ({highlights}), nhân vật chỉ vào sản phẩm rồi chỉ xuống góc trái kêu gọi đặt mua"
    elif any(k in norm for k in ["bom lop", "ap suat lop", "o to", "xe hoi", "xe may", "phu kien xe", "camera hanh trinh", "rua xe"]):
        category = "Thiết bị & Phụ kiện ô tô"
        store_context = "showroom thiết bị và phụ kiện chăm sóc ô tô xe máy hiện đại"
        benefits = effective_ben_hint or f"hỗ trợ kiểm tra, bơm lốp và chăm sóc xe hơi, xe máy nhanh gọn chuẩn xác ngay tại chỗ, giúp các bác tài luôn an tâm trên mọi hành trình"
        highlights = ocr_high or "màn hình hiển thị sắc nét, công suất mạnh mẽ tự ngắt thông minh, thiết kế nhỏ gọn tiện lợi để sẵn trong cốp xe"
        s1_raw = f"Các bác tài lái xe đi đường xa muốn trang bị {p_name} để chủ động xử lý nhanh gọn mọi tình huống trên đường? Sản phẩm giúp {benefits}!"
        s2_raw = f"Đặc biệt {p_name} được trang bị {highlights}. Đang có ưu đãi trợ giá kèm miễn phí giao hàng toàn quốc, các bác bấm ngay giỏ hàng góc trái chốt đơn nhé!"
        s1_action = f"Nhân vật tươi cười trong {store_context}, đặt tay và chỉ trực tiếp vào thân sản phẩm {p_name} trong ảnh tham chiếu để giới thiệu tính năng {benefits}"
        s2_action = f"Máy quay tiến nhẹ cận cảnh làm nổi bật màn hình, nút điều khiển và kết cấu chi tiết của {p_name} ({highlights}), nhân vật chỉ vào sản phẩm rồi chỉ xuống góc trái kêu gọi các bác tài chốt đơn"
    elif any(k in norm for k in ["may khoan", "may duc", "may cat", "may han", "laser", "co khi", "dung cu cam tay", "tua vit", "kim", "co le"]):
        category = "Thiết bị & Dụng cụ chuyên dụng"
        store_context = "cửa hàng máy móc cơ khí và dụng cụ cầm tay chuyên nghiệp"
        benefits = effective_ben_hint or "vận hành công suất mạnh mẽ giúp khoan đục, cắt gọt, sửa chữa công trình và nhà cửa nhanh gọn, tiết kiệm tối đa thời gian công sức"
        highlights = ocr_high or "động cơ lõi đồng bền bỉ, vỏ hợp kim chịu va đập tốt, tay cầm chắc chắn chống rung trượt và an toàn khi thao tác"
        s1_raw = f"Các bác thợ và anh em đang tìm {p_name} khỏe, bền bỉ để làm việc công trình hay sửa chữa tại nhà? Sản phẩm giúp {benefits}!"
        s2_raw = f"Đặc biệt {p_name} sở hữu {highlights}. Hôm nay shop đang trợ giá ưu đãi kèm miễn phí giao hàng, các bác bấm ngay giỏ hàng góc trái chốt đơn nhé!"
        s1_action = f"Nhân vật tươi cười trong {store_context}, chỉ tay trực tiếp vào thân máy và phụ kiện của {p_name} trong ảnh tham chiếu để giới thiệu sức mạnh {benefits}"
        s2_action = f"Máy quay tiến nhẹ cận cảnh làm nổi bật phần đầu máy, vỏ hợp kim và tay cầm chắc chắn của {p_name} ({highlights}), nhân vật chỉ vào sản phẩm rồi chỉ xuống góc trái kêu gọi chốt đơn"
    elif any(k in norm for k in ["muong", "thia", "dua", "noi", "chao", "dao", "thot", "khay", "bat", "dia", "binh giu nhiet", "am", "bep", "inox 304", "go oc cho"]):
        category = "Điện gia dụng & Nhà bếp"
        store_context = "showroom đồ dùng nhà bếp và bàn ăn cao cấp ấm cúng"
        benefits = effective_ben_hint or f"giúp công việc nấu nướng và thưởng thức bữa cơm gia đình thêm tiện lợi, sạch sẽ, hạn chế bám dính và an toàn tuyệt đối cho sức khỏe"
        highlights = ocr_high or "chất liệu inox 304 và vật liệu cao cấp dày dặn sáng bóng, bo viền tỉ mỉ chống trầy xước, cách nhiệt tốt và cực kỳ bền đẹp"
        s1_raw = f"Chị em nội trợ đang tìm {p_name} vừa bền đẹp sang trọng vừa an toàn sức khỏe cho căn bếp gia đình? Sản phẩm giúp {benefits} mỗi ngày!"
        s2_raw = f"Đặc biệt {p_name} được hoàn thiện với {highlights}. Hôm nay shop đang trợ giá ưu đãi kèm giao hàng nhanh, cả nhà bấm ngay giỏ hàng góc trái chốt đơn nhé!"
        s1_action = f"Nhân vật tươi cười trong {store_context}, đặt tay và chỉ trực tiếp vào bề mặt và kiểu dáng của {p_name} trong ảnh tham chiếu để giới thiệu công dụng {benefits}"
        s2_action = f"Máy quay tiến nhẹ cận cảnh làm nổi bật chất liệu hoàn thiện sắc nét, đường bo viền và tay cầm của {p_name} ({highlights}), nhân vật chỉ vào sản phẩm rồi chỉ xuống góc trái kêu gọi mua hàng"
    elif any(k in norm for k in ["ke ", "ke 3 tang", "ke da nang", "tu ", "hop dung", "gio dung", "moc treo", "sap xep"]):
        category = "Gia dụng & Đời sống"
        store_context = "showroom nội thất và đồ gia dụng thông minh hiện đại"
        benefits = effective_ben_hint or "sắp xếp gọn gàng chai lọ nhà bếp, đồ dùng phòng tắm và vật dụng sinh hoạt, giúp tiết kiệm tối đa diện tích và giữ nhà cửa luôn ngăn nắp"
        highlights = ocr_high or "khung chịu lực chắc chắn chống rung lắc, các tầng khay đựng sâu lòng thoáng khí, dễ dàng lắp đặt và di chuyển linh hoạt"
        s1_raw = f"Không gian nhà bếp, phòng tắm hay phòng khách đang bừa bộn nhiều đồ đạc? {p_name} giúp {benefits} cực kỳ gọn gàng và đẹp mắt nhé!"
        s2_raw = f"Đặc biệt {p_name} sở hữu {highlights}. Hôm nay shop đang trợ giá ưu đãi kèm giao hàng nhanh, cả nhà bấm ngay giỏ hàng góc trái chốt đơn nhé!"
        s1_action = f"Nhân vật tươi cười trong {store_context}, chỉ tay trực tiếp vào kết cấu các tầng/ngăn của {p_name} trong ảnh tham chiếu để giới thiệu khả năng {benefits}"
        s2_action = f"Máy quay tiến nhẹ cận cảnh làm nổi bật khung chịu lực, khay chứa và chi tiết lắp ghép chắc chắn của {p_name} ({highlights}), nhân vật chỉ vào sản phẩm rồi chỉ xuống góc trái kêu gọi chốt đơn"
    elif any(k in norm for k in ["tui", "balo", "vi da", "cap da", "valy", "deo cheo", "tui xach"]):
        category = "Thời trang & Phụ kiện"
        store_context = "cửa hàng boutique thời trang và phụ kiện túi xách sang trọng"
        benefits = effective_ben_hint or "đựng gọn điện thoại, ví tiền, sổ tay và vật dụng cá nhân ngăn nắp khi đi làm hay đi chơi, giúp tôn dáng thanh lịch và dễ phối mọi trang phục"
        highlights = ocr_high or "chất liệu da và vải cao cấp chống thấm nhẹ, đường may sắc nét tỉ mỉ, khóa kéo mượt mà cùng nhiều ngăn chia khoa học"
        s1_raw = f"Anh chị em đang tìm một mẫu {p_name} vừa thời trang vừa đựng gọn gàng đồ dùng cá nhân khi ra ngoài? Sản phẩm giúp {benefits} suốt cả ngày!"
        s2_raw = f"Đặc biệt {p_name} được gia công từ {highlights}. Hôm nay shop đang trợ giá ưu đãi kèm giao hàng nhanh, cả nhà bấm ngay giỏ hàng góc trái chốt đơn nhé!"
        s1_action = f"Nhân vật tươi cười trong {store_context}, đặt tay giới thiệu phom dáng chuẩn đẹp và các ngăn chứa tiện lợi của {p_name} trong ảnh tham chiếu"
        s2_action = f"Máy quay tiến nhẹ cận cảnh làm nổi bật chất liệu bề mặt, đường kim mũi chỉ tỉ mỉ và khóa kéo chắc chắn của {p_name} ({highlights}), nhân vật chỉ vào sản phẩm rồi chỉ xuống góc trái kêu gọi mua hàng"
    elif any(k in norm for k in ["ao", "quan", "vay", "dam", "giay", "dep", "thoi trang", "kinh", "dong ho", "mu ", "non "]):
        category = "Thời trang & Phụ kiện"
        store_context = "showroom thời trang hiện đại ánh sáng ấm áp"
        benefits = effective_ben_hint or "tôn dáng chuẩn đẹp, mang lại cảm giác êm ái thoáng mát suốt cả ngày và dễ dàng phối hợp nhiều phong cách đi làm, dạo phố"
        highlights = ocr_high or "chất liệu tuyển chọn mềm mịn bền màu, phom dáng thiết kế hiện đại hợp xu hướng, đường may chắc chắn tỉ mỉ từng chi tiết"
        s1_raw = f"Anh chị em đang tìm mẫu {p_name} vừa lên phom tôn dáng đẹp mắt vừa thoải mái dễ chịu khi mặc cả ngày? Sản phẩm giúp {benefits}!"
        s2_raw = f"Đặc biệt {p_name} nổi bật với {highlights}. Hôm nay shop đang trợ giá ưu đãi kèm miễn phí vận chuyển, cả nhà bấm ngay giỏ hàng góc trái chốt đơn nhé!"
        s1_action = f"Nhân vật tươi cười trong {store_context}, chỉ tay trực tiếp vào thiết kế và phom dáng của {p_name} trong ảnh tham chiếu để giới thiệu ưu điểm {benefits}"
        s2_action = f"Máy quay tiến nhẹ cận cảnh làm nổi bật chất liệu vải, đường may và chi tiết hoàn thiện của {p_name} ({highlights}), nhân vật chỉ vào sản phẩm rồi chỉ xuống góc trái kêu gọi mua hàng"
    elif any(k in norm for k in ["kem", "serum", "son", "sua rua mat", "my pham", "goi", "tam", "duong da", "chong nang", "nuoc hoa", "trang diem", "collagen", "mun", "trang da"]):
        category = "Mỹ phẩm & Chăm sóc cá nhân"
        store_context = "showroom mỹ phẩm và chăm sóc sắc đẹp chính hãng"
        benefits = effective_ben_hint or "làm sạch dịu nhẹ, cấp ẩm chuyên sâu và nuôi dưỡng làn da, mái tóc sáng khỏe mịn màng rạng rỡ tự tin suốt cả ngày"
        highlights = ocr_high or "bảng thành phần chiết xuất lành tính an toàn, kết cấu mỏng nhẹ thẩm thấu nhanh không nhờn rít, hương thơm dịu nhẹ thư giãn"
        s1_raw = f"Chị em đang tìm dòng {p_name} lành tính giúp chăm sóc và nuôi dưỡng vẻ ngoài tươi tắn rạng rỡ mỗi ngày? Sản phẩm giúp {benefits}!"
        s2_raw = f"Với {highlights}, {p_name} cực kỳ êm dịu khi sử dụng. Hôm nay shop đang trợ giá ưu đãi kèm quà tặng hấp dẫn, chị em bấm ngay giỏ hàng góc trái nhé!"
        s1_action = f"Nhân vật tươi cười trong {store_context}, đặt tay và chỉ trực tiếp vào bao bì sản phẩm {p_name} trong ảnh tham chiếu để giới thiệu công dụng {benefits}"
        s2_action = f"Máy quay tiến nhẹ cận cảnh làm nổi bật thiết kế chai/hộp và thông tin thành phần lành tính trên nhãn của {p_name} ({highlights}), nhân vật chỉ vào sản phẩm rồi chỉ xuống góc trái kêu gọi đặt mua"
    elif any(k in norm for k in ["banh", "keo", "tra", "ca phe", "sua", "do an", "thuc pham", "hat dinh duong", "kho ga", "kho bo", "nuoc uong", "mat ong", "yen sao"]):
        category = "Thực phẩm & Đồ uống"
        store_context = "cửa hàng thực phẩm dinh dưỡng và đặc sản cao cấp"
        benefits = effective_ben_hint or "mang đến hương vị thơm ngon tròn vị, bổ sung nguồn dinh dưỡng và năng lượng lành mạnh cho cả gia đình thưởng thức mỗi ngày"
        highlights = ocr_high or "nguyên liệu tươi sạch tuyển chọn kỹ càng, chế biến theo quy trình chuẩn vệ sinh an toàn thực phẩm, đóng gói kín đáo tiện bảo quản"
        s1_raw = f"Cả nhà đang tìm món {p_name} thơm ngon, giàu dinh dưỡng để nhâm nhi hoặc bồi bổ sức khỏe cho gia đình? Sản phẩm giúp {benefits}!"
        s2_raw = f"Nhờ {highlights}, {p_name} luôn giữ trọn hương vị tươi ngon tự nhiên. Hôm nay shop trợ giá ưu đãi kèm giao hàng nhanh, cả nhà bấm ngay giỏ hàng góc trái nhé!"
        s1_action = f"Nhân vật tươi cười trong {store_context}, đặt tay và chỉ trực tiếp vào bao bì của {p_name} trong ảnh tham chiếu để giới thiệu hương vị và công dụng {benefits}"
        s2_action = f"Máy quay tiến nhẹ cận cảnh làm nổi bật quy cách đóng gói sạch đẹp và thành phần nguyên liệu trên bao bì {p_name} ({highlights}), nhân vật chỉ vào sản phẩm rồi chỉ xuống góc trái kêu gọi chốt đơn"
    else:
        category = "Gia dụng & Đời sống"
        store_context = "showroom trưng bày sản phẩm gia dụng và tiện ích hiện đại"
        benefits = effective_ben_hint or f"hỗ trợ xử lý nhanh gọn công việc sinh hoạt hằng ngày trong gia đình, mang lại sự tiện nghi, gọn gàng và tiết kiệm công sức tối đa"
        highlights = ocr_high or "thiết kế thông minh đa năng, chất liệu dày dặn bền bỉ theo thời gian, thao tác sử dụng đơn giản và an toàn cho mọi thành viên"
        s1_raw = f"Cả nhà đang tìm kiếm {p_name} thiết kế thông minh giúp sinh hoạt gia đình thêm tiện nghi và nhẹ nhàng hơn? Sản phẩm giúp {benefits}!"
        s2_raw = f"Đặc biệt {p_name} sở hữu {highlights}. Hôm nay shop đang trợ giá ưu đãi kèm giao hàng nhanh toàn quốc, cả nhà bấm ngay giỏ hàng góc trái chốt đơn nhé!"
        s1_action = f"Nhân vật tươi cười trong {store_context}, đặt tay và chỉ trực tiếp vào sản phẩm {p_name} trong ảnh tham chiếu để giới thiệu tính năng và công dụng {benefits}"
        s2_action = f"Máy quay tiến nhẹ cận cảnh làm nổi bật kiểu dáng thiết kế, chất liệu và các chi tiết hoàn thiện của {p_name} ({highlights}), nhân vật chỉ vào sản phẩm rồi chỉ xuống góc trái kêu gọi mua hàng"

    # Strip trailing repeated product name if benefits_hint came from legacy DB with "với {p_name}"
    if benefits.lower().endswith(f"với {p_name.lower()}"):
        benefits = benefits[: -(len(p_name) + 4)].strip()
    elif benefits.lower().endswith(f"nhờ {p_name.lower()}"):
        benefits = benefits[: -(len(p_name) + 4)].strip()
    elif benefits.lower().endswith(f"cùng {p_name.lower()}"):
        benefits = benefits[: -(len(p_name) + 5)].strip()

    s1 = ensure_42_words(s1_raw, filler="cho cả gia đình mình yên tâm sử dụng tiện lợi mỗi ngày nhé")
    s2 = ensure_42_words(s2_raw, filler="vào giỏ hàng góc trái bên dưới để chốt đơn nhận ưu đãi hôm nay nhé")

    return {
        "product_name": p_name,
        "category": category,
        "store_context": store_context,
        "benefits": benefits,
        "highlights": highlights,
        "target_customer": "Khách hàng mua sắm trực tuyến trên TikTok",
        "scene1_dialogue": s1,
        "scene2_dialogue": s2,
        "scene1_action": s1_action,
        "scene2_action": s2_action,
        "needs_product_name": False
    }


async def analyze_product_image_hybrid(
    original_image_path: str,
    on_log: Optional[Any] = None,
    hint_name: str = "",
    allow_gemini_vision: bool = True,
    orig_filename: str = ""
) -> Dict[str, Any]:
    """
    Hybrid product image analyzer:
    1. If user explicitly provided `hint_name`, uses it combined with OCR/Vision details.
    2. Runs Windows native OCR + rule matching for known products.
    3. Runs Gemini Flash Vision for unfamiliar products.
    4. Checks original filename and OCR text lines so the automatic queue never stalls.
    """
    async def log(msg: str, percent: int = 0):
        if on_log:
            await on_log(msg, percent)
        logger.info(f"[Product Analyzer Hybrid] {msg}")

    if not original_image_path or not os.path.exists(original_image_path):
        return {"success": False, "error": "Ảnh sản phẩm không tồn tại"}

    fname_for_ocr = orig_filename or Path(original_image_path).name

    clean_hint = (hint_name or "").strip()
    if clean_hint and is_valid_recognized_product_name(clean_hint):
        await log(f"Sử dụng tên sản phẩm đã nhập: {clean_hint}", 90)
        ocr_raw = await asyncio.to_thread(extract_text_via_windows_ocr, original_image_path)
        ocr_match = parse_product_from_ocr_text(f"{ocr_raw}\n{clean_hint}", fname_for_ocr)
        if ocr_match:
            ocr_match["product_name"] = clean_hint
            ocr_match["needs_product_name"] = False
            return {"success": True, "data": ocr_match}
        profile = generate_smart_product_profile_from_name(clean_hint, ocr_context=ocr_raw)
        return {"success": True, "data": profile}

    await log("Đang đọc kỹ chữ và nhãn mác bao bì sản phẩm trong ảnh...", 15)

    # Step 1: Local Windows Native OCR for instant known-product recognition
    ocr_raw = await asyncio.to_thread(extract_text_via_windows_ocr, original_image_path)
    ocr_data = parse_product_from_ocr_text(ocr_raw, fname_for_ocr)

    if ocr_data and is_valid_recognized_product_name(ocr_data.get("product_name", "")):
        ocr_data["needs_product_name"] = False
        await log(f"Đã nhận diện chuẩn xác sản phẩm qua bao bì: {ocr_data['product_name']} ({ocr_data['category']})", 95)
        return {"success": True, "data": ocr_data}

    # Step 2: Run Gemini Flash multimodal vision for unfamiliar product image
    gemini_data = None
    if allow_gemini_vision:
        try:
            from backend.app.services.gemini_automator import gemini_automator
            gem_res = await asyncio.wait_for(
                gemini_automator.analyze_product_image(
                    original_image_path=original_image_path,
                    on_log=lambda m, p: log(m, min(90, 40 + int(p * 0.5)))
                ),
                timeout=55
            )
            if gem_res and gem_res.get("success") and gem_res.get("data"):
                cand = gem_res["data"]
                if is_valid_recognized_product_name(cand.get("product_name", "")):
                    gemini_data = cand
                    gemini_data["needs_product_name"] = False
                    from backend.app.services.pipeline_runner import ensure_42_words
                    from backend.app.services.prompt_templates import sanitize_tiktok_dialogue
                    if gemini_data.get("scene1_dialogue"):
                        gemini_data["scene1_dialogue"] = ensure_42_words(sanitize_tiktok_dialogue(gemini_data["scene1_dialogue"]))
                    if gemini_data.get("scene2_dialogue"):
                        gemini_data["scene2_dialogue"] = ensure_42_words(sanitize_tiktok_dialogue(gemini_data["scene2_dialogue"]))
        except Exception as e_gem:
            logger.debug(f"Gemini Web product analysis attempt skipped or timed out: {e_gem}")

    if gemini_data:
        await log(f"Đã nhận diện sản phẩm qua Gemini Vision: {gemini_data['product_name']}", 100)
        return {"success": True, "data": gemini_data}

    # Step 3: Check if original filename or OCR packaging text gives a valid Vietnamese product name
    for candidate_fn in [orig_filename, Path(original_image_path).name]:
        if not candidate_fn:
            continue
        stem = Path(candidate_fn).stem.replace("_", " ").replace("-", " ").strip()
        stem = re.sub(r'^[0-9a-f]{6,}\s*', '', stem).strip()
        if (
            len(stem) >= 4
            and not any(stem.lower().startswith(p) for p in ["image", "media", "photo", "screenshot", "img", "pic", "product", "zalo", "whatsapp", "download", "untitled", "clip", "san pham clipboard"])
            and is_valid_recognized_product_name(stem)
        ):
            profile = generate_smart_product_profile_from_name(stem, ocr_context=ocr_raw)
            await log(f"Đã nhận diện sản phẩm: {profile['product_name']}", 100)
            return {"success": True, "data": profile}

    clues = _extract_packaging_clues_from_ocr(ocr_raw)
    if clues.get("ocr_title") and is_valid_recognized_product_name(clues["ocr_title"]):
        profile = generate_smart_product_profile_from_name(clues["ocr_title"], ocr_context=ocr_raw)
        await log(f"Đã đọc tên & công dụng từ bao bì: {profile['product_name']}", 100)
        return {"success": True, "data": profile}

    # Step 4: If allow_gemini_vision was False (initial quick upload), mark for Gemini Vision analysis during pipeline run
    # If allow_gemini_vision was True (inside pipeline run), fallback gracefully so the automatic queue never stops!
    if allow_gemini_vision:
        fallback_profile = generate_smart_product_profile_from_name("Sản Phẩm Chính Hãng Tiện Ích")
        fallback_profile["needs_product_name"] = False
        await log("Tự động tạo kịch bản & tiếp tục sản xuất video không gián đoạn...", 100)
        return {"success": True, "data": fallback_profile, "needs_product_name": False}

    return {
        "success": False,
        "needs_product_name": False,
        "defer_to_pipeline_vision": True,
        "data": {
            "product_name": "Đang nhận diện sản phẩm...",
            "category": "Thương mại & Bán lẻ",
            "benefits": "",
            "highlights": "",
            "target_customer": "Khách hàng trên TikTok",
            "scene1_dialogue": "",
            "scene2_dialogue": "",
            "needs_product_name": False
        }
    }


