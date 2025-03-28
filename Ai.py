# -*- coding: utf-8 -*-
import streamlit as st
import requests
import os
import platform
import json
import datetime
from streamlit_local_storage import LocalStorage
from duckduckgo_search import DDGS # <--- Импорт для DuckDuckGo
import traceback # <--- Для отладки ошибок поиска

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
MAX_SEARCH_RESULTS = 5 # <--- Увеличено количество результатов

# --- Настройка страницы ---
st.set_page_config(
    page_title="Чат ИИ с веб-поиском",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- Инициализация LocalStorage ---
localS = LocalStorage()

# --- Минимальный CSS для чистоты чата ---
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
        except Exception as e:
            print(f"Ошибка сохранения чатов: {e}")
            return False
    return False

def generate_new_chat_name(existing_names):
    i = 1
    while f"{DEFAULT_CHAT_NAME} {i}" in existing_names: i += 1
    return f"{DEFAULT_CHAT_NAME} {i}"

# --- Функция веб-поиска ---
def perform_web_search(query, max_results=MAX_SEARCH_RESULTS):
    """Выполняет веб-поиск с помощью DuckDuckGo и возвращает форматированные результаты."""
    results_text = ""
    # st.write(...) # <--- Индикатор поиска УДАЛЕН
    search_results = []
    try:
        # Используем менеджер контекста для DDGS
        with DDGS(timeout=10) as ddgs: # Установим таймаут
             search_results = list(ddgs.text(query, max_results=max_results))

        if search_results:
            results_text += "--- Результаты веб-поиска ---\n"
            for i, result in enumerate(search_results, 1):
                title = result.get('title', 'Нет заголовка')
                body = result.get('body', 'Нет описания')
                href = result.get('href', '#')
                # Укорачиваем описание для краткости
                body_short = (body[:180] + '...') if len(body) > 180 else body
                results_text += f"{i}. [{title}]({href}): {body_short}\n" # Добавим ссылку
            # Убрал "--- Конец результатов поиска ---" из строки результатов, т.к. добавляю в промпт ниже
        else:
             results_text = "По вашему запросу ничего не найдено в сети."

        return results_text.strip() # Возвращаем только сами результаты или сообщение об отсутствии

    except Exception as e:
        print(f"Ошибка веб-поиска: {e}") # Логируем ошибку
        # traceback.print_exc() # Раскомментируйте для детальной отладки
        return "Не удалось выполнить веб-поиск из-за ошибки."

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

# --- Определяем активный чат ДО обработки ввода/вывода ---
active_chat_name = st.session_state.active_chat
active_chat_history = list(st.session_state.all_chats.get(active_chat_name, []))

# --- Сайдбар: Управление чатами и режимом ---
with st.sidebar:
    st.markdown("## 💬 Чаты")
    chat_names = list(st.session_state.all_chats.keys())
    try: active_chat_index = chat_names.index(active_chat_name)
    except ValueError: active_chat_index = 0

    selected_chat = st.radio(
        "Выберите чат:", options=chat_names, index=active_chat_index,
        label_visibility="collapsed", key="chat_selector"
    )

    if selected_chat != active_chat_name:
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
        st.rerun()

# --- Основная область: Чат ---
current_mode_name = st.session_state.get("selected_mode", DEFAULT_MODE)
current_model_id = MODES.get(current_mode_name, MODES[DEFAULT_MODE])

# Отображение приветственного сообщения, если чат пуст
if not active_chat_history:
     welcome_message = {"role": "assistant", "content": f"👋 Привет! Я {current_mode_name} с доступом к веб-поиску. Начнем новый чат!"}
     st.session_state.all_chats[active_chat_name] = [welcome_message]
     save_all_chats(st.session_state.all_chats, active_chat_name)
     active_chat_history = [welcome_message]

# Контейнер для сообщений
chat_display_container = st.container()
with chat_display_container:
    for message in active_chat_history:
        avatar = "🧑‍💻" if message["role"] == "user" else "🤖"
        with st.chat_message(message["role"], avatar=avatar):
            st.markdown(message["content"], unsafe_allow_html=True)

# --- Функция стриминга (без изменений) ---
def stream_ai_response(model_id_func, chat_history_func):
    try:
        api_key_from_secrets = st.secrets.get("OPENROUTER_API_KEY")
        if not api_key_from_secrets:
             st.error("⛔ Секрет 'OPENROUTER_API_KEY' не найден или пустой.", icon="🚨")
             yield None; return
    except Exception as e:
        st.error(f"🤯 Ошибка доступа к секретам: {e}", icon="💥")
        yield None; return

    headers = {"Authorization": f"Bearer {api_key_from_secrets}", "Content-Type": "application/json"}
    if not isinstance(chat_history_func, list):
        print("Ошибка: История чата должна быть списком.")
        yield None; return

    headers.update({
        "HTTP-Referer": "http://localhost:8501", # Замените, если нужно
        "X-Title": "Streamlit Chat AI"
    })

    payload = {"model": model_id_func, "messages": chat_history_func, "stream": True}

    try:
        response = requests.post(OPENROUTER_API_URL, headers=headers, json=payload, stream=True, timeout=120)
        response.raise_for_status()
        has_content = False
        for line in response.iter_lines():
            if line:
                decoded_line = line.decode('utf-8')
                if decoded_line.startswith("data: "):
                    try:
                        json_data = decoded_line[len("data: "):]
                        if json_data.strip() == "[DONE]": break
                        chunk = json.loads(json_data)
                        delta_content = chunk.get("choices", [{}])[0].get("delta", {}).get("content")
                        if delta_content:
                            has_content = True
                            yield delta_content
                    except json.JSONDecodeError:
                        print(f"Ошибка декодирования JSON: {decoded_line}")
                        continue
                    except Exception as e_json:
                        print(f"Ошибка обработки чанка: {e_json}")
                        continue
        if not has_content:
             print("Стриминг завершился без получения контента.")

    except requests.exceptions.Timeout:
        st.error("⏳ Превышено время ожидания ответа от ИИ.", icon="⏱️")
        print("Ошибка: Таймаут запроса к API.")
        yield None
    except requests.exceptions.RequestException as e:
        st.error(f"🌐 Ошибка сети при запросе к ИИ: {e}", icon="💔")
        print(f"Ошибка сети: {e}")
        yield None
    except Exception as e:
        st.error(f"💥 Неожиданная ошибка при получении ответа ИИ: {e}", icon="🔥")
        print(f"Неожиданная ошибка стриминга: {e}")
        yield None


# --- Поле ввода пользователя ---
if prompt := st.chat_input(f"Спроси {current_mode_name}..."):
    st.session_state.all_chats[active_chat_name].append({"role": "user", "content": prompt})
    save_all_chats(st.session_state.all_chats, active_chat_name)
    st.rerun()

# --- Логика ответа ИИ (после rerun, если последнее сообщение от пользователя) ---
current_chat_state = st.session_state.all_chats.get(active_chat_name, [])
if current_chat_state and current_chat_state[-1]["role"] == "user":

    last_user_prompt = current_chat_state[-1]["content"]

    # --- Веб-поиск ---
    search_results_str = perform_web_search(last_user_prompt) # Результаты или сообщение об ошибке/отсутствии

    # --- Подготовка контекста для ИИ ---
    context_for_ai = list(current_chat_state)

    # Проверяем, что поиск был успешным и что-то вернул (не сообщение об ошибке/отсутствии)
    is_search_successful = not ("Не удалось" in search_results_str or "не найдено" in search_results_str)

    if is_search_successful and search_results_str:
        search_context_message = {
            "role": "system",
            "content": (
                f"Ниже приведены результаты веб-поиска по последнему запросу пользователя. Проанализируй их.\n\n"
                # Убрали разделители из search_results_str, добавляем их здесь
                f"{search_results_str}\n--- Конец результатов ---\n\n"
                "Инструкция: Используй информацию из этих результатов, если она напрямую относится к вопросу пользователя и помогает дать более точный, полный и актуальный ответ. "
                "Цитировать результаты дословно не нужно, интегрируй полезную информацию в свой ответ естественно. "
                "Если результаты нерелевантны или не несут ценности для ответа, проигнорируй их. "
                "Теперь ответь на основной запрос пользователя:"
            )
        }
        context_for_ai.insert(-1, search_context_message)
    elif search_results_str: # Если поиск не удался или ничего не нашел, но вернул сообщение
         search_context_message = {
            "role": "system",
             "content": f"(Примечание: {search_results_str}) Отвечай на запрос пользователя:"
         }
         context_for_ai.insert(-1, search_context_message)
    # Если search_results_str пустой (маловероятно, но на всякий случай), ничего не добавляем

    # --- Отображение ответа ИИ ---
    with chat_display_container:
        with st.chat_message("assistant", avatar="🤖"):
            response_generator = stream_ai_response(current_model_id, context_for_ai)
            full_response = st.write_stream(response_generator)

    # --- Сохранение ответа ИИ ---
    if full_response:
        st.session_state.all_chats[active_chat_name].append({"role": "assistant", "content": full_response})
        save_all_chats(st.session_state.all_chats, active_chat_name)

# --- Футер ---
# Убран
