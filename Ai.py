# -*- coding: utf-8 -*-
import streamlit as st
import requests
import os
import platform
import json
import datetime
from streamlit_local_storage import LocalStorage
from duckduckgo_search import DDGS
import traceback
import re

# --- Ключ API из секретов ---
# -----------------------------

# --- Константы ---
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"
MODES = {
    "Стандарт (V3)": "deepseek/deepseek-chat-v3-0324:free",
    "DeepThink (R1)": "deepseek/deepseek-r1:free",
}
DEFAULT_MODE = "Стандарт (V3)"
LOCAL_STORAGE_KEY = "multi_chat_storage_v10" # Новый ключ
DEFAULT_CHAT_NAME = "Новый чат"
# УВЕЛИЧИВАЕМ ГЛУБИНУ ПОИСКА
MAX_SEARCH_RESULTS_PER_QUERY = 8 # <<< Увеличено
MAX_QUERIES_TO_GENERATE = 5       # <<< Увеличено
MAX_SNIPPET_LENGTH = 250          # Ограничим длину сниппета для экономии контекста

# --- Настройка страницы ---
st.set_page_config(
    page_title="Супер Умный Чат ИИ", # Изменено
    page_icon="💡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- Инициализация LocalStorage ---
localS = LocalStorage()

# --- Минимальный CSS (без изменений) ---
custom_css = f"""
<style>
    /* ... (ваш CSS без изменений) ... */
     .main .block-container {{ padding-top: 1rem; padding-bottom: 4rem; padding-left: 1rem; padding-right: 1rem; }}
    [data-testid="stChatMessage"] {{ background: none !important; border: none !important; box-shadow: none !important; padding: 0.1rem 0 !important; margin-bottom: 0.75rem !important; }}
    [data-testid="stChatMessage"] > div {{ gap: 0.75rem; }}
    [data-testid="stChatMessage"] .stChatMessageContent {{ padding: 0 !important; }}
    [data-testid="stChatMessage"] .stChatMessageContent p {{ margin-bottom: 0.2rem; }}
    [data-testid="stSidebar"] {{ padding: 1rem; }}
    [data-testid="stSidebar"] h2 {{ text-align: center; margin-bottom: 1rem; font-size: 1.4rem; }}
    [data-testid="stSidebar"] .stButton button {{ width: 100%; margin-bottom: 0.5rem; border-radius: 5px; }}
    [data-testid="stSidebar"] .stRadio [data-testid="stWidgetLabel"] {{ font-size: 0.9rem; margin-bottom: 0.3rem; font-weight: bold; }}
</style>
"""
st.markdown(custom_css, unsafe_allow_html=True)


# --- Функции для работы с чатами (без изменений в логике, только улучшена стабильность) ---
def load_all_chats():
    # ... (код load_all_chats без изменений) ...
    data_str = localS.getItem(LOCAL_STORAGE_KEY)
    if data_str:
        try:
            data = json.loads(data_str)
            if isinstance(data, dict) and "chats" in data and "active_chat" in data and isinstance(data["chats"], dict):
                for chat_name, history in data["chats"].items():
                    if not isinstance(history, list): data["chats"][chat_name] = []
                    else: data["chats"][chat_name] = [msg for msg in history if isinstance(msg, dict) and "role" in msg and "content" in msg and msg["content"]]
                if data["active_chat"] not in data["chats"]: data["active_chat"] = list(data["chats"].keys())[0] if data["chats"] else None
                if data["active_chat"] is None: raise ValueError("No active chat found after loading.")
                return data["chats"], data["active_chat"]
        except Exception as e:
            print(f"Ошибка загрузки чатов: {e}. Возврат к стандартным.")
    first_chat_name = f"{DEFAULT_CHAT_NAME} 1"
    default_chats = {first_chat_name: []}
    return default_chats, first_chat_name


def save_all_chats(chats_dict, active_chat_name):
    # ... (код save_all_chats без изменений) ...
    if isinstance(chats_dict, dict) and isinstance(active_chat_name, str):
        cleaned_chats = {}
        for name, history in chats_dict.items():
            if isinstance(history, list): cleaned_chats[name] = [msg for msg in history if isinstance(msg, dict) and "role" in msg and "content" in msg and msg["content"]]
            else: cleaned_chats[name] = []
        if active_chat_name not in cleaned_chats: active_chat_name = list(cleaned_chats.keys())[0] if cleaned_chats else None
        if active_chat_name is None: return False
        data_to_save = {"chats": cleaned_chats, "active_chat": active_chat_name}
        try:
            localS.setItem(LOCAL_STORAGE_KEY, json.dumps(data_to_save)); return True
        except Exception as e:
            print(f"Ошибка сохранения чатов: {e}")
            st.error(f"Не удалось сохранить состояние чата: {e}")
            return False
    return False


def generate_new_chat_name(existing_names):
    # ... (код generate_new_chat_name без изменений) ...
    i = 1
    while f"{DEFAULT_CHAT_NAME} {i}" in existing_names: i += 1
    return f"{DEFAULT_CHAT_NAME} {i}"

# --- Функция генерации поисковых запросов (без изменений) ---
def generate_search_queries(user_prompt, model_id):
    # ... (код generate_search_queries без изменений) ...
    try: api_key = st.secrets.get("OPENROUTER_API_KEY"); assert api_key
    except: print("API ключ OpenRouter не найден."); return []
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json", "HTTP-Referer": "http://localhost:8501", "X-Title": "Streamlit Super Smart Chat AI"}
    generation_prompt = f"""Проанализируй следующий запрос пользователя и определи основную суть вопроса. Сгенерируй до {MAX_QUERIES_TO_GENERATE} эффективных и лаконичных поисковых запросов (на русском языке), которые помогут найти самую релевантную и актуальную информацию в интернете для ответа на этот запрос. Выведи только сами запросы, каждый на новой строке, без нумерации или дополнительных пояснений. Запрос пользователя: "{user_prompt}" Поисковые запросы:"""
    payload = {"model": model_id, "messages": [{"role": "user", "content": generation_prompt}], "max_tokens": 150, "temperature": 0.3}
    generated_queries = []
    try:
        print(f"Генерация поисковых запросов для: '{user_prompt[:50]}...'")
        response = requests.post(OPENROUTER_API_URL, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        data = response.json()
        raw_queries = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        if raw_queries:
            queries = [q.strip() for q in raw_queries.split('\n') if q.strip()]
            queries = [re.sub(r"^\s*[\d\.\-\*]+\s*", "", q) for q in queries]
            generated_queries = [q for q in queries if q]
            print(f"Сгенерированные запросы: {generated_queries}")
    except Exception as e: print(f"Ошибка при генерации поисковых запросов: {e}")
    return generated_queries[:MAX_QUERIES_TO_GENERATE]


# --- МОДИФИЦИРОВАННАЯ Функция веб-поиска ---
def perform_web_search(queries: list, max_results_per_query=MAX_SEARCH_RESULTS_PER_QUERY):
    """Выполняет веб-поиск по списку запросов и агрегирует результаты БЕЗ ССЫЛОК."""
    all_results_text = ""
    if not queries: return "Не было сгенерировано поисковых запросов."
    print(f"Выполнение поиска по запросам ({len(queries)} шт.)...")
    aggregated_results = []
    try:
        with DDGS(timeout=25) as ddgs: # Увеличим общий таймаут еще
            for query_idx, query in enumerate(queries, 1):
                print(f"  Запрос {query_idx}/{len(queries)}: '{query}' (max {max_results_per_query} рез.)...")
                try:
                    search_results = list(ddgs.text(query, max_results=max_results_per_query))
                    if search_results:
                        aggregated_results.extend(search_results)
                        print(f"    Найдено {len(search_results)} результатов.")
                    else: print(f"    Результатов не найдено.")
                except Exception as e_inner: print(f"    Ошибка при поиске по запросу '{query}': {e_inner}")
        if aggregated_results:
            unique_results = {result.get('body', ''): result for result in aggregated_results if result.get('body')}.values() # Уникальность по тексту сниппета
            print(f"Всего уникальных результатов после агрегации: {len(unique_results)}")
            if unique_results:
                 all_results_text += "--- Результаты веб-поиска ---\n"
                 for i, result in enumerate(unique_results, 1):
                    title = result.get('title', 'Нет заголовка')
                    body = result.get('body', '')
                    # Укорачиваем сниппет и УБИРАЕМ ССЫЛКУ
                    body_short = (body[:MAX_SNIPPET_LENGTH] + '...') if len(body) > MAX_SNIPPET_LENGTH else body
                    all_results_text += f"{i}. {title}: {body_short}\n" # <<< ССЫЛКА УБРАНА
            else: all_results_text = "Не найдено уникальных результатов после агрегации."
        else: all_results_text = "По сгенерированным запросам ничего не найдено в сети."
        return all_results_text.strip()
    except Exception as e:
        print(f"Общая ошибка веб-поиска: {e}")
        return "Не удалось выполнить веб-поиск из-за ошибки."

# --- Инициализация состояния (без изменений) ---
if "all_chats" not in st.session_state:
    st.session_state.all_chats, st.session_state.active_chat = load_all_chats()
if "selected_mode" not in st.session_state:
    st.session_state.selected_mode = DEFAULT_MODE

# --- Определяем активный чат (без изменений) ---
active_chat_name = st.session_state.active_chat
active_chat_history = list(st.session_state.all_chats.get(active_chat_name, []))

# --- Сайдбар (без изменений) ---
with st.sidebar:
    # ... (код сайдбара без изменений) ...
    st.markdown("## 💬 Чаты")
    chat_names = list(st.session_state.all_chats.keys())
    try: active_chat_index = chat_names.index(active_chat_name)
    except ValueError: active_chat_index = 0 if chat_names else -1
    if active_chat_index != -1:
         selected_chat = st.radio("Выберите чат:", options=chat_names, index=active_chat_index, label_visibility="collapsed", key="chat_selector")
         if selected_chat != active_chat_name: st.session_state.active_chat = selected_chat; save_all_chats(st.session_state.all_chats, st.session_state.active_chat); st.rerun()
    else: st.write("Нет доступных чатов.")
    st.divider()
    if st.button("➕ Новый чат", key="new_chat_button"): new_name = generate_new_chat_name(list(st.session_state.all_chats.keys())); st.session_state.all_chats[new_name] = []; st.session_state.active_chat = new_name; save_all_chats(st.session_state.all_chats, st.session_state.active_chat); st.rerun()
    if len(chat_names) > 0 and active_chat_index != -1:
        if st.button("🗑️ Удалить текущий чат", type="secondary", key="delete_chat_button"):
            current_active_chat_to_delete = st.session_state.active_chat
            if current_active_chat_to_delete in st.session_state.all_chats:
                del st.session_state.all_chats[current_active_chat_to_delete]
                remaining_chats = list(st.session_state.all_chats.keys())
                st.session_state.active_chat = remaining_chats[0] if remaining_chats else None
                if not st.session_state.active_chat: new_name = generate_new_chat_name([]); st.session_state.all_chats = {new_name: []}; st.session_state.active_chat = new_name
                save_all_chats(st.session_state.all_chats, st.session_state.active_chat)
                st.rerun()
    st.divider()
    mode_options = list(MODES.keys()); current_mode_index = mode_options.index(st.session_state.selected_mode) if st.session_state.selected_mode in mode_options else 0
    selected_mode_radio = st.radio("Режим работы:", options=mode_options, index=current_mode_index, key="mode_selector")
    if selected_mode_radio != st.session_state.selected_mode: st.session_state.selected_mode = selected_mode_radio; st.rerun()


# --- Основная область: Чат ---
current_mode_name = st.session_state.get("selected_mode", DEFAULT_MODE)
current_model_id = MODES.get(current_mode_name, MODES[DEFAULT_MODE])

# Приветственное сообщение
if not active_chat_history and active_chat_name in st.session_state.all_chats:
     welcome_message = {"role": "assistant", "content": f"👋 Привет! Я {current_mode_name}, ваш супер-ассистент. Я могу искать актуальную информацию в сети. Спрашивайте!"}
     st.session_state.all_chats[active_chat_name] = [welcome_message]
     save_all_chats(st.session_state.all_chats, active_chat_name)
     active_chat_history = [welcome_message]

# Отображение чата
chat_display_container = st.container()
with chat_display_container:
    current_display_history = list(st.session_state.all_chats.get(active_chat_name, [])) # Свежая копия для отображения
    for message in current_display_history:
        avatar = "🧑‍💻" if message["role"] == "user" else "💡" # Сменим иконку ИИ
        with st.chat_message(message["role"], avatar=avatar):
            st.markdown(message["content"], unsafe_allow_html=True)

# --- Функция стриминга (без изменений) ---
def stream_ai_response(model_id_func, chat_history_func):
    # ... (код stream_ai_response без изменений) ...
    try: api_key = st.secrets.get("OPENROUTER_API_KEY"); assert api_key
    except: st.error("⛔ Секрет 'OPENROUTER_API_KEY' не найден.", icon="🚨"); yield None; return
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json", "HTTP-Referer": "http://localhost:8501", "X-Title": "Streamlit Super Smart Chat AI"}
    if not isinstance(chat_history_func, list): print("История чата не список."); yield None; return
    payload = {"model": model_id_func, "messages": chat_history_func, "stream": True}
    try:
        response = requests.post(OPENROUTER_API_URL, headers=headers, json=payload, stream=True, timeout=180)
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
                        delta = chunk.get("choices", [{}])[0].get("delta", {})
                        if delta and "content" in delta: # Проверяем наличие контента
                             delta_content = delta["content"]
                             if delta_content: has_content = True; yield delta_content
                    except Exception as e: print(f"Ошибка обработки чанка: {e} | Строка: {decoded_line}"); continue # Логируем ошибку и продолжаем
        if not has_content: print("Стриминг завершился без контента.")
    except requests.exceptions.Timeout: st.error("⏳ Превышено время ожидания.", icon="⏱️"); print("Таймаут API."); yield None
    except requests.exceptions.RequestException as e: st.error(f"🌐 Ошибка сети: {e}", icon="💔"); print(f"Ошибка сети: {e}"); yield None
    except Exception as e: st.error(f"💥 Ошибка ответа ИИ: {e}", icon="🔥"); print(f"Ошибка стриминга: {e}"); yield None


# --- Поле ввода пользователя (без изменений) ---
if prompt := st.chat_input(f"Спроси {current_mode_name}..."):
    if active_chat_name in st.session_state.all_chats:
        st.session_state.all_chats[active_chat_name].append({"role": "user", "content": prompt})
        save_all_chats(st.session_state.all_chats, active_chat_name)
        st.rerun()
    else: st.error("Ошибка: Активный чат не найден.")


# --- МОДИФИЦИРОВАННАЯ Логика ответа ИИ ---
current_chat_state = st.session_state.all_chats.get(active_chat_name, [])
if current_chat_state and current_chat_state[-1]["role"] == "user":

    last_user_prompt = current_chat_state[-1]["content"]
    print(f"\n--- Обработка запроса: '{last_user_prompt[:100]}...' ---")
    current_date = datetime.datetime.now().strftime("%Y-%m-%d") # Получаем текущую дату

    # --- Этап 1: Генерация поисковых запросов ---
    with st.spinner("Думаю, как лучше поискать... 🤔"): # Индикатор
        generated_queries = generate_search_queries(last_user_prompt, current_model_id)

    # --- Этап 2: Веб-поиск ---
    search_results_str = ""
    if generated_queries:
        with st.spinner(f"Ищу в сети по {len(generated_queries)} запросам... 🌐"): # Индикатор
            search_results_str = perform_web_search(generated_queries)
    else:
        print("ИИ не сгенерировал запросы, поиск по исходному запросу.")
        with st.spinner("Ищу в сети по вашему запросу... 🌐"): # Индикатор
             search_results_str = perform_web_search([last_user_prompt], max_results_per_query=MAX_SEARCH_RESULTS_PER_QUERY) # Используем те же параметры

    # --- Этап 3: Подготовка контекста для финального ответа ---
    context_for_final_answer = list(current_chat_state)
    is_search_successful = not ("Не удалось" in search_results_str or "не найдено" in search_results_str or "Не было сгенерировано" in search_results_str)

    if is_search_successful and search_results_str:
        # НОВЫЙ, УСИЛЕННЫЙ СИСТЕМНЫЙ ПРОМПТ
        search_context_message = {
            "role": "system",
            "content": (
                f"ВАЖНО: Сегодня {current_date}. При ответе на запрос пользователя ОБЯЗАТЕЛЬНО учти эту дату и предоставленные ниже результаты веб-поиска. "
                f"Твоя задача - дать максимально точный и АКТУАЛЬНЫЙ ответ, основываясь ПРЕЖДЕ ВСЕГО на найденной в сети информации.\n\n"
                f"{search_results_str}\n--- Конец результатов ---\n\n"
                "Инструкция для ИИ:\n"
                "1.  **Приоритет веб-поиска:** Информация из результатов поиска имеет ВЫСШИЙ ПРИОРИТЕТ над твоими внутренними знаниями, особенно для фактов, дат, текущих событий, имен и должностей.\n"
                "2.  **Актуальность:** Если вопрос касается текущего положения дел (например, 'кто сейчас президент?', 'последние новости о X'), ответ ДОЛЖЕН отражать информацию из поиска по состоянию на {current_date}.\n"
                "3.  **Синтез:** Не пересказывай результаты поиска по пунктам. Твоя задача — синтезировать информацию из РАЗНЫХ сниппетов, чтобы дать связный и полный ответ на ОРИГИНАЛЬНЫЙ запрос пользователя.\n"
                "4.  **Игнорирование нерелевантного:** Если какие-то результаты поиска явно не относятся к запросу пользователя, игнорируй их.\n"
                "5.  **Отсутствие информации:** Если поиск не дал релевантной информации, честно скажи об этом и отвечай на основе своих знаний, но укажи на возможное устаревание информации.\n"
                "6.  **Без ссылок:** Не включай в свой ответ URL-адреса или формат ссылок Markdown.\n\n"
                "Теперь, основываясь на ВСЕХ этих инструкциях и результатах поиска, ответь на запрос пользователя (он последний в истории)."
            )
        }
        context_for_final_answer.insert(-1, search_context_message)
        print("Результаты поиска и усиленный промпт добавлены в контекст.")

    elif search_results_str: # Поиск не удался или ничего не нашел
         search_context_message = {
            "role": "system",
             "content": f"(Примечание: {search_results_str}. Сегодня {current_date}. Отвечай на запрос пользователя, основываясь на своих знаниях, но предупреди о возможной неактуальности данных.)"
         }
         context_for_final_answer.insert(-1, search_context_message)
         print("В контекст добавлено уведомление о неудачном поиске.")
    else: # Не было ни результатов, ни сообщения об ошибке (маловероятно)
        search_context_message = {
            "role": "system",
             "content": f"(Примечание: Веб-поиск не дал результатов. Сегодня {current_date}. Отвечай на запрос пользователя, основываясь на своих знаниях, но предупреди о возможной неактуальности данных.)"
         }
        context_for_final_answer.insert(-1, search_context_message)
        print("В контекст добавлено уведомление об отсутствии результатов поиска.")


    # --- Этап 4: Генерация и отображение финального ответа ---
    with chat_display_container:
        with st.chat_message("assistant", avatar="💡"):
            print("Запрос финального ответа у ИИ...")
            # Добавляем индикатор и сюда
            with st.spinner("Формулирую ответ... ✍️"):
                 response_generator = stream_ai_response(current_model_id, context_for_final_answer)
                 full_response = st.write_stream(response_generator)
            print("Финальный ответ получен.")

    # --- Этап 5: Сохранение ответа ---
    if full_response:
        if active_chat_name in st.session_state.all_chats:
             st.session_state.all_chats[active_chat_name].append({"role": "assistant", "content": full_response})
             save_all_chats(st.session_state.all_chats, active_chat_name)
             print("Ответ ассистента сохранен.")
        else: print("Ошибка: Активный чат исчез перед сохранением ответа.")
    else:
        print("Финальный ответ пуст, сохранение не требуется.")

    print("--- Обработка запроса завершена ---")


# --- Футер ---
# Убран
