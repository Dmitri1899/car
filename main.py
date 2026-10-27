import io
import json
import re
from urllib.parse import urlparse

import streamlit as st
from PIL import Image
from google import genai
from google.genai import types

st.set_page_config(
    page_title="자동차 렌즈 | 사진으로 차 찾기",
    page_icon="🚘",
    layout="wide",
)

st.markdown("""
<style>
    .block-container {max-width: 1150px; padding-top: 2rem; padding-bottom: 3rem;}
    .hero {padding: 1.3rem 1.5rem; border-radius: 18px; background: linear-gradient(120deg,#101827,#263c59); color: white; margin-bottom: 1.2rem;}
    .hero h1 {color:white; margin-bottom:.25rem;}
    .muted {color:#667085; font-size:.92rem;}
    div[data-testid="stMetric"] {border:1px solid #e6eaf0; padding:14px; border-radius:12px;}
</style>
""", unsafe_allow_html=True)

CATEGORIES = {
    "제작 연도": "출시 연도 및 해당 차량의 모델 연식",
    "최고 속도": "최고 속도(km/h)",
    "변속기 종류": "변속기 유형과 단수(예: 8단 자동, 6단 수동, CVT)",
    "무게": "공차중량(kg), 가능하면 트림별 범위",
    "폭": "전폭(mm), 사이드미러 포함 여부를 구분",
    "길이": "전장(mm)",
    "인승": "좌석 수/탑승 인원",
    "자동차 형식": "차체 유형(세단, 해치백, SUV, 쿠페, 왜건 등)",
    "가격": "출시 당시 또는 현재 신차 가격, 통화와 국가 및 기준 연도 명시",
    "연비": "연비(km/L) 또는 전기차 전비(kWh/100km 또는 km/kWh), 측정 기준 명시",
    "연료": "가솔린, 경유, 전기, 하이브리드, 플러그인 하이브리드, LPG 등",
}

DEFAULT_CATEGORIES = ["제작 연도", "최고 속도", "변속기 종류", "무게", "폭", "길이", "인승", "자동차 형식", "가격", "연비", "연료"]

if "selected_categories" not in st.session_state:
    st.session_state.selected_categories = DEFAULT_CATEGORIES.copy()
if "car_result" not in st.session_state:
    st.session_state.car_result = None
if "last_upload_signature" not in st.session_state:
    st.session_state.last_upload_signature = None

def get_api_key():
    try:
        return st.secrets["GEMINI_API_KEY"]
    except Exception:
        return ""

def strip_code_fences(text):
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return text

def extract_json(text):
    text = strip_code_fences(text)
    try:
        return json.loads(text)
    except Exception:
        start, end = text.find("{"), text.rfind("}")
        if start >= 0 and end > start:
            return json.loads(text[start:end + 1])
        raise ValueError("AI 응답에서 JSON을 읽지 못했습니다.")

def host_of(url):
    try:
        return urlparse(url).netloc.replace("www.", "")
    except Exception:
        return ""

