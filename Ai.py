# -*- coding: utf-8 -*-
import streamlit as st
import requests
import os
import platform
import json # Для работы с JSON при сохранении/загрузке
# Импортируем библиотеку для работы с локальным хранилищем
from streamlit_local_storage import LocalStorage

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
LOCAL_STORAGE_KEY = "ai_chat_history" # Ключ для сохранения в localStorage

# --- Настройка страницы Streamlit ---
st.set_page_config(
    page_title="Добро пожаловать",
    page_icon="💬",
    layout="wide",
    # initial_sidebar_state убран, т.к. сайдбара нет
)

# --- Инициализация LocalStorage ---
# Должна быть вызвана до попытки чтения/записи
localS = LocalStorage()

# --- Пользовательский CSS ---
# (CSS остается в основном тем же, убраны стили для sidebar)
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

    /* Стили для кнопок и радио/селектбокса в основной части */
    .stButton button { border-radius: 8px; }
    .stRadio label, .stSelectbox label { font-weight: bold; }
    /* Курсор для SelectBox (если используется) */
    [data-testid="stSelectbox"] > div { cursor: pointer; }
    /* Курсор для Radio */
    div[role="radiogroup"] label { cursor: pointer; }

</style>
"""
st.markdown(custom_css, unsafe_allow_html=True)

# --- Заголовок ---
st.title("👋 Добро пожаловать")

# --- Выбор модели и кнопка очистки (в основной части) ---
col1, col2 = st.columns([3, 1]) # Колонки для размещения элементов

with col1:
    # Используем radio для двух моделей, выглядит компактнее
    selected_model_name = st.radio(
        "🧠 Выберите модель ИИ:",
        options=list(AVAILABLE_MODELS.keys()),
        horizontal=True, # Располагаем опции горизонтально
        key="model_selector" # Добавляем ключ для виджета
    )
    model_id = AVAILABLE_MODELS[selected_model_name]
    st.caption(f"ID: `{model_id}`")

with col2:
    st.caption(" ") # Пустой caption для выравнивания кнопки по вертикали
    if st.button("🗑️ Очистить чат", type="secondary", key="clear_chat_button"):
        st.session_state.messages = [
             {"role": "assistant", "content": f"👋 История очищена! Чем могу помочь теперь?"}
        ]
        # Очищаем и локальное хранилище
        localS.deleteItem(LOCAL_STORAGE_KEY)
        # Используем rerun для немедленного обновления интерфейса после очистки
        st.rerun()


st.divider() # Разделитель под настройками

# --- Загрузка и Инициализация истории чата ---
# Используем ключ сессии, чтобы избежать повторной загрузки при каждом rerun
if "history_loaded" not in st.session_state:
    st.session_state.messages = [] # Инициализируем пустым списком по умолчанию
    saved_history_str = localS.getItem(LOCAL_STORAGE_KEY)
    loaded_successfully = False
    if saved_history_str:
        try:
            saved_history = json.loads(saved_history_str)
            if isinstance(saved_history, list) and saved_history: # Проверяем, что не пустой список
                st.session_state.messages = saved_history
                st.info("История чата загружена из вашего браузера.", icon="💾")
                loaded_successfully = True
            # else: формат некорректный или пустой, используем приветствие ниже
        except json.JSONDecodeError:
             # Если не удалось распарсить JSON, используем приветствие ниже
             pass # Ошибка парсинга, используем приветствие

    # Если не загрузили или загрузка не удалась, ставим приветственное сообщение
    if not loaded_successfully:
         st.session_state.messages = [
             {"role": "assistant", "content": f"👋 Привет! Я ваш ИИ-помощник ({selected_model_name}). Чем могу помочь?"}
         ]
    st.session_state.history_loaded = True # Ставим флаг, что история загружена/инициализирована


# --- Отображение истории чата ---
# Убедимся, что messages существует в session_state перед отображением
if "messages" in st.session_state:
    for message in st.session_state.messages[:]:
        avatar = "🧑‍💻" if message["role"] == "user" else "🤖"
        with st.chat_message(message["role"], avatar=avatar):
            st.markdown(message["content"])

# --- Функция для СТРИМИНГА ответа API OpenRouter ---
def stream_ai_response(model_id_func, chat_history_func):
    """Запрашивает ответ у API в режиме стриминга и возвращает кусочки текста."""
    try:
        # Проверяем наличие секрета перед использованием
        if "OPENROUTER_API_KEY" not in st.secrets:
             st.error("⛔ Секрет 'OPENROUTER_API_KEY' не найден в настройках приложения.", icon="🚨")
             yield None; return

        api_key_from_secrets = st.secrets["OPENROUTER_API_KEY"]
        # Проверка, что ключ не пустой
        if not api_key_from_secrets:
             st.error("⛔ Секрет 'OPENROUTER_API_KEY' найден, но он пустой.", icon="🚨")
             yield None; return

    except Exception as e: # Ловим более общие ошибки доступа к секретам
        st.error(f"🤯 Ошибка при доступе к секретам: {e}", icon="💥")
        yield None; return

    headers = {"Authorization": f"Bearer {api_key_from_secrets}", "Content-Type": "application/json"}
    # Убедимся, что передаем корректную историю (список словарей)
    if not isinstance(chat_history_func, list):
         st.error("Ошибка: Некорректный формат истории чата.", icon="⚠️")
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
                    except json.JSONDecodeError:
                        # Игнорируем ошибки декодирования отдельных чанков
                        continue
                    except Exception as e:
                        # Логируем другие ошибки обработки чанков
                        st.warning(f"Проблема при обработке части ответа.", icon="⚠️"); break
    except requests.exceptions.Timeout:
        st.error("⏳ Таймаут ответа от API.", icon="⏱️"); yield None
    except requests.exceptions.RequestException as e:
        error_message = f"Ошибка API: {e}"
        try: # Пытаемся получить детали ошибки, если возможно
             if e.response is not None: error_message += f" ({e.response.text[:100]})" # Показываем начало ответа сервера
        except: pass
        st.error(error_message, icon="🌐"); yield None
    except Exception as e:
        st.error(f"🤯 Ошибка стриминга: {e}", icon="💥"); yield None

# --- Поле ввода пользователя ---
if prompt := st.chat_input("Напишите ваше сообщение здесь...", key="chat_input"):

    # Убедимся, что messages существует и является списком
    if "messages" not in st.session_state or not isinstance(st.session_state.messages, list):
        st.session_state.messages = [] # Инициализируем, если что-то пошло не так

    # 1. Добавляем сообщение пользователя и СОХРАНЯЕМ историю
    st.session_state.messages.append({"role": "user", "content": prompt})
    try:
        # Сохраняем в localStorage
        localS.setItem(LOCAL_STORAGE_KEY, json.dumps(st.session_state.messages))
    except Exception as e:
        st.warning(f"Не удалось сохранить историю в браузере: {e}", icon="💾")

    # Отображаем сообщение пользователя
    with st.chat_message("user", avatar="🧑‍💻"):
        st.markdown(prompt)

    # 2. Отображаем ответ ИИ
    with st.chat_message("assistant", avatar="🤖"):
        # Передаем текущую историю сообщений
        current_chat_history = st.session_state.get("messages", [])
        full_response = st.write_stream(stream_ai_response(model_id, current_chat_history))

    # 3. Добавляем ПОЛНЫЙ ответ ИИ и СНОВА СОХРАНЯЕМ историю
    if full_response:
        # Убедимся, что messages все еще список перед добавлением
        if isinstance(st.session_state.messages, list):
             st.session_state.messages.append({"role": "assistant", "content": full_response})
             try:
                 # Сохраняем в localStorage
                 localS.setItem(LOCAL_STORAGE_KEY, json.dumps(st.session_state.messages))
             except Exception as e:
                  st.warning(f"Не удалось сохранить историю в браузере после ответа ИИ: {e}", icon="💾")
        else:
             # Если messages перестал быть списком, это ошибка, но пытаемся восстановиться
             st.session_state.messages = [{"role": "assistant", "content": full_response}]
             st.error("Произошла ошибка с историей чата. История может быть неполной.", icon="⚠️")


    # Не вызываем rerun() здесь явно. Streamlit обновит интерфейс.

# --- Футер ---
# Убран
