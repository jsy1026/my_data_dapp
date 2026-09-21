import requests
import streamlit as st
from datetime import datetime, timedelta, date
from zoneinfo import ZoneInfo


# ---------------------------------------------------------
# 기본 설정
# ---------------------------------------------------------

st.set_page_config(
    page_title="박스오피스",
    page_icon="🎬",
    layout="wide",
)

API_URL = (
    "https://www.kobis.or.kr/kobisopenapi/webservice/rest/"
    "boxoffice/searchDailyBoxOfficeList.json"
)


# ---------------------------------------------------------
# 숫자로 변환하는 함수
# KOBIS API에서는 숫자도 문자열로 보내므로 정수로 바꿉니다.
# ---------------------------------------------------------

def to_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


# ---------------------------------------------------------
# 한국 시간 기준으로 오늘과 어제 날짜를 구합니다.
# 서버가 한국 시간이 아니어도 정확하게 동작합니다.
# ---------------------------------------------------------

def get_kst_dates():
    """한국 시간 기준 오늘과 어제 날짜를 반환합니다."""
    now_kst = datetime.now(ZoneInfo("Asia/Seoul"))

    today = now_kst.date()
    yesterday = today - timedelta(days=1)

    return today, yesterday


# ---------------------------------------------------------
# KOBIS API 호출
#
# 같은 날짜를 다시 조회하면 1시간 동안 캐시된 결과를
# 사용하므로 API를 불필요하게 반복 호출하지 않습니다.
# ---------------------------------------------------------