def identify_car_and_research(image_bytes, mime_type, categories, api_key):
    client = genai.Client(api_key=api_key)
    category_instructions = "\n".join(
        f'- "{name}": {CATEGORIES[name]}' for name in categories
    )
    prompt = f"""
당신은 자동차 사진 식별 및 웹 조사 도우미다. 첨부 사진 속 차량을 가능한 한 정확히 식별하고 Google Search로 확인하라.
사진만으로 세부 트림이나 연식을 확정할 수 없으면 추정이라고 분명히 표시하고, 확인할 수 없는 값은 "확인 불가"로 둔다.
브랜드 국가(country)는 브랜드 본사가 시작된 국가를 한국어로 적는다.
공식 모델명은 제조사가 사용하는 이름을 우선한다.
공식 모델 사진은 제조사 공식 웹사이트의 모델 페이지나 미디어 페이지를 우선해서 찾는다. 공식 이미지의 직접 URL을 확실히 찾지 못하면 image_url은 빈 문자열로 둔다. 이미지 URL을 지어내지 말라.
가격은 국가, 통화, 트림, 연식이 다르면 기준을 밝혀라. 제원은 가능하면 제조사 공식 자료를 우선하라.
선택한 카테고리만 상세 조사하라. 나머지 카테고리 정보는 만들지 말라.

사용자가 선택한 카테고리:
{category_instructions}

JSON 객체만 반환하라. 마크다운 코드 블록이나 JSON 바깥 설명은 쓰지 말라.
반환 스키마:
{{
  "brand": "브랜드",
  "brand_country": "브랜드 국가",
  "official_model_name": "공식 모델명",
  "model_year_or_generation": "확인된 연식/세대 또는 불확실성",
  "confidence": "높음/보통/낮음",
  "identification_note": "식별 근거와 사진만으로 구분하기 어려운 점",
  "official_model_page": "제조사 공식 모델 페이지 URL 또는 빈 문자열",
  "official_image_url": "공식 이미지 직접 URL 또는 빈 문자열",
  "specifications": [
    {{"category": "선택한 카테고리 이름", "value": "확인된 값과 단위", "basis": "연식/트림/시장/측정 기준 또는 불확실성", "source_title": "출처 제목", "source_url": "출처 URL"}}
  ],
  "sources": [
    {{"title": "출처 제목", "url": "출처 URL", "why_relevant": "이 출처가 확인하는 내용"}}
  ]
}}
specifications에는 아래 선택 목록의 각 항목을 한 번씩만 넣어라:
{", ".join(categories)}
가능한 경우 출처 URL을 각 제원 항목에 연결하라. 제조사 공식 자료와 신뢰도 높은 자동차 제원 자료를 우선하라.
"""
    image_part = types.Part.from_bytes(data=image_bytes, mime_type=mime_type)
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=[prompt, image_part],
        config=types.GenerateContentConfig(
            tools=[types.Tool(google_search=types.GoogleSearch())],
            temperature=0.2,
        ),
    )
    result = extract_json(response.text or "")
    # Keep only requested categories, even if the model returns extras.
    specs = result.get("specifications", [])
    result["specifications"] = [
        item for item in specs
        if isinstance(item, dict) and item.get("category") in categories
    ]
    return result

st.markdown("""
<div class="hero">
  <h1>🚘 자동차 렌즈</h1>
  <div>사진 한 장으로 차종을 식별하고, 필요한 제원만 골라 확인하세요.</div>
</div>
""", unsafe_allow_html=True)

with st.sidebar:
    st.header("🔎 검색 설정")
    st.caption("선택한 카테고리는 이 브라우저 세션의 다음 검색에도 유지됩니다.")
    selected = st.multiselect(
        "검색할 정보 카테고리",
        options=list(CATEGORIES.keys()),
        default=st.session_state.selected_categories,
        help="여러 항목을 동시에 선택할 수 있어요.",
    )
    st.session_state.selected_categories = selected
    st.divider()
    st.markdown("**검색할 수 있는 정보**")
    for name in CATEGORIES:
        st.caption(f"• {name}")

left, right = st.columns([1, 1.15], gap="large")
with left:
    st.subheader("1. 자동차 사진 업로드")
    uploaded = st.file_uploader(
        "자동차가 잘 보이는 사진을 선택하세요.",
        type=["jpg", "jpeg", "png", "webp"],
        help="차량 앞면 또는 뒷면의 로고와 디자인이 선명하면 식별에 도움이 됩니다.",
    )
    if uploaded:
        raw_bytes = uploaded.getvalue()
        try:
            image = Image.open(io.BytesIO(raw_bytes)).convert("RGB")
            st.image(image, caption="업로드한 사진", use_container_width=True)
        except Exception:
            st.error("이미지를 읽을 수 없습니다. JPG 또는 PNG 파일을 사용해 주세요.")
            raw_bytes = None
    else:
        raw_bytes = None
        st.info("사진을 업로드하면 분석을 시작할 수 있습니다.")

    run_search = st.button("🔍 자동차 식별 및 정보 검색", type="primary", use_container_width=True)

