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
AVAILABLE_MODELS = {
    "DeepSeek Chat v3 (Free)": "deepseek/deepseek-chat-v3-0324:free",
    "DeepSeek R1 (Free)": "deepseek/deepseek-r1:free",
}
LOCAL_STORAGE_KEY = "multi_chat_storage_v3" # Ключ для хранения ВСЕХ чатов
DEFAULT_CHAT_NAME = "Новый чат"

# --- Настройка страницы ---
st.set_page_config(
    page_title="Мульти-Чат ИИ",
    page_icon="💬",
    layout="wide",
    initial_sidebar_state="expanded" # Открываем сайдбар по умолчанию
)

# --- Инициализация LocalStorage ---
localS = LocalStorage()

# --- Пользовательский CSS (добавлены стили для сайдбара и активного чата) ---
custom_css = """
<style>
    /* --- Общие стили --- */
    .stApp {
        /* background: linear-gradient(to bottom right, #f0f2f6, #e6e9f0); */ /* Пример светлого градиента */
        /* background-color: #1e1e1e; color: #d4d4d4; */ /* Пример темной темы (нужно больше стилей для элементов) */
    }
    h1 { text-align: center; padding-bottom: 10px; }
    .stButton button { border-radius: 8px; width: 100%; } /* Кнопки в сайдбаре на всю ширину */
    .stSelectbox label { font-weight: bold; }
    div[data-testid="stSelectbox"] > div { cursor: pointer; }

    /* --- Стили чата --- */
    .stChatFloatingInputContainer {
        background-color: rgba(255, 255, 255, 0.8); backdrop-filter: blur(5px);
        border-top: 1px solid #e6e6e6;
    }
    [data-testid="stChatMessage"] {
        border-radius: 15px; padding: 12px 18px; margin-bottom: 10px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05); max-width: 90%;
    }
    [data-testid="stChatMessageContent"] p { margin-bottom: 0.5rem; }

    /* --- Темные блоки кода --- */
    [data-testid="stChatMessage"] code {
        background-color: #282c34; color: #abb2bf; padding: 0.15em 0.4em;
        border-radius: 3px; font-size: 0.9em; word-wrap: break-word;
    }
    [data-testid="stChatMessage"] pre {
        background-color: #282c34; border: 1px solid #3b4048; border-radius: 5px;
        padding: 12px; overflow-x: auto; font-size: 0.9em;
    }
    [data-testid="stChatMessage"] pre code {
        background-color: transparent; color: #abb2bf; padding: 0;
        font-size: inherit; border-radius: 0;
    }

    /* --- Стили Сайдбара --- */
    [data-testid="stSidebar"] {
        /* background-color: #f8f9fa; */ /* Пример светлого фона сайдбара */
        padding-top: 1rem;
    }
    [data-testid="stSidebar"] h2 { /* Заголовок "Чаты" */
        text-align: center;
        margin-bottom: 1rem;
        font-size: 1.5rem;
    }
     /* Стиль для списка чатов (радио) */
    div[data-testid="stSidebar"] div[role="radiogroup"] > label {
        display: block; /* Каждый чат на новой строке */
        padding: 8px 12px;
        border-radius: 8px;
        margin-bottom: 5px;
        cursor: pointer;
        transition: background-color 0.2s ease;
        border: 1px solid transparent; /* Для выравнивания */
    }
    /* Стиль при наведении на чат */
    div[data-testid="stSidebar"] div[role="radiogroup"] > label:hover {
        background-color: rgba(0, 0, 0, 0.05);
    }
     /* Стиль для ВЫБРАННОГО чата - попробуем выделить */
    /* (Это может быть сложно из-за структуры Streamlit, может не сработать идеально) */
    div[data-testid="stSidebar"] div[role="radiogroup"] input[type="radio"]:checked + label {
        background-color: rgba(0, 100, 255, 0.1); /* Легкий синий фон */
        border: 1px solid rgba(0, 100, 255, 0.2);
        font-weight: bold;
    }

</style>
"""
st.markdown(custom_css, unsafe_allow_html=True)

# --- Функции для работы с чатами в localStorage ---

