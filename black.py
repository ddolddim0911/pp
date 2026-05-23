import streamlit as st
import random
import time

st.set_page_config(page_title="공유 시크릿 포커 덱", layout="centered")

# =========================================================================
# [핵심] 1. 모든 플레이어가 공유할 '서버 공용 저장소' 정의
# =========================================================================
@st.cache_resource
def get_shared_game_state():
    """서버에 단 하나만 존재하며 모든 유저가 공유하는 게임 상태 객체"""
    return {
        "deck": [],            # 공용 카드 덱
        "game_started": False, # 게임 시작 여부
        "excluded_suits": [],  # 배제된 문양
        "excluded_values": [], # 배제된 숫자
        "discard_pile": [],    # 바닥에 내려놓은 카드 정보 [{"suit", "value", "owner"}]
        "turn_message": "게임이 시작 대기 중입니다." # 👈 [신규] 공용 알림 메시지 전광판
    }

shared = get_shared_game_state()

# 2. 내 브라우저(세션)에만 저장될 '개인 변수' 초기화
if "my_cards" not in st.session_state:
    st.session_state.my_cards = []
if "user_name" not in st.session_state:
    st.session_state.user_name = "" # 👈 [신규] 유저 개인 이름 저장소

# =========================================================================
# ⚙️ 게임 로직 함수들
# =========================================================================
def build_and_shuffle_deck():
    """설정된 배제 조건을 반영하여 새로운 52장(혹은 그 이하) 덱을 만들고 섞음"""
    suits = ['♠', '◆', '♥', '♣']
    values = ['A', '2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K']
    
    filtered_suits = [s for s in suits if s not in shared["excluded_suits"]]
    filtered_values = [v for v in values if v not in shared["excluded_values"]]
    
    new_deck = [{"suit": s, "value": v} for s in filtered_suits for v in filtered_values]
    random.shuffle(new_deck)
    
    shared["deck"] = new_deck
    shared["game_started"] = True
    shared["discard_pile"] = []
    shared["turn_message"] = "🃏 새로운 게임이 시작되었습니다! 카드를 뽑으세요."

def global_reset():
    """모든 유저의 게임판을 완전히 초기화"""
    shared["deck"] = []
    shared["game_started"] = False
    shared["excluded_suits"] = []
    shared["excluded_values"] = []
    shared["discard_pile"] = []
    shared["turn_message"] = "🚨 게임이 리셋되었습니다. 다시 접속 대기 상태입니다."
    st.session_state.my_cards = []
    st.toast("🚨 서버의 모든 게임 데이터가 리셋되었습니다!")

# =========================================================================
# 🖥️ 화면 UI 구성
# =========================================================================
st.title("🃏")

# -------------------------------------------------------------------------
# [Step 0] 🚪 입장 제한: 이름 입력 전까지는 게임 참가 불가
# -------------------------------------------------------------------------
if not st.session_state.user_name:
    st.subheader("🚪 포커 룸 입장")
    input_name = st.text_input("게임에서 사용할 이름을 입력해주세요:", max_chars=10, placeholder="람")
    
    if st.button("입장하기", use_container_width=True, type="primary"):
        if input_name.strip() == "":
            st.error("이름을 한 글자 이상 입력해주세요!")
        else:
            st.session_state.user_name = input_name.strip()
            st.toast(f"🎉 {st.session_state.user_name}님 환영합니다!")
            st.rerun()
    st.stop() # 이름을 입력하기 전엔 아래의 게임 코드를 실행하지 않고 멈춥니다.

# 이름을 정상적으로 입력한 유저에게만 아래 화면이 보입니다.
st.caption(f"👤 접속자: **{st.session_state.user_name}**님 | 친구들과 공유 중입니다.")

# 📣 [신규] 실시간 공용 전광판 (턴 넘기기 알림용)
st.info(shared["turn_message"])


# -------------------------------------------------------------------------
# [Phase 1] 게임 시작 전: 카드 배제 및 설정 레이아웃
# -------------------------------------------------------------------------
if not shared["game_started"]:
    st.subheader("게임 준비(딜러를 기다려 주세요.)")
    
    ex_suits = st.multiselect("제외할 문양 선택", ['♠', '◆', '♥', '♣'], key="suit_sel")
    ex_values = st.multiselect("제외할 숫자/심볼 선택", ['A', '2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K'], key="val_sel")
    
    if st.button("설정 완료 및 게임 시작 (덱 셔플)", use_container_width=True, type="primary"):
        shared["excluded_suits"] = ex_suits
        shared["excluded_values"] = ex_values
        build_and_shuffle_deck()
        st.rerun()

