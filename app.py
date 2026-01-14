import streamlit as st
import json, os, requests
from datetime import datetime
from dotenv import load_dotenv
import google.generativeai as genai
from pinecone import Pinecone
from korean_lunar_calendar import KoreanLunarCalendar

# 1. 시스템 초기 설정
load_dotenv()
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
index = pc.Index(os.getenv("PINECONE_INDEX_NAME"))
model = genai.GenerativeModel('gemini-2.0-flash')

# 2. 데이터베이스 로드
@st.cache_data
def load_all_databases():
    dbs = {}
    f_map = {
        'ilju': '60ganja.json', 
        'tojeong': 'tojeong_144_weighted.json', 
        'sipsin': 'sipsin_data.json', 
        'gyeok': 'gyeok_data.json', 
        'unseong': '12unsung.json'
    }
    for k, path in f_map.items():
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                dbs[k] = json.load(f)
        else:
            dbs[k] = {}
    return dbs

dbs = load_all_databases()

# 3. 역학 로직 및 데이터 매핑
ILJU_BRIDGE = {
    "무술": {"sipsin": "비견(比肩)", "unseong": "묘(墓)", "gyeok": "건록격(建祿格)"},
    "경신": {"sipsin": "비견(比肩)", "unseong": "건록(建祿)", "gyeok": "양인격(陽刃格)"},
    "임자": {"sipsin": "겁재(劫財)", "unseong": "제왕(帝旺)", "gyeok": "양인격(陽刃格)"}
}

def get_json_info(ilju_name):
    ilju_basic = next((v for v in dbs.get('ilju', {}).values() if ilju_name in v.get('ilju', '')), {})
    bridge = ILJU_BRIDGE.get(ilju_name, {"sipsin": "비견(比肩)", "unseong": "묘(墓)", "gyeok": "건록격(建祿格)"})
    sipsin_info = dbs.get('sipsin', {}).get(bridge['sipsin'], {})
    unseong_info = dbs.get('unseong', {}).get(bridge['unseong'], {})
    gyeok_info = dbs.get('gyeok', {}).get(bridge['gyeok'], "자수성가형 명조")
    return ilju_basic, sipsin_info, unseong_info, gyeok_info, bridge

def get_saju_pillars(y, m, d, h_str, is_lunar=False):
    calendar = KoreanLunarCalendar()
    try:
        if is_lunar: calendar.setLunarDate(y, m, d, False)
        else: calendar.setSolarDate(y, m, d)
        full_gapja = calendar.getGapJaString() 
        parts = full_gapja.split()
        return {"year": parts[0].replace('년',''), "month": parts[1].replace('월',''), "day": parts[2].replace('일',''), "hour": h_str}
    except: return None

