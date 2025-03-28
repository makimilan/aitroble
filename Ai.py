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
MODEL_V3_NAME = "Стандарт (V3)"
MODEL_V3_ID = "deepseek/deepseek-chat-v3-0324:free"
MODEL_R1_NAME = "DeepThink (R1)"
MODEL_R1_ID = "deepseek/deepseek-r1:free"
LOCAL_STORAGE_KEY = "multi_chat_storage_v4" # Обновил ключ
DEFAULT_CHAT_NAME = "Новый чат"

# --- Настройка страницы ---
st.set_page_config(
    page_title="DeepSeek-подобный Чат",
    page_icon="🐳", # Иконка кита
    layout="centered", # Центрируем основной контент для лучшего вида
    initial_sidebar_state="collapsed" # Скрываем стандартный сайдбар Streamlit
)

# --- Инициализация LocalStorage ---
localS = LocalStorage()

# --- Пользовательский CSS ---
custom_css = f"""
<style>
    /* --- Базовая темная тема (Streamlit сам может переключить) --- */
    body {{
        /* background-color: #2f3136; */ /* Пример фона Discord */
        /* color: #dcddde; */
    }}

    /* --- Убираем стандартный отступ сверху --- */
     .main .block-container {{
        padding-top: 1rem;
        padding-bottom: 3.5rem; /* Отступ снизу, чтобы поле ввода не перекрывало контент */
    }}

     /* --- Центрирование приветствия --- */
    .welcome-block {{
        text-align: center;
        margin-bottom: 2rem;
    }}
    .welcome-block h1 {{
        font-size: 2.5rem; /* Крупнее */
        margin-bottom: 0.5rem;
    }}
     .welcome-block p {{
        font-size: 1.1rem;
        color: #b9bbbe; /* Светло-серый */
     }}

     /* --- Блок управления чатами и моделью --- */
     .controls-container {{
        max-width: 600px; /* Ограничим ширину для центрирования */
        margin: 0 auto 1.5rem auto; /* Центрируем блок и добавляем отступ снизу */
        padding: 15px;
        background-color: rgba(79,84,92, 0.3); /* Полупрозрачный серый фон */
        border-radius: 8px;
     }}
     .controls-container .stButton button {{ width: auto; margin: 0 5px; }} /* Кнопки чатов не на всю ширину */
     .controls-container .stSelectbox {{ width: 100%; margin-bottom: 10px; }} /* Селектбокс чатов */
     .controls-container [data-testid="stHorizontalBlock"] {{ /* Контейнер для кнопок */
        display: flex;
        justify-content: center;
        margin-bottom: 15px;
     }}
     /* Стили для st.toggle */
    .controls-container [data-testid="stToggle"] label {{
        display: flex;
        align-items: center;
        justify-content: center; /* Центрируем toggle */
        cursor: pointer;
        color: #b9bbbe;
    }}

    /* --- Стили чата --- */
    .stChatFloatingInputContainer {{ /* Поле ввода */
        background-color: #40444b; /* Темно-серый фон поля ввода */
        border-top: 1px solid #2f3136;
    }}
    /* Стилизация самого поля ввода текста */
     .stChatFloatingInputContainer textarea {{
        background-color: #40444b;
        color: #dcddde;
        border: none;
     }}
     /* Кнопка отправки */
     .stChatFloatingInputContainer button[data-testid="send-button"] svg {{
        fill: #7289da; /* Цвет иконки отправки (Discord фиолетовый) */
     }}

    [data-testid="stChatMessage"] {{ /* Сообщения */
        background-color: transparent; /* Убираем фон сообщений, т.к. фон страницы темный */
        border-radius: 0;
        padding: 5px 0; /* Уменьшаем отступы */
        margin-bottom: 0;
        box-shadow: none;
        max-width: 100%; /* Сообщения могут занимать всю ширину */
    }}
     /* Аватар и имя пользователя/бота */
     [data-testid="stChatMessage"] [data-testid="chatAvatarIcon-user"],
     [data-testid="stChatMessage"] [data-testid="chatAvatarIcon-assistant"] {{
        /* background-color: #7289da; */ /* Можно задать фон аватару */
     }}
    [data-testid="stChatMessageContent"] {{
        color: #dcddde; /* Цвет текста сообщений */
    }}
    [data-testid="stChatMessageContent"] p {{ margin-bottom: 0.2rem; }}

    /* --- Темные блоки кода (остаются без изменений) --- */
    [data-testid="stChatMessage"] code {{ background-color: #282c34; color: #abb2bf; ... }}
    [data-testid="stChatMessage"] pre {{ background-color: #282c34; border: 1px solid #3b4048; ... }}
    [data-testid="stChatMessage"] pre code {{ background-color: transparent; color: #abb2bf; ... }}

    /* --- Скрыть стандартный сайдбар Streamlit --- */
    [data-testid="stSidebar"] {{ display: none; }}

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
if "thinking_enabled" not in st.session_state:
    st.session_state.thinking_enabled = False

# --- Приветствие ---
st.markdown("""
<div class="welcome-block">
    <h1>🐳 Hi, I'm DeepSeek.</h1>
    <p>How can I help you today?</p>
