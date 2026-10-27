import streamlit as st
import requests
import json
import re
import base64
from io import BytesIO
from ddgs import DDGS
from openai import OpenAI
from PIL import Image

st.set_page_config(
    page_title="AI 자동차 제원 검색",
    page_icon="🚗",
    layout="wide"
)

st.title("🚗 AI 자동차 제원 검색")
st.caption("자동차 사진을 올리고 모델과 세부 제원을 확인하세요.")

# --------------------------------------------------
# 제원 항목
# --------------------------------------------------
SPEC_OPTIONS = [
    "연식",
    "최고 속도",
    "변속기",
    "공차 중량",
    "전폭",
    "전장",
    "전고",
    "좌석 수",
    "차체 형태",
    "가격",
    "연비",
    "연료",
    "마력",
    "최고 출력",
    "배기량",
    "0-100km/h 가속 시간",
    "엔진 종류",
    "엔진명",
    "구동 방식",
    "최대 토크",
]

DEFAULT_SPECS = [
    "연식",
    "최고 속도",
    "변속기",
    "공차 중량",
    "전장",
    "연료",
    "마력",
    "구동 방식",
    "가격",
]

# --------------------------------------------------
# 세션 상태
# --------------------------------------------------
if "selected_specs" not in st.session_state:
    st.session_state.selected_specs = DEFAULT_SPECS.copy()

if "car_result" not in st.session_state:
    st.session_state.car_result = None

if "search_results" not in st.session_state:
    st.session_state.search_results = []

# --------------------------------------------------
# API 토큰
# --------------------------------------------------
with st.sidebar:
    st.header("⚙️ AI 설정")
    st.write("Hugging Face API 토큰을 입력하세요.")

    hf_token = st.text_input(
        "Hugging Face 토큰",
        type="password",
        help="토큰은 Hugging Face 계정에서 만들 수 있습니다."
    )

    st.caption(
        "무료 이용에는 사용량 제한이 있을 수 있습니다. "
        "토큰을 다른 사람에게 공개하지 마세요."
    )

    st.divider()
    st.markdown(
        "[Hugging Face 토큰 발급](https://huggingface.co/settings/tokens)"
    )

# --------------------------------------------------
# 사진 업로드와 제원 선택
# --------------------------------------------------
left, right = st.columns([1, 1])

with left:
    st.subheader("📷 자동차 사진")
    uploaded_file = st.file_uploader(
        "자동차 사진을 업로드하세요.",
        type=["jpg", "jpeg", "png", "webp"]
    )

    if uploaded_file:
        image = Image.open(uploaded_file).convert("RGB")
        st.image(image, caption="업로드한 자동차", use_container_width=True)

with right:
    st.subheader("📋 표시할 제원")

    selected_specs = st.multiselect(
        "확인할 항목을 선택하세요.",
        options=SPEC_OPTIONS,
        default=st.session_state.selected_specs,
        key="spec_selector"
    )

    st.session_state.selected_specs = selected_specs

    st.info(
        "엔진, 변속기, 구동 방식 등이 다른 세부 모델은 "
        "가능한 경우 각각 구분해서 표시합니다."
    )

analyze_button = st.button(
    "🔍 자동차 분석 및 제원 검색",
    type="primary",
    use_container_width=True
)

# --------------------------------------------------
# 검색 기능
# --------------------------------------------------
def search_car_information(query, max_results=6):
    """웹 검색 결과의 제목, 링크, 요약을 수집한다."""
    results = []

    try:
        with DDGS() as ddgs:
            items = ddgs.text(
                query,
                max_results=max_results
            )

            for item in items:
                results.append({
                    "title": item.get("title", ""),
                    "url": item.get("href", ""),
                    "snippet": item.get("body", "")
                })

    except Exception as exc:
        st.warning(f"웹 검색 중 문제가 발생했습니다: {exc}")

    return results


