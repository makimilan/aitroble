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
LOCAL_STORAGE_KEY = "multi_chat_storage_v8" # Новый ключ
DEFAULT_CHAT_NAME = "Новый чат"

# --- Настройка страницы ---
st.set_page_config(
    page_title="Чат ИИ",
    page_icon="🤖",
    layout="wide", # Широкий макет для чата
    initial_sidebar_state="expanded"
)

# --- Инициализация LocalStorage ---
localS = LocalStorage()

# --- Минимальный CSS для чистоты чата ---
# Убираем лишние отступы и фон у сообщений, остальное - тема Streamlit
custom_css = f"""
<style>
    /* Уменьшаем отступы основного контейнера */
     .main .block-container {{
        padding-top: 1rem; padding-bottom: 4rem; padding-left: 1rem; padding-right: 1rem;
    }}
    /* Убираем фон и лишние отступы у сообщений */
    [data-testid="stChatMessage"] {{
        background: none !important; border: none !important; box-shadow: none !important;
        padding: 0.1rem 0 !important; margin-bottom: 0.75rem !important;
    }}
     /* Выравнивание аватара и текста */
     [data-testid="stChatMessage"] > div {{
        gap: 0.75rem;
     }}
     /* Убираем padding у контента сообщения */
     [data-testid="stChatMessage"] .stChatMessageContent {{
         padding: 0 !important;
    }}
     /* Уменьшаем отступ параграфов в сообщении */
    [data-testid="stChatMessage"] .stChatMessageContent p {{ margin-bottom: 0.2rem; }}

    /* Стили для сайдбара (минимальные) */
    [data-testid="stSidebar"] {{ padding: 1rem; }}
    [data-testid="stSidebar"] h2 {{ text-align: center; margin-bottom: 1rem; font-size: 1.4rem; }}
    [data-testid="stSidebar"] .stButton button {{ width: 100%; margin-bottom: 0.5rem; border-radius: 5px; }}
    /* Заголовок для радио выбора режима */
     [data-testid="stSidebar"] .stRadio [data-testid="stWidgetLabel"] {{ font-size: 0.9rem; margin-bottom: 0.3rem; font-weight: bold; }}

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
    # Проверка и исправление активного чата, если его нет в словаре
    if st.session_state.active_chat not in st.session_state.all_chats:
        if st.session_state.all_chats:
            st.session_state.active_chat = list(st.session_state.all_chats.keys())[0]
        else: # Если чатов вообще нет
            new_name = generate_new_chat_name([])
            st.session_state.all_chats = {new_name: []}
            st.session_state.active_chat = new_name
            save_all_chats(st.session_state.all_chats, st.session_state.active_chat)

if "selected_mode" not in st.session_state:
    # Пытаемся загрузить режим из сохраненных данных (если есть)
    # Это необязательно, но может быть удобно
    # data_str = localS.getItem(LOCAL_STORAGE_KEY)
    # if data_str:
    #     try: data = json.loads(data_str); st.session_state.selected_mode = data.get("mode", DEFAULT_MODE)
    #     except: st.session_state.selected_mode = DEFAULT_MODE
    # else: st.session_state.selected_mode = DEFAULT_MODE
    st.session_state.selected_mode = DEFAULT_MODE # Пока просто ставим по умолчанию

# --- Определяем активный чат ДО обработки ввода/вывода ---
# ИСПРАВЛЕНИЕ NameError: Определяем здесь, чтобы было доступно везде
active_chat_name = st.session_state.active_chat
active_chat_history = st.session_state.all_chats.get(active_chat_name, [])

# --- Сайдбар: Управление чатами и режимом ---
with st.sidebar:
    st.markdown("## 💬 Чаты")
    chat_names = list(st.session_state.all_chats.keys())
    try: active_chat_index = chat_names.index(active_chat_name) # Используем уже определенную переменную
    except ValueError: active_chat_index = 0

    selected_chat = st.radio(
        "Выберите чат:", options=chat_names, index=active_chat_index,
        label_visibility="collapsed", key="chat_selector"
    )

    if selected_chat != active_chat_name: # Сравниваем с уже определенной переменной
        st.session_state.active_chat = selected_chat
        # Сохраняем ВСЕ данные, включая режим, если нужно
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
            if active_chat_name in st.session_state.all_chats:
                del st.session_state.all_chats[active_chat_name]
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
        # Можно добавить сохранение режима в save_all_chats, если нужно
        st.rerun()

# --- Основная область: Чат ---
current_mode_name = st.session_state.get("selected_mode", DEFAULT_MODE)
current_model_id = MODES.get(current_mode_name, MODES[DEFAULT_MODE])

# Отображение сообщений АКТИВНОГО чата
if not active_chat_history: # Используем уже полученную историю
     active_chat_history.append(
         {"role": "assistant", "content": f"👋 Привет! Я {current_mode_name}. Начнем новый чат!"}
     )
     st.session_state.all_chats[active_chat_name] = active_chat_history
     save_all_chats(st.session_state.all_chats, active_chat_name)

# Контейнер для сообщений
chat_display_container = st.container()
with chat_display_container:
    for message in active_chat_history: # Используем уже полученную историю
        avatar = "🧑‍💻" if message["role"] == "user" else "🤖"
        with st.chat_message(message["role"], avatar=avatar):
            st.markdown(message["content"], unsafe_allow_html=True) # Добавил unsafe_allow_html на всякий случай

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
    # active_chat_name и active_chat_history уже определены выше
    active_chat_history.append({"role": "user", "content": prompt})
    st.session_state.all_chats[active_chat_name] = active_chat_history
    save_all_chats(st.session_state.all_chats, active_chat_name)
    st.rerun() # Перерисовываем, чтобы показать сообщение пользователя

# --- Логика ответа ИИ (после rerun) ---
# active_chat_name и active_chat_history уже определены выше
if active_chat_history and active_chat_history[-1]["role"] == "user":
     with chat_display_container:
         with st.chat_message("assistant", avatar="🤖"):
             # Используем active_chat_history, определенную в начале
             full_response = st.write_stream(stream_ai_response(current_model_id, active_chat_history))

     if full_response:
         # Используем active_chat_history, определенную в начале
         active_chat_history.append({"role": "assistant", "content": full_response})
         st.session_state.all_chats[active_chat_name] = active_chat_history
         save_all_chats(st.session_state.all_chats, active_chat_name)
         # st.rerun() не нужен после write_stream

# --- Футер ---
# Убран
