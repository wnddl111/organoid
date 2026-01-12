import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import json
from pathlib import Path
import io

# 데이터 저장 경로
DATA_FILE = Path("schedules_data.json")
TEMPLATE_FILE = Path("schedule_templates.json")
PROTOCOL_FILE = Path("protocols.json")
PEOPLE_FILE = Path("people.json")

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

# 기본 Organoid 프로토콜 예시
DEFAULT_ORGANOID_PROTOCOLS = {
    0: {
        "title": "Day 0: 세포 파종",
        "protocol": "1. Matrigel 해동 (4°C, 30분)\n2. 세포 계수 및 농도 조정\n3. 96-well plate에 파종\n4. 37°C, 5% CO2 배양기에 배치"
    },
    3: {
        "title": "Day 3: 배지 교환",
        "protocol": "1. 현미경으로 형태 확인\n2. 배지 절반 교환\n3. 사진 촬영 (10x)"
    },
    7: {
        "title": "Day 7: 첫 계대배양",
        "protocol": "1. TrypLE로 세포 분리 (37°C, 5분)\n2. 원심분리 (300g, 5분)\n3. 신선한 Matrigel에 재현탁\n4. 새 plate에 파종"
    }
}

# 색상 팔레트 (사람별 배정)
PERSON_COLORS = [
    "🔴", "🟠", "🟡", "🟢", "🔵", "🟣", "🟤", "⚫", 
    "🔶", "🟨", "🟩", "🟦", "🟪", "⬛", "🟥", "🟧"
]

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

def load_protocols():
    """프로토콜 로드"""
    if PROTOCOL_FILE.exists():
        with open(PROTOCOL_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    else:
        # 기본 프로토콜만 있는 상태로 초기화
        protocols = {"Organoid": DEFAULT_ORGANOID_PROTOCOLS}
        save_protocols(protocols)
        return protocols

def save_protocols(protocols):
    """프로토콜 저장"""
    with open(PROTOCOL_FILE, 'w', encoding='utf-8') as f:
        json.dump(protocols, f, ensure_ascii=False, indent=2)

def load_people():
    """사람 목록 로드"""
    if PEOPLE_FILE.exists():
        with open(PEOPLE_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []

def save_people(people):
    """사람 목록 저장"""
    with open(PEOPLE_FILE, 'w', encoding='utf-8') as f:
        json.dump(people, f, ensure_ascii=False, indent=2)

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
                "is_weekend": visit_date.weekday() >= 5,
                "selected_protocol": None,  # 사용자가 선택한 프로토콜
                "memo": "",  # 사용자 메모
                "assigned_people": []  # 배정된 사람들
            })
            current_day += period["interval"]
    
    return visits

def count_weekend_visits(visits):
    """주말 방문 횟수 계산"""
    return sum(1 for v in visits if v["is_weekend"])

def find_overlaps(new_visits, existing_schedules):
    """기존 스케줄과의 겹침 찾기"""
    # new_visits의 date는 이미 datetime 객체이므로 .date()로 변환
    new_dates = set(
        v["date"].date() if isinstance(v["date"], datetime) else v["date"]
        for v in new_visits
    )
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
    ["📅 스케줄 현황", "➕ 새 라인 추가", "📋 템플릿 관리", "📝 프로토콜 관리", "👥 인원 관리", "📊 캘린더 뷰"]
)