@st.cache_data(ttl=3600, show_spinner=False)
def get_boxoffice(target_dt):
    """지정한 날짜의 KOBIS 일별 박스오피스를 가져옵니다."""

    # Streamlit Cloud Secrets에서 인증키를 가져옵니다.
    try:
        api_key = st.secrets["KOBIS_KEY"]
    except KeyError:
        return {
            "success": False,
            "empty": False,
            "message": (
                "KOBIS_KEY를 찾을 수 없습니다.\n\n"
                "Streamlit Cloud의 앱 Settings → Secrets에서 "
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

        response.raise_for_status()
        data = response.json()

    except requests.exceptions.RequestException as e:
        return {
            "success": False,
            "empty": False,
            "message": (
                "KOBIS API 요청에 실패했습니다.\n\n"
                "인터넷 연결이나 KOBIS API 상태를 확인하세요.\n"
                f"오류 내용: {e}"
            ),
            "movies": [],
        }

    except ValueError:
        return {
            "success": False,
            "empty": False,
            "message": (
                "KOBIS API의 응답을 JSON으로 읽지 못했습니다. "
                "잠시 후 다시 시도해 주세요."
            ),
            "movies": [],
        }

    # -----------------------------------------------------
    # 인증키가 잘못된 경우에도 HTTP 상태코드는 200일 수 있습니다.
    # 이때 KOBIS는 faultInfo를 반환합니다.
    # -----------------------------------------------------

    if "faultInfo" in data:
        fault_info = data["faultInfo"]

        fault_code = fault_info.get("faultCode", "")
        fault_string = fault_info.get("faultString", "")

        return {
            "success": False,
            "empty": False,
            "message": (
                "KOBIS API에서 오류를 반환했습니다.\n\n"
                f"오류 코드: {fault_code}\n"
                f"오류 내용: {fault_string}\n\n"
                "KOBIS_KEY가 정확한지 확인하세요."
            ),
            "movies": [],
        }

    # -----------------------------------------------------
    # 정상적인 박스오피스 결과 확인
    # -----------------------------------------------------

    boxoffice_result = data.get("boxOfficeResult")

    if not boxoffice_result:
        return {
            "success": False,
            "empty": False,
            "message": (
                "KOBIS 응답에 박스오피스 결과가 없습니다.\n\n"
                "선택한 날짜와 KOBIS API 응답을 확인하세요."
            ),
            "movies": [],
        }

    movie_list = boxoffice_result.get("dailyBoxOfficeList", [])

    # 영화 목록이 없으면 별도로 표시합니다.
    if not movie_list:
        return {
            "success": False,
            "empty": True,
            "message": "",
            "movies": [],
        }

    # -----------------------------------------------------
    # API에서 받은 문자열 숫자를 정수로 변환합니다.
    # rankInten도 함께 저장합니다.
    # -----------------------------------------------------

    movies = []

    for movie in movie_list:
        movies.append(
            {
                "순위": to_int(movie.get("rank")),
                "순위증감": to_int(movie.get("rankInten")),
                "영화명": movie.get("movieNm", ""),
                "개봉일": movie.get("openDt", ""),
                "관객수": to_int(movie.get("audiCnt")),
                "누적관객": to_int(movie.get("audiAcc")),
                "스크린수": to_int(movie.get("scrnCnt")),
            }
        )

    return {
        "success": True,
        "empty": False,
        "message": "",
        "movies": movies,
    }


# ---------------------------------------------------------
# 한국 시간 기준 날짜 계산
# ---------------------------------------------------------

today_kst, yesterday_kst = get_kst_dates()


# ---------------------------------------------------------
# 제목
# ---------------------------------------------------------

st.title("🎬 일별 박스오피스")


# ---------------------------------------------------------
# 날짜 선택
#
# 가장 늦은 날짜는 어제입니다.
# 미래 날짜와 오늘은 선택할 수 없습니다.
# ---------------------------------------------------------

selected_date = st.date_input(
    "조회 날짜",
    value=yesterday_kst,
    max_value=yesterday_kst,
    format="YYYY-MM-DD",
)

target_dt = selected_date.strftime("%Y%m%d")
display_date = selected_date.strftime("%Y-%m-%d")


# ---------------------------------------------------------
# 선택한 날짜의 데이터 가져오기
# ---------------------------------------------------------

with st.spinner("박스오피스 데이터를 불러오는 중입니다..."):
    result = get_boxoffice(target_dt)


# ---------------------------------------------------------
# 영화 목록이 없는 경우
# ---------------------------------------------------------

if result["empty"]:
    st.warning(
        f"📅 {display_date}의 박스오피스 영화 목록이 없습니다.\n\n"
        "그날은 아직 집계 전입니다."
    )

    st.info(
        "다른 날짜를 선택하거나, KOBIS에서 해당 날짜의 "
        "박스오피스 집계 여부를 확인해 주세요."
    )

    st.stop()


# ---------------------------------------------------------
# API 오류 처리
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

        4. 선택한 날짜에 박스오피스 데이터가 집계되어 있는지
           확인하세요.
        """
    )

    st.stop()


movies = result["movies"]

if not movies:
    st.warning(
        "그날은 아직 집계 전입니다."
    )
    st.stop()


# ---------------------------------------------------------
# 순위 순서대로 정렬합니다.
# ---------------------------------------------------------

movies = sorted(
    movies,
    key=lambda x: x["순위"],
)


# ---------------------------------------------------------
# 1위 영화
# ---------------------------------------------------------

first_movie = movies[0]

st.subheader(
    f"🥇 {display_date} 1위 — {first_movie['영화명']}"
)


# ---------------------------------------------------------
# 1위 영화의 주요 지표 3개
# ---------------------------------------------------------

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
# 영화명에 트로피 이모지를 붙이는 함수
#
# 누적관객이 100만 명을 초과하면 🏆 표시합니다.
# ---------------------------------------------------------

def movie_name_with_trophy(movie):
    """누적관객 100만 명 초과 영화의 이름에 트로피를 붙입니다."""

    if movie["누적관객"] > 1_000_000:
        return f"{movie['영화명']} 🏆"

    return movie["영화명"]


# ---------------------------------------------------------
# 순위 증감을 표시하는 함수
#
# KOBIS의 rankInten 기준:
#   양수 → 순위 상승 → 빨간색 위 화살표
#   음수 → 순위 하락 → 파란색 아래 화살표
#   0    → 변동 없음
#
# 표 안에서 색상을 표시하기 위해 HTML을 사용합니다.
# ---------------------------------------------------------

def rank_change_html(change):
    """순위 증감을 색상과 화살표가 있는 HTML로 만듭니다."""

    if change > 0:
        return (
            f'<span style="color:red; font-weight:bold;">'
            f'▲ {change}</span>'
        )

    if change < 0:
        return (
            f'<span style="color:blue; font-weight:bold;">'
            f'▼ {abs(change)}</span>'
        )

    return '<span style="color:gray;">-</span>'


# ---------------------------------------------------------
# 표용 데이터 만들기
# ---------------------------------------------------------

table_rows = []

for movie in movies:
    table_rows.append(
        {
            "순위": movie["순위"],
            "증감": rank_change_html(movie["순위증감"]),
            "영화명": movie_name_with_trophy(movie),
            "개봉일": movie["개봉일"],
            "관객수": f"{movie['관객수']:,}",
            "누적관객": f"{movie['누적관객']:,}",
            "스크린수": f"{movie['스크린수']:,}",
        }
    )


# ---------------------------------------------------------
# HTML 표로 출력
#
# st.dataframe에서는 셀 안의 HTML 색상 표현이 어렵기 때문에
# 순위 증감 화살표의 색상을 정확하게 보여주기 위해
# HTML 표를 사용합니다.
# ---------------------------------------------------------

st.subheader(f"📋 {display_date} 박스오피스")

table_html = """
<style>
.boxoffice-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 15px;
}

.boxoffice-table th {
    text-align: center;
    padding: 10px 8px;
    border-bottom: 2px solid #888;
    white-space: nowrap;
}

.boxoffice-table td {
    padding: 9px 8px;
    border-bottom: 1px solid #ddd;
}

.boxoffice-table th:nth-child(1),
.boxoffice-table td:nth-child(1),
.boxoffice-table th:nth-child(2),
.boxoffice-table td:nth-child(2),
.boxoffice-table th:nth-child(4),
.boxoffice-table td:nth-child(4),
.boxoffice-table th:nth-child(7),
.boxoffice-table td:nth-child(7) {
    text-align: center;
}

.boxoffice-table th:nth-child(5),
.boxoffice-table td:nth-child(5),
.boxoffice-table th:nth-child(6),
.boxoffice-table td:nth-child(6) {
    text-align: right;
}
</style>

<table class="boxoffice-table">
    <thead>
        <tr>
            <th>순위</th>
            <th>증감</th>
            <th>영화명</th>
            <th>개봉일</th>
            <th>관객수</th>
            <th>누적관객</th>
            <th>스크린수</th>
        </tr>
    </thead>
    <tbody>
"""

for row in table_rows:
    table_html += f"""
        <tr>
            <td>{row["순위"]}</td>
            <td>{row["증감"]}</td>
            <td>{row["영화명"]}</td>
            <td>{row["개봉일"]}</td>
            <td>{row["관객수"]}</td>
            <td>{row["누적관객"]}</td>
            <td>{row["스크린수"]}</td>
        </tr>
    """

table_html += """
    </tbody>
</table>
"""

st.markdown(table_html, unsafe_allow_html=True)


# ---------------------------------------------------------
# 관객수 상위 5편
# ---------------------------------------------------------

st.subheader("📊 관객수 상위 5편")

top5 = sorted(
    movies,
    key=lambda x: x["관객수"],
    reverse=True,
)[:5]


# ---------------------------------------------------------
# 막대그래프용 데이터
#
# 여기서는 이미 관객수를 int로 변환했기 때문에
# 그래프에서도 숫자로 정상적으로 처리됩니다.
# ---------------------------------------------------------

chart_data = {
    movie_name_with_trophy(movie): movie["관객수"]
    for movie in top5
}

st.bar_chart(
    chart_data,
    horizontal=True,
)


# ---------------------------------------------------------
# 안내 문구
# ---------------------------------------------------------

st.caption(
    "※ 관객수는 해당 날짜의 일일 관객수입니다. "
    "순위 증감은 전날 대비 순위 변화입니다. "
    "▲는 순위 상승, ▼는 순위 하락을 의미합니다. "
    "🏆는 누적관객 100만 명 초과를 의미합니다."
)

st.caption(
    "데이터 출처: 영화진흥위원회(KOBIS)"
)
