import streamlit as st
import random
import os
import json
from pathlib import Path
from collections import Counter

st.set_page_config(page_title="포커 룸", page_icon="🃏", layout="centered")

# =========================================================================
# [중요] 타 프로그램(디스코드 봇 등) 데이터베이스 파일 연동 설정
# =========================================================================
DISCORD_DATA_FILE_PATH = Path("user_data.json")

# ⭐ [필독] 예나님의 본계정 디스코드 고유 ID(숫자)를 여기에 꼭 적어주세요!
# 예나님 본계정으로 로그인했을 때만 딜러 제어 콘솔이 열리게 됩니다.
ADMIN_DISCORD_ID = "1246351887461257262"

def load_all_discord_data():
    if not DISCORD_DATA_FILE_PATH.exists():
        return {}
    try:
        with DISCORD_DATA_FILE_PATH.open("r", encoding="utf-8") as file:
            return json.load(file)
    except Exception as e:
        st.error(f"데이터베이스 로드 실패 (파일 경로를 확인하세요): {e}")
        return {}

def save_all_discord_data(data):
    try:
        temp_file = DISCORD_DATA_FILE_PATH.with_name(f"{DISCORD_DATA_FILE_PATH.name}.tmp")
        with temp_file.open("w", encoding="utf-8") as file:
            json.dump(data, file, indent=4, ensure_ascii=False)
        temp_file.replace(DISCORD_DATA_FILE_PATH)
    except Exception as e:
        st.error(f"데이터베이스 저장 실패: {e}")

# =========================================================================
# 서버 공용 게임 룸 데이터 정의 (실시간 공유 저장소)
# =========================================================================
@st.cache_resource
def get_poker_game_state():
    return {
        "room_created": False,   
        "deck": [],
        "game_started": False,
        "pot": 0,               
        "current_max_bet": 0,   
        "game_log": ["포커 매니저가 가동되었습니다."],
        "chat_room": [("시스템", "디스코드 연동 포커 룸입니다.")],
        "waiting_room": {},     
        "players": {},          
        "player_cards": {}      
    }

shared = get_poker_game_state()

if "my_discord_id" not in st.session_state:
    st.session_state.my_discord_id = "" 
if "my_display_name" not in st.session_state:
    st.session_state.my_display_name = ""

# =========================================================================
# 포커 족보 판정 알고리즘
# =========================================================================
def evaluate_5_card_hand(cards):
    if len(cards) != 5: return (0, "카드 오류")
    val_map = {'A': 14, 'K': 13, 'Q': 12, 'J': 11, '10': 10, '9': 9, '8': 8, '7': 7, '6': 6, '5': 5, '4': 4, '3': 3, '2': 2}
    suits = [c['suit'] for c in cards]
    values = sorted([val_map[c['value']] for c in cards], reverse=True)
    val_counts = Counter(values)
    suit_counts = Counter(suits)
    
    is_flush = any(count == 5 for count in suit_counts.values())
    is_straight = False
    straight_high = 0
    if len(val_counts) == 5:
        if values[0] - values[4] == 4:
            is_straight = True
            straight_high = values[0]
        elif values == [14, 5, 4, 3, 2]:
            is_straight = True
            straight_high = 5

    most_common = val_counts.most_common()
    if is_flush and is_straight and straight_high == 14: return (10, "로열 스트레이트 플러시")
    if is_flush position and is_straight: return (9, "스트레이트 플러시")
    if most_common[0][1] == 4: return (8, "포카드")
    if most_common[0][1] == 3 and most_common[1][1] == 2: return (7, "풀하우스")
    if is_flush: return (6, "플러시")
    if is_straight: return (5, "스트레이트")
    if most_common[0][1] == 3: return (4, "트리플")
    if most_common[0][1] == 2 and most_common[1][1] == 2: return (3, "투페어")
    if most_common[0][1] == 2: return (2, "원페어")
    return (1, "하이카드")

def log_action(msg):
    shared["game_log"].insert(0, msg)