# -------------------------------------------------------------------------
# [Phase 2] 게임 진행 중: 카드 뽑기, 내기, 턴 넘기기 및 리셋
# -------------------------------------------------------------------------
else:
    remaining = len(shared["deck"])
    st.metric(label="공유 덱에 남은 카드 수", value=f"{remaining} 장")

    # 상단 제어 버튼 배치 (4개 분할)
    col1, col2, col3, col4 = st.columns([2, 2, 2, 1])
    
    with col1:
        if st.button("🔴 카드 한 장 뽑기", use_container_width=True):
            if remaining > 0:
                drawn_card = shared["deck"].pop(0)
                st.session_state.my_cards.append(drawn_card)
                st.rerun()
            else:
                st.error("공유 덱의 카드가 바닥났습니다!")
                
    with col2:
        # 🟢 [신규 추가] 턴 넘기기 버튼
        if st.button("🟢 턴 넘기기", use_container_width=True):
            shared["turn_message"] = f"📢 **{st.session_state.user_name}**님이 다음 사람에게 턴을 넘겼습니다!"
            st.toast(f"턴을 넘겼습니다.")
            st.rerun()
                
    with col2:
        if st.button("🔄 화면 동기화", use_container_width=True):
            st.rerun()

    with col4:
        if st.button("💥 리셋", use_container_width=True, type="secondary"):
            global_reset()
            st.rerun()

    st.markdown("---")

    # -------------------------------------------------------------------------
    # 📤 카드 내기 & 바닥 상황판 (낸 사람 이름 노출)
    # -------------------------------------------------------------------------
    st.markdown("### 카드 제출하기")
    
    if st.session_state.my_cards:
        my_card_options = [f"{c['suit']}{c['value']}" for c in st.session_state.my_cards]
        
        col_sel, col_btn = st.columns([3, 1])
        with col_sel:
            selected_card_str = st.selectbox("낼 카드를 선택하세요", my_card_options, label_visibility="collapsed")
        
        with col_btn:
            if st.button("카드 내기", use_container_width=True, type="primary"):
                chosen_idx = my_card_options.index(selected_card_str)
                submitted_card = st.session_state.my_cards.pop(chosen_idx)
                
                # 👈 [수정] 내 이름을 카드 정보에 각인시켜 공유 바닥에 등록합니다.
                submitted_card["owner"] = st.session_state.user_name 
                shared["discard_pile"].append(submitted_card)
                
                # 전광판 메시지도 갱신해줍니다.
                shared["turn_message"] = f"📤 **{st.session_state.user_name}**님이 바닥에 카드를 냈습니다!"
                st.rerun()
    else:
        st.caption("낼 수 있는 카드가 없습니다. 먼저 카드를 뽑으세요.")

    # 👥 모두가 볼 수 있는 공용 바닥 현황판
    st.markdown("### 오픈된 바닥 카드")
    if shared["discard_pile"]:
        dis_cols = st.columns(max(len(shared["discard_pile"]), 5))
        for idx, c in enumerate(shared["discard_pile"]):
            with dis_cols[idx]:
                is_red = c['suit'] in ['♥', '◆']
                color = "red" if is_red else "black"
                
                # 👈 [수정] 카드 아래쪽에 제출자(owner)의 이름이 표시되도록 카드를 깔끔하게 디자인했습니다.
                st.markdown(f"""
                <div style="
                    background-color: #f1f2f6; color: {color}; border-radius: 8px; 
                    padding: 10px 5px; text-align: center; font-size: 18px; font-weight: bold;
                    border: 2px dashed #ced6e0; margin-bottom: 5px;
                ">
                    {c['suit']}{c['value']}
                </div>
                <div style="text-align: center; font-size: 12px; color: #aaa; font-weight: bold;">
                    👤 {c['owner']}
                </div>
                """, unsafe_allow_html=True)
    else:
        st.info("아직 바닥에 제출된 카드가 없습니다.")

    st.markdown("---")

    # 🔒 내 카드 보기 영역
    st.subheader("🔒 내가 뽑은 카드 (나한테만 보임)")
    
    if not shared["game_started"]:
        st.session_state.my_cards = []

    if st.session_state.my_cards:
        card_cols = st.columns(max(len(st.session_state.my_cards), 5))
        
        for idx, card in enumerate(st.session_state.my_cards):
            with card_cols[idx]:
                is_red = card['suit'] in ['♥', '◆']
                color = "red" if is_red else "black"
                
                card_html = f"""
                <div style="
                    background-color: white; color: {color}; border-radius: 10px; 
                    padding: 15px 5px; text-align: center; font-size: 22px; font-weight: bold;
                    box-shadow: 2px 2px 5px rgba(0,0,0,0.15); border: 1px solid #ddd;
                ">
                    {card['suit']}{card['value']}
                </div>
                """
                st.markdown(card_html, unsafe_allow_html=True)
    else:
        st.info("아직 뽑은 카드가 없습니다. 카드를 뽑으세요!")