# 4. n8n 연동 함수
def sync_to_n8n(action_type, payload):
    # n8n의 Webhook 노드에서 복사한 Production URL을 여기에 넣으세요
    N8N_WEBHOOK_URL = "https://여러분의-n8n-주소/webhook/saju-save" 
    
    payload["action"] = action_type
    payload["timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    try:
        requests.post(N8N_WEBHOOK_URL, json=payload, timeout=5)
    except:
        pass

# --- UI 레이아웃 ---
st.set_page_config(page_title="운명 대서사시 V2.7", layout="wide")
st.title("🔮 사주·체질·성명학 통합 대서사시 V2.7")

with st.container():
    st.subheader("👤 기본 정보 및 서비스 구독")
    c1, c2 = st.columns(2)
    with c1: u_name = st.text_input("한글 성함", value="")
    with c2: u_telegram = st.text_input("텔레그램 ID (@ID)", placeholder="@username")
    
    u_hanja = st.text_input("한자 성함 (선택)", placeholder="")
    
    row = st.columns(4)
    with row[0]: cal_type = st.radio("달력", ["양력", "음력"], horizontal=True)
    with row[1]: y_val = st.selectbox("년", range(2026, 1950, -1), index=50) 
    with row[2]: m_val = st.selectbox("월", range(1, 13), index=3) 
    with row[3]: d_val = st.selectbox("일", range(1, 32), index=15) 
    
    h_opts = ["모름"] + [f"{h:02d}:00" for h in range(24)]
    h_input = st.selectbox("태어난 시", h_opts, index=12)

st.write("---")

# 32문항 정밀 체질 문진
with st.expander("🧬 8체질 & 아유르베다 정밀 문진", expanded=False):
    questions = [
        "1. 육식(고기)을 하면 힘이 나고 소화가 잘 되나요?", "2. 생선이나 해산물을 먹으면 속이 편안한가요?",
        "3. 땀을 푹 내고 나면 몸이 가벼워지나요?", "4. 땀을 내면 오히려 기운이 빠지고 피곤한가요?",
        "5. 밀가루 음식(면, 빵)을 먹으면 속이 더부룩한가요?", "6. 찬 우유를 마시면 설사를 하거나 배가 아픈가요?",
        "7. 사우나나 온탕 목욕을 즐기며 하고 나면 개운한가요?", "8. 평소 대변이 묽은 편이며 하루에 여러 번 보나요?",
        "9. 성격이 급하고 일 처리를 빨리 끝내야 직성이 풀리나요?", "10. 매사에 신중하고 꼼꼼하며 결정을 내리는 데 시간이 걸리나요?",
        "11. 일광욕이나 햇볕을 쬐는 것을 좋아하나요?", "12. 피부가 예민하여 금속 알레르기나 아토피가 있나요?",
        "13. 어깨보다 골격과 하체가 더 발달한 편인가요?", "14. 가슴 윗부분(상체)이 발달하고 걸음걸이가 빠른가요?",
        "15. 커피를 마시면 잠이 안 오거나 가슴이 두근거리나요?", "16. 술을 조금만 마셔도 얼굴이 심하게 빨개지나요?",
        "17. 화가 나면 얼굴이 달아오르고 위로 열이 솟구치나요?", "18. 평소 몸이 차고 아랫배가 냉한 느낌이 있나요?",
        "19. 육식을 끊고 채식만 하면 기운이 없고 무기력해지는 것을 느끼나요?", "20. 매운 음식을 먹으면 땀이 비 오듯 쏟아지나요?",
        "21. 포도나 푸른 채소를 먹으면 컨디션이 좋아지나요?", "22. 오이나 참외 같은 찬 성질의 과일이 잘 맞나요?",
        "23. 말수가 적고 조용하며 자신의 속마음을 잘 숨기나요?", "24. 목소리가 크고 화술이 좋아 사교적인 편인가요?",
        "25. 평소 소화력이 좋아 과식해도 금방 배가 고픈가요?", "26. 생각이 너무 많아 불면증에 시달릴 때가 있나요?",
        "27. 손발이 항상 따뜻하고 추위를 별로 안 타나요?", "28. 추위를 몹시 타고 찬바람을 맞으면 재채기가 나나요?",
        "29. 비타민 C를 먹으면 속이 쓰리거나 불편한가요?", "30. 창의적이고 직관적이지만 끈기가 부족한가요?",
        "31. 한 가지 일에 집요하게 매달리는 집중력이 좋나요?", "32. 물을 많이 마시지 않아도 갈증을 별로 안 느끼나요?"
    ]
    user_ans = []
    q_cols = st.columns(2)
    for i, q in enumerate(questions):
        with q_cols[i % 2]:
            a = st.radio(q, ["전혀 아니다", "아니다", "그렇다", "매우 그렇다"], horizontal=True, key=f"q{i}")
            user_ans.append(f"{q}: {a}")

st.write("---")

pillars = get_saju_pillars(y_val, m_val, d_val, h_input, cal_type=="음력")

if pillars:
    ilju_name = pillars['day']
    # 고유 ID 생성 (이름_생년월일_시)
    user_unique_id = f"{u_name}_{y_val}{m_val:02d}{d_val:02d}_{h_input.replace(':', '')}"

    if st.button("📜 최종 운명 리포트 생성"):
        if not u_name:
            st.warning("분석을 위해 성함을 입력해 주세요.")
        else:
            with st.spinner("방대한 데이터베이스를 융합하여 분석 중입니다..."):
                # 1. 데이터 추출
                ilju_info, sipsin_info, unseong_info, gyeok_info, bridge = get_json_info(ilju_name)
                tid = f"{(y_val+m_val)%8+1}{(m_val+d_val)%6+1}{(d_val+y_val)%3+1}"
                tojeong = dbs.get('tojeong', {}).get(tid, {"full_content": ""})['full_content']

                # 2. n8n 자동 동기화 (Upsert용 데이터 전송)
                sync_to_n8n("save_user", {
                    "user_id": user_unique_id,
                    "name": u_name,
                    "birth": f"{y_val}-{m_val:02d}-{d_val:02d}",
                    "hour": h_input,
                    "telegram": u_telegram if u_telegram else "미입력",
                    "ilju": ilju_name,
                    "subscribed": "FALSE"
                })

                # 3. AI 분석 실행
                prompt = f"""
                당신은 데이터 명리학의 거장입니다. '{u_name}' 님을 위한 정밀 분석 보고서를 작성하세요.
                
                [표현 규칙 - 필수]
                - 모든 한자는 반드시 `:orange[**한자**]` 형식을 사용하세요. 예: 무술(:orange[**戊戌**]), 재물운(:orange[**財物運**])

                [제공 데이터]
                - 성함: {u_name}(한자: {u_hanja}) / 사주 원국: {pillars}
                - 일주 핵심: {ilju_info} / 십신({bridge['sipsin']}): {sipsin_info} / 십이운성({bridge['unseong']}): {unseong_info}
                - 격국: {gyeok_info} / 올해의 운세: {tojeong} / 체질 답변: {user_ans}

                [보고서 구성]
                1. 제1장 성명학: 이름의 기운과 {ilju_name}일주의 조화.
                2. 제2장 사주 정밀 해독: [재물운], [부모운], [직업운], [배우자운], [건강운]을 아주 상세히 종합 분석.
                3. 제3장 올해의 운세: 서사적 소설처럼 상세히 풀이.
                4. 제4장 체질 판정 및 처방: 32개 답변 기반 8체질/아유르베다 확정 및 생활 처방.
                """
                st.markdown(model.generate_content(prompt).text)

    # 구독 섹션 (리포트 생성 버튼 밖으로 배치하여 안정성 확보)
    st.write("---")
    st.subheader("🔔 체질 맞춤 건강 알림 서비스")
    st.write("구독하시면 매일 아침 귀하의 체질에 맞는 건강 정보를 텔레그램으로 보내드립니다.")
    
    if st.button("🚀 텔레그램 구독하기"):
        if u_name and u_telegram and u_telegram != "@":
            sync_to_n8n("subscribe", {
                "user_id": user_unique_id,
                "telegram": u_telegram,
                "subscribed": "TRUE"
            })
            st.success(f"✅ {u_name}님, 구독 신청이 전송되었습니다! n8n에서 데이터 업데이트를 확인하세요.")
        else:
            st.error("성함과 텔레그램 ID를 정확히 입력한 후 구독 버튼을 눌러주세요.")