# --------------------------------------------------
# AI 분석 기능
# --------------------------------------------------
def analyze_car(image, token, specs, search_results):
    """이미지와 웹 검색 결과를 이용해 자동차 정보를 분석한다."""

    client = OpenAI(
        base_url="https://router.huggingface.co/v1",
        api_key=token
    )

    buffer = BytesIO()
    image.save(buffer, format="JPEG", quality=90)

    encoded_image = base64.b64encode(
        buffer.getvalue()
    ).decode("utf-8")

    image_data_url = f"data:image/jpeg;base64,{encoded_image}"

    search_text = json.dumps(
        search_results,
        ensure_ascii=False,
        indent=2
    )

    prompt = f"""
당신은 자동차 모델과 제원을 조사하는 도우미입니다.

업로드된 자동차 사진과 아래 웹 검색 결과를 이용해 자동차를 식별하세요.

[웹 검색 결과]
{search_text}

[요청 사항]
1. 브랜드와 자동차의 공식 모델명을 식별합니다.
2. 가능하면 제조 국가를 확인합니다.
3. 사진만으로 정확한 세부 트림을 구분할 수 없다면 확정하지 않습니다.
4. 세부 모델별로 엔진, 변속기, 구동 방식이 다르면 각각 구분합니다.
5. 확인할 제원 항목은 다음과 같습니다.
{json.dumps(specs, ensure_ascii=False)}
6. 검색 결과로 확인되지 않은 값은 추측하지 말고 "확인 필요"라고 표시합니다.
7. 가격은 국가, 연식, 트림에 따라 달라질 수 있으므로 기준을 설명합니다.
8. 단위가 있는 수치는 단위를 함께 표시합니다.
9. 출처 URL이 제공된 경우 해당 URL을 활용합니다.

다음 JSON 형식으로만 답변하세요.

{{
  "brand": "브랜드",
  "official_model_name": "공식 모델명",
  "country": "제조사 본사 국가 또는 확인 가능한 국가",
  "identification_confidence": "높음/보통/낮음",
  "identification_notes": "식별 근거와 한계",
  "variants": [
    {{
      "variant_name": "세부 모델 또는 트림명",
      "specs": {{
        "연식": "값 또는 확인 필요",
        "최고 속도": "값 또는 확인 필요"
      }},
      "notes": "해당 세부 모델에 대한 설명",
      "source_urls": []
    }}
  ],
  "official_model_page": "공식 모델 페이지 URL 또는 빈 문자열",
  "image_search_terms": "공식 이미지 검색에 사용할 검색어"
}}

주의:
- variants에는 확인 가능한 세부 모델을 각각 넣으세요.
- 제원은 실제 출처로 확인할 수 있는 경우에만 확정적으로 작성하세요.
- 검색 결과가 부족하면 세부 모델을 임의로 만들어내지 마세요.
- 출력은 유효한 JSON이어야 합니다.
"""

    response = client.chat.completions.create(
        model="Qwen/Qwen2.5-VL-3B-Instruct",
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": prompt
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": image_data_url
                        }
                    }
                ]
            }
        ],
        max_tokens=2500
    )

    return response.choices[0].message.content


def extract_json(text):
    """AI 응답에서 JSON 객체를 추출한다."""
    text = text.strip()

    text = re.sub(r"^```json\s*", "", text)
    text = re.sub(r"^```\s*", "", text)
    text = re.sub(r"\s*```$", "", text)

    start = text.find("{")
    end = text.rfind("}")

    if start == -1 or end == -1:
        raise ValueError("AI 응답에서 JSON 데이터를 찾을 수 없습니다.")

    return json.loads(text[start:end + 1])