# 데이터 로드
templates = load_templates()
schedules = load_schedules()
protocols = load_protocols()
people = load_people()

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
        date_selection_mode = st.radio(
            "시작일 선택 방법",
            ["🔍 최적 시작일 찾기", "📅 직접 날짜 지정"],
            horizontal=True
        )
        
        if date_selection_mode == "🔍 최적 시작일 찾기":
            search_start_date = st.date_input("희망 시작 기간", datetime.now())
            search_days = st.slider("검색할 날짜 범위 (일)", 7, 30, 14)
        else:
            manual_start_date = st.date_input("시작 날짜 선택", datetime.now())
    
    # 최적 시작일 찾기 모드
    if date_selection_mode == "🔍 최적 시작일 찾기" and st.button("최적 시작일 찾기", type="primary"):
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
    
    # 직접 날짜 지정 모드
    elif date_selection_mode == "📅 직접 날짜 지정":
        # Session state 초기화
        if 'preview_schedule' not in st.session_state:
            st.session_state.preview_schedule = None
        
        if st.button("이 날짜로 시작하기", type="primary"):
            if not line_name:
                st.error("라인 이름을 입력하세요.")
            else:
                # 선택한 날짜로 방문 일정 생성
                visits = generate_visit_dates(manual_start_date, templates[selected_template])
                weekend_count = count_weekend_visits(visits)
                overlaps = find_overlaps(visits, schedules)
                overlap_total = sum(overlaps.values())
                
                # Session state에 저장
                st.session_state.preview_schedule = {
                    "line_name": line_name,
                    "template": selected_template,
                    "start_date": manual_start_date,
                    "visits": visits,
                    "weekend_count": weekend_count,
                    "overlaps": overlaps,
                    "overlap_total": overlap_total
                }
        
        # 미리보기 표시
        if st.session_state.preview_schedule:
            preview = st.session_state.preview_schedule
            
            st.subheader("📋 생성될 스케줄 미리보기")
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("시작일", preview["start_date"].strftime('%Y-%m-%d (%A)'))
            with col2:
                st.metric("주말 방문", f"{preview['weekend_count']}회")
            with col3:
                st.metric("기존 라인과 겹침", f"{preview['overlap_total']}회")
            
            if preview["overlaps"]:
                overlap_text = ", ".join([f"{name}({count})" for name, count in preview["overlaps"].items()])
                st.info(f"겹치는 라인: {overlap_text}")
            
            st.write("**처음 5개 방문 일정:**")
            for v in preview["visits"][:5]:
                weekend_str = "🔴 주말" if v["is_weekend"] else ""
                st.write(f"- Day {v['day']}: {v['date'].strftime('%Y-%m-%d (%A)')} {weekend_str}")
            
            col1, col2 = st.columns(2)
            with col1:
                if st.button("✅ 확인 및 추가", key="confirm_manual", type="primary"):
                    new_schedule = {
                        "name": preview["line_name"],
                        "template": preview["template"],
                        "start_date": preview["start_date"].strftime("%Y-%m-%d"),
                        "status": "active",
                        "weekend_count": preview["weekend_count"],
                        "visits": [
                            {
                                "day": v["day"],
                                "date": v["date"].strftime("%Y-%m-%d"),
                                "is_weekend": v["is_weekend"]
                            }
                            for v in preview["visits"]
                        ]
                    }
                    
                    schedules.append(new_schedule)
                    save_schedules(schedules)
                    st.session_state.preview_schedule = None  # 미리보기 초기화
                    st.success(f"✅ {preview['line_name']} 라인이 추가되었습니다!")
                    st.balloons()
                    st.rerun()
            
            with col2:
                if st.button("❌ 취소", key="cancel_manual"):
                    st.session_state.preview_schedule = None
                    st.rerun()

