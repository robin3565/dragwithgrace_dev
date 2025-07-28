import streamlit as st
import pandas as pd
import re
import io
import numpy as np

# 페이지 설정 (제목, 넓은 레이아웃 사용)
st.set_page_config(page_title="🛒품의있는 드래그", layout="wide")

col1, col2 = st.columns([8, 1])
with col1:
    st.markdown(
    """
    <h1 style='cursor: pointer; color: charcoal;' onclick="window.location.reload()">🛒 품의있는 드래그</h1>
    """,
    unsafe_allow_html=True
)
with col2:
    st.image("img/logo.png", width=150)
    
st.markdown(
    """
    <div style='line-height: 1.8; font-size: 1rem; margin-bottom: 15px;'>
        • 장바구니 내용을 드래그(복사)+붙여넣기 하고 아래 버튼을 클릭하면, 지출품의 양식서가 엑셀로 추출됩니다.<br>
        • 현재 <strong>쿠팡</strong>, <strong>아이스크림몰</strong>, <strong>G마켓</strong>, <strong>레드포인트</strong> 사이트만 지원합니다.<br>
        • 문의사항은 <a href="mailto:yuseoni@korea.kr">yuseoni@korea.kr</a> 로 주세요.
    </div>
    """,
    unsafe_allow_html=True
)

# st.badge("장바구니 드래그(복사+붙여넣기) 한 번으로 품의 양식서 추출하기!")

# ✅ 세션 상태 초기화 (처음 실행 시)
if "text_input" not in st.session_state:
    st.session_state.text_input = ""
if "last_site" not in st.session_state:
    st.session_state.last_site = "🚀 쿠팡"

# ✅ 1. 사이트 선택
site = st.selectbox("1️⃣ 데이터를 추출할 사이트를 선택하세요.", ["🚀 쿠팡", "🍦 아이스크림몰", "✅ G마켓", "레드포인트"])

# ✅ 사이트가 바뀌었으면 text 초기화
if site != st.session_state.last_site:
    st.session_state.text_input = ""  # text_area 내용 비우기
    st.session_state.last_site = site

# ✅ 2. 텍스트 입력
text = st.text_area(
    """2️⃣ '장바구니' 페이지에서 복사한 텍스트를 여기에 붙여넣으세요/
(Ctrl+A → Ctrl+C 하면 전체 선택 복사됩니다!)""",
    height=270,
    key="text_input"
)


# 🧠 3-1. 쿠팡 텍스트 파싱 함수
def parse_coupang(text):
    lines = [line.strip() for line in text.strip().split('\n') if line.strip()]
    products = []
    i = 0

    while i < len(lines):
        line = lines[i]
        has_next = i + 1 < len(lines)

        # 쿠팡 상품 라인 감지 조건:
        # 다음 줄에 '삭제' 또는 '도착 보장' 포함 && 8줄 이내에 '원' 있는 줄이 있음
        is_potential_product = (
            has_next and ('삭제' in lines[i+1] or '도착 보장' in lines[i+1])
            and any('원' in lines[i+offset] for offset in range(1, 8) if i+offset < len(lines))
        )

        if is_potential_product:
            name = line
            total_price = 0

            # 총 가격 추출 (가격 문자열에서 가장 마지막 '원' 기준)
            for offset in range(1, 10):
                if i+offset < len(lines):
                    clean_line = lines[i+offset].replace('badge', '').replace('coupon', '')
                    matches = re.findall(r'\d{1,3}(?:,\d{3})*원', clean_line)
                    if matches:
                        price_str = matches[-1]
                        total_price = int(price_str.replace(',', '').replace('원', ''))
                        break

            if total_price == 0:
                i += 1
                continue

            # 수량 추출 (숫자 하나만 있는 줄 감지)
            quantity = 1
            for offset in range(1, 10):
                if i+offset < len(lines) and re.fullmatch(r'\d+', lines[i+offset]):
                    quantity = int(lines[i+offset])
                    break

            unit_price = int(total_price / quantity) if quantity else 0

            # (1 / 2)와 같은 묶음 상품 제외
            if re.match(r'^\(\d+\s*/\s*\d+\)$', name):
                i += 1
                continue

            # 최종 상품 정보 추가
            products.append({
                '품명': name,
                '규격': "",
                '수량': quantity,
                '단위': '개',
                '단가': unit_price,
                '금액': total_price,
                '품의상세유형': "",
                '직책급': "",
                'G2B분류번호': "",
                'G2B물품코드': "",
            })

            i += 7  # 다음 상품으로 이동
        else:
            i += 1

    # ✅ 배송비 추출 (맨 뒤에서부터 '배송비 + 3,000원' 형식 찾기)
    shipping_fee = 0
    for line in reversed(lines):
        match_fee = re.search(r'배송비\s*\+?\s*([\d,]+)원', line)
        if match_fee:
            shipping_fee = int(match_fee.group(1).replace(',', ''))
            break

    if shipping_fee > 0:
        products.append({
            '품명': "배송비",
            '규격': "",
            '수량': 1,
            '단위': "건",
            '단가': shipping_fee,
            '금액': shipping_fee,
            '품의상세유형': "",
            '직책급': "",
            'G2B분류번호': "",
            'G2B물품코드': "",
        })

    return pd.DataFrame(products)