# =========================================================================
# 대기실 전용 포커 족보 및 기본 규칙 가이드 UI 함수
# =========================================================================
def render_poker_guide():
    with st.expander("초보자를 위한 정통 5카드 포커 족보 가이드 (가장 강한 패 순서) 모를 시 미리 캡쳐", expanded=False):
        st.markdown("""
        ### 카드 서열 규칙 (동일 족보 시 승패 결정)
        * **숫자 서열 (왼쪽이 가장 강함):** **A** > **K** > **Q** > **J** > **10** > **9** > **8** > **7** > **6** > **5** > **4** > **3** > **2**
        * **문양 서열 (왼쪽이 가장 강함):** **♠ (스페이드)** > **◆ (다이아)** > **♥ (하트)** > **♣ (클로버)**

        ---

        ### 포커 족보 순위
        1. **로열 스트레이트 플러시**
           * 문양이 모두 같으면서 A, K, Q, J, 10 이 연달아 모인 최고의 패.
        2. **스트레이트 플러시**
           * 문양이 모두 같으면서 숫자가 순서대로 이어지는 패. (예: 하트 5, 6, 7, 8, 9)
        3. **포카드 (Four of a Kind)**
           * 문양과 상관없이 같은 숫자의 카드가 4장 모인 패. (예: 7이 4장)
        4. **풀하우스 (Full House)**
           * 같은 숫자 3장(트리플)과 같은 숫자 2장(원페어)이 동시에 들어온 패. (예: Q 3장 + 5 2장)
        5. **플러시 (Flush)**
           * 숫자와 상관없이 5장의 문양(스페이드, 다이아, 하트, 클로버)이 모두 일치하는 패.
        6. **스트레이트 (Straight)**
           * 문양과 상관없이 5장의 숫자가 줄줄이 이어지는 패. (예: 3, 4, 5, 6, 7)
        7. **트리플 (Three of a Kind)**
           * 문양과 상관없이 같은 숫자의 카드가 3장 모인 패. (예: J 3장)
        8. **투페어 (Two Pair)**
           * 같은 숫자 2장 쌍이 2구역 있는 패. (예: J 2장 + 9 2장)
        9. **원페어 (One Pair)**
           * 같은 숫자 2장 쌍이 1구역 있는 패. (예: A 2장)
        10. **하이카드**
            * 아무 족보도 완성되지 않았을 때, 가진 카드 중 가장 높은 숫자로 겨루는 패.
        ---
        * **쉽게 외우는 순서:** 문양도 같고 숫자도 이어진 패 > 숫자 여러 개 같음 > 문양만 같음 > 숫자만 이어짐 > 페어류 묶음
        """)

def start_classic_game():
    if len(shared["players"]) < 2: return "테이블에 최소 2명 이상 참여해야 합니다."
    suits = ['♠', '◆', '♥', '♣']
    values = ['A', '2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K']
    deck = [{"suit": s, "value": v} for s in suits for v in values]
    random.shuffle(deck)
    
    shared["deck"] = deck
    shared["game_started"] = True
    shared["pot"] = 0
    shared["current_max_bet"] = 0
    shared["player_cards"] = {}
    
    for dc_id in shared["players"]:
        shared["players"][dc_id]["bet"] = 0
        shared["players"][dc_id]["folded"] = False
        shared["players"][dc_id]["final_hand_text"] = ""
        shared["player_cards"][dc_id] = [shared["deck"].pop(0) for _ in range(5)]
        
    log_action("게임 시작! 테이블 인원에게 5장의 카드가 분배되었습니다. 배팅을 시작하세요.")
    return None

def open_all_hands_and_settle():
    best_score = -1
    winners = []
    
    for dc_id, info in shared["players"].items():
        if not info["folded"]:
            user_cards = shared["player_cards"].get(dc_id, [])
            score, hand_name = evaluate_5_card_hand(user_cards)
            info["final_hand_text"] = hand_name
            
            if score > best_score:
                best_score = score
                winners = [dc_id]
            elif score == best_score:
                winners.append(dc_id)
                
    if winners:
        prize = shared["pot"] // len(winners)
        discord_db = load_all_discord_data()
        
        winner_names = []
        for w_id in winners:
            if w_id in discord_db:
                discord_db[w_id]["points"] += prize
                winner_names.append(discord_db[w_id]["name"])
        
        save_all_discord_data(discord_db) 
        log_action(f"게임 종료! 승자: {', '.join(winner_names)} (+{prize:,} 포인트 지급 완료)")
        
    shared["game_started"] = False
    shared["pot"] = 0
    shared["current_max_bet"] = 0

