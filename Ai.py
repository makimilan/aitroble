# -*- coding: utf-8 -*-
import streamlit as st
import requests
import os
import platform
import json # Для работы с JSON при сохранении/загрузке
from streamlit_local_storage import LocalStorage # Для сохранения истории в браузере

# --- API КЛЮЧ БУДЕТ ВЗЯТ ИЗ СЕКРЕТОВ STREAMLIT ---
# Убедитесь, что в настройках приложения на share.streamlit.io
# в разделе Secrets добавлена строка:
# OPENROUTER_API_KEY = "sk-or-v1-..."
# --------------------------------------------------

# --- Константы ---
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"
AVAILABLE_MODELS = {
    "DeepSeek Chat v3 (Free)": "deepseek/deepseek-chat-v3-0324:free",
    "DeepSeek R1 (Free)": "deepseek/deepseek-r1:free",
}
LOCAL_STORAGE_KEY = "ai_chat_history_v2" # Слегка изменил ключ на случай конфликта со старой версией

# --- Настройка страницы Streamlit ---
st.set_page_config(
    page_title="Добро пожаловать",
    page_icon="💬",
    layout="wide",
)

# --- Инициализация LocalStorage ---
localS = LocalStorage()

# --- Пользовательский CSS ---
custom_css = """
<style>
    .stApp { } /* Общий фон */

    .stChatFloatingInputContainer { /* Поле ввода */
        background-color: rgba(255, 255, 255, 0.8);
        backdrop-filter: blur(5px);
        border-top: 1px solid #e6e6e6;
    }
    [data-testid="stChatMessage"] { /* Сообщения */
        border-radius: 15px; padding: 12px 18px; margin-bottom: 10px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05); max-width: 90%;
    }
    [data-testid="stChatMessageContent"] p { margin-bottom: 0.5rem; }

    /* Темные блоки кода */
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
    h1 { text-align: center; padding-bottom: 10px; } /* Заголовок */

    /* Стили для кнопок и радио в основной части */
    .stButton button { border-radius: 8px; }
    .stRadio label { font-weight: bold; } /* Убрали .stSelectbox */
    /* Курсор для Radio */
    div[role="radiogroup"] label { cursor: pointer; }

    /* Центрирование выбора модели и кнопки очистки */
    div[data-testid="stHorizontalBlock"] {
        display: flex;
        justify-content: center; /* Центрируем содержимое блока */
        align-items: center; /* Выравниваем по вертикали */
        flex-wrap: wrap; /* Позволяем переносить на новую строку */
        margin-bottom: 10px; /* Добавляем отступ снизу */
    }
     /* Контейнер для радио-кнопок */
    div[data-testid="stRadio"] {
        display: flex; /* Используем flex для выравнивания */
        justify-content: center; /* Центрируем радио-кнопки */
        width: 100%; /* Занимаем всю ширину для центрирования */
        margin-bottom: 10px; /* Отступ под радио-кнопками */
    }
     /* Контейнер для кнопки очистки */
     div.stButton {
        display: flex;
        justify-content: center; /* Центрируем кнопку */
        width: 100%;
     }


</style>
"""
st.markdown(custom_css, unsafe_allow_html=True)

# --- Заголовок ---
st.title("👋 Добро пожаловать")
st.write("") # Небольшой отступ

# --- Блок выбора модели и очистки ---
with st.container(): # Используем контейнер для группировки
    # Используем radio для двух моделей
    selected_model_name = st.radio(
        "🧠 Выберите модель ИИ:",
        options=list(AVAILABLE_MODELS.keys()),
        horizontal=True, # Располагаем опции горизонтально
        # key убран
        label_visibility="collapsed" # Скрываем стандартный label "Выберите модель ИИ:"
    )
    model_id = AVAILABLE_MODELS[selected_model_name]
    # Показываем выбранную модель и ID под радио кнопками
    st.caption(f"Выбрано: **{selected_model_name}** (ID: `{model_id}`)", unsafe_allow_html=True)

    # Кнопка очистки под моделью
    if st.button("🗑️ Очистить чат", type="secondary"): # key убран
        st.session_state.messages = [
             {"role": "assistant", "content": f"👋 История очищена! Чем могу помочь теперь?"}
        ]
        localS.deleteItem(LOCAL_STORAGE_KEY)
        st.rerun()

st.divider() # Разделитель под настройками

# --- Загрузка и Инициализация истории чата ---
if "history_loaded" not in st.session_state:
    st.session_state.messages = []
    saved_history_str = localS.getItem(LOCAL_STORAGE_KEY)
    loaded_successfully = False
    if saved_history_str:
        try:
            saved_history = json.loads(saved_history_str)
            if isinstance(saved_history, list) and saved_history:
                st.session_state.messages = saved_history
                # Убрал st.info о загрузке, чтобы не мешало
                loaded_successfully = True
        except json.JSONDecodeError:
             pass

    if not loaded_successfully:
         st.session_state.messages = [
             {"role": "assistant", "content": f"👋 Привет! Я ваш ИИ-помощник ({selected_model_name}). Чем могу помочь?"}
         ]
    st.session_state.history_loaded = True


# --- Отображение истории чата ---
if "messages" in st.session_state:
    for message in st.session_state.messages[:]:
        avatar = "🧑‍💻" if message["role"] == "user" else "🤖"
        with st.chat_message(message["role"], avatar=avatar):
            st.markdown(message["content"])

# --- Функция для СТРИМИНГА ответа API OpenRouter ---
# (Функция остается без изменений, т.к. проблема была не в ней)
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
                    except Exception as e: break # Прерываем при ошибке парсинга чанка
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
if prompt := st.chat_input("Напишите ваше сообщение здесь..."): # key убран

    if "messages" not in st.session_state or not isinstance(st.session_state.messages, list):
        st.session_state.messages = []

    # 1. Добавляем сообщение пользователя и СОХРАНЯЕМ историю
    st.session_state.messages.append({"role": "user", "content": prompt})
    try:
        localS.setItem(LOCAL_STORAGE_KEY, json.dumps(st.session_state.messages))
    except Exception as e:
        # Ошибку сохранения теперь не выводим явно, чтобы не мешать
        pass # st.warning(f"Не удалось сохранить историю: {e}", icon="💾")

    # Отображаем сообщение пользователя
    with st.chat_message("user", avatar="🧑‍💻"):
        st.markdown(prompt)

    # 2. Отображаем ответ ИИ
    with st.chat_message("assistant", avatar="🤖"):
        current_chat_history = st.session_state.get("messages", [])
        full_response = st.write_stream(stream_ai_response(model_id, current_chat_history))

    # 3. Добавляем ПОЛНЫЙ ответ ИИ и СНОВА СОХРАНЯЕМ историю
    if full_response:
        if isinstance(st.session_state.messages, list):
             st.session_state.messages.append({"role": "assistant", "content": full_response})
             try:
                 localS.setItem(LOCAL_STORAGE_KEY, json.dumps(st.session_state.messages))
             except Exception as e:
                  # Ошибку сохранения теперь не выводим явно
                  pass # st.warning(f"Не удалось сохранить историю: {e}", icon="💾")
        else:
             st.session_state.messages = [{"role": "assistant", "content": full_response}]


# --- Футер ---
# Убран
