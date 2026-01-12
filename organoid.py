import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import json
from pathlib import Path
import io

# 데이터 저장 경로
DATA_FILE = Path("schedules_data.json")
TEMPLATE_FILE = Path("schedule_templates.json")

# 기본 Organoid 템플릿
DEFAULT_ORGANOID_TEMPLATE = {
    "name": "Organoid",
    "schedule": [
        {"start_day": 0, "end_day": 6, "interval": 1, "description": "Day 0-6: 매일"},
        {"start_day": 7, "end_day": 15, "interval": 1, "description": "Day 7-15: 매일"},
        {"start_day": 16, "end_day": 24, "interval": 2, "description": "Day 16-24: 2일마다"},
        {"start_day": 25, "end_day": 42, "interval": 2, "description": "Day 25-42: 2일마다"},
        {"start_day": 43, "end_day": 150, "interval": 4, "description": "Day 43-150: 4일마다"}
    ]
}

def load_templates():
    """템플릿 로드"""
    if TEMPLATE_FILE.exists():
        with open(TEMPLATE_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    else:
        # 기본 템플릿만 있는 상태로 초기화
        templates = {"Organoid": DEFAULT_ORGANOID_TEMPLATE}
        save_templates(templates)
        return templates

def save_templates(templates):
    """템플릿 저장"""
    with open(TEMPLATE_FILE, 'w', encoding='utf-8') as f:
        json.dump(templates, f, ensure_ascii=False, indent=2)

def load_schedules():
    """저장된 스케줄 로드"""
    if DATA_FILE.exists():
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []

def save_schedules(schedules):
    """스케줄 저장"""
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(schedules, f, ensure_ascii=False, indent=2)

def generate_visit_dates(start_date, template):
    """템플릿 기반으로 방문 날짜 생성"""
    visits = []
    
    for period in template["schedule"]:
        current_day = period["start_day"]
        while current_day <= period["end_day"]:
            visit_date = start_date + timedelta(days=current_day)
            visits.append({
                "day": current_day,
                "date": visit_date,
                "is_weekend": visit_date.weekday() >= 5
            })
            current_day += period["interval"]
    
    return visits

def count_weekend_visits(visits):
    """주말 방문 횟수 계산"""
    return sum(1 for v in visits if v["is_weekend"])

def find_overlaps(new_visits, existing_schedules):
    """기존 스케줄과의 겹침 찾기"""
    new_dates = set(v["date"].date() for v in new_visits)
    overlaps = {}
    
    for schedule in existing_schedules:
        if schedule.get("status") == "completed":
            continue
            
        schedule_dates = set(
            datetime.strptime(v["date"], "%Y-%m-%d").date() 
            for v in schedule["visits"]
        )
        overlap_dates = new_dates & schedule_dates
        
        if overlap_dates:
            overlaps[schedule["name"]] = len(overlap_dates)
    
    return overlaps

def get_start_date_candidates(base_date, days_range=14):
    """시작일 후보 생성 (다음 2주 이내)"""
    candidates = []
    for i in range(days_range):
        candidate = base_date + timedelta(days=i)
        candidates.append(candidate)
    return candidates

# Streamlit UI 시작
st.set_page_config(page_title="Organoid Schedule Manager", layout="wide")

st.title("🧬 Organoid Schedule Manager")

# 사이드바: 메뉴
menu = st.sidebar.radio(
    "메뉴",
    ["📅 스케줄 현황", "➕ 새 라인 추가", "📋 템플릿 관리", "📊 캘린더 뷰"]
)

# 데이터 로드
templates = load_templates()
schedules = load_schedules()

# ==================== 스케줄 현황 ====================
if menu == "📅 스케줄 현황":
    st.header("현재 진행중인 라인")
    
    active_schedules = [s for s in schedules if s.get("status") != "completed"]
    
    if not active_schedules:
        st.info("현재 진행중인 라인이 없습니다. '새 라인 추가'에서 시작하세요!")
    else:
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("활성 라인 수", len(active_schedules))
        with col2:
            total_visits_upcoming = sum(
                len([v for v in s["visits"] if datetime.strptime(v["date"], "%Y-%m-%d").date() >= datetime.now().date()])
                for s in active_schedules
            )
            st.metric("남은 총 방문 횟수", total_visits_upcoming)
        with col3:
            upcoming_7days = sum(
                len([v for v in s["visits"] 
                     if datetime.strptime(v["date"], "%Y-%m-%d").date() >= datetime.now().date()
                     and datetime.strptime(v["date"], "%Y-%m-%d").date() <= (datetime.now() + timedelta(days=7)).date()])
                for s in active_schedules
            )
            st.metric("다음 7일 방문", upcoming_7days)
        
        st.divider()
        
        # 라인별 상세 정보
        for idx, schedule in enumerate(active_schedules):
            with st.expander(f"📌 {schedule['name']} - {schedule['template']} (시작: {schedule['start_date']})"):
                col1, col2 = st.columns([3, 1])
                
                with col1:
                    start_date = datetime.strptime(schedule['start_date'], "%Y-%m-%d").date()
                    today = datetime.now().date()
                    current_day = (today - start_date).days
                    
                    total_visits = len(schedule['visits'])
                    completed_visits = len([v for v in schedule['visits'] 
                                           if datetime.strptime(v["date"], "%Y-%m-%d").date() < today])
                    
                    st.write(f"**현재 Day:** {current_day}")
                    st.write(f"**진행률:** {completed_visits}/{total_visits} 방문 완료")
                    st.write(f"**주말 방문:** {schedule.get('weekend_count', 0)}회")
                    
                    # 다가오는 방문 일정 (다음 5개)
                    upcoming = [v for v in schedule['visits'] 
                               if datetime.strptime(v["date"], "%Y-%m-%d").date() >= today][:5]
                    
                    if upcoming:
                        st.write("**다가오는 방문:**")
                        for v in upcoming:
                            date_str = v['date']
                            day_str = f"Day {v['day']}"
                            weekend_str = "🔴 주말" if v['is_weekend'] else ""
                            st.write(f"- {date_str} ({day_str}) {weekend_str}")
                
                with col2:
                    if st.button("완료", key=f"complete_{idx}"):
                        schedules[schedules.index(schedule)]["status"] = "completed"
                        save_schedules(schedules)
                        st.rerun()
                    
                    if st.button("삭제", key=f"delete_{idx}"):
                        schedules.remove(schedule)
                        save_schedules(schedules)
                        st.rerun()
        
        # 엑셀 다운로드
        st.divider()
        if st.button("📥 전체 스케줄 엑셀로 다운로드"):
            all_data = []
            for schedule in active_schedules:
                for visit in schedule['visits']:
                    all_data.append({
                        "라인명": schedule['name'],
                        "템플릿": schedule['template'],
                        "시작일": schedule['start_date'],
                        "Day": visit['day'],
                        "방문일": visit['date'],
                        "주말여부": "주말" if visit['is_weekend'] else "평일"
                    })
            
            df = pd.DataFrame(all_data)
            
            # 엑셀 파일로 변환
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df.to_excel(writer, index=False, sheet_name='전체스케줄')
            
            st.download_button(
                label="💾 Excel 파일 다운로드",
                data=output.getvalue(),
                file_name=f"organoid_schedules_{datetime.now().strftime('%Y%m%d')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

# ==================== 새 라인 추가 ====================
elif menu == "➕ 새 라인 추가":
    st.header("새로운 라인 추가")
    
    col1, col2 = st.columns(2)
    
    with col1:
        line_name = st.text_input("라인 이름", placeholder="예: Line_A, 환자001")
        selected_template = st.selectbox("템플릿 선택", list(templates.keys()))
        
        # 템플릿 정보 표시
        if selected_template:
            st.info(f"**{selected_template} 템플릿 정보:**")
            for period in templates[selected_template]["schedule"]:
                st.write(f"- {period['description']}")
    
    with col2:
        search_start_date = st.date_input("희망 시작 기간", datetime.now())
        search_days = st.slider("검색할 날짜 범위 (일)", 7, 30, 14)
    
    if st.button("최적 시작일 찾기", type="primary"):
        if not line_name:
            st.error("라인 이름을 입력하세요.")
        else:
            candidates = get_start_date_candidates(search_start_date, search_days)
            
            results = []
            for candidate_date in candidates:
                visits = generate_visit_dates(candidate_date, templates[selected_template])
                weekend_count = count_weekend_visits(visits)
                overlaps = find_overlaps(visits, schedules)
                overlap_total = sum(overlaps.values())
                
                results.append({
                    "date": candidate_date,
                    "weekend_count": weekend_count,
                    "overlap_total": overlap_total,
                    "overlaps": overlaps,
                    "visits": visits
                })
            
            # 결과 정렬 (주말 적고, 겹침 많은 순)
            results.sort(key=lambda x: (x["weekend_count"], -x["overlap_total"]))
            
            st.success(f"✅ {len(results)}개의 후보 날짜를 찾았습니다!")
            
            # 상위 5개 후보 표시
            st.subheader("추천 시작일 (주말 방문 최소화)")
            
            for i, result in enumerate(results[:5]):
                rank_emoji = "🥇" if i == 0 else "🥈" if i == 1 else "🥉" if i == 2 else "📅"
                
                with st.container():
                    col1, col2, col3, col4 = st.columns([2, 1, 1, 1])
                    
                    with col1:
                        st.write(f"{rank_emoji} **{result['date'].strftime('%Y-%m-%d (%A)')}**")
                    
                    with col2:
                        st.metric("주말 방문", f"{result['weekend_count']}회")
                    
                    with col3:
                        st.metric("겹침", f"{result['overlap_total']}회")
                    
                    with col4:
                        if st.button("선택", key=f"select_{i}"):
                            # 스케줄 저장
                            new_schedule = {
                                "name": line_name,
                                "template": selected_template,
                                "start_date": result['date'].strftime("%Y-%m-%d"),
                                "status": "active",
                                "weekend_count": result['weekend_count'],
                                "visits": [
                                    {
                                        "day": v["day"],
                                        "date": v["date"].strftime("%Y-%m-%d"),
                                        "is_weekend": v["is_weekend"]
                                    }
                                    for v in result['visits']
                                ]
                            }
                            
                            schedules.append(new_schedule)
                            save_schedules(schedules)
                            st.success(f"✅ {line_name} 라인이 추가되었습니다!")
                            st.balloons()
                            st.rerun()
                    
                    # 겹치는 라인 정보
                    if result['overlaps']:
                        overlap_text = ", ".join([f"{name}({count})" for name, count in result['overlaps'].items()])
                        st.caption(f"겹치는 라인: {overlap_text}")
                    
                    st.divider()

# ==================== 템플릿 관리 ====================
elif menu == "📋 템플릿 관리":
    st.header("스케줄 템플릿 관리")
    
    tab1, tab2 = st.tabs(["기존 템플릿", "새 템플릿 추가"])
    
    with tab1:
        for template_name, template_data in templates.items():
            with st.expander(f"📋 {template_name}"):
                st.write("**스케줄 구성:**")
                for period in template_data["schedule"]:
                    st.write(f"- {period['description']}")
                
                col1, col2 = st.columns(2)
                with col1:
                    # 샘플 시작일로 미리보기
                    sample_date = datetime.now()
                    sample_visits = generate_visit_dates(sample_date, template_data)
                    st.write(f"**총 방문 횟수:** {len(sample_visits)}회")
                    st.write(f"**예상 소요 기간:** {sample_visits[-1]['day']}일")
                
                with col2:
                    if template_name != "Organoid":  # 기본 템플릿은 삭제 불가
                        if st.button("삭제", key=f"del_template_{template_name}"):
                            del templates[template_name]
                            save_templates(templates)
                            st.rerun()
    
    with tab2:
        st.subheader("새 템플릿 추가")
        
        new_template_name = st.text_input("템플릿 이름")
        
        st.write("**스케줄 기간 추가** (하나씩 추가하세요)")
        
        if "temp_schedule" not in st.session_state:
            st.session_state.temp_schedule = []
        
        col1, col2, col3 = st.columns(3)
        with col1:
            start_day = st.number_input("시작 Day", min_value=0, value=0)
        with col2:
            end_day = st.number_input("종료 Day", min_value=0, value=10)
        with col3:
            interval = st.number_input("방문 간격 (일)", min_value=1, value=1)
        
        if st.button("기간 추가"):
            st.session_state.temp_schedule.append({
                "start_day": start_day,
                "end_day": end_day,
                "interval": interval,
                "description": f"Day {start_day}-{end_day}: {interval}일마다"
            })
            st.rerun()
        
        if st.session_state.temp_schedule:
            st.write("**현재 설정된 스케줄:**")
            for i, period in enumerate(st.session_state.temp_schedule):
                col1, col2 = st.columns([4, 1])
                with col1:
                    st.write(f"{i+1}. {period['description']}")
                with col2:
                    if st.button("삭제", key=f"remove_period_{i}"):
                        st.session_state.temp_schedule.pop(i)
                        st.rerun()
            
            if st.button("템플릿 저장", type="primary"):
                if not new_template_name:
                    st.error("템플릿 이름을 입력하세요.")
                elif new_template_name in templates:
                    st.error("이미 존재하는 템플릿 이름입니다.")
                else:
                    templates[new_template_name] = {
                        "name": new_template_name,
                        "schedule": st.session_state.temp_schedule
                    }
                    save_templates(templates)
                    st.session_state.temp_schedule = []
                    st.success(f"✅ {new_template_name} 템플릿이 저장되었습니다!")
                    st.rerun()

# ==================== 캘린더 뷰 ====================
elif menu == "📊 캘린더 뷰":
    st.header("전체 스케줄 캘린더")
    
    active_schedules = [s for s in schedules if s.get("status") != "completed"]
    
    if not active_schedules:
        st.info("현재 진행중인 라인이 없습니다.")
    else:
        # 날짜 범위 선택
        view_start = st.date_input("시작 날짜", datetime.now())
        view_days = st.slider("표시할 기간 (일)", 7, 60, 30)
        
        # 날짜별 방문 정리
        calendar_data = {}
        for schedule in active_schedules:
            for visit in schedule['visits']:
                visit_date = datetime.strptime(visit['date'], "%Y-%m-%d").date()
                
                if view_start <= visit_date <= view_start + timedelta(days=view_days):
                    if visit_date not in calendar_data:
                        calendar_data[visit_date] = []
                    
                    calendar_data[visit_date].append({
                        "name": schedule['name'],
                        "day": visit['day'],
                        "is_weekend": visit['is_weekend']
                    })
        
        # 주별로 표시
        current_date = view_start
        week_num = 0
        
        while current_date <= view_start + timedelta(days=view_days):
            week_start = current_date
            week_end = current_date + timedelta(days=6)
            
            st.subheader(f"Week {week_num + 1}: {week_start.strftime('%Y-%m-%d')} ~ {week_end.strftime('%Y-%m-%d')}")
            
            week_data = []
            for i in range(7):
                day_date = week_start + timedelta(days=i)
                if day_date in calendar_data:
                    visits = calendar_data[day_date]
                    day_info = f"{day_date.strftime('%m/%d (%a)')}\n"
                    day_info += f"방문: {len(visits)}건\n"
                    day_info += "\n".join([f"- {v['name']} (D{v['day']})" for v in visits])
                    week_data.append(day_info)
                else:
                    week_data.append(f"{day_date.strftime('%m/%d (%a)')}\n-")
            
            cols = st.columns(7)
            for i, col in enumerate(cols):
                with col:
                    day_date = week_start + timedelta(days=i)
                    is_weekend = day_date.weekday() >= 5
                    
                    if is_weekend:
                        st.markdown(f"**:red[{week_data[i]}]**")
                    else:
                        st.text(week_data[i])
            
            st.divider()
            current_date = week_end + timedelta(days=1)
            week_num += 1

# 푸터
st.sidebar.divider()
st.sidebar.caption("🧬 Organoid Schedule Manager v1.0")
st.sidebar.caption(f"활성 라인: {len([s for s in schedules if s.get('status') != 'completed'])}개")