# =========================================================================
# 화면 UI 레이아웃
# =========================================================================
st.title("포커 시스템")

# --- [대기실 단계 1] 로그인 전 대기실 상태 ---
if not st.session_state.my_discord_id:
    st.subheader("디스코드 연동 자동 로그인")
    st.caption("디스코드 닉네임(Name)을 입력하면 실시간 데이터베이스를 검색하여 로그인합니다.")
    
    render_poker_guide()
    
    input_dc_name = st.text_input("본인의 디스코드 닉네임(Name)을 입력하세요:", placeholder="예: 홍길동").strip()
    
    if st.button("자동 로그인 및 대기실 입장", type="primary", use_container_width=True):
        if input_dc_name:
            discord_db = load_all_discord_data()
            found_id = None
            
            for uid, info in discord_db.items():
                db_name = str(info.get("name", "")).strip()
                if db_name.lower() == input_dc_name.lower():
                    found_id = uid
                    break
            
            if found_id:
                st.session_state.my_discord_id = found_id
                st.session_state.my_display_name = discord_db[found_id]["name"]
                
                shared["waiting_room"][found_id] = discord_db[found_id]["name"]
                log_action(f"{discord_db[found_id]['name']}님이 대기실에 입장했습니다.")
                st.rerun()
            else:
                st.error(f"'{input_dc_name}' 이름은 외부 연동 데이터베이스에 존재하지 않습니다. 디스코드 봇에 등록된 이름인지 혹은 파일 연동 경로가 올바른지 확인해 주세요.")
    st.stop()

# 최신 포인트 동기화
current_db = load_all_discord_data()
my_current_points = current_db.get(st.session_state.my_discord_id, {}).get("points", 0)

# --- [대기실 단계 2] 로그인 후 테이블 입장 전 대기 상태 ---
st.markdown(f"접속 유저: **{st.session_state.my_display_name}** | 내 디스코드 잔여 포인트: **{my_current_points:,} P**")

col_sync, col_msg = st.columns([1, 4])
with col_sync:
    if st.button("화면 동기화", use_container_width=True): st.rerun()
with col_msg:
    st.info(f"최신 로그: {shared['game_log'][0]}")

render_poker_guide()

# =========================================================================
# 실시간 대화방 (채팅 시스템)
# =========================================================================
st.markdown("### 라이브 대화방")
chat_container = st.container(height=120)
for speaker, text in shared["chat_room"][-10:]:
    chat_container.write(f"**[{speaker}]**: {text}")

col_input, col_send = st.columns([4, 1])
with col_input:
    msg_input = st.text_input("메시지 입력", label_visibility="collapsed", placeholder="채팅 내용을 입력하세요...")
with col_send:
    if st.button("전송", use_container_width=True):
        if msg_input.strip():
            shared["chat_room"].append((st.session_state.my_display_name, msg_input.strip()))
            st.rerun()

# =========================================================================
# 관리자 전용 제어 센터 (방 만들기 및 인원 추가)
# =========================================================================
st.markdown("---")

