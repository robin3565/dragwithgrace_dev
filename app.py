import streamlit as st
import pandas as pd
import re
import io

st.set_page_config(page_title="장바구니 파서", layout="wide")
st.title("🛒 장바구니 파서")

# ✅ 1. 사이트 선택
site = st.selectbox("🔍 데이터를 추출할 사이트를 선택하세요", ["쿠팡", "아이스크림몰"])

# ✅ 2. 텍스트 입력
text = st.text_area(
    """👇 선택한 사이트에서 복사한 텍스트를 여기에 붙여넣으세요
(Ctrl+A → Ctrl+C 하면 전체 선택 복사됩니다!)""",
    height=300
)

# 🧠 3. 쿠팡 파싱 함수 (기존 유지)
def parse_coupang(text):
    lines = [line.strip() for line in text.strip().split('\n') if line.strip()]
    products = []
    i = 0

    while i < len(lines):
        line = lines[i]
        has_next = i + 1 < len(lines)
        is_potential_product = (
            has_next and ('삭제' in lines[i+1] or '도착 보장' in lines[i+1])
            and any('원' in lines[i+offset] for offset in range(1, 8) if i+offset < len(lines))
        )

        if is_potential_product:
            name = line
            total_price = 0

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

            quantity = 1
            for offset in range(1, 10):
                if i+offset < len(lines) and re.fullmatch(r'\d+', lines[i+offset]):
                    quantity = int(lines[i+offset])
                    break

            unit_price = int(total_price / quantity) if quantity else 0

            if re.match(r'^\(\d+\s*/\s*\d+\)$', name):
                i += 1
                continue

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

            i += 7
        else:
            i += 1

    # ✅ 배송비 추출
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

# ✅ 4. 아이스크림몰 파싱 함수
def parse_icecream(text):
    lines = [line.strip() for line in text.strip().split('\n') if line.strip()]
    products = []
    i = 0

    while i < len(lines):
        line = lines[i]

        # ✅ 제품 블록 패턴 감지: 상품명 == 상품명 && 수량 && 가격 존재
        if (
            i+2 < len(lines)
            and lines[i] == lines[i+2]
            and ('단일상품' in lines[i+3] or '추가구매' in lines[i+3])
            and re.search(r'[\d,]+원', lines[i+4])
        ):
            name = line
            quantity = 1
            price = 0

            # 수량
            match_qty = re.search(r'(\d+)\s*개', lines[i+3])
            if match_qty:
                quantity = int(match_qty.group(1))

            # 가격
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

    # ✅ 배송비 추출
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


# ✅ 5. 변환 버튼
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

        if df.empty:
            st.error("❌ 추출된 데이터가 없습니다. 입력한 텍스트 및 선택한 사이트를 다시 확인해 주세요.")
        else:
            st.success(f"✅ [{site}] 데이터 변환 완료!")
            st.subheader("📋 파싱 결과")
            df.index = df.index + 1
            st.dataframe(df)

            towrite = io.BytesIO()
            with pd.ExcelWriter(towrite, engine='openpyxl') as writer:
                df.to_excel(writer, sheet_name="품목내역", index=False)
            towrite.seek(0)

            st.download_button(
                label="💾 Excel 파일 다운로드",
                data=towrite,
                file_name=f"{site}_장바구니.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