def load_all_chats():
    """Загружает все чаты и имя активного чата из localStorage."""
    data_str = localS.getItem(LOCAL_STORAGE_KEY)
    if data_str:
        try:
            data = json.loads(data_str)
            # Проверяем базовую структуру
            if isinstance(data, dict) and "chats" in data and "active_chat" in data:
                # Дополнительно проверяем, что chats это словарь
                if isinstance(data["chats"], dict):
                    return data["chats"], data["active_chat"]
        except json.JSONDecodeError:
            pass # Ошибка парсинга, вернем дефолт
    # Если ничего нет или ошибка, создаем первый чат
    first_chat_name = f"{DEFAULT_CHAT_NAME} 1"
    default_chats = {first_chat_name: []} # Начинаем с пустого списка сообщений
    return default_chats, first_chat_name

def save_all_chats(chats_dict, active_chat_name):
    """Сохраняет все чаты и имя активного чата в localStorage."""
    if isinstance(chats_dict, dict) and isinstance(active_chat_name, str):
        data_to_save = {"chats": chats_dict, "active_chat": active_chat_name}
        try:
            localS.setItem(LOCAL_STORAGE_KEY, json.dumps(data_to_save))
            return True
        except Exception as e:
            # Не выводим ошибку пользователю, чтобы не мешать
            # print(f"Ошибка сохранения в localStorage: {e}") # Для отладки
            return False
    return False

def generate_new_chat_name(existing_names):
    """Генерирует уникальное имя для нового чата."""
    i = 1
    while f"{DEFAULT_CHAT_NAME} {i}" in existing_names:
        i += 1
    return f"{DEFAULT_CHAT_NAME} {i}"

# --- Инициализация состояния приложения ---
if "all_chats" not in st.session_state:
    st.session_state.all_chats, st.session_state.active_chat = load_all_chats()
    # Убедимся, что активный чат существует в словаре чатов
    if st.session_state.active_chat not in st.session_state.all_chats:
        # Если активный чат не найден (например, удален в другой вкладке),
        # выбираем первый попавшийся или создаем новый
        if st.session_state.all_chats:
            st.session_state.active_chat = list(st.session_state.all_chats.keys())[0]
        else: # Если вообще нет чатов
            new_name = generate_new_chat_name([])
            st.session_state.all_chats = {new_name: []}
            st.session_state.active_chat = new_name
            save_all_chats(st.session_state.all_chats, st.session_state.active_chat)

# --- Сайдбар для управления чатами ---
with st.sidebar:
    st.markdown("## 💬 Чаты")

    chat_names = list(st.session_state.all_chats.keys())
    # Находим индекс текущего активного чата для st.radio/selectbox
    try:
        active_chat_index = chat_names.index(st.session_state.active_chat)
    except ValueError:
        active_chat_index = 0 # Если активный чат не найден, выбираем первый

    # Виджет для выбора чата
    selected_chat = st.radio(
        "Выберите чат:",
        options=chat_names,
        index=active_chat_index,
        label_visibility="collapsed" # Скрываем label, т.к. есть заголовок "Чаты"
    )

    # Если выбран другой чат, обновляем состояние и сохраняем
    if selected_chat != st.session_state.active_chat:
        st.session_state.active_chat = selected_chat
        save_all_chats(st.session_state.all_chats, st.session_state.active_chat)
        st.rerun() # Перезапускаем для отображения нужного чата

    st.divider()

    # Кнопки управления чатами
    if st.button("➕ Новый чат"):
        new_name = generate_new_chat_name(chat_names)
        st.session_state.all_chats[new_name] = [] # Добавляем пустой чат
        st.session_state.active_chat = new_name # Делаем его активным
        save_all_chats(st.session_state.all_chats, st.session_state.active_chat)
        st.rerun()

    if len(chat_names) > 0: # Показываем кнопку удаления, только если есть чаты
        if st.button("🗑️ Удалить текущий чат", type="secondary"):
            if st.session_state.active_chat in st.session_state.all_chats:
                del st.session_state.all_chats[st.session_state.active_chat] # Удаляем из словаря

                # Выбираем новый активный чат
                remaining_chats = list(st.session_state.all_chats.keys())
                if remaining_chats:
                    st.session_state.active_chat = remaining_chats[0] # Выбираем первый оставшийся
                else:
                    # Если чатов не осталось, создаем новый
                    new_name = generate_new_chat_name([])
                    st.session_state.all_chats = {new_name: []}
                    st.session_state.active_chat = new_name

                save_all_chats(st.session_state.all_chats, st.session_state.active_chat)
                st.rerun()

