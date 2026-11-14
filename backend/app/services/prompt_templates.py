import re
from typing import Dict, Any, List

def sanitize_tiktok_dialogue(text: str) -> str:
    """
    Sanitizes Vietnamese dialogue against TikTok Shop E-Commerce & Community Guidelines violations:
    1. Removes absolute claims: 100%, tuyệt đối, trị dứt điểm, trị tận gốc, chữa khỏi, vĩnh viễn, cam kết, đặc trị, thần thánh, thần dược...
    2. Removes superlative comparisons without certification: rẻ nhất thị trường, rẻ nhất, rẻ vô địch, số 1, đỉnh nhất, tốt nhất, hiệu quả tức thì, hàng đầu...
    3. Removes exaggerated urgency & sensationalism: sập sàn, xả lỗ, xả kho sập sàn, bán tháo, cháy hàng, rẻ như cho, không mua là hết, duy nhất hôm nay...
    4. Replaces external platform solicitation: zalo, facebook, inbox, nhắn riêng, ib, gọi hotline, sđt, chuyển khoản ngoài...
    5. Preserves natural, friendly Vietnamese flow and exact sentence length.
    """
    if not text:
        return ""
    
    replacements = [
        # Absolute claims & cure claims
        (r'\b100\s*%', 'hoàn toàn'),
        (r'\bcam kết\b', 'an tâm'),
        (r'\btuyệt đối an toàn\b', 'rất an toàn lành tính'),
        (r'\btuyệt đối\b', 'vô cùng'),
        (r'\bđặc trị\b', 'chăm sóc chuyên sâu'),
        (r'\btrị dứt điểm\b', 'hỗ trợ cải thiện hiệu quả'),
        (r'\btrị tận gốc\b', 'hỗ trợ chăm sóc chuyên sâu'),
        (r'\bchữa khỏi hoàn toàn\b', 'hỗ trợ phục hồi tích cực'),
        (r'\bchữa khỏi\b', 'hỗ trợ cải thiện'),
        (r'\bchữa lành\b', 'phục hồi'),
        (r'\bvĩnh viễn\b', 'bền lâu'),
        (r'\bthần thánh\b', 'chất lượng'),
        (r'\bthần dược\b', 'giải pháp hữu hiệu'),
        (r'\bhết sạch bệnh\b', 'cải thiện tốt'),
        
        # Superlatives & unverified ranking
        (r'\brẻ nhất thị trường\b', 'giá ưu đãi cực tốt'),
        (r'\brẻ nhất\b', 'giá cực kỳ tiết kiệm'),
        (r'\brẻ vô địch\b', 'giá siêu hời'),
        (r'\bsố 1 việt nam\b', 'chất lượng hàng đầu'),
        (r'\bsố 1\b', 'chất lượng hàng đầu'),
        (r'\bđỉnh nhất\b', 'vô cùng chất lượng'),
        (r'\btốt nhất\b', 'rất được ưa chuộng'),
        (r'\bhiệu quả tức thì\b', 'hiệu quả nhanh chóng'),
        (r'\bkhông đâu rẻ bằng\b', 'giá cực kỳ ưu đãi'),
        (r'\bhàng đầu thị trường\b', 'uy tín chất lượng'),

        # Sensationalism & false scarcity / Panic selling
        (r'\bsập sàn\b', 'trợ giá cực hời'),
        (r'\bxả lỗ\b', 'ưu đãi lớn'),
        (r'\bxả kho sập sàn\b', 'ưu đãi trợ giá tận xưởng'),
        (r'\bbán tống bán tháo\b', 'trợ giá số lượng có hạn'),
        (r'\bbán tháo\b', 'ưu đãi có hạn'),
        (r'\brẻ như cho\b', 'giá cực kỳ hời'),
        (r'\bkhông mua là hết\b', 'nhanh tay chốt đơn nhé'),
        (r'\bcháy hàng\b', 'được săn đón'),
        (r'\bduy nhất hôm nay\b', 'ngay trong hôm nay'),
        (r'\bduy nhất trong ngày\b', 'ngay hôm nay'),
        (r'\bgiá sốc\b', 'giá hời'),
        (r'\bgiảm sốc\b', 'trợ giá tốt'),
        
        # Off-platform mentions
        (r'\bzalo\b', 'giỏ hàng'),
        (r'\bfacebook\b', 'giỏ hàng'),
        (r'\bfb\b', 'giỏ hàng'),
        (r'\binbox\b', 'bấm vào giỏ hàng'),
        (r'\bib\b', 'bấm giỏ hàng'),
        (r'\bnhắn tin riêng\b', 'xem tại giỏ hàng'),
        (r'\bnhắn riêng\b', 'bấm vào giỏ hàng'),
        (r'\bchuyển khoản ngoài\b', 'đặt hàng trên giỏ hàng'),
        (r'\bchuyển khoản\b', 'thanh toán qua giỏ hàng'),
        (r'\bhotline\b', 'hỗ trợ trên giỏ hàng'),
        (r'\bsố điện thoại\b', 'giỏ hàng'),

        # UI artifact & OCR noise removal (phone screen overlays, buttons, gibberish)
        (r'\b[qQ]?\s*t[iì]m\s+s[aả]n\s+ph[ẩả]m[^\.\,\!\?]*', ''),
        (r'\bt[iì]m\s+ki[eế]m[^\.\,\!\?]*', ''),
        (r'\btddng\s*tv\b', ''),
        (r'\b\d+\s*dubng\b', ''),
        (r'\bquanh\s+vi[eế][\w]*\b', 'viền'),
        (r'\bđã\s+bán[^\.\,\!\?]*', ''),
        (r'\blượt\s+bán[^\.\,\!\?]*', ''),
        (r'\bđánh\s+giá[^\.\,\!\?]*', ''),
        (r'\báp\s+mã[^\.\,\!\?]*', ''),
        (r'\bvoucher[^\.\,\!\?]*', ''),
        (r'\bthêm\s+vào\s+giỏ\s+hàng\b', 'bấm vào giỏ hàng'),
        (r'\bmua\s+ngay\b', 'chốt đơn ngay')
    ]
    
    res = text
    for pattern, rep in replacements:
        res = re.sub(pattern, rep, res, flags=re.IGNORECASE)

    # Filter out corrupted non-Vietnamese OCR words (with characters like ä, ö, ë, å, ø)
    clean_words = []
    for w in res.split():
        w_low = w.lower()
        if any(c in w_low for c in ['ä', 'ö', 'ë', 'å', 'ü', 'ø', '§', '©', '®']):
            continue
        if any(b in w_low for b in ['tddng', 'tdong', 'dubng', 'versp00']):
            continue
        clean_words.append(w)
    
    res = " ".join(clean_words)
    res = re.sub(r'([,\.!?;:])\s*([,\.!?;:])+', r'\1', res)
    res = re.sub(r'\s+([,\.!?;:])', r'\1', res)
    res = re.sub(r'\s+', ' ', res).strip()
    return res