# ✅ 3-2. 아이스크림몰 텍스트 파싱 함수
def parse_icecream(text):
    lines = [line.strip() for line in text.strip().split('\n') if line.strip()]
    products = []
    i = 0

    while i < len(lines):
        line = lines[i]

        # 제품 블록 감지 조건:
        # 줄 구조: 상품명 == 상품명 && 수량/가격 라인이 존재
        if (
            i+2 < len(lines)
            and lines[i] == lines[i+2]
            and ('단일상품' in lines[i+3] or '추가구매' in lines[i+3])
            and re.search(r'[\d,]+원', lines[i+4])
        ):
            name = line
            quantity = 1
            price = 0

            # 수량 추출 (예: "단일상품 / 1개")
            match_qty = re.search(r'(\d+)\s*개', lines[i+3])
            if match_qty:
                quantity = int(match_qty.group(1))

            # 가격 추출
            match_price = re.search(r'([\d,]+)원', lines[i+4])
            if match_price:
                price = int(match_price.group(1).replace(',', ''))

            unit_price = int(price / quantity) if quantity else 0

            products.append({
                '품명': name,
                '규격': "",
                '수량': quantity,
                '단위': '개',
                '단가': unit_price,
                '금액': price,
                '품의상세유형': "",
                '직책급': "",
                'G2B분류번호': "",
                'G2B물품코드': "",
            })

            i += 6
        else:
            i += 1

    # ✅ 배송비 추출 (예: "배송비 3,000원")
    shipping_fee = 0
    for line in reversed(lines):
        match_fee = re.search(r'배송비\s*([\d,]+)원', line)
        if match_fee:
            shipping_fee = int(match_fee.group(1).replace(',', ''))
            break

    if shipping_fee > 0:
        products.append({
            '품명': "배송비",
            '규격': "",
            '수량': 1,
            '단위': "건",
            '단가': shipping_fee,
            '금액': shipping_fee,
            '품의상세유형': "",
            '직책급': "",
            'G2B분류번호': "",
            'G2B물품코드': "",
        })

    return pd.DataFrame(products)