# --- Основная область ---
st.title("👋 Добро пожаловать")

# --- Выбор модели ---
model_keys = list(AVAILABLE_MODELS.keys())
# Сохраняем выбор модели в session_state, чтобы он не сбрасывался
if "selected_model_name" not in st.session_state:
    st.session_state.selected_model_name = model_keys[0] # По умолчанию первая

st.session_state.selected_model_name = st.selectbox(
    "🧠 Выберите модель ИИ:",
    options=model_keys,
    index=model_keys.index(st.session_state.selected_model_name) # Устанавливаем текущее значение
)
model_id = AVAILABLE_MODELS[st.session_state.selected_model_name]
st.caption(f"ID: `{model_id}`")
st.divider()

# --- Отображение сообщений АКТИВНОГО чата ---
# Получаем сообщения текущего активного чата
current_messages = st.session_state.all_chats.get(st.session_state.active_chat, [])

# Добавляем приветствие, если чат пуст
if not current_messages:
     current_messages.append(
         {"role": "assistant", "content": f"👋 Привет! Я ваш ИИ-помощник ({st.session_state.selected_model_name}). Чем могу помочь в этом чате?"}
     )
     # Сразу сохраняем приветствие в этот чат
     st.session_state.all_chats[st.session_state.active_chat] = current_messages
     save_all_chats(st.session_state.all_chats, st.session_state.active_chat)


# Отображаем сообщения
for message in current_messages:
    avatar = "🧑‍💻" if message["role"] == "user" else "🤖"
    with st.chat_message(message["role"], avatar=avatar):
        st.markdown(message["content"])

# --- Функция стриминга (без изменений) ---
def stream_ai_response(model_id_func, chat_history_func):
    """Запрашивает ответ у API в режиме стриминга и возвращает кусочки текста."""
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
    if not isinstance(chat_history_func, list):
         st.error("Ошибка: Некорректный формат истории.", icon="⚠️")
         yield None; return
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
                    except json.JSONDecodeError: continue
                    except Exception as e: break
    except requests.exceptions.Timeout:
        st.error("⏳ Таймаут.", icon="⏱️"); yield None
    except requests.exceptions.RequestException as e:
        error_message = f"Ошибка API: {e}"
        try:
             if e.response is not None: error_message += f" ({e.response.text[:100]})"
        except: pass
        st.error(error_message, icon="🌐"); yield None
    except Exception as e:
        st.error(f"🤯 Ошибка стриминга: {e}", icon="💥"); yield None


# --- Поле ввода пользователя ---
if prompt := st.chat_input("Напишите ваше сообщение здесь..."):

    # 1. Добавляем сообщение пользователя в ТЕКУЩИЙ АКТИВНЫЙ чат
    active_chat_name = st.session_state.active_chat
    # Получаем текущую историю активного чата (или пустой список, если что-то не так)
    active_chat_history = st.session_state.all_chats.get(active_chat_name, [])
    active_chat_history.append({"role": "user", "content": prompt})

    # Обновляем словарь всех чатов
    st.session_state.all_chats[active_chat_name] = active_chat_history
    # Сохраняем ВСЕ чаты в localStorage
    save_all_chats(st.session_state.all_chats, active_chat_name)

    # Отображаем сообщение пользователя (сразу после добавления)
    # Перезагрузка страницы не нужна, Streamlit обновит чат ниже
    with st.chat_message("user", avatar="🧑‍💻"):
        st.markdown(prompt)

    # 2. Отображаем ответ ИИ
    with st.chat_message("assistant", avatar="🤖"):
        # Передаем историю ТОЛЬКО текущего активного чата
        full_response = st.write_stream(stream_ai_response(model_id, active_chat_history))

    # 3. Добавляем ПОЛНЫЙ ответ ИИ в ТЕКУЩИЙ АКТИВНЫЙ чат и СНОВА СОХРАНЯЕМ
    if full_response:
        active_chat_history.append({"role": "assistant", "content": full_response})
        st.session_state.all_chats[active_chat_name] = active_chat_history
        save_all_chats(st.session_state.all_chats, active_chat_name)
        # Важно: Перезагружаем страницу после ответа ИИ, чтобы st.write_stream корректно отработал
        # и чтобы следующее сообщение пользователя отправлялось с уже обновленной историей.
        st.rerun()


# --- Футер ---
# Убран