with right:
    st.subheader("2. 검색 결과")
    if run_search:
        if not raw_bytes:
            st.warning("먼저 자동차 사진을 업로드해 주세요.")
        elif not selected:
            st.warning("검색할 카테고리를 하나 이상 선택해 주세요.")
        else:
            api_key = get_api_key()
            if not api_key:
                st.error("Gemini API 키가 설정되지 않았습니다. 아래 배포 안내의 Secrets 설정을 먼저 완료해 주세요.")
            else:
                mime_type = uploaded.type or "image/jpeg"
                with st.spinner("사진을 분석하고 웹에서 정보를 확인하고 있습니다..."):
                    try:
                        st.session_state.car_result = identify_car_and_research(
                            raw_bytes, mime_type, selected, api_key
                        )
                        st.session_state.last_upload_signature = uploaded.name
                    except Exception as exc:
                        st.error(f"검색 중 문제가 발생했습니다: {exc}")
                        st.caption("API 키, 인터넷 연결, API 사용량 한도를 확인해 주세요.")

    result = st.session_state.car_result
    if result:
        brand = result.get("brand", "확인 불가")
        model = result.get("official_model_name", "확인 불가")
        country = result.get("brand_country", "확인 불가")
        st.markdown(f"### {brand} {model}")
        c1, c2 = st.columns(2)
        c1.metric("브랜드", brand or "확인 불가")
        c2.metric("브랜드 국가", country or "확인 불가")
        st.write(f"**공식 모델명:** {model or '확인 불가'}")
        st.write(f"**식별 신뢰도:** {result.get('confidence', '미표시')}")
        if result.get("model_year_or_generation"):
            st.write(f"**연식/세대 참고:** {result['model_year_or_generation']}")
        if result.get("identification_note"):
            st.info(result["identification_note"])

        official_image = result.get("official_image_url", "")
        official_page = result.get("official_model_page", "")
        if official_image:
            st.image(official_image, caption="검색된 공식 모델 이미지", use_container_width=True)
        elif official_page:
            st.info("공식 모델 사진의 직접 주소를 확인하지 못했습니다. 제조사 공식 모델 페이지에서 사진을 확인해 주세요.")
        if official_page:
            st.link_button("제조사 공식 모델 페이지 열기", official_page)

        st.markdown("#### 선택한 카테고리의 정보")
        specs = result.get("specifications", [])
        if specs:
            for spec in specs:
                with st.container(border=True):
                    st.markdown(f"**{spec.get('category', '항목')}**")
                    st.write(spec.get("value", "확인 불가"))
                    if spec.get("basis"):
                        st.caption(spec["basis"])
                    if spec.get("source_url"):
                        st.markdown(f"출처: [{spec.get('source_title') or host_of(spec['source_url'])}]({spec['source_url']})")
        else:
            st.warning("선택한 항목의 확인 가능한 정보가 반환되지 않았습니다. 다른 카테고리를 선택하거나 사진을 바꿔 다시 검색해 보세요.")

        sources = result.get("sources", [])
        if sources:
            with st.expander("전체 검색 출처 보기"):
                for source in sources:
                    url = source.get("url", "")
                    if url:
                        st.markdown(f"- [{source.get('title') or host_of(url)}]({url})")
                        if source.get("why_relevant"):
                            st.caption(source["why_relevant"])

        st.caption("참고: 사진만으로 정확한 연식·트림을 확정하기 어려울 수 있습니다. 중요한 구매·정비 결정 전에는 제조사 자료로 다시 확인하세요.")
    else:
        st.markdown("""
        <div style="padding:1.5rem;border:1px dashed #cbd5e1;border-radius:16px;color:#667085;">
        검색을 실행하면 이곳에 공식 모델명, 브랜드 국가, 공식 모델 사진 및 선택한 제원이 표시됩니다.
        </div>
        """, unsafe_allow_html=True)

st.divider()
with st.expander("⚙️ Streamlit Cloud 배포 방법"):
    st.markdown("""
1. GitHub 저장소에 `main.py`와 `requirements.txt`를 올립니다.
2. [Google AI Studio](https://aistudio.google.com/)에서 Gemini API 키를 발급합니다.
3. Streamlit Community Cloud에서 앱을 배포합니다.
4. 앱의 **Settings → Secrets**에 아래 내용을 입력합니다.

```toml
GEMINI_API_KEY = "여기에_발급받은_API_키"
```

5. 앱의 메인 파일 경로를 `main.py`로 지정합니다.

API 키를 코드에 직접 적거나 GitHub에 올리지 마세요. Gemini API의 사용량 및 요금 정책은 Google AI 공식 안내를 확인하세요.
""")
st.caption("이 앱은 Gemini의 이미지 분석과 Google 검색 기반 답변을 사용합니다. 검색 결과 및 이미지 URL이 항상 제공되거나 완벽히 정확한 것은 아닙니다.")