# ==================== 프로토콜 관리 ====================
elif menu == "📝 프로토콜 관리":
    st.header("프로토콜 관리")
    
    st.write("각 템플릿별로 Day에 따른 프로토콜을 저장하고 관리할 수 있습니다.")
    
    # 템플릿 선택
    selected_protocol_template = st.selectbox(
        "프로토콜을 관리할 템플릿 선택",
        list(templates.keys())
    )
    
    if selected_protocol_template not in protocols:
        protocols[selected_protocol_template] = {}
    
    tab1, tab2 = st.tabs(["프로토콜 보기/수정", "새 프로토콜 추가"])
    
    with tab1:
        st.subheader(f"{selected_protocol_template} 템플릿의 프로토콜")
        
        if not protocols[selected_protocol_template]:
            st.info("아직 등록된 프로토콜이 없습니다. '새 프로토콜 추가' 탭에서 추가하세요.")
        else:
            # Day 순서대로 정렬
            sorted_days = sorted([int(day) for day in protocols[selected_protocol_template].keys()])
            
            for day in sorted_days:
                day_str = str(day)
                protocol_data = protocols[selected_protocol_template][day_str]
                
                with st.expander(f"📌 Day {day}: {protocol_data.get('title', '제목 없음')}"):
                    # 수정 가능한 형태로 표시
                    new_title = st.text_input(
                        "제목",
                        value=protocol_data.get('title', ''),
                        key=f"title_{selected_protocol_template}_{day}"
                    )
                    
                    new_protocol = st.text_area(
                        "프로토콜 내용",
                        value=protocol_data.get('protocol', ''),
                        height=200,
                        key=f"protocol_{selected_protocol_template}_{day}"
                    )
                    
                    col1, col2 = st.columns([1, 4])
                    with col1:
                        if st.button("💾 저장", key=f"save_{selected_protocol_template}_{day}"):
                            protocols[selected_protocol_template][day_str] = {
                                "title": new_title,
                                "protocol": new_protocol
                            }
                            save_protocols(protocols)
                            st.success("저장되었습니다!")
                            st.rerun()
                    
                    with col2:
                        if st.button("🗑️ 삭제", key=f"delete_{selected_protocol_template}_{day}"):
                            del protocols[selected_protocol_template][day_str]
                            save_protocols(protocols)
                            st.success("삭제되었습니다!")
                            st.rerun()
    
    with tab2:
        st.subheader("새 프로토콜 추가")
        
        new_day = st.number_input("Day", min_value=0, max_value=500, value=0)
        new_title = st.text_input("프로토콜 제목", placeholder="예: Day 0: 세포 파종")
        new_protocol = st.text_area(
            "프로토콜 내용",
            placeholder="상세한 프로토콜 내용을 입력하세요...\n\n예:\n1. 준비물 확인\n2. 실험 절차\n3. 주의사항",
            height=300
        )
        
        if st.button("➕ 프로토콜 추가", type="primary"):
            if not new_title:
                st.error("프로토콜 제목을 입력하세요.")
            elif str(new_day) in protocols[selected_protocol_template]:
                st.error(f"Day {new_day}에 이미 프로토콜이 존재합니다. '프로토콜 보기/수정' 탭에서 수정하세요.")
            else:
                protocols[selected_protocol_template][str(new_day)] = {
                    "title": new_title,
                    "protocol": new_protocol
                }
                save_protocols(protocols)
                st.success(f"✅ Day {new_day} 프로토콜이 추가되었습니다!")
                st.rerun()

