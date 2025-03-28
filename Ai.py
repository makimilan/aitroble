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
LOCAL_STORAGE_KEY = "multi_chat_storage_v13" # Новый ключ
DEFAULT_CHAT_NAME = "Новый чат"
MAX_SEARCH_RESULTS_PER_QUERY = 4 # Можно чуть меньше, т.к. запросы должны быть точнее
MAX_QUERIES_IN_RESPONSE = 3      # Сколько запросов ожидаем от ИИ
MAX_SNIPPET_LENGTH = 220
SEARCH_TRIGGER_TOKEN = "[SEARCH_NEEDED]"

# --- Настройка страницы ---
st.set_page_config(
    page_title="Самостоятельный Чат ИИ", page_icon="🤖", layout="wide", initial_sidebar_state="expanded"
)

# --- Инициализация LocalStorage ---
localS = LocalStorage()

# --- Минимальный CSS (без изменений) ---
custom_css = f"""
<style>
    /* ... ваш CSS ... */
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

# --- Функции для работы с чатами (без изменений) ---
def load_all_chats():
    # ... (код load_all_chats) ...
    data_str = localS.getItem(LOCAL_STORAGE_KEY); default_chats = {f"{DEFAULT_CHAT_NAME} 1": []}; default_name = f"{DEFAULT_CHAT_NAME} 1"
    if data_str:
        try:
            data = json.loads(data_str)
            if isinstance(data, dict) and "chats" in data and "active_chat" in data and isinstance(data["chats"], dict):
                for name, history in data["chats"].items(): data["chats"][name] = [msg for msg in history if isinstance(msg, dict) and msg.get("role") and msg.get("content")] if isinstance(history, list) else []
                if not data["chats"]: return default_chats, default_name
                if data["active_chat"] not in data["chats"]: data["active_chat"] = list(data["chats"].keys())[0]
                return data["chats"], data["active_chat"]
        except Exception as e: print(f"Ошибка загрузки: {e}.")
    return default_chats, default_name

def save_all_chats(chats_dict, active_chat_name):
    # ... (код save_all_chats) ...
    if isinstance(chats_dict, dict) and isinstance(active_chat_name, str):
        cleaned_chats = {}
        for name, history in chats_dict.items(): cleaned_chats[name] = [msg for msg in history if isinstance(msg, dict) and msg.get("role") and msg.get("content")] if isinstance(history, list) else []
        if not cleaned_chats: active_chat_name = None
        elif active_chat_name not in cleaned_chats: active_chat_name = list(cleaned_chats.keys())[0] if cleaned_chats else None
        if active_chat_name is None and cleaned_chats: active_chat_name = list(cleaned_chats.keys())[0] # Подстраховка
        data_to_save = {"chats": cleaned_chats, "active_chat": active_chat_name}
        try: localS.setItem(LOCAL_STORAGE_KEY, json.dumps(data_to_save)); return True
        except Exception as e: print(f"Ошибка сохранения: {e}"); return False
    return False

def generate_new_chat_name(existing_names):
    # ... (код generate_new_chat_name) ...
    i = 1; base_name = DEFAULT_CHAT_NAME
    while f"{base_name} {i}" in existing_names: i += 1
    return f"{base_name} {i}"

# --- НОВАЯ Функция для первого вызова ИИ (Решение + Запросы ИЛИ Ответ) ---
def get_ai_decision_or_response(model_id, chat_history_with_prompt):
    """Делает НЕСТРИМИНГОВЫЙ вызов ИИ для получения решения о поиске или прямого ответа."""
    try: api_key = st.secrets.get("OPENROUTER_API_KEY"); assert api_key
    except: st.error("API ключ не найден."); return None

    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {"model": model_id, "messages": chat_history_with_prompt, "stream": False} # stream=False

    try:
        print("Запрос решения/ответа у ИИ...")
        response = requests.post(OPENROUTER_API_URL, headers=headers, json=payload, timeout=45) # Увеличим таймаут
        response.raise_for_status()
        data = response.json()
        full_content = data.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
        print(f"  Получен ответ ИИ (для анализа): '{full_content[:150]}...'")
        return full_content
    except requests.exceptions.Timeout:
        st.error("Таймаут при запросе решения у ИИ."); print("Таймаут API (решение).")
        return None
    except requests.exceptions.RequestException as e:
        st.error(f"Ошибка сети при запросе решения: {e}"); print(f"Ошибка сети (решение): {e}")
        return None
    except Exception as e:
        st.error(f"Ошибка при получении решения от ИИ: {e}"); print(f"Ошибка API (решение): {e}")
        return None

# --- Функция веб-поиска (без изменений) ---
def perform_web_search(queries: list, max_results_per_query=MAX_SEARCH_RESULTS_PER_QUERY):
    # ... (код perform_web_search) ...
    all_results_text = ""; aggregated_results = []
    if not queries: return "Нет запросов для поиска."
    print(f"Поиск по {len(queries)} запросам...");
    try:
        with DDGS(timeout=25) as ddgs:
            for idx, query in enumerate(queries, 1): print(f"  Запрос {idx}/{len(queries)}: '{query}'..."); search_results = list(ddgs.text(query, max_results=max_results_per_query)); aggregated_results.extend(search_results)
        if aggregated_results:
            unique_results = {res.get('body', ''): res for res in aggregated_results if res.get('body')}.values(); print(f"Всего уникальных результатов: {len(unique_results)}")
            if unique_results:
                 all_results_text += "--- Результаты веб-поиска ---\n"; [all_results_text := all_results_text + f"{i}. {res.get('title', '')}: {(res.get('body', '')[:MAX_SNIPPET_LENGTH] + '...') if len(res.get('body', '')) > MAX_SNIPPET_LENGTH else res.get('body', '')}\n" for i, res in enumerate(unique_results, 1)]
            else: all_results_text = "Не найдено уникальных результатов."
        else: all_results_text = "Поиск не дал результатов."
        return all_results_text.strip()
    except Exception as e: print(f"Ошибка веб-поиска: {e}"); return "Ошибка веб-поиска."


# --- Функция стриминга (остается для второго вызова) ---
def stream_ai_response(model_id_func, chat_history_func):
    # ... (код stream_ai_response без изменений) ...
    try: api_key = st.secrets.get("OPENROUTER_API_KEY"); assert api_key
    except: st.error("⛔ API ключ не найден.", icon="🚨"); yield None; return
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json", "HTTP-Referer": "http://localhost:8501", "X-Title": "Streamlit Self-Deciding Chat AI"}
    if not isinstance(chat_history_func, list): yield None; return
    payload = {"model": model_id_func, "messages": chat_history_func, "stream": True}
    try:
        response = requests.post(OPENROUTER_API_URL, headers=headers, json=payload, stream=True, timeout=180)
        response.raise_for_status(); has_content = False
        for line in response.iter_lines():
            if line:
                decoded_line = line.decode('utf-8')
                if decoded_line.startswith("data: "):
                    try:
                        json_data = decoded_line[len("data: "):]; chunk = json.loads(json_data)
                        if json_data.strip() == "[DONE]": break
                        delta = chunk.get("choices", [{}])[0].get("delta", {})
                        if delta and "content" in delta: delta_content = delta["content"]; has_content = True; yield delta_content
                    except Exception as e: print(f"Ошибка чанка: {e}"); continue
        if not has_content: print("Стриминг без контента.")
    except Exception as e: print(f"Ошибка стриминга: {e}"); yield None


# --- Инициализация состояния (без изменений) ---
if "all_chats" not in st.session_state: st.session_state.all_chats, st.session_state.active_chat = load_all_chats()
if "selected_mode" not in st.session_state: st.session_state.selected_mode = DEFAULT_MODE

# --- Определяем активный чат (без изменений) ---
active_chat_name = st.session_state.active_chat

# --- Сайдбар (без изменений) ---
with st.sidebar:
    # ... (код сайдбара) ...
    st.markdown("## 💬 Чаты"); chat_names = list(st.session_state.all_chats.keys())
    try: active_chat_index = chat_names.index(active_chat_name) if active_chat_name in chat_names else (0 if chat_names else -1)
    except ValueError: active_chat_index = 0 if chat_names else -1 # Доп. защита
    if active_chat_index != -1: selected_chat = st.radio("Выберите чат:", options=chat_names, index=active_chat_index, label_visibility="collapsed", key="chat_selector"); assert selected_chat is not None; if selected_chat != active_chat_name: st.session_state.active_chat = selected_chat; save_all_chats(st.session_state.all_chats, st.session_state.active_chat); st.rerun()
    else: st.write("Нет чатов.")
    st.divider()
    if st.button("➕ Новый чат", key="new_chat_button"): new_name = generate_new_chat_name(list(st.session_state.all_chats.keys())); st.session_state.all_chats[new_name] = []; st.session_state.active_chat = new_name; save_all_chats(st.session_state.all_chats, st.session_state.active_chat); st.rerun()
    if len(chat_names) > 0 and active_chat_index != -1:
        if st.button("🗑️ Удалить текущий чат", type="secondary", key="delete_chat_button"):
            current_chat_to_delete = st.session_state.active_chat
            if current_chat_to_delete in st.session_state.all_chats: del st.session_state.all_chats[current_chat_to_delete]; remaining_chats = list(st.session_state.all_chats.keys()); st.session_state.active_chat = remaining_chats[0] if remaining_chats else None;
            if not st.session_state.active_chat: new_name = generate_new_chat_name([]); st.session_state.all_chats = {new_name: []}; st.session_state.active_chat = new_name
            save_all_chats(st.session_state.all_chats, st.session_state.active_chat); st.rerun()
    st.divider()
    mode_options = list(MODES.keys()); current_mode_index = mode_options.index(st.session_state.selected_mode) if st.session_state.selected_mode in mode_options else 0
    selected_mode_radio = st.radio("Режим работы:", options=mode_options, index=current_mode_index, key="mode_selector"); assert selected_mode_radio is not None; if selected_mode_radio != st.session_state.selected_mode: st.session_state.selected_mode = selected_mode_radio; st.rerun()


# --- Основная область: Чат ---
current_mode_name = st.session_state.get("selected_mode", DEFAULT_MODE)
current_model_id = MODES.get(current_mode_name, MODES[DEFAULT_MODE])

# --- Поле ввода пользователя и ОБРАБОТКА ---
user_prompt_submitted = False
if prompt := st.chat_input(f"Спроси {current_mode_name}..."):
    if active_chat_name in st.session_state.all_chats:
        st.session_state.all_chats[active_chat_name].append({"role": "user", "content": prompt})
        save_all_chats(st.session_state.all_chats, active_chat_name)
        user_prompt_submitted = True
        # НЕ rerun()
    else: st.error("Ошибка: Активный чат не найден.")

# --- Логика ответа ИИ ---
current_chat_state = st.session_state.all_chats.get(active_chat_name, [])

# Выполняем, если последнее сообщение от пользователя
if current_chat_state and current_chat_state[-1]["role"] == "user":

    last_user_prompt = current_chat_state[-1]["content"]
    print(f"\n--- Обработка: '{last_user_prompt[:100]}...' ---")
    current_date = datetime.datetime.now().strftime("%Y-%m-%d")

    # --- Этап 1: Первый вызов ИИ (Решение + Запросы ИЛИ Ответ) ---
    # Готовим контекст для ПЕРВОГО вызова
    initial_context = list(current_chat_state)
    # Добавляем СПЕЦИАЛЬНЫЙ системный промпт для принятия решения
    decision_system_prompt = {
        "role": "system",
        "content": f"""Твоя задача - проанализировать последний запрос пользователя.
