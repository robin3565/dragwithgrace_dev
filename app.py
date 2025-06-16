import streamlit as st
import pandas as pd
import re
import io


# 페이지 설정 (제목, 넓은 레이아웃 사용)
st.set_page_config(page_title="🛒품의있는 드래그", layout="wide")

col1, col2 = st.columns([8, 1])
with col1:
    st.markdown(
    """
    <h1 style='cursor: pointer; color: charcoal;' onclick="windows.location.reload()">🛒 품의있는 드래그</h1>
    """,
    unsafe_allow_html=True
)
with col2:
    st.image("img/logo.png", width=150)
    
st.markdown(
    """
    <div style='line-height: 1.8; font-size: 1rem; margin-bottom: 10px;'>
        • 장바구니 내용을 드래그(복사)+붙여넣기 하고 아래 버튼을 클릭하면, 지출품의 양식서가 엑셀로 추출됩니다.<br>
        • 현재 <strong>쿠팡</strong>, <strong>아이스크림몰</strong> 사이트만 지원합니다.<br>
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
    st.session_state.last_site = "쿠팡"

# ✅ 1. 사이트 선택
site = st.selectbox("🔍 데이터를 추출할 사이트를 선택하세요", ["쿠팡", "아이스크림몰"])

# ✅ 사이트가 바뀌었으면 text 초기화
if site != st.session_state.last_site:
    st.session_state.text_input = ""  # text_area 내용 비우기
    st.session_state.last_site = site

# ✅ 2. 텍스트 입력
text = st.text_area(
    """👇 선택한 사이트에서 복사한 텍스트를 여기에 붙여넣으세요
(Ctrl+A → Ctrl+C 하면 전체 선택 복사됩니다!)""",
    height=300,
    key="text_input"
)


# 🧠 3. 쿠팡 텍스트 파싱 함수
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


# ✅ 4. 아이스크림몰 텍스트 파싱 함수
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


# ✅ 5. 버튼 클릭 시 파싱 실행
if st.button("🚀 변환 시작"):
    if not text.strip():
        st.warning("⚠️ 텍스트를 입력해 주세요.")
    else:
        with st.spinner("🧠 데이터를 분석 중입니다..."):
            if site == "쿠팡":
                df = parse_coupang(text)
            elif site == "아이스크림몰":
                df = parse_icecream(text)
            else:
                df = pd.DataFrame()

        # ✅ 결과가 없을 경우 경고 메시지 출력
        if df.empty:
            st.error("❌ 추출된 데이터가 없습니다. 입력한 텍스트 및 선택한 사이트를 다시 확인해 주세요.")
        else:
            st.success(f"✅ [{site}] 데이터 변환 완료!")
            st.subheader("📋 품의서 추출 결과")

            # ✅ Streamlit에서 1번부터 인덱스 보이도록
            df.index = df.index + 1
            st.dataframe(df)

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
