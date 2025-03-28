# --- Пользовательский CSS (Финальная попытка темной темы) ---
custom_css = f"""
<style>
    /* --- Базовая темная тема --- */
    body {{ color: #dcddde; }} /* Светлый текст по умолчанию */
    .stApp {{ background-color: #36393f; }} /* Темно-серый фон */

    /* --- Убираем лишние отступы --- */
     .main .block-container {{ padding: 1rem 1rem 4rem 1rem !important; }} /* Увеличил нижний отступ */

    /* --- Поле ввода --- */
    .stChatFloatingInputContainer {{ background-color: #40444b !important; border-top: 1px solid #2f3136 !important; }}
    .stChatFloatingInputContainer textarea {{ background-color: #40444b !important; color: #dcddde !important; border: none !important; }}
    .stChatFloatingInputContainer button[data-testid="send-button"] svg {{ fill: #7289da !important; }}

    /* --- *СУПЕР ИСПРАВЛЕННЫЕ* Стили чата --- */
    [data-testid="stChatMessage"] {{
        background: none !important; /* Убираем фон */
        border: none !important; /* Убираем границу */
        box-shadow: none !important; /* Убираем тень */
        padding: 0.25rem 0 !important; /* Вертикальные отступы */
        margin-bottom: 0.75rem !important; /* Отступ между сообщениями */
        max-width: 100%;
    }}
     /* Контейнер аватара и контента */
     [data-testid="stChatMessage"] > div {{
        display: flex;
        align-items: flex-start; /* Выравниваем аватар и текст по верху */
        gap: 0.75rem; /* Отступ между аватаром и текстом */
     }}
     /* Контейнер контента внутри сообщения */
    [data-testid="stChatMessage"] .stChatMessageContent {{
         background: none !important; /* Убираем фон */
         color: #dcddde !important; /* Яркий текст */
         padding: 0 !important; /* Убираем внутренние отступы */
    }}
    [data-testid="stChatMessage"] .stChatMessageContent p {{ margin-bottom: 0.2rem; }}

    /* Аватары */
    [data-testid="chatAvatarIcon-assistant"] svg,
    [data-testid="chatAvatarIcon-user"] svg {{
         color: #7289da; /* Цвет иконки аватара */
         width: 1.75rem; /* Увеличим размер аватара */
         height: 1.75rem;
         margin-top: 2px; /* Небольшой отступ сверху для выравнивания */
    }}

    /* --- Темные блоки кода (без изменений) --- */
    [data-testid="stChatMessage"] code {{ background-color: #282c34; color: #abb2bf; padding: 0.15em 0.4em; border-radius: 3px; font-size: 0.9em; word-wrap: break-word; }}
    [data-testid="stChatMessage"] pre {{ background-color: #282c34; border: 1px solid #3b4048; border-radius: 5px; padding: 12px; overflow-x: auto; font-size: 0.9em; }}
    [data-testid="stChatMessage"] pre code {{ background-color: transparent; color: #abb2bf; padding: 0; font-size: inherit; border-radius: 0; }}

    /* --- Стили Сайдбара (без изменений) --- */
    [data-testid="stSidebar"] {{ background-color: #2f3136; padding: 1rem; }}
    [data-testid="stSidebar"] h2 {{ text-align: center; margin-bottom: 1rem; font-size: 1.5rem; color: #ffffff; }}
    [data-testid="stSidebar"] .stButton button {{ border-radius: 5px; width: 100%; margin-bottom: 0.5rem; background-color: #40444b; border: none; color: #dcddde; }}
    [data-testid="stSidebar"] .stButton button:hover {{ background-color: #4f545c; }}
    div[data-testid="stSidebar"] div[role="radiogroup"] > label {{ display: block; padding: 8px 12px; border-radius: 5px; margin-bottom: 5px; cursor: pointer; transition: background-color 0.2s ease; border: 1px solid transparent; color: #b9bbbe; }}
    div[data-testid="stSidebar"] div[role="radiogroup"] > label:hover {{ background-color: rgba(255, 255, 255, 0.05); }}
    div[data-testid="stSidebar"] div[role="radiogroup"] input[type="radio"]:checked + label {{ background-color: #3a3d43; border: 1px solid #3a3d43; font-weight: 500; color: #ffffff; }}
    [data-testid="stSidebar"] .stRadio [data-testid="stWidgetLabel"] {{ color: #b9bbbe; font-size: 0.9rem; margin-bottom: 0.3rem; }}

</style>
"""