1. Если запрос ТРЕБУЕТ поиска актуальной информации в интернете (новости, события после 2023, текущие данные типа погоды/статуса/президента, или явная просьба поискать), ответь ТОЛЬКО так:
{SEARCH_TRIGGER_TOKEN}
Запрос 1 для поиска
Запрос 2 для поиска (если нужно)
Запрос 3 для поиска (если нужно)

2. Если запрос НЕ требует поиска (общие знания, история до 2023, творчество, small talk, арифметика, вопрос о тебе), просто ОТВЕТЬ на него полно и развернуто БЕЗ использования токена {SEARCH_TRIGGER_TOKEN}.

Сегодня {current_date}. Последний запрос пользователя находится в конце истории."""
    }
    initial_context.insert(0, decision_system_prompt) # Вставляем в начало для важности

    ai_initial_response = None
    with st.spinner("Думаю... 🤔"): # Общий спиннер для первого вызова
        ai_initial_response = get_ai_decision_or_response(current_model_id, initial_context)

    needs_search = False
    search_queries = []
    direct_answer = None
    final_response_to_save = None # Переменная для ответа, который пойдет в историю

    if ai_initial_response and ai_initial_response.startswith(SEARCH_TRIGGER_TOKEN):
        needs_search = True
        print(">>> ИИ решил, что нужен поиск.")
        # Извлекаем запросы
        lines = ai_initial_response.split('\n')
        search_queries = [q.strip() for q in lines[1:] if q.strip()] # Берем строки после токена
        search_queries = search_queries[:MAX_QUERIES_IN_RESPONSE] # Ограничиваем
        print(f"  Предложенные запросы: {search_queries}")
    elif ai_initial_response:
        # Если токена нет, значит это прямой ответ
        print(">>> ИИ решил ответить напрямую.")
        direct_answer = ai_initial_response
        final_response_to_save = direct_answer # Этот ответ и сохраним
    else:
        # Ошибка при первом вызове
        print(">>> Ошибка при получении решения/ответа от ИИ.")
        # Отобразим сообщение об ошибке (уже сделано в get_ai_decision_or_response через st.error)
        # Ничего не сохраняем, выходим из блока обработки
        pass # Переходим к отрисовке чата

    # --- Этап 2-4 (Если нужен поиск) ---
    if needs_search:
        search_results_str = ""
        if search_queries:
            with st.spinner(f"Ищу в сети по запросам ИИ... 🌐"):
                search_results_str = perform_web_search(search_queries)
        else:
            print("ИИ запросил поиск, но не предоставил запросы. Поиск не выполнен.")
            search_results_str = "ИИ запросил поиск, но не предоставил запросы." # Уведомление

        # Готовим контекст для ВТОРОГО вызова (финальный ответ)
        context_for_final_answer = list(current_chat_state) # Берем ОРИГИНАЛЬНУЮ историю
        is_search_successful = not ("Ошибка" in search_results_str or "не найдено" in search_results_str or "Нет запросов" in search_results_str)

        # Системный промпт для второго вызова
        second_system_prompt = {"role": "system"}
        if is_search_successful and search_results_str:
             second_system_prompt["content"] = (
                 f"ВАЖНО: Сегодня {current_date}. Был выполнен веб-поиск по запросам, которые ты сгенерировал ранее. Результаты ниже. "
                 f"Используй их как ОСНОВНОЙ источник для актуального и полного ответа на ОРИГИНАЛЬНЫЙ запрос пользователя.\n\n"
                 f"{search_results_str}\n--- Конец результатов ---\n\n"
                 "Инструкция: Синтезируй ответ из результатов. Без ссылок. Ответь на оригинальный запрос пользователя."
             )
             print("Контекст поиска добавлен для финального ответа.")
        else:
             second_system_prompt["content"] = (
                 f"(Примечание: Инициированный тобой веб-поиск не дал результатов ({search_results_str}). Сегодня {current_date}. "
                 f"Отвечай на оригинальный запрос пользователя на основе своих знаний, предупредив о возможной неактуальности.)"
             )
             print("Добавлено уведомление о неудачном поиске для финального ответа.")

        context_for_final_answer.insert(-1, second_system_prompt) # Вставляем перед последним сообщением пользователя

        # Выполняем ВТОРОЙ вызов (стриминг)
        with st.chat_message("assistant", avatar="🤖"): # Используем стандартный аватар
            print("Запрос финального ответа (после поиска)..."); spinner_message = "Анализирую веб-данные... ✍️" if is_search_successful else "Поиск не помог, отвечаю... 🤔"
            with st.spinner(spinner_message):
                 response_generator = stream_ai_response(current_model_id, context_for_final_answer)
                 final_response_streamed = st.write_stream(response_generator)
                 final_response_to_save = final_response_streamed # Сохраняем стриминговый ответ
            print("Финальный ответ (после поиска) получен.")

    # --- Отображение прямого ответа (если поиск не нужен) ---
    elif direct_answer:
        with st.chat_message("assistant", avatar="🤖"):
            st.markdown(direct_answer) # Просто выводим полученный ответ
        print("Прямой ответ отображен.")

    # --- Сохранение финального ответа (если он есть) ---
    if final_response_to_save:
        if active_chat_name in st.session_state.all_chats:
             # Проверяем, не дублируется ли ответ (на случай странного поведения)
             if not current_chat_state or current_chat_state[-1].get("content") != final_response_to_save:
                 st.session_state.all_chats[active_chat_name].append({"role": "assistant", "content": final_response_to_save})
                 save_all_chats(st.session_state.all_chats, active_chat_name)
                 print("Ответ ассистента сохранен.")
             else:
                  print("Ответ ассистента уже присутствует в истории, повторное сохранение пропущено.")
        else: print("Ошибка сохранения: чат исчез.")
    elif not needs_search and not direct_answer:
         print("Нет ответа для сохранения (возможно, была ошибка на первом этапе).")


    print("--- Обработка завершена ---")
    # НЕ rerun()

# --- Отображение чата (в конце) ---
chat_display_container = st.container()
with chat_display_container:
    final_display_history = list(st.session_state.all_chats.get(active_chat_name, []))
    for message in final_display_history:
        avatar = "🧑‍💻" if message["role"] == "user" else "🤖" # Стандартный аватар
        with st.chat_message(message["role"], avatar=avatar):
            st.markdown(message["content"], unsafe_allow_html=True)

# --- Футер ---
# Убран
