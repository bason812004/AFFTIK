import re
from typing import Dict, Any, List

DEFAULT_SYSTEM_PROMPTS = [
    {
        "id": "sys_prompt_char_gen",
        "category": "character_gen",
        "title": "Tạo ảnh nhân vật thương mại đứng cùng sản phẩm (Chuẩn cửa hàng / Tổng kho xưởng 9:16)",
        "variables": ["product_name", "category", "description", "benefits", "target_customer"],
        "content": """Tạo ảnh quảng cáo sản phẩm siêu chân thực 8K, tỷ lệ dọc 9:16, phong cách chụp ảnh thương mại cao cấp, sang trọng, chuyên nghiệp, giống ảnh chụp thực tế bằng máy ảnh full-frame chuyên nghiệp với ống kính 50mm.

## 1. BỐI CẢNH CỬA HÀNG HOẶC TỔNG KHO XƯỞNG PHÙ HỢP VỚI SẢN PHẨM ({{category}})

Dựa hoàn toàn vào hình ảnh sản phẩm tham chiếu (Tên sản phẩm: {{product_name}} - Ngành hàng: {{category}} - Công dụng: {{benefits}}) để thiết kế một cửa hàng/showroom trưng bày hoặc tổng kho xưởng xuất nhập hàng hiện đại, sạch sẽ, quy mô lớn phù hợp với chính sản phẩm đó.
- Nếu bối cảnh là tổng kho xưởng: Phía sau là các dãy kệ chứa hàng pallet lớn xếp hàng hóa ngăn nắp, quy củ, ánh sáng sáng rõ, thể hiện nguồn hàng xuất xưởng tận gốc không qua trung gian, mang lại cảm giác giá kho xưởng rẻ nhất thị trường.
- Nếu bối cảnh là cửa hàng/showroom: Thiết kế hiện đại, cao cấp, sạch sẽ, rộng rãi và chuyên nghiệp. Màu sắc nội thất, vật liệu trang trí, quầy trưng bày, kệ sản phẩm hài hòa với sản phẩm.

Bố trí khu vực trưng bày sản phẩm nổi bật ở tiền cảnh trên bàn hoặc bục kiểm hàng. Phía sau là các kiện hàng hoặc sản phẩm phụ tạo không gian chân thực, không được lấn át sản phẩm chính. Không tự ý thêm mặt hàng không liên quan.

## 2. KHÓA SẢN PHẨM – BẮT BUỘC GIỮ NGUYÊN 100%

Sử dụng chính xác sản phẩm trong hình ảnh tham chiếu (Tên sản phẩm: {{product_name}}). Giữ nguyên tuyệt đối hình dáng, kích thước, tỷ lệ, màu sắc, chất liệu, cấu trúc, thiết kế, logo, chữ viết và toàn bộ chi tiết gốc.
Tuyệt đối không thiết kế lại, không thay đổi màu sắc, không bóp méo, không kéo giãn, không làm biến dạng, không thêm hoặc xóa bất kỳ chi tiết nào trên sản phẩm.
Đặt sản phẩm trên một bàn trưng bày hoặc bục kiểm hàng ở tiền cảnh, gần máy ảnh, chiếm vị trí nổi bật, nhìn thấy đầy đủ từ trên xuống dưới và từ trái sang phải, không bị cắt mất bất kỳ phần nào.

## 3. NGƯỜI MẪU / ĐẠI DIỆN THƯƠNG HIỆU & KHO XƯỞNG

Một người mẫu (nữ hoặc nam) Việt Nam 20-25 tuổi, gương mặt sáng sủa, thanh tú, đôi mắt sáng có thần, nụ cười thân thiện, làn da tự nhiên và mái tóc chỉn chu.
Người mẫu mặc trang phục đại diện thương hiệu hoặc đồng phục nhân viên tổng kho xưởng hiện đại (áo thun polo thanh lịch, trang phục gọn gàng năng động), màu sắc hài hòa với không gian và sản phẩm.
Người mẫu đứng sát bên cạnh sản phẩm ở vị trí gần máy ảnh, một tay chỉ hoặc mở lòng bàn tay hướng về sản phẩm giới thiệu với phong thái hào sảng, tự tin như đang livestream giới thiệu nguồn hàng giá xuất xưởng rẻ tận gốc. Ánh mắt nhìn thẳng vào ống kính máy ảnh giao tiếp chân thực với người xem.

## 4. BỐ CỤC VÀ KHOẢNG CÁCH MÁY ẢNH

Khung hình dọc 9:16, góc máy chính diện, bố cục quảng cáo thương mại chuyên nghiệp.
Đưa sản phẩm và người mẫu lại gần máy ảnh hơn, tạo cảm giác gần gũi và nổi bật. Sản phẩm chiếm phần lớn tiền cảnh nhưng vẫn giữ nguyên tỷ lệ thực tế.
Người mẫu xuất hiện ở góc chụp từ thắt lưng trở lên (medium shot) hoặc gần hơn (medium close-up), thấy rõ biểu cảm gương mặt tươi tắn và sự tương tác tự nhiên với sản phẩm.

## 5. ÁNH SÁNG, MÀU SẮC VÀ ĐỘ NÉT 8K

Hệ thống ánh sáng studio thương mại chuyên nghiệp, ánh sáng ấm áp, tự nhiên, rõ ràng từng chi tiết sản phẩm và khuôn mặt người mẫu.
Chất lượng ảnh siêu cao 8K, độ nét cực cao, rõ từng chi tiết nhỏ nhất trên sản phẩm (chữ in, logo, chất liệu bề mặt).
Không có ngón tay thừa/thiếu, không biến dạng cơ thể. Bắt buộc là ảnh chụp thực tế (photorealistic photography), không sử dụng phong cách hoạt hình 3D."""
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
- ĐẶC BIỆT CÓ GÓC KHO XƯỞNG GIÁ RẺ: Nhân vật đứng tại tổng kho xưởng, nói hào sảng về nguồn hàng xuất trực tiếp từ kho xưởng tận gốc không qua trung gian nên giá rẻ bất ngờ, xả kho ưu đãi sập sàn. Cảnh 2 có chốt đơn khéo léo ở giỏ hàng góc trái màn hình nhận freeship.
- Prompt tạo video Cảnh 1 và Cảnh 2 phải mô tả cụ thể cử chỉ nhân vật tương tác với đúng các bộ phận/chi tiết của {{product_name}} và góc máy lấy nét cận cảnh đúng đặc điểm của {{product_name}} tại Cảnh 2 (khóa chặt 100% sản phẩm trong ảnh tham chiếu không bị biến dạng).

ĐỊNH DẠNG ĐẦU RA BẮT BUỘC:

### PHƯƠNG ÁN A: [Góc Kho Xưởng Giá Rẻ Tận Gốc - {{product_name}}]
**Ý tưởng và hook:** [Quay trực tiếp tại tổng kho xưởng, xả hàng giá xưởng rẻ tận gốc không qua trung gian]

**CẢNH 1**
- Lời thoại: [Tối thiểu 42 từ tiếng Việt (42-50 từ), trọn câu đọc hết trong 10s, giới thiệu giá kho xưởng rẻ & công dụng]
- Bộ đếm: [Số từ] từ
- Prompt Veo 3: [Prompt Veo 3 chi tiết bằng tiếng Việt riêng cho {{product_name}}, nhân vật đứng tại kho xưởng giới thiệu giá xưởng & công dụng, khóa 100% ảnh tham chiếu]

**CẢNH 2**
- Lời thoại: [Tối thiểu 42 từ tiếng Việt (42-50 từ), trọn câu đọc hết trong 10s, cận cảnh chất lượng và giục bấm giỏ hàng góc trái nhận giá xuất xưởng]
- Bộ đếm: [Số từ] từ
- Prompt Veo 3: [Prompt Veo 3 chi tiết bằng tiếng Việt riêng cho {{product_name}}, camera tiến chậm cận cảnh chi tiết sản phẩm, khóa sản phẩm không bị biến dạng]"""
    },
    {
        "id": "sys_prompt_veo3_scene1",
        "category": "veo3_scene1",
        "title": "Mẫu Prompt Veo 3 - Cảnh 1 (Hook Giá Kho Xưởng & Giới thiệu công dụng theo sản phẩm)",
        "variables": ["character_description", "product_name", "category", "benefits", "dialogue_1"],
        "content": """[Cảnh 1 - Giá kho xưởng rẻ & Giới thiệu công dụng {{product_name}} ({{category}}) | 9:16, 10s, 60fps]
Nhân vật Việt Nam từ ảnh tham chiếu mỉm cười tươi tắn, tự tin đứng tại bối cảnh tổng kho xưởng / showroom trưng bày với các kệ hàng hóa quy mô lớn phía sau, chỉ tay trực tiếp giới thiệu sản phẩm {{product_name}} đang đặt trên bàn kiểm hàng ở tiền cảnh, nói về giá xuất xưởng rẻ tận gốc không qua trung gian và công dụng vượt trội ({{benefits}}).
Chuyển động trực tiếp từ đúng khung hình ảnh tham chiếu đính kèm: giữ nguyên 100% nhân vật, bối cảnh tổng kho xưởng ({{category}}) và đúng sản phẩm {{product_name}} trong ảnh tham chiếu (tuyệt đối không đổi màu sắc, kiểu dáng hay tự sinh ra sản phẩm khác).
Nhân vật nói tiếng Việt giọng miền Bắc tự nhiên, khẩu hình miệng khớp hoàn hảo với lời thoại trong 10 giây:
"{{dialogue_1}}"
Không chữ trên màn hình, không phụ đề, không watermark."""
    },
    {
        "id": "sys_prompt_veo3_scene2",
        "category": "veo3_scene2",
        "title": "Mẫu Prompt Veo 3 - Cảnh 2 (Cận cảnh chi tiết sản phẩm & Chốt đơn giá xuất xưởng)",
        "variables": ["character_description", "product_name", "category", "highlights", "dialogue_2"],
        "content": """[Cảnh 2 - Cận cảnh chi tiết {{product_name}} & Chốt đơn giá xuất xưởng | 9:16, 10s, 60fps]
Máy quay tiến chậm lấy nét cận cảnh (slow smooth push-in) làm nổi bật chi tiết chất liệu chuẩn xưởng của {{product_name}} ({{highlights}}), nhân vật mỉm cười duyên dáng, chỉ vào sản phẩm rồi chỉ xuống giỏ hàng góc trái màn hình kêu gọi đặt mua nhận giá ưu đãi xuất xưởng kèm freeship tận nhà.
Tiếp tục trực tiếp từ đúng khung hình ảnh tham chiếu đính kèm: giữ nguyên 100% nhân vật, bối cảnh ({{category}}) và khóa 100% thiết kế, màu sắc, nhãn mác thật của sản phẩm {{product_name}} trong ảnh tham chiếu, không biến dạng.
Nhân vật nói tiếng Việt giọng miền Bắc truyền cảm, khẩu hình miệng khớp hoàn hảo với lời thoại trong 10 giây:
"{{dialogue_2}}"
Không chữ trên màn hình, không phụ đề, không watermark."""
    },
    {
        "id": "sys_prompt_warehouse_variant",
        "category": "warehouse_variant",
        "title": "Mẫu Nhân Bản Video - Bối cảnh Kho Xưởng Giá Rẻ Tận Gốc",
        "variables": ["product_name", "category", "benefits", "highlights", "price", "offer"],
        "content": """[Kịch bản Nhân bản Video Kho Xưởng - {{product_name}}]
Nhân vật quay trực tiếp tại tổng kho xưởng xuất nhập hàng, cầm/chỉ vào {{product_name}}, khẳng định hàng chính hãng xuất thẳng từ kho xưởng không qua trung gian, bao giá rẻ tận gốc, chất lượng chuẩn xưởng và kêu gọi chốt đơn tại giỏ hàng góc trái."""
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