</div>
""", unsafe_allow_html=True)

# --- Блок управления чатами и моделью ---
with st.container():
    st.markdown('<div class="controls-container">', unsafe_allow_html=True) # Открываем div для стилизации

    chat_names = list(st.session_state.all_chats.keys())
    try: active_chat_index = chat_names.index(st.session_state.active_chat)
    except ValueError: active_chat_index = 0

    selected_chat = st.selectbox(
        "Текущий чат:", options=chat_names, index=active_chat_index,
        label_visibility="collapsed"
    )

    if selected_chat != st.session_state.active_chat:
        st.session_state.active_chat = selected_chat
        save_all_chats(st.session_state.all_chats, st.session_state.active_chat)
        st.rerun()

    # Кнопки под селектбоксом
    cols = st.columns(2)
    with cols[0]:
        if st.button("➕ Новый чат"):
            new_name = generate_new_chat_name(chat_names)
            st.session_state.all_chats[new_name] = []
            st.session_state.active_chat = new_name
            save_all_chats(st.session_state.all_chats, st.session_state.active_chat)
            st.rerun()
    with cols[1]:
        if len(chat_names) > 0:
            if st.button("🗑️ Удалить текущий"): # Укоротил текст кнопки
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

    st.write("") # Небольшой отступ

    # Переключатель модели
    st.session_state.thinking_enabled = st.toggle(
        f"Режим: {MODEL_R1_NAME if st.session_state.thinking_enabled else MODEL_V3_NAME}",
        value=st.session_state.thinking_enabled,
        help="Включено - DeepThink (R1), Выключено - Стандарт (V3)"
    )

    st.markdown('</div>', unsafe_allow_html=True) # Закрываем div

# --- Определяем активную модель ---
is_thinking_enabled = st.session_state.get("thinking_enabled", False)
current_model_name = MODEL_R1_NAME if is_thinking_enabled else MODEL_V3_NAME
current_model_id = MODEL_R1_ID if is_thinking_enabled else MODEL_V3_ID

# --- Контейнер для истории чата (для возможной прокрутки) ---
chat_container = st.container()
with chat_container:
    current_messages = st.session_state.all_chats.get(st.session_state.active_chat, [])
    if not current_messages:
         current_messages.append(
             {"role": "assistant", "content": f"👋 Привет! Я {current_model_name}. Спрашивай!"}
         )
         st.session_state.all_chats[st.session_state.active_chat] = current_messages
         save_all_chats(st.session_state.all_chats, st.session_state.active_chat)

    for message in current_messages:
        avatar = "🧑‍💻" if message["role"] == "user" else "🐳" # Кит для ассистента
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
    if not isinstance(chat_history_func, list): yield None; return # Проверка истории
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
                    except: continue # Игнорируем ошибки парсинга чанков
    except requests.exceptions.RequestException as e: yield None # Ошибка API/Сети
    except Exception as e: yield None # Другая ошибка

# --- Поле ввода пользователя ---
if prompt := st.chat_input(f"Message {current_model_name}..."): # Placeholder зависит от модели

    active_chat_name = st.session_state.active_chat
    active_chat_history = st.session_state.all_chats.get(active_chat_name, [])
    active_chat_history.append({"role": "user", "content": prompt})
    st.session_state.all_chats[active_chat_name] = active_chat_history
    save_all_chats(st.session_state.all_chats, active_chat_name)

    # --- Обновляем интерфейс СРАЗУ после добавления сообщения пользователя ---
    # Это важно, чтобы пользователь видел свое сообщение до ответа ИИ
    # Мы не используем with st.chat_message здесь, т.к. вся история перерисовывается
    st.rerun()

# --- Логика получения ответа ИИ (вынесена из-под if prompt) ---
# Проверяем, есть ли последнее сообщение от пользователя и нет ли уже ответа на него
active_chat_history = st.session_state.all_chats.get(st.session_state.active_chat, [])
if active_chat_history and active_chat_history[-1]["role"] == "user":
     # Добавляем плейсхолдер для ответа ассистента
     with chat_container: # Рисуем внутри контейнера чата
         with st.chat_message("assistant", avatar="🐳"):
             # Получаем и отображаем ответ
             full_response = st.write_stream(stream_ai_response(current_model_id, active_chat_history))

     # Если ответ получен, добавляем его и сохраняем
     if full_response:
         active_chat_history.append({"role": "assistant", "content": full_response})
         st.session_state.all_chats[st.session_state.active_chat] = active_chat_history
         save_all_chats(st.session_state.all_chats, st.session_state.active_chat)
         # Не вызываем rerun здесь, т.к. st.write_stream уже обновил интерфейс

# --- Футер ---
# Убран