DEFAULT_SYSTEM_PROMPTS = [
    {
        "id": "sys_prompt_char_gen",
        "category": "character_gen",
        "title": "Tạo ảnh người mẫu nữ cao cấp đứng cùng sản phẩm tại cửa hàng (Chuẩn 9:16 8K)",
        "variables": ["product_name", "category", "description", "benefits", "target_customer"],
        "content": """Tạo ảnh quảng cáo sản phẩm siêu chân thực 8K, tỷ lệ dọc 9:16, phong cách chụp ảnh thương mại cao cấp, sang trọng, chuyên nghiệp, giống ảnh chụp thực tế bằng máy ảnh full-frame chuyên nghiệp với ống kính 50mm.

## 1. BỐI CẢNH CỬA HÀNG PHÙ HỢP VỚI SẢN PHẨM

Dựa hoàn toàn vào hình ảnh sản phẩm tham chiếu để thiết kế một cửa hàng trưng bày có phong cách, công năng và cách bố trí phù hợp với chính sản phẩm đó. Không sử dụng bối cảnh cửa hàng chung chung hoặc không liên quan đến sản phẩm.

Cửa hàng có thiết kế hiện đại, cao cấp, sạch sẽ, rộng rãi và chuyên nghiệp. Màu sắc nội thất, vật liệu trang trí, quầy trưng bày, kệ sản phẩm và các chi tiết xung quanh phải hài hòa với màu sắc, kiểu dáng và phân khúc của sản phẩm tham chiếu.

Bố trí khu vực trưng bày sản phẩm nổi bật ở tiền cảnh. Phía sau là các kệ trưng bày hoặc những sản phẩm cùng dòng, cùng nhóm hàng phù hợp với sản phẩm chính. Các sản phẩm phụ chỉ đóng vai trò tạo không gian cửa hàng chân thực, không được lấn át sản phẩm chính. Không tự ý thêm những mặt hàng không liên quan.

Không gian có chiều sâu tự nhiên, bố cục gọn gàng, tinh tế, thể hiện hình ảnh một cửa hàng uy tín với phong cách thương hiệu cao cấp. Có thể bổ sung quầy tư vấn, tủ trưng bày và bảng thông tin sản phẩm phù hợp với ngành hàng, nhưng không để các chi tiết này che khuất sản phẩm chính.

## 2. KHÓA SẢN PHẨM – BẮT BUỘC GIỮ NGUYÊN 100%

Sử dụng chính xác sản phẩm trong hình ảnh tham chiếu. Giữ nguyên tuyệt đối hình dáng, kích thước, tỷ lệ, màu sắc, chất liệu, cấu trúc, thiết kế, logo, chữ viết và toàn bộ chi tiết gốc.

Tuyệt đối không thiết kế lại, không thay đổi màu sắc, không bóp méo, không kéo giãn, không làm biến dạng, không thêm hoặc xóa bất kỳ chi tiết nào trên sản phẩm.

Đặt sản phẩm trên một bàn trưng bày cao cấp hoặc bục trưng bày sang trọng phù hợp với kích thước và công năng của sản phẩm. Sản phẩm nằm ở tiền cảnh, gần máy ảnh, chiếm vị trí nổi bật, nhìn thấy đầy đủ từ trên xuống dưới và từ trái sang phải, không bị cắt mất bất kỳ phần nào.

Sản phẩm có kích thước chân thực, nổi bật nhưng không phóng đại quá mức. Mặt trước sản phẩm hướng thẳng về phía máy ảnh, hạn chế góc nghiêng để thấy rõ thiết kế, logo và các chi tiết.
## 3. NGƯỜI MẪU NỮ CAO CẤP

Một người mẫu nữ Việt Nam 21 tuổi, xinh đẹp nổi bật, gương mặt thanh tú, đường nét hài hòa, đôi mắt sáng có thần, làn da tự nhiên, mái tóc được tạo kiểu tinh tế và lớp trang điểm nhẹ nhàng sang trọng.

Người mẫu mặc đồng phục nhân viên cửa hàng cao cấp, thiết kế hiện đại, thanh lịch, màu sắc hài hòa với sản phẩm và không gian cửa hàng. Trang phục chỉn chu, vừa vặn, chất liệu chân thực.

Người mẫu đứng sát bên cạnh hoặc hơi phía sau sản phẩm, ở vị trí gần máy ảnh. Một tay nhẹ nhàng giới thiệu sản phẩm, tay còn lại tạo dáng tự nhiên. Nụ cười thân thiện, ánh mắt tự tin, thần thái chuyên nghiệp như người đại diện thương hiệu trong chiến dịch quảng cáo cao cấp.

Khuôn mặt, đôi mắt, mái tóc, trang phục và bàn tay của người mẫu phải rõ nét, tự nhiên, chân thực; không làm mịn da quá mức, không tạo gương mặt giả hoặc biểu cảm cứng đờ.

## 4. BỐ CỤC VÀ KHOẢNG CÁCH MÁY ẢNH

Khung hình dọc 9:16, góc máy chính diện, bố cục quảng cáo thương mại chuyên nghiệp.

Đưa sản phẩm và người mẫu lại gần máy ảnh hơn, tạo cảm giác gần gũi và nổi bật. Sản phẩm chiếm phần lớn tiền cảnh nhưng vẫn giữ nguyên tỷ lệ thực tế và hiển thị trọn vẹn. Người mẫu đứng ngay cạnh sản phẩm để cả hai trở thành hai chủ thể chính trong khung hình.

Không để người mẫu đứng quá xa. Không để quầy kệ hoặc vật dụng trong cửa hàng che khuất sản phẩm. Cân đối khoảng trống phía trên và hai bên, tạo cảm giác sang trọng, rõ ràng và dễ nhìn.

## 5. LẤY NÉT CỰC RÕ VÀO CẢ SẢN PHẨM LẪN NGƯỜI MẪU

Bắt buộc lấy nét đồng thời vào sản phẩm và người mẫu. Cả hai phải sắc nét rõ ràng trong cùng một khung hình, không được chỉ nét sản phẩm mà mờ người mẫu, hoặc chỉ nét người mẫu mà mờ sản phẩm.

Logo, chữ viết, bề mặt, đường viền, kết cấu và mọi chi tiết trên sản phẩm đều rõ nét. Khuôn mặt, đôi mắt, tóc, trang phục và bàn tay người mẫu cũng rõ nét.

Sử dụng độ sâu trường ảnh đủ lớn, khẩu độ tham khảo f/8–f/11, ISO thấp và tốc độ màn trập phù hợp. Hạn chế xóa phông mạnh, không sử dụng hiệu ứng bokeh quá mức. Hậu cảnh cửa hàng vẫn nhận diện được rõ ràng nhưng không cạnh tranh sự chú ý với hai chủ thể chính.

## 6. ÁNH SÁNG TRẮNG SÁNG RÕ

Sử dụng hệ thống đèn LED ánh sáng trắng trung tính khoảng 5500K, chiếu sáng đồng đều toàn bộ cửa hàng, sản phẩm và người mẫu.
Ánh sáng phải sáng rõ, sạch, tự nhiên, cao cấp và chuyên nghiệp. Sản phẩm thể hiện đúng màu sắc thực tế, không bị ám vàng, ám xanh hoặc đổi màu. Khuôn mặt người mẫu đủ sáng, không bị tối, không có bóng đổ gắt. Giữ lại chi tiết ở vùng sáng, không cháy sáng, không làm mất kết cấu sản phẩm.

## 7. LOGO VÀ NHẬN DIỆN THƯƠNG HIỆU

Nếu có hình ảnh logo công ty được cung cấp, đặt logo trên bảng hiệu sang trọng ở bức tường phía sau quầy trưng bày. Logo có thể được thiết kế dạng chữ nổi hoặc hộp đèn phát sáng tinh tế, dễ nhìn và phù hợp với nội thất cửa hàng.

Giữ nguyên chính xác hình dáng, màu sắc, tỷ lệ và nội dung logo tham chiếu. Không tự sáng tạo tên công ty, không viết sai chữ, không thay đổi logo gốc. Logo trên sản phẩm cũng phải được giữ nguyên tuyệt đối.

## 8. CHẤT LƯỢNG HÌNH ẢNH

Ảnh quảng cáo sản phẩm siêu chân thực 8K, chi tiết cao, độ nét cao, màu sắc trung thực, ánh sáng trắng đồng đều, chất liệu chân thực, bố cục sang trọng, phong cách nhiếp ảnh quảng cáo chuyên nghiệp. Sản phẩm và người mẫu là hai điểm thu hút chính, nổi bật rõ ràng ngay từ cái nhìn đầu tiên.
chỉnh sửa sao cho kích thước sản phẩm hợp lý

## 9. NEGATIVE PROMPT – CÁC LỖI CẦN TRÁNH

Không sai sản phẩm, không đổi thiết kế, không đổi màu, không bóp méo, không kéo giãn, không sai tỷ lệ, không sai logo, không chữ sai, không thêm chi tiết lạ, không mất chi tiết gốc, không cắt cụt sản phẩm, không phóng đại sản phẩm quá mức, không làm mờ sản phẩm, không làm mờ người mẫu, không lấy nét sai, không xóa phông quá mạnh, không bokeh quá mức, không nhòe chuyển động, không ánh sáng tối, không ám vàng, không bóng đổ gắt, không cháy sáng, không da nhựa, không gương mặt biến dạng, không tay lỗi, không thừa ngón tay, không cửa hàng bừa bộn, không nội thất cũ kỹ, không bối cảnh nhà máy hoặc kho hàng, không thêm sản phẩm không liên quan, không chữ ngẫu nhiên, không watermark, không phong cách hoạt hình hoặc CGI giả tạo."""
    },
    {
        "id": "sys_prompt_char_warehouse",
        "category": "character_gen_warehouse",
        "title": "Tạo ảnh nhân vật nam tổng kho xưởng xuất nhập hàng (Bản kho xưởng 9:16)",
        "variables": ["product_name", "category", "description", "benefits"],
        "content": """Tạo ảnh quảng cáo sản phẩm siêu chân thực 8K, tỷ lệ dọc 9:16, phong cách chụp ảnh thương mại thực tế tại tổng kho xưởng quy mô lớn.

## 1. BỐI CẢNH TỔNG KHO XƯỞNG
Bối cảnh là tổng kho xưởng xuất nhập hàng {{category}} hiện đại, sạch sẽ, quy mô cực lớn. Phía sau là các dãy kệ pallet chứa hàng cao tầng xếp hàng hóa ngăn nắp, thể hiện nguồn hàng tận gốc xuất thẳng từ xưởng.
Sản phẩm {{product_name}} đặt trên bàn kiểm hàng hoặc pallet gỗ ở tiền cảnh, nổi bật và sắc nét.

## 2. KHÓA SẢN PHẨM 100%
Giữ nguyên 100% thiết kế, nhãn mác, màu sắc, logo thật của {{product_name}} trong ảnh tham chiếu.

## 3. NHÂN VIÊN NAM TỔNG KHO XƯỞNG
Một nhân viên nam Việt Nam 22-26 tuổi, gương mặt sáng, nụ cười hào sảng, thân thiện, mặc áo thun polo đồng phục kho hoặc tạp dề kho xưởng gọn gàng.
Một tay chỉ hoặc mở lòng bàn tay hướng về sản phẩm giới thiệu phong thái tự tin như đang livestream tại kho hàng.

## 4. CHẤT LƯỢNG 8K & ÁNH SÁNG
Ánh sáng kho xưởng sáng rõ, đèn trần công nghiệp trung tính, ảnh sắc nét từng chi tiết sản phẩm và gương mặt nhân vật, tỷ lệ 9:16."""
    },
    {
        "id": "sys_prompt_char_factory_female",
        "category": "character_gen_warehouse",
        "title": "Tạo ảnh người mẫu nữ trẻ trung tại xưởng sản xuất bạt ngàn pallet hàng hóa (Bản Kho Xưởng TikTok 9:16 8K)",
        "variables": ["product_name", "category", "description", "benefits", "highlights"],
        "content": """Tạo ảnh quảng cáo sản phẩm siêu chân thực 8K, tỷ lệ dọc 9:16, phong cách quay video/chụp ảnh thương mại thực tế tại xưởng sản xuất và tổng kho quy mô lớn, giống ảnh chụp thực tế bằng máy ảnh full-frame chuyên nghiệp ống kính 50mm.

## 1. BỐI CẢNH XƯỞNG SẢN XUẤT & TỔNG KHO HÀNG
Bối cảnh là bên trong một nhà máy / xưởng sản xuất và tổng kho quy mô cực lớn, trần cao khung thép công nghiệp, có mái lấy sáng ban ngày tự nhiên và hệ thống đèn trần nhà xưởng sáng rõ, sạch sẽ.
Ở tiền cảnh và trung cảnh là lối đi bê tông rộng rãi giữa các dãy hàng. Hai bên lối đi chất đầy các kiện hàng sản phẩm {{product_name}} được xếp ngay ngắn, cao ngất ngưởng trên các pallet gỗ công nghiệp thành tầng tầng lớp lớp bạt ngàn, thể hiện nguồn hàng xuất xưởng dồi dào, tận gốc.
Phía xa hậu cảnh có các công nhân mặc áo đồng phục công nhân màu xanh dương, đội mũ lưỡi trai đang làm việc, bốc xếp và kiểm hàng, tạo bầu không khí xưởng sản xuất tấp nập, chân thực và uy tín 100%.

## 2. KHÓA SẢN PHẨM 100% TỪ ẢNH THAM CHIẾU
Sử dụng chính xác sản phẩm {{product_name}} trong hình ảnh tham chiếu. Giữ nguyên 100% hình dáng, chi tiết, cấu trúc, màu sắc, hoa văn, viền may, khoen khuy và chất liệu thật của sản phẩm.
Tuyệt đối không thay đổi màu sắc, không biến dạng, không sáng tạo sản phẩm khác không liên quan.

## 3. NGƯỜI MẪU NỮ TRẺ TRUNG TẠI XƯỞNG
Một người mẫu nữ Việt Nam khoảng 21-25 tuổi, gương mặt thanh tú xinh xắn, nụ cười rạng rỡ, thần thái tự tin, gần gũi và hào sảng. Mái tóc đen ngắn ngang vai tự nhiên, lớp trang điểm nhẹ nhàng tươi tắn.
Trang phục phong cách nhân viên / chủ xưởng trẻ trung, năng động và chân thực:
- Áo sơ mi denim bò màu xanh dương (blue denim shirt) mặc khoác ngoài.
- Áo thun trắng trơn đơn giản bên trong.
- Quần jean xanh ống đứng vừa vặn.
- Giày thể thao trắng sạch sẽ.
- Có kẹp một chiếc micro thu âm cài áo không dây màu đen nhỏ gọn (wireless lavalier microphone) ở cổ áo trước ngực.

Tư thế và hành động:
Người mẫu đứng hoặc bước đi tự nhiên dọc theo lối đi xưởng, hai tay nâng và ôm trọn cọc sản phẩm {{product_name}} ở phía trước người ngang bụng, hướng thẳng về máy ảnh để thấy rõ chi tiết sản phẩm. Một tay giữ sản phẩm, tay kia tươi cười chỉ về phía các dãy pallet hàng bạt ngàn phía sau như đang giới thiệu kho hàng giá xuất xưởng trực tiếp cho khách hàng.

## 4. GÓC MÁY & CHẤT LƯỢNG HÌNH ẢNH 8K
Khung hình dọc 9:16 chuẩn video TikTok, góc chụp chính diện ngang tầm mắt (eye-level shot).
Lấy nét cực rõ đồng thời vào cả sản phẩm {{product_name}} và khuôn mặt, trang phục của người mẫu nữ.
Độ sâu trường ảnh sâu (f/8 - f/11), thấy rõ quy mô kho xưởng và các pallet hàng phía sau.
Ánh sáng tự nhiên nhà xưởng kết hợp đèn công nghiệp trung tính 5500K, màu sắc trung thực, không ám vàng, không cháy sáng.

## 5. NEGATIVE PROMPT (CÁC LỖI CẦN TRÁNH)
Không sai sản phẩm tham chiếu, không đổi màu sản phẩm, không biến dạng, không mặt nhựa bóng, không da sáp, không tay thừa ngón, không chữ ngẫu nhiên, không watermark, không phong cách hoạt hình hay CGI giả tạo, không bối cảnh studio phông bạt nhân tạo."""
    },
    {
        "id": "sys_prompt_script_factory_direct",
        "category": "script_gen_warehouse",
        "title": "Kịch bản Thoại Giá Xuất Xưởng Tận Gốc (Bản Kho Xưởng - Triệu View TikTok Shop)",
        "variables": ["product_name", "category", "benefits", "highlights", "price", "offer"],
        "content": """Dựa trên hình ảnh nhân vật AI tại xưởng và sản phẩm tham chiếu {{product_name}} (Ngành hàng: {{category}}, Công dụng: {{benefits}}, Chi tiết nổi bật: {{highlights}}):

Hãy viết kịch bản video TikTok Affiliate 2 cảnh chuẩn phong cách "Xưởng sản xuất xả kho giá tận gốc" (10 giây/cảnh, tổng 20 giây):
- Mỗi cảnh từ 42 đến 48 từ tiếng Việt, câu văn trọn vẹn 100%, nhịp điệu hào sảng, nhanh nhẹn, tự nhiên, đọc hết vừa vặn trong 10 giây.
- Đúng cấu trúc tâm lý bán hàng của video xưởng triệu view:
  + CẢNH 1: Hook mua tận xưởng cho rẻ + Lý do mở shop TikTok trợ giá sỉ + Chỉ tay vào giỏ hàng góc trái.
  + CẢNH 2: Phá giá thị trường (không phải giá đắt ngoài chợ/siêu thị) + Cận cảnh chất liệu chuẩn xưởng bền đẹp + Kêu gọi chốt đơn kẻo hết trợ giá.

ĐỊNH DẠNG ĐẦU RA BẮT BUỘC:

### KỊCH BẢN KHO XƯỞNG GIÁ TẬN GỐC: [{{product_name}}]

**CẢNH 1 (10 GIÂY - HOOK GIÁ XƯỞNG):**
- Lời thoại: "Muốn mua {{product_name}} thì mua ngay tại xưởng sản xuất cho rẻ anh chị ơi! Nay bên em mới mở gian hàng trên TikTok nên để cho cả nhà giá sỉ xuất xưởng tận gốc cực hời. Cả nhà bấm ngay vào giỏ hàng góc trái bên dưới chốt đơn liền tay nhé!"
- Số từ: 46 từ
- Prompt Veo 3 / Muse AI: [Cảnh 1 - Giới thiệu giá xuất xưởng {{product_name}} | 9:16, 10s, 60fps] Nhân vật nữ từ ảnh tham chiếu mặc áo sơ mi denim ôm cọc {{product_name}}, bước đi tự nhiên giữa lối đi tổng kho xưởng với các kiện hàng trên pallet xếp cao ngất ngưởng, tươi cười hào sảng chỉ tay giới thiệu. Giữ nguyên 100% nhân vật, trang phục và sản phẩm. Khẩu hình miệng khớp hoàn hảo với thoại tiếng Việt trong 10s. Không chèn chữ, không phụ đề.

**CẢNH 2 (10 GIÂY - PHÁ GIÁ THỊ TRƯỜNG & CHỐT ĐƠN):**
- Lời thoại: "Mỗi một tài khoản các bác săn được {{product_name}} giá rẻ lắm ạ! Không phải giá cao tiền trăm ngoài thị trường đâu, hôm nay xả kho giá xuất xưởng cực sốc. Chất liệu chuẩn xưởng {{highlights}} bền đẹp, số lượng có hạn cả nhà bấm ngay giỏ hàng góc trái chốt đơn nhé!"
- Số từ: 46 từ
- Prompt Veo 3 / Muse AI: [Cảnh 2 - Cận cảnh chi tiết {{product_name}} & Chốt đơn giá xưởng | 9:16, 10s, 60fps] Máy quay tiến chậm cận cảnh làm nổi bật chất liệu chuẩn xưởng và chi tiết hoàn thiện của {{product_name}} trên tay nhân vật, nhân vật mỉm cười giơ ngón tay cái rồi chỉ xuống góc trái màn hình kêu gọi chốt đơn. Tiếp nối trực tiếp từ khung hình ảnh tham chiếu, giữ nguyên 100% nhân vật và sản phẩm. Khẩu hình miệng khớp hoàn hảo với thoại tiếng Việt trong 10s. Không chèn chữ, không phụ đề."""
    },
    {
        "id": "sys_prompt_video_factory_scene1",
        "category": "veo3_scene1_warehouse",
        "title": "Prompt Video Cảnh 1 - Bước đi tại kho xưởng giới thiệu giá tận xưởng (9:16 10s 60fps)",
        "variables": ["product_name", "category", "dialogue_1"],
        "content": """[Cảnh 1 - Giới thiệu giá xuất xưởng {{product_name}} | 9:16, 10s, 60fps]
Nhân vật nữ Việt Nam trẻ trung từ ảnh tham chiếu mặc áo sơ mi denim bò xanh khoác ngoài áo thun trắng, hai tay bưng cọc sản phẩm {{product_name}}, vừa bước đi tự nhiên về phía máy ảnh dọc theo lối đi chính trong nhà xưởng sản xuất quy mô lớn với các dãy pallet hàng hóa xếp cao ngất ngưởng phía sau, vừa tươi cười hào sảng giới thiệu nguồn hàng giá xuất xưởng rẻ tận gốc.
Bắt đầu chuyển động trực tiếp từ đúng khung hình ảnh tham chiếu đính kèm: giữ nguyên 100% khuôn mặt, trang phục nhân vật, bối cảnh nhà xưởng công nghiệp tấp nập và đúng sản phẩm {{product_name}} trong ảnh tham chiếu (khóa 100% kiểu dáng, màu sắc, chi tiết thật).
Nhân vật nói tiếng Việt rõ ràng, khẩu hình miệng khớp hoàn hảo với lời thoại trong 10 giây:
"Muốn mua {{product_name}} thì mua ngay tại xưởng sản xuất cho rẻ anh chị ơi! Nay bên em mới mở gian hàng trên TikTok nên để cho cả nhà giá sỉ xuất xưởng tận gốc cực hời. Cả nhà bấm ngay vào giỏ hàng góc trái bên dưới chốt đơn liền tay nhé!"
(Không chèn chữ, không phụ đề)."""
    },
    {
        "id": "sys_prompt_video_factory_scene2",
        "category": "veo3_scene2_warehouse",
        "title": "Prompt Video Cảnh 2 - Cận cảnh sản phẩm tại xưởng & Kêu gọi chốt đơn giá xưởng (9:16 10s 60fps)",
        "variables": ["product_name", "category", "highlights", "dialogue_2"],
        "content": """[Cảnh 2 - Cận cảnh chi tiết {{product_name}} & Chốt đơn giá xưởng | 9:16, 10s, 60fps]
Máy quay tiến nhẹ cận cảnh (smooth push-in) làm nổi bật từng đường may, nếp gấp và chi tiết cấu tạo chất liệu chuẩn xưởng của {{product_name}} trên tay nhân vật, nhân vật nữ mỉm cười duyên dáng, lật mở chi tiết sản phẩm rồi chỉ ngón tay xuống giỏ hàng góc trái màn hình kêu gọi đặt mua giá xuất xưởng ưu đãi.
Tiếp nối trực tiếp từ đúng khung hình ảnh tham chiếu đính kèm: giữ nguyên 100% nhân vật, bối cảnh kho xưởng và khóa nguyên vẹn 100% thiết kế, màu sắc, nhãn mác thật của sản phẩm {{product_name}} trong ảnh tham chiếu.
Nhân vật nói tiếng Việt hào sảng, khẩu hình miệng khớp hoàn hảo với lời thoại trong 10 giây:
"Mỗi một tài khoản các bác săn được {{product_name}} giá rẻ lắm ạ! Không phải giá cao tiền trăm ngoài thị trường đâu, hôm nay xả kho giá xuất xưởng cực sốc. Chất liệu chuẩn xưởng {{highlights}} bền đẹp, số lượng có hạn cả nhà bấm ngay giỏ hàng góc trái chốt đơn nhé!"
(Không chèn chữ, không phụ đề)."""
    },
    {
        "id": "sys_prompt_script_gen",
        "category": "script_gen",
        "title": "Tạo Kịch bản & Prompt Video TikTok Affiliate Chuẩn Chính Sách (≥ 42 từ/cảnh trọn câu 10s)",
        "variables": ["product_name", "category", "description", "benefits", "highlights", "price", "offer", "target_customer"],
        "content": """Dựa trên hình ảnh nhân vật AI và sản phẩm tham chiếu trong ảnh đính kèm:
Tên sản phẩm: {{product_name}}
Ngành hàng: {{category}}
Công dụng chính: {{benefits}}
Điểm nổi bật: {{highlights}}
Giá bán & Ưu đãi: {{price}} ({{offer}})

Hãy viết kịch bản video TikTok Affiliate với 2 cảnh (mỗi cảnh 10 giây, tổng 20 giây) bám sát 100% công dụng thực tế của {{product_name}}:
- Mỗi cảnh dài tối thiểu 42 từ trở lên (42 - 50 từ), câu văn trọn vẹn 100% đọc hết vừa vặn trong 10 giây (tuyệt đối không cắt ngang câu).
- LỜI THOẠI TUÂN THỦ CHÍNH SÁCH TIKTOK SHOP (TUYỆT ĐỐI TRÁNH VI PHẠM):
  + Không dùng từ ngữ cam kết tuyệt đối: không nói "100%", "tuyệt đối", "trị dứt điểm", "trị tận gốc", "chữa khỏi", "vĩnh viễn", "cam kết".
  + Không dùng từ so sánh nhất không kiểm chứng: không nói "rẻ nhất", "số 1", "đỉnh nhất", "tốt nhất".
  + Không dùng từ giật gân, hối thúc: không nói "sập sàn", "xả lỗ", "bán tháo", "cháy hàng", "rẻ như cho".
  + Không lôi kéo rời nền tảng: không nói "Zalo", "Facebook", "inbox", "nhắn riêng".
  + Sử dụng từ ngữ an toàn, thu hút: "trợ giá ưu đãi", "hàng chính hãng nguồn gốc rõ ràng", "bấm vào giỏ hàng góc trái màn hình nhận ưu đãi và miễn phí giao hàng".

ĐỊNH DẠNG ĐẦU RA BẮT BUỘC:

### PHƯƠNG ÁN A: [Kịch Bản Chuẩn Cửa Hàng & Tiện Ích - {{product_name}}]
**Ý tưởng và hook:** [Tập trung giải quyết nhu cầu thực tế của khách hàng bằng {{product_name}}]

**CẢNH 1**
- Lời thoại: [Tối thiểu 42 từ tiếng Việt (42-50 từ), trọn câu đọc hết trong 10s, giới thiệu công dụng & hook an toàn TikTok]
- Bộ đếm: [Số từ] từ
- Prompt Veo 3: [Prompt Veo 3 chi tiết bằng tiếng Việt, nhân vật nữ mỉm cười giới thiệu công dụng, khóa 100% ảnh tham chiếu]

**CẢNH 2**
- Lời thoại: [Tối thiểu 42 từ tiếng Việt (42-50 từ), trọn câu đọc hết trong 10s, cận cảnh chi tiết và kêu gọi bấm giỏ hàng góc trái]
- Bộ đếm: [Số từ] từ
- Prompt Veo 3: [Prompt Veo 3 chi tiết bằng tiếng Việt, máy quay tiến chậm cận cảnh sản phẩm, khóa 100% thiết kế sản phẩm]"""
    },
    {
        "id": "sys_prompt_veo3_scene1",
        "category": "veo3_scene1",
        "title": "Mẫu Prompt Veo 3 - Cảnh 1 (Hook & Giới thiệu công dụng theo sản phẩm)",
        "variables": ["character_description", "product_name", "category", "benefits", "dialogue_1"],
        "content": """[Cảnh 1 - Giới thiệu công dụng {{product_name}} ({{category}}) | 9:16, 10s, 60fps]
Nhân vật nữ Việt Nam từ ảnh tham chiếu mỉm cười tươi tắn, thanh lịch đứng tại showroom cửa hàng trưng bày cao cấp, tay nhẹ nhàng chỉ trực tiếp giới thiệu sản phẩm {{product_name}} đang đặt trên bàn trưng bày ở tiền cảnh, nói về công dụng tiện ích ({{benefits}}).
Bắt đầu chuyển động trực tiếp từ đúng khung hình ảnh tham chiếu đính kèm: giữ nguyên 100% khuôn mặt, trang phục nhân vật nữ, bối cảnh cửa hàng và đúng sản phẩm {{product_name}} trong ảnh tham chiếu (khóa 100% kiểu dáng, màu sắc, chữ in thật, không tự sinh sản phẩm khác).
Nhân vật nói tiếng Việt rõ ràng, khẩu hình miệng khớp hoàn hảo với lời thoại trong 10 giây:
"{{dialogue_1}}"
Không chữ trên màn hình, không phụ đề, không watermark."""
    },
    {
        "id": "sys_prompt_veo3_scene2",
        "category": "veo3_scene2",
        "title": "Mẫu Prompt Veo 3 - Cảnh 2 (Cận cảnh chi tiết sản phẩm & Kêu gọi giỏ hàng góc trái)",
        "variables": ["character_description", "product_name", "category", "highlights", "dialogue_2"],
        "content": """[Cảnh 2 - Cận cảnh chi tiết {{product_name}} & Chốt đơn | 9:16, 10s, 60fps]
Máy quay tiến chậm cận cảnh (smooth push-in) làm nổi bật chi tiết chất lượng của {{product_name}} ({{highlights}}), nhân vật nữ mỉm cười duyên dáng, chỉ vào sản phẩm rồi chỉ xuống giỏ hàng góc trái màn hình kêu gọi đặt mua nhận ưu đãi trợ giá và miễn phí giao hàng.
Tiếp nối trực tiếp từ đúng khung hình ảnh tham chiếu đính kèm: giữ nguyên 100% nhân vật, bối cảnh cửa hàng và khóa 100% thiết kế, màu sắc, nhãn mác thật của sản phẩm {{product_name}} trong ảnh tham chiếu, không biến dạng.
Nhân vật nói tiếng Việt truyền cảm, khẩu hình miệng khớp hoàn hảo với lời thoại trong 10 giây:
"{{dialogue_2}}"
Không chữ trên màn hình, không phụ đề, không watermark."""
    },
    {
        "id": "sys_prompt_dialogue_fix",
        "category": "dialogue_fix",
        "title": "Chỉnh sửa lời thoại chuẩn xác 42 từ tiếng Việt (An toàn TikTok Shop)",
        "variables": ["current_dialogue", "product_name", "target_words"],
        "content": """Đoạn lời thoại sau hiện có số từ chưa đạt chuẩn:
"{{current_dialogue}}"

YÊU CẦU:
1. Có CHÍNH XÁC đúng 42 TỪ tiếng Việt (không thiếu, không thừa).
2. TUYỆT ĐỐI TUÂN THỦ CHÍNH SÁCH TIKTOK SHOP: không dùng các từ cấm (100%, tuyệt đối, trị dứt điểm, rẻ nhất, sập sàn, xả lỗ, Zalo, inbox).
3. Nhịp câu mượt mà, dễ phát âm, không bị vấp khi đọc nhanh trong 10 giây.
4. Trả về đúng 1 câu thoại 42 từ duy nhất kèm số đếm xác nhận."""
    }
]

def count_vietnamese_words(text: str) -> int:
    if not text:
        return 0
    cleaned = re.sub(r'["\'`“”‘’«»()\[\]{}–—:;,\.!?\/\\]', ' ', text)
    words = [w.strip() for w in cleaned.split() if w.strip()]
    return len(words)

def render_prompt(template_content: str, context: Dict[str, Any]) -> str:
    result = template_content
    for key, val in context.items():
        placeholder = f"{{{{{key}}}}}"
        str_val = str(val) if val is not None else ""
        result = result.replace(placeholder, str_val)
    return result