# ✅ 3-3. G마켓 텍스트 파싱 함수
def parse_gmarket(text: str) -> pd.DataFrame:
    lines = [line.strip() for line in text.strip().split('\n') if line.strip()]
    products = []
    i = 0
    total_delivery_price = 0

    while i < len(lines):
        if lines[i].startswith("상품명:") and i + 1 < len(lines):
            name = lines[i + 1].strip()
            quantity = 1
            total_price = 0
            discount = 0
            order_price = 0
            delivery_price = 0

            # 수량 찾기
            for j in range(i + 2, i + 10):
                if j < len(lines) and re.fullmatch(r'\d+', lines[j]):
                    quantity = int(lines[j])
                    break

            # 금액 관련 정보 파싱
            for j in range(i, min(i + 20, len(lines))):
                # 상품 금액 패턴 예시: "상품 금액 :25,000원상품 삭제"
                if "상품 금액" in lines[j]:
                    if '삭제' in lines[j]:
                        match = re.search(r'상품 금액\s*[:：]\s*([\d,]+)원', lines[j])
                        if match:
                            total_price = int(match.group(1).replace(",", ""))
                    elif j + 1 < len(lines):
                        match = re.search(r'([\d,]+)원', lines[j + 1])
                        if match:
                            total_price = int(match.group(1).replace(",", ""))

                if "할인" in lines[j]:
                    match = re.search(r'([\d,]+)원', lines[j])
                    if match:
                        discount = int(match.group(1).replace(",", ""))
                        print('discount', discount)

                if "주문금액" in lines[j]:
                    match = re.search(r'([\d,]+)원', lines[j])
                    if match:
                        order_price = int(match.group(1).replace(",", ""))

                if "배송비" in lines[j] and j + 1 < len(lines):
                    if "무료배송" in lines[j + 1]:
                        delivery_price = 0
                    else:
                        match = re.search(r'([\d,]+)원', lines[j + 1])
                        if match:
                            delivery_price = int(match.group(1).replace(',', ''))

                # if "배송비" in lines[j] and "무료배송" not in lines[j] and "이상" not in lines[j]:
                #     match = re.search(r'([\d,]+)원', lines[j])
                #     if match:
                #         delivery_price = int(match.group(1).replace(',', ''))

            final_price = order_price if discount > 0 else total_price
            unit_price = final_price // quantity if quantity else 0

            products.append({
                "품명": name,
                "규격": "",
                "수량": quantity,
                "단위": "개",
                "단가": unit_price,
                "금액": final_price,
                "품의상세유형": "",
                "직책급": "",
                "G2B분류번호": "",
                "G2B물품코드": "",
            })

            if delivery_price > 0:
                total_delivery_price += delivery_price
            i += 20
        else:
            i += 1

    if total_delivery_price > 0:
        products.append({
            "품명": "총 배송비",
            "규격": "",
            "수량": 1,
            "단위": "건",
            "단가": total_delivery_price,
            "금액": total_delivery_price,
            "품의상세유형": "",
            "직책급": "",
            "G2B분류번호": "",
            "G2B물품코드": "",
        })
    return pd.DataFrame(products)

    