# --------------------------------------------------
# 분석 실행
# --------------------------------------------------
if analyze_button:
    if not uploaded_file:
        st.error("먼저 자동차 사진을 업로드하세요.")

    elif not hf_token:
        st.error("왼쪽 설정에서 Hugging Face 토큰을 입력하세요.")

    elif not selected_specs:
        st.error("확인할 제원 항목을 하나 이상 선택하세요.")

    else:
        try:
            with st.spinner("자동차 모델을 식별하는 중입니다..."):
                image = Image.open(uploaded_file).convert("RGB")

                # 사진에 대한 1차 식별을 위해 웹 검색 결과를 준비한다.
                # 사진 속 모델명은 아직 모르므로 일반적인 자동차 식별
                # 자료를 검색한 뒤, AI가 이미지와 함께 검토한다.
                preliminary_results = search_car_information(
                    "자동차 모델 식별 제조사 공식 차량 모델 제원"
                )

                raw_result = analyze_car(
                    image,
                    hf_token,
                    selected_specs,
                    preliminary_results
                )

                result = extract_json(raw_result)

            # 식별된 모델명으로 추가 검색
            model_name = result.get(
                "official_model_name",
                ""
            )

            brand = result.get("brand", "")

            if model_name:
                with st.spinner("모델별 제원과 공식 자료를 검색하는 중입니다..."):
                    extra_results = search_car_information(
                        f"{brand} {model_name} 공식 제원 엔진 트림"
                    )

                    result["web_search_results"] = extra_results

            st.session_state.car_result = result
            st.session_state.search_results = result.get(
                "web_search_results",
                []
            )

            st.success("분석이 완료되었습니다.")

        except Exception as exc:
            message = str(exc)

            if "429" in message or "rate" in message.lower():
                st.error(
                    "AI 사용량 한도에 도달했거나 요청이 너무 많습니다. "
                    "잠시 후 다시 시도하거나 Hugging Face 사용량을 확인하세요."
                )
            elif "401" in message or "403" in message:
                st.error(
                    "인증에 실패했습니다. Hugging Face 토큰과 권한을 확인하세요."
                )
            else:
                st.error(f"분석 중 오류가 발생했습니다: {message}")


# --------------------------------------------------
# 결과 표시
# --------------------------------------------------
result = st.session_state.car_result

if result:
    st.divider()
    st.header("🚘 분석 결과")

    brand = result.get("brand", "확인 필요")
    model_name = result.get(
        "official_model_name",
        "확인 필요"
    )
    country = result.get("country", "확인 필요")

    info1, info2, info3 = st.columns(3)

    info1.metric("브랜드", brand)
    info2.metric("공식 모델명", model_name)
    info3.metric("국가", country)

    st.caption(
        "식별 신뢰도: "
        + str(result.get("identification_confidence", "확인 필요"))
    )

    notes = result.get("identification_notes", "")
    if notes:
        st.write(notes)

    # 공식 모델 페이지
    official_url = result.get("official_model_page", "")

    if official_url.startswith("https://"):
        st.markdown(f"**공식 모델 페이지:** {official_url}")

    # 세부 모델별 제원
    st.subheader("세부 모델별 제원")

    variants = result.get("variants", [])

    if not variants:
        st.info("확인된 세부 모델 정보가 없습니다.")

    for index, variant in enumerate(variants, start=1):
        variant_name = variant.get(
            "variant_name",
            f"세부 모델 {index}"
        )

        with st.expander(variant_name, expanded=(index == 1)):
            specs = variant.get("specs", {})

            rows = []

            for spec_name in st.session_state.selected_specs:
                rows.append({
                    "제원": spec_name,
                    "값": specs.get(spec_name, "확인 필요")
                })

            if rows:
                st.dataframe(
                    rows,
                    hide_index=True,
                    use_container_width=True
                )

            variant_notes = variant.get("notes", "")
            if variant_notes:
                st.write(variant_notes)

            urls = variant.get("source_urls", [])

            if urls:
                st.markdown("**관련 출처**")
                for url in urls:
                    if isinstance(url, str) and url.startswith("https://"):
                        st.markdown(f"- {url}")

    # 추가 웹 검색 결과
    search_results = st.session_state.search_results

    if search_results:
        st.subheader("🔗 추가 검색 결과")

        for item in search_results:
            title = item.get("title", "검색 결과")
            url = item.get("url", "")
            snippet = item.get("snippet", "")

            if url.startswith("https://"):
                st.markdown(f"**[{title}]({url})**")
            else:
                st.write(title)

            if snippet:
                st.caption(snippet)
