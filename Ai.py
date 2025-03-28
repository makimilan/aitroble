# -*- coding: utf-8 -*-
import streamlit as st
import requests
import os
import platform
import json # Для парсинга стриминговых данных

# --- API КЛЮЧ БУДЕТ ВЗЯТ ИЗ СЕКРЕТОВ STREAMLIT ---
# Убедитесь, что в настройках приложения на share.streamlit.io
# в разделе Secrets добавлена строка:
# OPENROUTER_API_KEY = "sk-or-v1-..."
# --------------------------------------------------

# --- Константы ---
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"
# Оставляем только DeepSeek модели
AVAILABLE_MODELS = {
    "DeepSeek Chat v3 (Free)": "deepseek/deepseek-chat-v3-0324:free",
    "DeepSeek R1 (Free)": "deepseek/deepseek-r1:free",
}

# --- Настройка страницы Streamlit ---
st.set_page_config(
    page_title="Добро пожаловать", # Заголовок вкладки браузера
    page_icon="💬", # Иконка вкладки
    layout="wide", # Макет страницы (широкий)
    initial_sidebar_state="expanded", # Начальное состояние боковой панели (открыта)
)

# --- Пользовательский CSS для улучшения дизайна ---
custom_css = """
<style>
    /* Общий фон */
    .stApp {
        /* background-color: #f0f2f6; */ /* Можете раскомментировать для светлого фона */
    }

    /* Контейнер поля ввода */
    .stChatFloatingInputContainer {
        background-color: rgba(255, 255, 255, 0.8); /* Полупрозрачный белый фон */
        backdrop-filter: blur(5px); /* Эффект размытия под полем ввода */
        border-top: 1px solid #e6e6e6; /* Тонкая линия сверху */
    }

    /* Сообщения чата */
    [data-testid="stChatMessage"] {
        border-radius: 15px; /* Скругленные углы */
        padding: 12px 18px; /* Внутренние отступы */
        margin-bottom: 10px; /* Отступ снизу */
        box-shadow: 0 2px 4px rgba(0,0,0,0.05); /* Легкая тень */
        max-width: 90%; /* Максимальная ширина сообщения */
    }

    /* Уменьшение отступа между параграфами внутри сообщения */
    [data-testid="stChatMessageContent"] p {
         margin-bottom: 0.5rem;
    }

    /* --- Стилизация блоков кода (ТЕМНАЯ ТЕМА) --- */
    /* Инлайновый код (между ``) */
    [data-testid="stChatMessage"] code {
        background-color: #282c34; /* Темный фон */
        color: #abb2bf; /* Светло-серый текст */
        padding: 0.15em 0.4em; /* Небольшие отступы */
        border-radius: 3px; /* Легкое скругление */
        font-size: 0.9em; /* Чуть меньше основного текста */
        word-wrap: break-word; /* Перенос длинных слов */
    }
    /* Блок кода (между ```) */
    [data-testid="stChatMessage"] pre {
        background-color: #282c34; /* Темный фон */
        border: 1px solid #3b4048; /* Чуть светлее граница */
        border-radius: 5px; /* Скругление углов */
        padding: 12px; /* Внутренние отступы */
        overflow-x: auto; /* Горизонтальная прокрутка при необходимости */
        font-size: 0.9em; /* Немного уменьшим шрифт блока кода */
    }
    /* Текст внутри блока кода (<pre><code>...</code></pre>) */
    [data-testid="stChatMessage"] pre code {
        background-color: transparent; /* Убираем фон, т.к. он уже есть у <pre> */
        color: #abb2bf; /* Светло-серый текст */
        padding: 0; /* Убираем лишние отступы */
        font-size: inherit; /* Наследуем размер шрифта от <pre> */
        border-radius: 0; /* Убираем скругление у внутреннего code */
    }
    /* --------------------------------------------- */

    /* Заголовок страницы */
    h1 {
        text-align: center; /* Центрируем */
        padding-bottom: 10px; /* Небольшой отступ снизу */
    }

    /* Стили для элементов боковой панели */
    [data-testid="stSidebar"] .stButton button {
        width: 100%; /* Кнопка на всю ширину */
        border-radius: 8px; /* Скругление кнопки */
    }
    [data-testid="stSidebar"] .stSelectbox label {
        font-weight: bold; /* Жирный шрифт для названия селектора */
    }

    /* --- ИСПРАВЛЕНИЕ КУРСОРА ДЛЯ SELECTBOX --- */
    [data-testid="stSidebar"] [data-testid="stSelectbox"] > div {
        cursor: pointer; /* Курсор-рука для элемента выбора модели */
    }
    /* --------------------------------------- */

</style>
"""
st.markdown(custom_css, unsafe_allow_html=True)