# ✅ 3-4. 레드포인트 텍스트 파싱 함수
def parse_redpoint(text: str) -> pd.DataFrame:
    def is_valid_product_name(line):
        # 상품명이 아닌 단어들을 필터링
        blocked_keywords = ['무료', '조건', '이미지', '배송', '삭제', '장바구니', '쿠폰', '총 상품금액', '수량', '할인금액', '적립금']
        if any(keyword in line for keyword in blocked_keywords):
            return False
        if re.search(r'\d+원', line):  # 가격 정보 포함된 줄 제외
            return False
        if len(line.strip()) < 4:
            return False
        return True

    lines = [line.strip() for line in text.strip().split('\n') if line.strip()]
    products = []
    i = 0
    total_shipping = 0

    while i < len(lines):
        # 유효한 상품명 조건 만족
        if is_valid_product_name(lines[i]):
            name = lines[i].split('\t')[0] if '\t' in lines[i] else lines[i]
            quantity = 1
            unit_price = 0
            total_price = 0
            delivery_price = 0
            discount = 0

            # 수량과 금액 정보 탐색 (다음 10줄 안에서)
            for j in range(i+1, min(i+10, len(lines))):
                # 수량: 순수 숫자 줄
                if re.fullmatch(r'\d+', lines[j]):
                    quantity = int(lines[j])
                # 금액: 예) "4,500원"
                if re.search(r'\d{1,3}(?:,\d{3})*원', lines[j]):
                    match = re.search(r'([\d,]+)원', lines[j])
                    if match:
                        total_price = int(match.group(1).replace(',', ''))

                # 배송비: 예) "3,000원", "무료"
                if "배송" in lines[j]:
                    if '무료' in lines[j]:
                        delivery_price = 0
                    else:
                        match = re.search(r'([\d,]+)원', lines[j])
                        if match:
                            delivery_price = int(match.group(1).replace(',', ''))

            unit_price = total_price // quantity if quantity else 0
            final_price = total_price

            products.append({
                '품명': name,
                '규격': '',
                '수량': quantity,
                '단위': '개',
                '단가': unit_price,
                '금액': final_price,
                '품의상세유형': '',
                '직책급': '',
                'G2B분류번호': '',
                'G2B물품코드': ''
            })

            total_shipping += delivery_price
            i += 10  # 다음 상품으로 이동
        else:
            i += 1

    # 배송비 별도 추가
    if total_shipping > 0:
        products.append({
            '품명': '배송비',
            '규격': '',
            '수량': 1,
            '단위': '건',
            '단가': total_shipping,
            '금액': total_shipping,
            '품의상세유형': '',
            '직책급': '',
            'G2B분류번호': '',
            'G2B물품코드': ''
        })

    return pd.DataFrame(products)


# ✅ 5. 버튼 클릭 시 파싱 실행
if st.button("✨ 변환 시작"):
    if not text.strip():
        st.warning("⚠️ 텍스트를 입력해 주세요.")
    else:
        with st.spinner("🧠 데이터를 분석 중입니다..."):
            if site == "🚀 쿠팡":
                df = parse_coupang(text)
            elif site == "🍦 아이스크림몰":
                df = parse_icecream(text)
            elif site == "✅ G마켓":
                df = parse_gmarket(text)
            elif site == "레드포인트":
                df = parse_redpoint(text)
            else:
                df = pd.DataFrame()

        # ✅ 결과가 없을 경우 경고 메시지 출력
        if df.empty:
            st.error("❌ 추출된 데이터가 없습니다. 입력한 텍스트 및 선택한 사이트를 다시 확인해 주세요.")
        else:
            st.success(f"[{site}] 데이터 변환 완료!")
            st.subheader("📋 품의서 추출 결과")

            # ✅ Streamlit에서 1번부터 인덱스 보이도록
            df.index = df.index + 1
            
            # 총합 계산 (금액만)
            total_row = df[["금액"]].sum().to_dict()
            total_row.update({
                '품명': '총 합계',
                '규격': '',
                '수량': np.nan,  # <- 빈 문자열 대신 np.nan 사용
                '단위': '',
                '품의상세유형': '',
                '직책급': '',
                'G2B분류번호': '',
                'G2B물품코드': ''
            })

            # 화면 출력용 DataFrame (총합 포함)
            df_view = pd.concat([df, pd.DataFrame([total_row])], ignore_index=True)
            st.dataframe(df_view.style.format({'수량': '{:,.0f}', '단가': '{:,.0f}', '금액': '{:,.0f}'}))

            # ✅ Excel 다운로드 처리
            towrite = io.BytesIO()
            with pd.ExcelWriter(towrite, engine='openpyxl') as writer:
                df.to_excel(writer, sheet_name="품목내역", index=False)
            towrite.seek(0)

            st.download_button(
                label="💾 Excel 파일 다운로드",
                data=towrite,
                file_name=f"{site}_품의업로드양식.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )


# ✅ Footer 추가
st.markdown(
    """
    <hr style="margin-top: 3em;">
    <div style='text-align: center; font-size: 0.9em; color: gray;'>
        ⓒ 2025 전라남도교육청 미래교육과. All rights reserved. | <a href="mailto:yuseoni@korea.kr">Contact</a>
    </div>
    """,
    unsafe_allow_html=True
)