# 🔒 [보안 적용] 접속한 사람의 ID가 본계정 ID(ADMIN_DISCORD_ID)일 때만 제어 센터 조작 허용!
if st.session_state.my_discord_id == ADMIN_DISCORD_ID:
    with st.expander("관리자 및 딜러 전용 제어 콘솔", expanded=not shared["room_created"]):
        if not shared["room_created"]:
            st.warning("현재 개설된 포커 방이 없습니다. 관리자가 방을 먼저 개설해야 합니다.")
            if st.button("새로운 포커 게임 룸 개설하기", type="primary", use_container_width=True):
                shared["room_created"] = True
                log_action("관리자가 새로운 포커 게임 룸을 개설했습니다.")
                st.rerun()
        else:
            st.success("현재 포커 게임 룸이 활성화되어 있습니다.")
            
            st.markdown("#### 대기실 인원 관리 및 테이블 초대")
            if shared["waiting_room"]:
                waiting_ids = list(shared["waiting_room"].keys())
                waiting_names = [shared["waiting_room"][uid] for uid in waiting_ids]
                
                selected_names = st.multiselect("테이블에 추가할 대기실 인원을 선택하세요:", waiting_names)
                
                if st.button("선택한 인원 게임 테이블에 추가", use_container_width=True):
                    for name in selected_names:
                        for uid, uname in shared["waiting_room"].items():
                            if uname == name and uid not in shared["players"]:
                                shared["players"][uid] = {
                                    "name": uname,
                                    "bet": 0,
                                    "folded": False,
                                    "final_hand_text": ""
                                }
                                log_action(f"딜러가 {uname}님을 게임 테이블에 참여시켰습니다.")
                    st.rerun()
            else:
                st.caption("현재 로그인 후 대기실에서 대기 중인 유저가 없습니다.")
                
            st.markdown("---")
            st.markdown("#### 게임 라운드 제어")
            d_col1, d_col2, d_col3 = st.columns(3)
            with d_col1:
                if not shared["game_started"]:
                    if st.button("포커 매치 시작", use_container_width=True, type="primary"):
                        err = start_classic_game()
                        if err: st.error(err)
                        else: st.rerun()
                else:
                    st.button("배팅 레이스 진행 중", disabled=True, use_container_width=True)

            with d_col2:
                if shared["game_started"]:
                    if st.button("쇼다운 (패 오픈 및 상금 정산)", use_container_width=True, type="primary"):
                        open_all_hands_and_settle()
                        st.rerun()
                else:
                    st.button("쇼다운 대기", disabled=True, use_container_width=True)

            with d_col3:
                if st.button("포커 룸 폐쇄 (전체 리셋)", use_container_width=True, type="secondary"):
                    shared["room_created"] = False
                    shared["deck"] = []
                    shared["game_started"] = False
                    shared["pot"] = 0
                    shared["current_max_bet"] = 0
                    shared["players"] = {}
                    shared["waiting_room"] = {}
                    shared["player_cards"] = {}
                    shared["chat_room"] = [("SYSTEM", "방이 폐쇄되었습니다. 다시 개설해 주세요.")]
                    st.session_state.my_discord_id = ""
                    st.session_state.my_display_name = ""
                    st.rerun()
else:
    # 패드 계정이나 일반 계정으로 접속 시 콘솔 대신 노출되는 가림막 안내 문구
    st.info("♣ 딜러가 게임 테이블 조작 및 라운드를 제어하고 있습니다. 대기실 혹은 테이블 현황을 확인하며 대기해 주세요.")

# =========================================================================
# 테이블 베팅 및 게임 진행 상황판
# =========================================================================
st.markdown("---")
st.markdown("### 게임 테이블 상황판")

if not shared["room_created"]:
    st.info("방이 개설되지 않아 활성화된 테이블이 없습니다.")
else:
    c_pot, c_max = st.columns(2)
    c_pot.metric("현재 누적 팟 (POT)", f"{shared['pot']:,} P")
    c_max.metric("현재 최고 배팅 금액", f"{shared['current_max_bet']:,} P")

    with st.expander("테이블 참여 유저 현황", expanded=True):
        if shared["players"]:
            for dc_id, p_info in shared["players"].items():
                me_lbl = " (나)" if dc_id == st.session_state.my_discord_id else ""
                fold_lbl = " [기권]" if p_info["folded"] else ""
                hand_lbl = f" ➡️ **{p_info['final_hand_text']}**" if p_info["final_hand_text"] else ""
                st.write(f"• **{p_info['name']}{me_lbl}** : 현재 {p_info['bet']:,} P 배팅 중{fold_lbl}{hand_lbl}")
        else:
            st.caption("현재 게임 테이블에 참가한 인원이 없습니다. 관리자가 대기실 인원을 추가해야 합니다.")