# --- Заголовок ---
st.title("👋 Добро пожаловать") # Основной заголовок страницы

# --- Боковая панель (Sidebar) ---
with st.sidebar:
    st.header("⚙️ Настройки Чата")
    st.divider() # Разделитель

    st.subheader("🧠 Выбор Модели")
    # Выпадающий список для выбора модели
    selected_model_name = st.selectbox(
        "Выберите модель ИИ:",
        options=list(AVAILABLE_MODELS.keys()), # Ключи словаря как опции
        index=0 # Модель по умолчанию (первая в списке)
    )
    # Получаем ID выбранной модели
    model_id = AVAILABLE_MODELS[selected_model_name]
    st.caption(f"ID модели: `{model_id}`") # Показываем ID модели под списком
    st.divider() # Разделитель

    st.subheader("🧹 Управление Чатом")
    # Кнопка для очистки истории
    if st.button("🗑️ Очистить историю чата", type="secondary"):
        st.session_state.messages = [] # Очищаем список сообщений
        # Добавляем приветственное сообщение после очистки
        st.session_state.messages.append(
             {"role": "assistant", "content": f"👋 История очищена! Чем могу помочь теперь?"}
        )
        st.rerun() # Перезапускаем скрипт для немедленного обновления интерфейса
    st.divider() # Разделитель
    # Надпись "❤️ Streamlit" удалена

# --- Инициализация истории чата ---
# Проверяем, есть ли ключ 'messages' в состоянии сессии
if "messages" not in st.session_state:
    st.session_state.messages = [] # Если нет, создаем пустой список
    # Добавляем приветственное сообщение только при самой первой загрузке сессии
    st.session_state.messages.append(
         {"role": "assistant", "content": f"👋 Привет! Я ваш ИИ-помощник ({selected_model_name}). Чем могу помочь?"}
     )

# --- Отображение истории чата ---
# Проходим по всем сообщениям в истории
for message in st.session_state.messages[:]: # Используем копию списка
    # Определяем аватар в зависимости от роли
    avatar = "🧑‍💻" if message["role"] == "user" else "🤖"
    # Создаем контейнер для сообщения с аватаром
    with st.chat_message(message["role"], avatar=avatar):
        # Отображаем текст сообщения с поддержкой Markdown
        st.markdown(message["content"])

