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
LOCAL_STORAGE_KEY = "multi_chat_storage_v7" # Снова обновил ключ
DEFAULT_CHAT_NAME = "Новый чат"

# --- Настройка страницы ---
st.set_page_config(
    page_title="Чат ИИ",
    page_icon="🤖", # Сменил иконку
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- Инициализация LocalStorage ---
localS = LocalStorage()

# --- Пользовательский CSS (Чистая темная тема) ---
custom_css = f"""
<style>
    /* --- Основные цвета --- */
    :root {{
        --bg-color: #1E1E1E; /* Почти черный фон */
        --sidebar-bg-color: #191919; /* Чуть темнее для сайдбара */
        --input-bg-color: #252526; /* Фон поля ввода и кнопок */
        --text-color: #EAEAEA; /* Основной светлый текст */
        --text-color-muted: #A0A0A0; /* Приглушенный текст */
        --accent-color: #007AFF; /* Синий акцент (для выделения) */
        --hover-bg-color: #333333; /* Фон при наведении */
    }}

    /* --- Глобальные стили --- */
    body {{ color: var(--text-color); }}
    .stApp {{ background-color: var(--bg-color); }}
    .main .block-container {{ padding: 1rem 1rem 4rem 1rem !important; }} /* Отступы */

    /* --- Поле ввода --- */
    .stChatFloatingInputContainer {{
        background-color: var(--input-bg-color) !important;
        border-top: 1px solid var(--hover-bg-color) !important;
    }}
    .stChatFloatingInputContainer textarea {{
        background-color: var(--input-bg-color) !important;
        color: var(--text-color) !important;
        border: none !important;
    }}
    .stChatFloatingInputContainer button[data-testid="send-button"] svg {{
        fill: var(--accent-color) !important;
    }}

    /* --- Сообщения чата --- */
    [data-testid="stChatMessage"] {{
        background: none !important; border: none !important; box-shadow: none !important;
        padding: 0.5rem 0 !important; margin-bottom: 1rem !important; max-width: 100%;
    }}
    [data-testid="stChatMessage"] > div {{ display: flex; align-items: flex-start; gap: 0.75rem; }}
    [data-testid="stChatMessage"] .stChatMessageContent {{
         background: none !important; color: var(--text-color) !important; padding: 0 !important;
    }}
    [data-testid="stChatMessage"] .stChatMessageContent p {{ margin-bottom: 0.2rem; line-height: 1.6; }} /* Улучшаем читаемость */

    /* Аватары */
    [data-testid="chatAvatarIcon-assistant"] svg,
    [data-testid="chatAvatarIcon-user"] svg {{
         color: var(--accent-color); width: 1.5rem; height: 1.5rem; margin-top: 3px;
    }}

    /* --- Темные блоки кода --- */
    [data-testid="stChatMessage"] code {{ background-color: #2D2D2D; color: #CCCCCC; padding: 0.2em 0.4em; border-radius: 3px; font-size: 0.85em; word-wrap: break-word; }}
    [data-testid="stChatMessage"] pre {{ background-color: #2D2D2D; border: 1px solid var(--hover-bg-color); border-radius: 5px; padding: 12px; overflow-x: auto; font-size: 0.85em; }}
    [data-testid="stChatMessage"] pre code {{ background: none; color: #CCCCCC; padding: 0; font-size: inherit; border-radius: 0; }}

    /* --- Стили Сайдбара --- */
    [data-testid="stSidebar"] {{ background-color: var(--sidebar-bg-color); padding: 1rem; border-right: 1px solid var(--hover-bg-color); }}
    [data-testid="stSidebar"] h2 {{ text-align: center; margin-bottom: 1rem; font-size: 1.4rem; color: #ffffff; }}
    /* Кнопки в сайдбаре */
    [data-testid="stSidebar"] .stButton button {{
        border-radius: 5px; width: 100%; margin-bottom: 0.5rem; background-color: var(--input-bg-color);
        border: 1px solid var(--hover-bg-color); color: var(--text-color); text-align: center;
    }}
    [data-testid="stSidebar"] .stButton button:hover {{ background-color: var(--hover-bg-color); border-color: var(--hover-bg-color); }}
     /* Радио-кнопки */
    div[data-testid="stSidebar"] div[role="radiogroup"] > label {{
        display: block; padding: 8px 12px; border-radius: 5px; margin-bottom: 5px; cursor: pointer;
        transition: background-color 0.2s ease, color 0.2s ease; border: 1px solid transparent; color: var(--text-color-muted);
    }}
    div[data-testid="stSidebar"] div[role="radiogroup"] > label:hover {{ background-color: var(--hover-bg-color); color: var(--text-color); }}
    /* Выбранный элемент радио */
    div[data-testid="stSidebar"] div[role="radiogroup"] input[type="radio"]:checked + label {{
        background-color: var(--accent-color); border: 1px solid var(--accent-color);
        font-weight: 500; color: #ffffff;
    }}
     /* Заголовок для радио выбора режима */
     [data-testid="stSidebar"] .stRadio [data-testid="stWidgetLabel"] {{
        color: var(--text-color-muted); font-size: 0.9rem; margin-bottom: 0.3rem; font-weight: bold;
     }}
     /* Разделители в сайдбаре */
     [data-testid="stSidebar"] hr {{ background-color: var(--hover-bg-color); }}

</style>
"""
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
        avatar = "🧑‍💻" if message["role"] == "user" else "🤖" # Сменил аватара ассистента
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
         with st.chat_message("assistant", avatar="🤖"): # Сменил аватара
             full_response = st.write_stream(stream_ai_response(current_model_id, active_chat_history))

     if full_response:
         active_chat_history.append({"role": "assistant", "content": full_response})
         st.session_state.all_chats[active_chat_name] = active_chat_history
         save_all_chats(st.session_state.all_chats, active_chat_name)
         # st.rerun() не нужен

# --- Футер ---
# Убран