# --- Весь остальной код Python остается БЕЗ ИЗМЕНЕНИЙ ---

# ... (вставьте сюда весь остальной код Python из предыдущего ответа) ...

# Вот он еще раз для полноты:
# -*- coding: utf-8 -*-
import streamlit as st
import requests
import os
import platform
import json
import datetime
from streamlit_local_storage import LocalStorage

# --- Ключ API из секретов ---
# Убедитесь, что секрет OPENROUTER_API_KEY добавлен в Streamlit Cloud
# -----------------------------

# --- Константы ---
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"
MODES = {
    "Стандарт (V3)": "deepseek/deepseek-chat-v3-0324:free",
    "DeepThink (R1)": "deepseek/deepseek-r1:free",
}
DEFAULT_MODE = "Стандарт (V3)"
LOCAL_STORAGE_KEY = "multi_chat_storage_v6" # Ключ для localStorage
DEFAULT_CHAT_NAME = "Новый чат"

# --- Настройка страницы ---
st.set_page_config(
    page_title="Чат с ИИ",
    page_icon="💬",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- Инициализация LocalStorage ---
localS = LocalStorage()

# --- Пользовательский CSS (ВСТАВЬТЕ ОБНОВЛЕННЫЙ БЛОК СЮДА) ---
# custom_css = f""" ... """ # <--- Сюда вставляется CSS выше
st.markdown(custom_css, unsafe_allow_html=True)


# --- Функции для работы с чатами (без изменений) ---
def load_all_chats():
    data_str = localS.getItem(LOCAL_STORAGE_KEY)
    if data_str:
        try:
            data = json.loads(data_str)
            if isinstance(data, dict) and "chats" in data and "active_chat" in data and isinstance(data["chats"], dict):
                return data["chats"], data["active_chat"]
        except json.JSONDecodeError: pass
    first_chat_name = f"{DEFAULT_CHAT_NAME} 1"
    default_chats = {first_chat_name: []}
    return default_chats, first_chat_name

def save_all_chats(chats_dict, active_chat_name):
    if isinstance(chats_dict, dict) and isinstance(active_chat_name, str):
        data_to_save = {"chats": chats_dict, "active_chat": active_chat_name}
        try:
            localS.setItem(LOCAL_STORAGE_KEY, json.dumps(data_to_save)); return True
        except Exception as e: return False
    return False

def generate_new_chat_name(existing_names):
    i = 1
    while f"{DEFAULT_CHAT_NAME} {i}" in existing_names: i += 1
    return f"{DEFAULT_CHAT_NAME} {i}"

# --- Инициализация состояния ---
if "all_chats" not in st.session_state:
    st.session_state.all_chats, st.session_state.active_chat = load_all_chats()
    if st.session_state.active_chat not in st.session_state.all_chats:
        if st.session_state.all_chats:
            st.session_state.active_chat = list(st.session_state.all_chats.keys())[0]
        else:
            new_name = generate_new_chat_name([])
            st.session_state.all_chats = {new_name: []}
            st.session_state.active_chat = new_name
            save_all_chats(st.session_state.all_chats, st.session_state.active_chat)
if "selected_mode" not in st.session_state:
    st.session_state.selected_mode = DEFAULT_MODE

# --- Сайдбар: Управление чатами и режимом ---
with st.sidebar:
    st.markdown("## 💬 Чаты")
    chat_names = list(st.session_state.all_chats.keys())
    try: active_chat_index = chat_names.index(st.session_state.active_chat)
    except ValueError: active_chat_index = 0

    selected_chat = st.radio(
        "Выберите чат:", options=chat_names, index=active_chat_index,
        label_visibility="collapsed", key="chat_selector"
    )

    if selected_chat != st.session_state.active_chat:
        st.session_state.active_chat = selected_chat
        save_all_chats(st.session_state.all_chats, st.session_state.active_chat)
        st.rerun()

    st.divider()

    if st.button("➕ Новый чат", key="new_chat_button"):
        new_name = generate_new_chat_name(chat_names)
        st.session_state.all_chats[new_name] = []
        st.session_state.active_chat = new_name
        save_all_chats(st.session_state.all_chats, st.session_state.active_chat)
        st.rerun()

    if len(chat_names) > 0:
        if st.button("🗑️ Удалить текущий чат", type="secondary", key="delete_chat_button"):
            if st.session_state.active_chat in st.session_state.all_chats:
                del st.session_state.all_chats[st.session_state.active_chat]
                remaining_chats = list(st.session_state.all_chats.keys())
                if remaining_chats: st.session_state.active_chat = remaining_chats[0]
                else:
                    new_name = generate_new_chat_name([])
                    st.session_state.all_chats = {new_name: []}
                    st.session_state.active_chat = new_name
                save_all_chats(st.session_state.all_chats, st.session_state.active_chat)
                st.rerun()

    st.divider()

    mode_options = list(MODES.keys())
    try: current_mode_index = mode_options.index(st.session_state.selected_mode)
    except ValueError: current_mode_index = 0

    selected_mode_radio = st.radio(
        "Режим работы:", options=mode_options, index=current_mode_index,
        key="mode_selector"
    )
    if selected_mode_radio != st.session_state.selected_mode:
        st.session_state.selected_mode = selected_mode_radio
        st.rerun()

# --- Основная область: Чат ---
current_mode_name = st.session_state.get("selected_mode", DEFAULT_MODE)
current_model_id = MODES.get(current_mode_name, MODES[DEFAULT_MODE])

current_messages = st.session_state.all_chats.get(st.session_state.active_chat, [])
if not current_messages:
     current_messages.append(
         {"role": "assistant", "content": f"👋 Привет! Я {current_mode_name}. Начнем новый чат!"}
     )
     st.session_state.all_chats[st.session_state.active_chat] = current_messages
     save_all_chats(st.session_state.all_chats, st.session_state.active_chat)

chat_display_container = st.container()
with chat_display_container:
    for message in current_messages:
        avatar = "🧑‍💻" if message["role"] == "user" else "🐳"
        with st.chat_message(message["role"], avatar=avatar):
            st.markdown(message["content"])

# --- Функция стриминга (без изменений) ---
def stream_ai_response(model_id_func, chat_history_func):
    try:
        if "OPENROUTER_API_KEY" not in st.secrets:
             st.error("⛔ Секрет 'OPENROUTER_API_KEY' не найден.", icon="🚨")
             yield None; return
        api_key_from_secrets = st.secrets["OPENROUTER_API_KEY"]
        if not api_key_from_secrets:
             st.error("⛔ Секрет 'OPENROUTER_API_KEY' пустой.", icon="🚨")
             yield None; return
    except Exception as e:
        st.error(f"🤯 Ошибка доступа к секретам: {e}", icon="💥")
        yield None; return

    headers = {"Authorization": f"Bearer {api_key_from_secrets}", "Content-Type": "application/json"}
    if not isinstance(chat_history_func, list): yield None; return
    payload = {"model": model_id_func, "messages": chat_history_func, "stream": True}

    try:
        response = requests.post(OPENROUTER_API_URL, headers=headers, json=payload, stream=True, timeout=90)
        response.raise_for_status()
        for line in response.iter_lines():
            if line:
                decoded_line = line.decode('utf-8')
                if decoded_line.startswith("data: "):
                    try:
                        json_data = decoded_line[len("data: "):]
                        if json_data.strip() == "[DONE]": break
                        chunk = json.loads(json_data)
                        delta_content = chunk.get("choices", [{}])[0].get("delta", {}).get("content")
                        if delta_content: yield delta_content
                    except: continue
    except requests.exceptions.RequestException as e: yield None
    except Exception as e: yield None

# --- Поле ввода пользователя ---
if prompt := st.chat_input(f"Спроси {current_mode_name}..."):
    active_chat_name = st.session_state.active_chat
    active_chat_history = st.session_state.all_chats.get(active_chat_name, [])
    active_chat_history.append({"role": "user", "content": prompt})
    st.session_state.all_chats[active_chat_name] = active_chat_history
    save_all_chats(st.session_state.all_chats, active_chat_name)
    st.rerun()

# --- Логика ответа ИИ (после rerun) ---
active_chat_history = st.session_state.all_chats.get(st.session_state.active_chat, [])
if active_chat_history and active_chat_history[-1]["role"] == "user":
     with chat_display_container:
         with st.chat_message("assistant", avatar="🐳"):
             full_response = st.write_stream(stream_ai_response(current_model_id, active_chat_history))

     if full_response:
         active_chat_history.append({"role": "assistant", "content": full_response})
         st.session_state.all_chats[active_chat_name] = active_chat_history
         save_all_chats(st.session_state.all_chats, active_chat_name)
         # st.rerun() не нужен

# --- Футер ---
# Убран