# --- Функция для СТРИМИНГА ответа API OpenRouter ---
# Эта функция является генератором (использует yield)
def stream_ai_response(model_id_func, chat_history_func):
    """Запрашивает ответ у API в режиме стриминга и возвращает кусочки текста."""
    # --- ПОЛУЧЕНИЕ КЛЮЧА ИЗ СЕКРЕТОВ ---
    try:
        api_key_from_secrets = st.secrets["OPENROUTER_API_KEY"]
    except KeyError:
        st.error("⛔ Секрет 'OPENROUTER_API_KEY' не найден. Убедитесь, что он добавлен в настройках приложения Streamlit Cloud.", icon="🚨")
        yield None # Прерываем выполнение генератора
        return # Выходим из функции
    except Exception as e:
        st.error(f"🤯 Ошибка при доступе к секретам: {e}", icon="💥")
        yield None
        return
    # ------------------------------------

    headers = {
        "Authorization": f"Bearer {api_key_from_secrets}", # Используем ключ из секретов
        "Content-Type": "application/json",
    }
    payload = {
        "model": model_id_func,
        "messages": chat_history_func,
        "stream": True # Включаем режим стриминга
    }
    try:
        # Отправляем POST-запрос с параметром stream=True
        response = requests.post(OPENROUTER_API_URL, headers=headers, json=payload, stream=True, timeout=90)
        response.raise_for_status() # Проверяем на HTTP ошибки (4xx, 5xx)

        # Итерируемся по строкам ответа (Server-Sent Events)
        for line in response.iter_lines():
            if line: # Пропускаем пустые строки (keep-alive)
                decoded_line = line.decode('utf-8') # Декодируем строку
                # События SSE начинаются с "data: "
                if decoded_line.startswith("data: "):
                    try:
                        # Убираем префикс "data: "
                        json_data = decoded_line[len("data: "):]
                        # Проверяем маркер конца потока "[DONE]"
                        if json_data.strip() == "[DONE]":
                            break # Завершаем цикл, если поток закончен
                        # Парсим JSON-строку с данными чанка
                        chunk = json.loads(json_data)
                        # Извлекаем дельту (изменение) контента из чанка
                        delta_content = chunk.get("choices", [{}])[0].get("delta", {}).get("content")
                        # Если в чанке есть текст, возвращаем его
                        if delta_content:
                            yield delta_content # Возвращаем кусочек текста
                    except json.JSONDecodeError:
                        # Обработка случая, если пришел невалидный JSON
                        st.warning(f"Не удалось декодировать JSON из потока: {json_data}", icon="⚠️")
                        continue # Пропускаем эту строку и ждем следующую
                    except Exception as e:
                        # Обработка других ошибок при парсинге чанка
                        st.error(f"Ошибка обработки чанка: {e} | Строка: {decoded_line}", icon="💥")
                        break # Прерываем обработку потока

    # Обработка ошибок запроса (таймаут, сеть, API)
    except requests.exceptions.Timeout:
        st.error("⏳ Ошибка: Время ожидания ответа от API истекло.", icon="⏱️")
        yield None # Сигнализируем об ошибке
    except requests.exceptions.RequestException as e:
        error_message = f"Ошибка сети или API OpenRouter: {e}"
        try:
            # Пытаемся получить текст ошибки из ответа сервера
            error_details = e.response.text if e.response is not None else "Нет деталей ответа"
            error_message += f"\nДетали: {error_details}"
        except:
             pass # Если не удалось получить детали, ничего страшного
        st.error(error_message, icon="🌐")
        yield None # Сигнализируем об ошибке
    except Exception as e:
        # Обработка других непредвиденных ошибок
        st.error(f"🤯 Произошла непредвиденная ошибка при стриминге: {e}", icon="💥")
        yield None # Сигнализируем об ошибке

# --- Поле ввода пользователя ---
# st.chat_input возвращает введенный текст или None
if prompt := st.chat_input("Напишите ваше сообщение здесь...", key="chat_input"):

    # 1. Добавляем сообщение пользователя в историю сессии
    st.session_state.messages.append({"role": "user", "content": prompt})
    # Отображаем сообщение пользователя в интерфейсе
    with st.chat_message("user", avatar="🧑‍💻"):
        st.markdown(prompt)

    # 2. Отображаем ответ ИИ с использованием стриминга
    with st.chat_message("assistant", avatar="🤖"):
        # st.write_stream принимает генератор и отображает его вывод по мере поступления
        # Он также возвращает объединенный полный текст после завершения генератора
        full_response = st.write_stream(stream_ai_response(model_id, st.session_state.messages))

    # 3. Добавляем ПОЛНЫЙ ответ ИИ в историю сессии ПОСЛЕ завершения стриминга
    # Это нужно, чтобы при следующем запросе ИИ видел весь предыдущий ответ
    if full_response: # Проверяем, что ответ не пустой (не было ошибки)
        st.session_state.messages.append({"role": "assistant", "content": full_response})
    # Если full_response пустой или None, значит была ошибка, сообщение о ней уже выведено

# --- Футер ---
# st.divider() # Эта строка удалена или закомментирована
# Надпись про Network URL удалена