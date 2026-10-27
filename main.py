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
