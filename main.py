import requests
import streamlit as st
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo


# ---------------------------------------------------------
# 기본 설정
# ---------------------------------------------------------

st.set_page_config(
    page_title="어제의 박스오피스",
    page_icon="🎬",
    layout="wide",
)

API_URL = (
    "https://www.kobis.or.kr/kobisopenapi/webservice/rest/"
    "boxoffice/searchDailyBoxOfficeList.json"
)


# ---------------------------------------------------------
# 숫자로 변환하는 함수
# API에서는 숫자도 문자열로 보내므로 int로 바꿉니다.
# ---------------------------------------------------------

def to_int(value):
    """문자열로 받은 숫자를 정수로 바꿉니다."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


# ---------------------------------------------------------
# 한국 시간 기준으로 '어제' 날짜를 계산합니다.
# 배포 서버의 시간이 한국 시간이 아니어도 정상적으로 동작합니다.
# ---------------------------------------------------------

def get_yesterday_kst():
    """한국 시간 기준 어제 날짜를 YYYYMMDD 형태로 반환합니다."""
    now_kst = datetime.now(ZoneInfo("Asia/Seoul"))
    yesterday = now_kst - timedelta(days=1)
    return yesterday.strftime("%Y%m%d")


# ---------------------------------------------------------
# KOBIS API를 호출합니다.
#
# st.cache_data를 사용해서 같은 날짜를 다시 조회하면
# 약 1시간 동안 저장해 둔 결과를 재사용합니다.
# ---------------------------------------------------------

@st.cache_data(ttl=3600, show_spinner=False)
def get_boxoffice(target_dt):
    """KOBIS 일별 박스오피스 데이터를 가져옵니다."""

    # Streamlit Cloud Secrets에서 인증키를 가져옵니다.
    # 코드에 실제 인증키를 직접 적지 않습니다.
    try:
        api_key = st.secrets["KOBIS_KEY"]
    except KeyError:
        return {
            "success": False,
            "message": (
                "KOBIS_KEY를 찾을 수 없습니다. "
                "Streamlit Cloud의 앱 Settings → Secrets에 "
                "KOBIS_KEY를 등록했는지 확인하세요."
            ),
            "movies": [],
        }

    params = {
        "key": api_key,
        "targetDt": target_dt,
    }

    try:
        response = requests.get(
            API_URL,
            params=params,
            timeout=10,
        )

        # HTTP 오류가 있으면 예외를 발생시킵니다.
        response.raise_for_status()

        data = response.json()

    except requests.exceptions.RequestException as e:
        return {
            "success": False,
            "message": (
                "KOBIS API 요청에 실패했습니다.\n\n"
                f"네트워크 연결이나 KOBIS API 상태를 확인하세요.\n"
                f"오류 내용: {e}"
            ),
            "movies": [],
        }

    except ValueError:
        return {
            "success": False,
            "message": (
                "KOBIS API의 응답을 JSON으로 읽지 못했습니다. "
                "잠시 후 다시 시도하거나 KOBIS API 상태를 확인하세요."
            ),
            "movies": [],
        }

    # -----------------------------------------------------
    # 인증키가 잘못된 경우 HTTP 상태코드는 200이지만
    # 응답 안에 faultInfo가 들어옵니다.
    # -----------------------------------------------------

    if "faultInfo" in data:
        fault_info = data["faultInfo"]

        fault_code = fault_info.get("faultCode", "")
        fault_string = fault_info.get("faultString", "")

        return {
            "success": False,
            "message": (
                "KOBIS API에서 오류를 반환했습니다.\n\n"
                f"오류 코드: {fault_code}\n"
                f"오류 내용: {fault_string}\n\n"
                "특히 KOBIS_KEY가 정확한지 확인하세요. "
                "Streamlit Cloud Secrets의 키 이름이 "
                "정확히 KOBIS_KEY인지도 확인하세요."
            ),
            "movies": [],
        }

    # -----------------------------------------------------
    # 정상적인 박스오피스 결과를 가져옵니다.
    # -----------------------------------------------------

    boxoffice_result = data.get("boxOfficeResult")

    if not boxoffice_result:
        return {
            "success": False,
            "message": (
                "KOBIS 응답에 boxOfficeResult가 없습니다. "
                "조회 날짜와 KOBIS API 응답을 확인하세요."
            ),
            "movies": [],
        }

    movie_list = boxoffice_result.get("dailyBoxOfficeList", [])

    # 영화 목록이 비어 있으면 안내 메시지를 보여줍니다.
    if not movie_list:
        return {
            "success": False,
            "message": (
                f"{target_dt} 날짜의 박스오피스 영화 목록이 비어 있습니다.\n\n"
                "해당 날짜에 집계된 데이터가 아직 없는지, "
                "조회 날짜가 올바른지, KOBIS API가 정상적으로 "
                "응답하고 있는지 확인하세요."
            ),
            "movies": [],
        }

    # -----------------------------------------------------
    # API에서 받은 문자열 숫자를 실제 정수로 변환합니다.
    # -----------------------------------------------------

    movies = []

    for movie in movie_list:
        movies.append(
            {
                "순위": to_int(movie.get("rank")),
                "영화명": movie.get("movieNm", ""),
                "개봉일": movie.get("openDt", ""),
                "관객수": to_int(movie.get("audiCnt")),
                "누적관객": to_int(movie.get("audiAcc")),
                "스크린수": to_int(movie.get("scrnCnt")),
            }
        )

    return {
        "success": True,
        "message": "",
        "movies": movies,
    }


# ---------------------------------------------------------
# 화면 제목
# ---------------------------------------------------------

st.title("🎬 어제의 박스오피스")

target_dt = get_yesterday_kst()

# 보기 편하게 YYYY-MM-DD 형식도 만들어 줍니다.
display_date = datetime.strptime(target_dt, "%Y%m%d").strftime("%Y-%m-%d")

st.caption(
    f"한국 시간 기준 {display_date}의 KOBIS 일별 박스오피스입니다."
)


# ---------------------------------------------------------
# API 호출
# 같은 날짜라면 최대 1시간 동안 캐시된 결과를 사용합니다.
# ---------------------------------------------------------

with st.spinner("박스오피스 데이터를 불러오는 중입니다..."):
    result = get_boxoffice(target_dt)


# ---------------------------------------------------------
# API 오류 또는 데이터 없음 처리
# 빈 화면 대신 확인할 사항을 안내합니다.
# ---------------------------------------------------------

if not result["success"]:
    st.error(result["message"])

    st.info(
        """
        확인할 사항

        1. Streamlit Cloud → 앱 Settings → Secrets에
           `KOBIS_KEY`가 등록되어 있는지 확인하세요.

        2. KOBIS 인증키가 유효한지 확인하세요.

        3. KOBIS API 서버가 정상적으로 응답하는지 확인하세요.

        4. 조회 날짜에 실제 일별 박스오피스 데이터가
           집계되어 있는지 확인하세요.
        """
    )

    st.stop()


movies = result["movies"]

# 혹시 모를 예외적인 빈 목록도 한 번 더 확인합니다.
if not movies:
    st.warning(
        "박스오피스 영화 목록이 없습니다. "
        "KOBIS에서 해당 날짜의 데이터가 집계되었는지 확인하세요."
    )
    st.stop()


# ---------------------------------------------------------
# 1위 영화 찾기
# ---------------------------------------------------------

movies = sorted(movies, key=lambda x: x["순위"])

first_movie = movies[0]


# ---------------------------------------------------------
# 1위 영화의 주요 지표 3개를 크게 표시합니다.
# ---------------------------------------------------------

st.subheader(f"🥇 1위 — {first_movie['영화명']}")

col1, col2, col3 = st.columns(3)

with col1:
    st.metric(
        "관객수",
        f"{first_movie['관객수']:,}명",
    )

with col2:
    st.metric(
        "누적관객",
        f"{first_movie['누적관객']:,}명",
    )

with col3:
    st.metric(
        "스크린수",
        f"{first_movie['스크린수']:,}개",
    )


st.divider()


# ---------------------------------------------------------
# 전체 박스오피스 표
# ---------------------------------------------------------

st.subheader(f"📋 {display_date} 박스오피스")

table_data = [
    {
        "순위": movie["순위"],
        "영화명": movie["영화명"],
        "개봉일": movie["개봉일"],
        "관객수": movie["관객수"],
        "누적관객": movie["누적관객"],
        "스크린수": movie["스크린수"],
    }
    for movie in movies
]

st.dataframe(
    table_data,
    use_container_width=True,
    hide_index=True,
    column_config={
        "순위": st.column_config.NumberColumn(
            "순위",
            format="%d",
        ),
        "관객수": st.column_config.NumberColumn(
            "관객수",
            format="%d",
        ),
        "누적관객": st.column_config.NumberColumn(
            "누적관객",
            format="%d",
        ),
        "스크린수": st.column_config.NumberColumn(
            "스크린수",
            format="%d",
        ),
    },
)


# ---------------------------------------------------------
# 관객수 상위 5편 막대그래프
# ---------------------------------------------------------

st.subheader("📊 관객수 상위 5편")

top5 = sorted(
    movies,
    key=lambda x: x["관객수"],
    reverse=True,
)[:5]

# Streamlit의 bar_chart에 넣을 수 있는 형태로 만듭니다.
chart_data = {
    movie["영화명"]: movie["관객수"]
    for movie in top5
}

st.bar_chart(
    chart_data,
    horizontal=True,
)

st.caption(
    "※ 관객수는 해당 날짜의 일일 관객수입니다. "
    "데이터 출처: 영화진흥위원회(KOBIS)"
)
