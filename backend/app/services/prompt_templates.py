import re
from typing import Dict, Any, List

DEFAULT_SYSTEM_PROMPTS = [
    {
        "id": "sys_prompt_char_gen",
        "category": "character_gen",
        "title": "Tạo ảnh nhân vật thương mại đứng cùng sản phẩm (Chuẩn cửa hàng 9:16)",
        "variables": ["product_name", "category", "description", "benefits", "target_customer"],
        "content": """Tạo ảnh quảng cáo sản phẩm siêu chân thực 8K, tỷ lệ dọc 9:16, phong cách chụp ảnh thương mại cao cấp, sang trọng, chuyên nghiệp, giống ảnh chụp thực tế bằng máy ảnh full-frame chuyên nghiệp với ống kính 50mm.

## 1. BỐI CẢNH CỬA HÀNG PHÙ HỢP VỚI SẢN PHẨM ({{category}})

Dựa hoàn toàn vào hình ảnh sản phẩm tham chiếu (Tên sản phẩm: {{product_name}} - Ngành hàng: {{category}} - Công dụng: {{benefits}}) để thiết kế một cửa hàng/showroom trưng bày có phong cách, công năng và cách bố trí phù hợp với chính sản phẩm đó. Không sử dụng bối cảnh cửa hàng chung chung hoặc không liên quan đến sản phẩm.

Cửa hàng có thiết kế hiện đại, cao cấp, sạch sẽ, rộng rãi và chuyên nghiệp. Màu sắc nội thất, vật liệu trang trí, quầy trưng bày, kệ sản phẩm và các chi tiết xung quanh phải hài hòa với màu sắc, kiểu dáng và phân khúc của sản phẩm tham chiếu.

Bố trí khu vực trưng bày sản phẩm nổi bật ở tiền cảnh. Phía sau là các kệ trưng bày hoặc những sản phẩm cùng dòng, cùng nhóm hàng phù hợp với sản phẩm chính. Các sản phẩm phụ chỉ đóng vai trò tạo không gian cửa hàng chân thực, không được lấn át sản phẩm chính. Không tự ý thêm những mặt hàng không liên quan.

Không gian có chiều sâu tự nhiên, bố cục gọn gàng, tinh tế, thể hiện hình ảnh một cửa hàng uy tín với phong cách thương hiệu cao cấp. Có thể bổ sung quầy tư vấn, tủ trưng bày và bảng thông tin sản phẩm phù hợp với ngành hàng, nhưng không để các chi tiết này che khuất sản phẩm chính.

## 2. KHÓA SẢN PHẨM – BẮT BUỘC GIỮ NGUYÊN 100%

Sử dụng chính xác sản phẩm trong hình ảnh tham chiếu (Tên sản phẩm: {{product_name}}). Giữ nguyên tuyệt đối hình dáng, kích thước, tỷ lệ, màu sắc, chất liệu, cấu trúc, thiết kế, logo, chữ viết và toàn bộ chi tiết gốc.

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

Đưa sản phẩm và người mẫu lại gần máy ảnh hơn, tạo cảm giác gần gũi và nổi bật. Sản phẩm chiếm phần lớn tiền cảnh nhưng vẫn giữ nguyên tỷ lệ thực tế và hài hòa với người mẫu.

Người mẫu xuất hiện ở góc chụp từ thắt lưng trở lên (medium shot) hoặc gần hơn (medium close-up), vừa đủ để thấy rõ biểu cảm gương mặt, trang phục, cử chỉ tay và sự tương tác tự nhiên với sản phẩm.

Toàn bộ bố cục phải cân đối, hài hòa, hướng toàn bộ sự chú ý của người xem vào sản phẩm và người mẫu.

## 5. TƯƠNG TÁC VÀ ĐẶT SẢN PHẨM

Sản phẩm được đặt chắc chắn trên bàn trưng bày hoặc bục trưng bày cao cấp ở tiền cảnh.

Người mẫu đứng ngay cạnh sản phẩm, mở lòng bàn tay hướng về sản phẩm như đang tư vấn cho khách hàng, hoặc một tay đặt nhẹ lên cạnh bàn gần sản phẩm (không chạm hoặc che bất kỳ chi tiết, logo hay chữ viết nào trên sản phẩm).

Tư thế đứng thẳng, phong thái tự tin, thanh lịch và cuốn hút. Ánh mắt nhìn thẳng vào ống kính máy ảnh như đang giao tiếp trực tiếp với người xem TikTok.

Tạo cảm giác chân thực như một bức ảnh chụp thực tế trong chiến dịch quảng cáo chính thức của thương hiệu.

## 6. ÁNH SÁNG VÀ MÀU SẮC

Hệ thống ánh sáng studio thương mại chuyên nghiệp, kết hợp ánh sáng chính (key light) mềm mại, ánh sáng phụ (fill light) dịu nhẹ và ánh sáng viền (rim light) tinh tế, làm nổi bật đường nét của sản phẩm và người mẫu.

Ánh sáng cửa hàng ấm áp, tự nhiên, sang trọng, tạo cảm giác cao cấp và chuyên nghiệp.

Không có bóng gắt khó chịu, không bị cháy sáng, không bị tối mờ bất kỳ chi tiết quan trọng nào trên sản phẩm và khuôn mặt người mẫu.

Màu sắc trung thực, tươi sáng, độ tương phản vừa phải, bão hòa tự nhiên, mang lại cảm giác dễ chịu và thu hút người xem ngay từ cái nhìn đầu tiên.

## 7. ĐỘ CHI TIẾT VÀ CHẤT LƯỢNG HÌNH ẢNH

Chất lượng ảnh siêu cao 8K, độ nét cực cao, rõ từng chi tiết nhỏ nhất trên sản phẩm (chữ in, logo, kết cấu bề mặt, đường nét thiết kế, vật liệu bao bì).

Chi tiết da của người mẫu tự nhiên, thấy rõ lỗ chân lông mịn, kết cấu da thật, từng sợi tóc mượt mà, ánh mắt có thần, phản chiếu ánh sáng chân thực.

Không có hiện tượng da sáp, không bị bóng nhờn phi tự nhiên, không mang cảm giác nhân vật 3D hoặc tranh vẽ AI.

Độ sâu trường ảnh (depth of field) nông tinh tế: sản phẩm và người mẫu sắc nét từng chi tiết; hậu cảnh cửa hàng phía sau mờ nhẹ tự nhiên (bokeh mềm mại), làm tăng chiều sâu không gian mà vẫn nhận biết rõ đó là một cửa hàng cao cấp phù hợp với sản phẩm.

## 8. YÊU CẦU ĐẶC BIỆT VỀ CHỮ VÀ VĂN BẢN

Giữ nguyên 100% chữ viết, logo và nhãn hiệu có sẵn trên sản phẩm gốc trong ảnh tham chiếu. Đảm bảo chữ trên sản phẩm rõ nét, đọc được, không bị nhòe, không biến dạng, không sai chính tả.

Ngoại trừ chữ có sẵn trên sản phẩm gốc và các biển hiệu cửa hàng mờ phía sau nếu có, TUYỆT ĐỐI KHÔNG tự ý thêm bất kỳ chữ viết, văn bản, slogan, phụ đề, biểu tượng giá tiền, hình dán hay watermark nào khác vào khung hình.

Hình ảnh hoàn toàn sạch sẽ, mang phong cách ảnh chụp thương mại thuần túy, chuyên nghiệp và sang trọng.

## 9. QUY TẮC AN TOÀN – BẮT BUỘC TUÂN THỦ

Không tạo ngón tay thừa, không tạo ngón tay thiếu, không làm dị dạng bàn tay, không vẽ mắt méo, không làm lệch đồng tử, không làm biến dạng tỷ lệ cơ thể của người mẫu.

Không làm sai lệch màu sắc, hình dáng, cấu trúc hoặc bất kỳ chi tiết nào của sản phẩm tham chiếu.

Không để bối cảnh cửa hàng lộn xộn, không để các chi tiết hậu cảnh làm phân tán sự chú ý khỏi sản phẩm chính.

Không sử dụng phong cách hoạt hình, 3D render, anime hay tranh vẽ minh họa. Bắt buộc phải là ảnh chụp thực tế (photorealistic photography)."""
    },
    {
        "id": "sys_prompt_script_gen",
        "category": "script_gen",
        "title": "Tạo Kịch bản & Prompt Video TikTok Affiliate Theo Đúng Công Dụng Sản Phẩm (≥ 42 từ/cảnh trọn câu 10s)",
        "variables": ["product_name", "category", "description", "benefits", "highlights", "price", "offer", "target_customer"],
        "content": """Dựa trên hình ảnh nhân vật AI và sản phẩm tham chiếu trong ảnh đính kèm:
Tên sản phẩm: {{product_name}}
Ngành hàng: {{category}}
Công dụng chính: {{benefits}}
Điểm nổi bật: {{highlights}}
Giá bán & Ưu đãi: {{price}} ({{offer}})

Hãy viết kịch bản Veo 3 với 2 cảnh (mỗi cảnh 10 giây, tổng 20 giây) bám sát 100% công dụng thực tế, cấu tạo và đối tượng khách hàng của sản phẩm {{product_name}} trong ảnh tham chiếu:
- Mỗi cảnh dài tối thiểu 42 từ trở lên (42 - 50 từ), câu văn trọn vẹn 100% đọc hết vừa vặn trong 10 giây (tuyệt đối không cắt ngang câu).
- Nói rõ đúng công dụng thực tế ({{benefits}}) và đặc điểm nổi bật ({{highlights}}) của sản phẩm {{product_name}}, không viết chung chung.
- Câu mở đầu đánh trúng nhu cầu/nỗi đau của khách hàng đối với sản phẩm {{product_name}}, Cảnh 2 có chốt đơn khéo léo ở giỏ hàng góc trái màn hình.
- Prompt tạo video Cảnh 1 và Cảnh 2 phải mô tả cụ thể cử chỉ nhân vật tương tác với đúng các bộ phận/chi tiết của {{product_name}} và góc máy lấy nét cận cảnh đúng đặc điểm của {{product_name}} tại Cảnh 2 (khóa chặt 100% sản phẩm trong ảnh tham chiếu không bị biến dạng).

ĐỊNH DẠNG ĐẦU RA BẮT BUỘC:

### PHƯƠNG ÁN A: [Đánh vào nhu cầu & công dụng thực tế của {{product_name}}]
**Ý tưởng và hook:** [Tóm tắt ngắn]

**CẢNH 1**
- Lời thoại: [Tối thiểu 42 từ tiếng Việt (42-50 từ), trọn câu đọc hết trong 10s]
- Bộ đếm: [Số từ] từ
- Prompt Veo 3: [Prompt Veo 3 chi tiết bằng tiếng Việt riêng cho {{product_name}}, mô tả rõ cử chỉ giới thiệu công dụng và khóa 100% ảnh tham chiếu]

**CẢNH 2**
- Lời thoại: [Tối thiểu 42 từ tiếng Việt (42-50 từ), trọn câu đọc hết trong 10s, nhắc giỏ hàng góc trái màn hình]
- Bộ đếm: [Số từ] từ
- Prompt Veo 3: [Prompt Veo 3 chi tiết bằng tiếng Việt riêng cho {{product_name}}, camera tiến chậm cận cảnh chi tiết sản phẩm, khóa sản phẩm không bị biến dạng]"""
    },
    {
        "id": "sys_prompt_veo3_scene1",
        "category": "veo3_scene1",
        "title": "Mẫu Prompt Veo 3 - Cảnh 1 (Hook & Giới thiệu công dụng theo sản phẩm)",
        "variables": ["character_description", "product_name", "category", "benefits", "dialogue_1"],
        "content": """[Cảnh 1 - Giới thiệu công dụng {{product_name}} ({{category}}) | 9:16, 10s, 60fps]
Nhân vật nữ Việt Nam từ ảnh tham chiếu mỉm cười tươi tắn, chỉ tay trực tiếp giới thiệu sản phẩm {{product_name}} đang đặt trên bàn trưng bày ở tiền cảnh, nhấn mạnh vào công dụng ({{benefits}}).
Chuyển động trực tiếp từ đúng khung hình ảnh tham chiếu đính kèm: giữ nguyên 100% nhân vật, bối cảnh cửa hàng ({{category}}) và đúng sản phẩm {{product_name}} trong ảnh tham chiếu (tuyệt đối không đổi màu sắc, kiểu dáng hay tự sinh ra sản phẩm khác).
Nhân vật nói tiếng Việt giọng miền Bắc tự nhiên, khẩu hình miệng khớp hoàn hảo với lời thoại trong 10 giây:
"{{dialogue_1}}"
Không chữ trên màn hình, không phụ đề, không watermark."""
    },
    {
        "id": "sys_prompt_veo3_scene2",
        "category": "veo3_scene2",
        "title": "Mẫu Prompt Veo 3 - Cảnh 2 (Cận cảnh chi tiết sản phẩm & Chốt đơn)",
        "variables": ["character_description", "product_name", "category", "highlights", "dialogue_2"],
        "content": """[Cảnh 2 - Cận cảnh chi tiết {{product_name}} & Chốt đơn | 9:16, 10s, 60fps]
Máy quay tiến chậm lấy nét cận cảnh (slow smooth push-in) làm nổi bật chi tiết sản phẩm {{product_name}} ({{highlights}}), nhân vật mỉm cười duyên dáng hướng dẫn khách đặt mua.
Tiếp tục trực tiếp từ đúng khung hình ảnh tham chiếu đính kèm: giữ nguyên 100% nhân vật, bối cảnh ({{category}}) và khóa 100% thiết kế, màu sắc, nhãn mác thật của sản phẩm {{product_name}} trong ảnh tham chiếu, không biến dạng.
Nhân vật nói tiếng Việt giọng miền Bắc truyền cảm, khẩu hình miệng khớp hoàn hảo với lời thoại trong 10 giây:
"{{dialogue_2}}"
Không chữ trên màn hình, không phụ đề, không watermark."""
    },
    {
        "id": "sys_prompt_dialogue_fix",
        "category": "dialogue_fix",
        "title": "Chỉnh sửa lời thoại chuẩn xác 42 từ tiếng Việt",
        "variables": ["current_dialogue", "product_name", "target_words"],
        "content": """Đoạn lời thoại sau hiện có số từ chưa đạt chuẩn:
"{{current_dialogue}}"

YÊU CẦU:
Hãy chỉnh sửa lại đoạn lời thoại này sao cho:
1. Có CHÍNH XÁC đúng 42 TỪ tiếng Việt (không thiếu, không thừa).
2. Giữ nguyên ý chính, phong cách cô gái xưng "em", gọi "các bác", giọng nữ miền Bắc Hà Nội tự nhiên, thân thiện.
3. Nhịp câu mượt mà, dễ phát âm, không bị vấp khi đọc nhanh trong 10 giây.
4. Trả về đúng 1 câu thoại 42 từ duy nhất kèm số đếm xác nhận."""
    },
    {
        "id": "sys_prompt_hook_gen",
        "category": "hook_gen",
        "title": "Tạo 5 Hook TikTok triệu view cho sản phẩm",
        "variables": ["product_name", "category", "target_customer"],
        "content": """Hãy tạo 5 câu hook mở đầu video TikTok Affiliate cực kỳ cuốn hút cho sản phẩm {{product_name}} thuộc ngành {{category}} nhắm tới {{target_customer}}.
Mỗi hook từ 8 đến 14 từ, gây tò mò hoặc đánh mạnh vào nỗi đau thường gặp. Trình bày ngắn gọn, sắc bén."""
    },
    {
        "id": "sys_prompt_variant_gen",
        "category": "variant_gen",
        "title": "Tạo biến thể kịch bản A/B Testing",
        "variables": ["product_name", "benefits"],
        "content": """Hãy tạo thêm các góc tiếp cận mới (Góc hài hước gần gũi, Góc chuyên gia đánh giá, Góc trải nghiệm thực tế) cho sản phẩm {{product_name}}, mỗi kịch bản tuân thủ 2 cảnh, mỗi cảnh đúng 42 từ."""
    }
]

def count_vietnamese_words(text: str) -> int:
    """
    Counts Vietnamese words in text by splitting on whitespace after normalizing.
    Punctuation attached to words is not counted separately.
    """
    if not text:
        return 0
    cleaned = re.sub(r'["\'`“”‘’«»()\[\]{}–—:;,\.!?\/\\]', ' ', text)
    words = [w.strip() for w in cleaned.split() if w.strip()]
    return len(words)

def render_prompt(template_content: str, context: Dict[str, Any]) -> str:
    """
    Replaces {{variable_name}} with values from context dictionary.
    """
    result = template_content
    for key, val in context.items():
        placeholder = f"{{{{{key}}}}}"
        str_val = str(val) if val is not None else ""
        result = result.replace(placeholder, str_val)
    return result