# =========================================================================
# 배팅 조작 및 내 카드 확인 영역
# =========================================================================
if shared["game_started"] and st.session_state.my_discord_id in shared["player_cards"]:
    my_info = shared["players"][st.session_state.my_discord_id]
    
    if not my_info["folded"]:
        st.markdown("---")
        st.markdown("### 내 시크릿 카드 (본인에게만 표시)")
        my_5_cards = shared["player_cards"][st.session_state.my_discord_id]
        
        card_cols = st.columns(5)
        for idx, card in enumerate(my_5_cards):
            with card_cols[idx]:
                is_red = card['suit'] in ['♥', '◆']
                color = "red" if is_red else "black"
                st.markdown(f'<div style="background-color: white; color: {color}; border-radius: 10px; padding: 20px 5px; text-align: center; font-size: 24px; font-weight: bold; box-shadow: 2px 2px 6px rgba(0,0,0,0.15); border: 1px solid #ddd;">{card["suit"]}{card["value"]}</div>', unsafe_allow_html=True)
                
        _, current_hand_title = evaluate_5_card_hand(my_5_cards)
        st.caption(f"내 현재 패 조합: {current_hand_title}")

        st.markdown("### 포인트 배팅 액션")
        call_needed = shared["current_max_bet"] - my_info["bet"]
        
        b_col1, b_col2, b_col3 = st.columns(3)
        with b_col1:
            if call_needed == 0:
                if st.button("CHECK (체크하고 패스)", use_container_width=True):
                    log_action(f"{st.session_state.my_display_name}님이 체크했습니다.")
                    st.rerun()
            else:
                if st.button(f"CALL ({call_needed:,} P 지불)", use_container_width=True, type="primary"):
                    if my_current_points >= call_needed:
                        current_db[st.session_state.my_discord_id]["points"] -= call_needed
                        save_all_discord_data(current_db)
                        
                        my_info["bet"] += call_needed
                        shared["pot"] += call_needed
                        log_action(f"{st.session_state.my_display_name}님이 콜을 선언했습니다.")
                        st.rerun()
                    else: st.error("포인트가 부족합니다.")
                    
        with b_col2:
            raise_input = st.number_input("추가 레이즈 포인트:", min_value=100, max_value=max(100, int(my_current_points)), step=100, value=100)
            if st.button("RAISE (판돈 올리기)", use_container_width=True):
                cost = call_needed + raise_input
                if my_current_points >= cost:
                    current_db[st.session_state.my_discord_id]["points"] -= cost
                    save_all_discord_data(current_db)
                    
                    total_new_bet = my_info["bet"] + cost
                    my_info["bet"] = total_new_bet
                    shared["pot"] += cost
                    shared["current_max_bet"] = total_new_bet
                    log_action(f"{st.session_state.my_display_name}님이 베팅금을 {total_new_bet:,} P로 올렸습니다.")
                    st.rerun()
                else: st.error("포인트가 부족합니다.")
                
        with b_col3:
            if st.button("FOLD (이번 판 다이)", use_container_width=True):
                my_info["folded"] = True
                log_action(f"{st.session_state.my_display_name}님이 다이(기권)했습니다.")
                st.rerun()
    else:
        st.warning("이번 판은 기권 상태입니다.")
else:
    if shared["room_created"] and not shared["game_started"]:
        if st.session_state.my_discord_id in shared["players"]:
            st.info("게임 테이블에 참가 완료되었습니다. 딜러가 카드를 분배할 때까지 대기하세요.")
        else:
            st.info("현재 대기실에서 대기 중입니다. 관리자가 당신을 테이블에 추가해야 게임에 참여할 수 있습니다.")

# 로그
st.markdown("### 실시간 테이블 타임라인")
st.text_area("Live Logs", value="\n".join(shared["game_log"]), height=100, disabled=True,