# ==================== 인원 관리 ====================
elif menu == "👥 인원 관리":
    st.header("인원 관리")
    
    st.write("실험 담당자를 등록하고 관리합니다. 각 사람에게 자동으로 색상이 배정됩니다.")
    
    tab1, tab2, tab3 = st.tabs(["인원 목록", "인원 추가", "랜덤 배정"])
    
    with tab1:
        st.subheader("등록된 인원")
        
        if not people:
            st.info("등록된 인원이 없습니다. '인원 추가' 탭에서 추가하세요.")
        else:
            for idx, person in enumerate(people):
                col1, col2, col3 = st.columns([1, 3, 1])
                
                with col1:
                    color_emoji = PERSON_COLORS[idx % len(PERSON_COLORS)]
                    st.markdown(f"## {color_emoji}")
                
                with col2:
                    st.markdown(f"### {person['name']}")
                    if person.get('note'):
                        st.caption(person['note'])
                
                with col3:
                    if st.button("🗑️ 삭제", key=f"delete_person_{idx}"):
                        people.pop(idx)
                        save_people(people)
                        st.success("삭제되었습니다!")
                        st.rerun()
                
                st.divider()
    
    with tab2:
        st.subheader("새 인원 추가")
        
        new_person_name = st.text_input("이름", placeholder="예: 김철수")
        new_person_note = st.text_input("메모 (선택)", placeholder="예: 박사과정 / 월수금 출근")
        
        if st.button("➕ 인원 추가", type="primary"):
            if not new_person_name:
                st.error("이름을 입력하세요.")
            elif any(p['name'] == new_person_name for p in people):
                st.error("이미 등록된 이름입니다.")
            else:
                people.append({
                    "name": new_person_name,
                    "note": new_person_note
                })
                save_people(people)
                
                # 색상 미리보기
                color_emoji = PERSON_COLORS[len(people) - 1 % len(PERSON_COLORS)]
                st.success(f"✅ {color_emoji} {new_person_name} 님이 추가되었습니다!")
                st.rerun()
    
    with tab3:
        st.subheader("인원 랜덤 배정")
        
        if len(people) < 2:
            st.warning("최소 2명 이상의 인원이 필요합니다. '인원 추가' 탭에서 추가하세요.")
        else:
            st.write("활성화된 모든 라인의 방문에 인원을 2명씩 랜덤 배정합니다.")
            
            active_schedules = [s for s in schedules if s.get("status") != "completed"]
            
            if not active_schedules:
                st.info("활성 라인이 없습니다.")
            else:
                # 날짜 범위 선택
                col1, col2 = st.columns(2)
                with col1:
                    assign_start = st.date_input("배정 시작일", datetime.now().date())
                with col2:
                    assign_end = st.date_input("배정 종료일", datetime.now().date() + timedelta(days=30))
                
                # 미배정 방문 수 계산
                unassigned_count = 0
                for schedule in active_schedules:
                    for visit in schedule['visits']:
                        visit_date = datetime.strptime(visit['date'], "%Y-%m-%d").date()
                        if assign_start <= visit_date <= assign_end:
                            if not visit.get('assigned_people') or len(visit.get('assigned_people', [])) == 0:
                                unassigned_count += 1
                
                st.info(f"선택한 기간 내 미배정 방문: {unassigned_count}건")
                
                if st.button("🎲 랜덤 배정 시작", type="primary"):
                    import random
                    
                    assigned_count = 0
                    for schedule in active_schedules:
                        for visit in schedule['visits']:
                            visit_date = datetime.strptime(visit['date'], "%Y-%m-%d").date()
                            
                            if assign_start <= visit_date <= assign_end:
                                # 이미 배정된 경우 스킵 (덮어쓰지 않음)
                                if visit.get('assigned_people') and len(visit.get('assigned_people', [])) > 0:
                                    continue
                                
                                # 2명 랜덤 선택
                                selected_people = random.sample(people, min(2, len(people)))
                                visit['assigned_people'] = [p['name'] for p in selected_people]
                                assigned_count += 1
                    
                    save_schedules(schedules)
                    st.success(f"✅ {assigned_count}건의 방문에 인원이 배정되었습니다!")
                    st.balloons()
                    st.rerun()
                
                st.divider()
                st.caption("⚠️ 주의: 이미 배정된 방문은 덮어쓰지 않습니다. 재배정하려면 캘린더에서 개별 삭제 후 다시 배정하세요.")

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
    st.header("📅 캘린더")
    
    active_schedules = [s for s in schedules if s.get("status") != "completed"]
    
    if not active_schedules:
        st.info("현재 진행중인 라인이 없습니다.")
    else:
        # 월 선택
        col1, col2 = st.columns([1, 3])
        with col1:
            selected_year = st.selectbox("년도", range(2024, 2030), index=2)  # 2026 default
        with col2:
            selected_month = st.selectbox("월", range(1, 13), index=datetime.now().month - 1)
        
        # 선택한 월의 첫날과 마지막날
        first_day = datetime(selected_year, selected_month, 1).date()
        if selected_month == 12:
            last_day = datetime(selected_year + 1, 1, 1).date() - timedelta(days=1)
        else:
            last_day = datetime(selected_year, selected_month + 1, 1).date() - timedelta(days=1)
        
        # 달력 시작일 (월요일부터 시작하도록 조정)
        calendar_start = first_day - timedelta(days=first_day.weekday())
        
        # 날짜별 방문 정리 (schedule_idx와 visit_idx 포함)
        calendar_data = {}
        for schedule_idx, schedule in enumerate(active_schedules):
            for visit_idx, visit in enumerate(schedule['visits']):
                visit_date = datetime.strptime(visit['date'], "%Y-%m-%d").date()
                
                if calendar_start <= visit_date <= last_day + timedelta(days=7):
                    if visit_date not in calendar_data:
                        calendar_data[visit_date] = []
                    
                    # 프로토콜 정보 가져오기
                    template_name = schedule['template']
                    day_num = str(visit['day'])
                    
                    # 기본 프로토콜 (템플릿에서)
                    default_protocol = None
                    if template_name in protocols and day_num in protocols[template_name]:
                        default_protocol = protocols[template_name][day_num]
                    
                    # 사용자가 선택한 프로토콜 (있으면)
                    selected_protocol_day = visit.get('selected_protocol', None)
                    selected_protocol = None
                    if selected_protocol_day and template_name in protocols and selected_protocol_day in protocols[template_name]:
                        selected_protocol = protocols[template_name][selected_protocol_day]
                    
                    calendar_data[visit_date].append({
                        "schedule_idx": schedule_idx,
                        "visit_idx": visit_idx,
                        "name": schedule['name'],
                        "day": visit['day'],
                        "template": template_name,
                        "default_protocol": default_protocol,
                        "selected_protocol": selected_protocol,
                        "selected_protocol_day": selected_protocol_day,
                        "memo": visit.get('memo', ''),
                        "assigned_people": visit.get('assigned_people', [])
                    })
        
        # CSS 스타일
        st.markdown("""
        <style>
        .calendar-day {
            min-height: 120px;
            padding: 5px;
            border: 1px solid #ddd;
            background-color: white;
        }
        .calendar-day-header {
            font-weight: bold;
            margin-bottom: 5px;
        }
        .weekend {
            background-color: #ffebee !important;
        }
        .other-month {
            background-color: #f5f5f5 !important;
            opacity: 0.6;
        }
        .today {
            border: 3px solid #1976d2 !important;
            background-color: #e3f2fd !important;
        }
        .visit-item {
            font-size: 0.85em;
            padding: 2px 4px;
            margin: 2px 0;
            background-color: #e8f5e9;
            border-radius: 3px;
            cursor: pointer;
        }
        </style>
        """, unsafe_allow_html=True)
        
        # 요일 헤더
        st.markdown("### " + first_day.strftime('%Y년 %m월'))
        weekdays = ["월", "화", "수", "목", "금", "토", "일"]
        cols = st.columns(7)
        for i, day in enumerate(weekdays):
            with cols[i]:
                st.markdown(f"**{day}**")
        
        # 달력 그리기 (주 단위)
        current_date = calendar_start
        today = datetime.now().date()
        
        while current_date <= last_day + timedelta(days=7):
            cols = st.columns(7)
            
            for i in range(7):
                with cols[i]:
                    day_date = current_date + timedelta(days=i)
                    
                    # 날짜 스타일 결정
                    is_weekend = day_date.weekday() >= 5
                    is_other_month = day_date.month != selected_month
                    is_today = day_date == today
                    
                    # 날짜 표시
                    date_str = day_date.strftime('%d')
                    if is_today:
                        st.markdown(f"**:blue[{date_str}일]** 📍")
                    elif is_weekend:
                        st.markdown(f"**:red[{date_str}일]**")
                    elif is_other_month:
                        st.markdown(f":gray[{date_str}일]")
                    else:
                        st.markdown(f"**{date_str}일**")
                    
                    # 방문 일정이 있으면 표시
                    if day_date in calendar_data:
                        visits = calendar_data[day_date]
                        
                        if len(visits) > 0:
                            st.caption(f"방문 {len(visits)}건")
                        
                        for visit_data in visits:
                            schedule_idx = visit_data['schedule_idx']
                            visit_idx = visit_data['visit_idx']
                            
                            # 배정된 인원 색상 아이콘
                            people_icons = ""
                            if visit_data['assigned_people']:
                                for person_name in visit_data['assigned_people']:
                                    # 인원 목록에서 인덱스 찾기
                                    person_idx = next((i for i, p in enumerate(people) if p['name'] == person_name), None)
                                    if person_idx is not None:
                                        color_emoji = PERSON_COLORS[person_idx % len(PERSON_COLORS)]
                                        people_icons += color_emoji
                            
                            # 간단한 요약 표시 (인원 아이콘 포함)
                            visit_summary = f"{people_icons} {visit_data['name']}(D{visit_data['day']})" if people_icons else f"{visit_data['name']}(D{visit_data['day']})"
                            
                            # 각 방문마다 고유 키 생성
                            unique_key = f"{day_date}_{schedule_idx}_{visit_idx}"
                            
                            # Expander로 상세 정보 표시
                            with st.expander(f"📌 {visit_summary}", expanded=False):
                                st.caption(f"**{visit_data['template']}** 템플릿")
                                
                                st.divider()
                                
                                # 담당자 배정
                                st.markdown("**👥 담당자**")
                                
                                if not people:
                                    st.warning("등록된 인원이 없습니다. '인원 관리' 메뉴에서 추가하세요.")
                                else:
                                    # 현재 배정된 사람들
                                    current_assigned = visit_data['assigned_people']
                                    
                                    # 멀티셀렉트로 담당자 선택
                                    selected_people_names = st.multiselect(
                                        "담당자 선택",
                                        options=[p['name'] for p in people],
                                        default=current_assigned,
                                        key=f"people_{unique_key}",
                                        label_visibility="collapsed"
                                    )
                                    
                                    # 선택된 사람들의 색상 표시
                                    if selected_people_names:
                                        color_display = ""
                                        for person_name in selected_people_names:
                                            person_idx = next((i for i, p in enumerate(people) if p['name'] == person_name), None)
                                            if person_idx is not None:
                                                color_emoji = PERSON_COLORS[person_idx % len(PERSON_COLORS)]
                                                color_display += f"{color_emoji} {person_name}  "
                                        st.caption(color_display)
                                
                                st.divider()
                                
                                # 프로토콜 선택
                                st.markdown("**📝 프로토콜**")
                                
                                # 사용 가능한 프로토콜 목록 (현재 템플릿의)
                                template_name = visit_data['template']
                                available_protocols = {}
                                
                                if template_name in protocols:
                                    available_protocols = protocols[template_name]
                                
                                protocol_options = ["(기본 프로토콜)"] + [f"Day {day}: {p['title']}" for day, p in sorted(available_protocols.items(), key=lambda x: int(x[0]))]
                                protocol_days = [None] + [day for day in sorted(available_protocols.keys(), key=lambda x: int(x))]
                                
                                # 현재 선택된 프로토콜 인덱스 찾기
                                current_selection = 0
                                if visit_data['selected_protocol_day']:
                                    try:
                                        current_selection = protocol_days.index(visit_data['selected_protocol_day'])
                                    except ValueError:
                                        current_selection = 0
                                
                                selected_protocol_idx = st.selectbox(
                                    "프로토콜 선택",
                                    range(len(protocol_options)),
                                    index=current_selection,
                                    format_func=lambda x: protocol_options[x],
                                    key=f"protocol_{unique_key}",
                                    label_visibility="collapsed"
                                )
                                
                                selected_protocol_day_key = protocol_days[selected_protocol_idx]
                                
                                # 선택된 프로토콜 표시
                                if selected_protocol_day_key:
                                    protocol_to_show = available_protocols[selected_protocol_day_key]
                                elif visit_data['default_protocol']:
                                    protocol_to_show = visit_data['default_protocol']
                                else:
                                    protocol_to_show = None
                                
                                if protocol_to_show:
                                    st.markdown(f"**{protocol_to_show['title']}**")
                                    protocol_lines = protocol_to_show['protocol'].split('\n')
                                    for line in protocol_lines:
                                        if line.strip():
                                            st.markdown(f"  {line.strip()}")
                                else:
                                    st.info("프로토콜 없음")
                                
                                st.divider()
                                
                                # 메모
                                st.markdown("**💬 메모**")
                                memo = st.text_area(
                                    "메모",
                                    value=visit_data['memo'],
                                    height=80,
                                    key=f"memo_{unique_key}",
                                    label_visibility="collapsed",
                                    placeholder="메모..."
                                )
                                
                                # 저장 버튼
                                if st.button("💾 저장", key=f"save_{unique_key}", use_container_width=True):
                                    # 스케줄 업데이트
                                    schedules[schedule_idx]['visits'][visit_idx]['selected_protocol'] = selected_protocol_day_key
                                    schedules[schedule_idx]['visits'][visit_idx]['memo'] = memo
                                    schedules[schedule_idx]['visits'][visit_idx]['assigned_people'] = selected_people_names if people else []
                                    save_schedules(schedules)
                                    st.success("✅")
                                    st.rerun()
            
            current_date += timedelta(days=7)
            
            # 다음 달로 넘어가면 중단
            if current_date.month != selected_month and current_date > last_day:
                break
        
        # 범례
        st.divider()
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.markdown("📍 **오늘**")
        with col2:
            st.markdown(":red[**주말**]")
        with col3:
            st.markdown("📌 **방문 예정**")
        with col4:
            total_visits = sum(len(v) for v in calendar_data.values() if any(d >= today for d in [k for k in calendar_data.keys() if k >= today]))
            st.metric("이번 달 총 방문", len([v for d, v in calendar_data.items() if d.month == selected_month]))

# 푸터
st.sidebar.divider()
st.sidebar.caption("🧬 Organoid Schedule Manager v2.0")
st.sidebar.caption(f"활성 라인: {len([s for s in schedules if s.get('status') != 'completed'])}개")
