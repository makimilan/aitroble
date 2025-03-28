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
LOCAL_STORAGE_KEY = "multi_chat_storage_v14" # Ключ из предыдущей версии
DEFAULT_CHAT_NAME = "Новый чат"
MAX_SEARCH_RESULTS_PER_QUERY = 5
MAX_QUERIES_TO_GENERATE = 3
MAX_SNIPPET_LENGTH = 250

# --- Настройка страницы ---
st.set_page_config(
    page_title="Чат ИИ с Переключателем Поиска", page_icon="💡", layout="wide", initial_sidebar_state="expanded"
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
    [data-testid="stSidebar"] [data-testid="stToggle"] label {{ font-size: 0.95rem; font-weight: bold; }}
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
                if not data["chats"]: st.session_state.web_search_enabled = False; return default_chats, default_name # Инициализируем поиск при пустых чатах
                if data["active_chat"] not in data["chats"]: data["active_chat"] = list(data["chats"].keys())[0]
                st.session_state.web_search_enabled = data.get("web_search_enabled", False) # Загружаем состояние поиска
                return data["chats"], data["active_chat"]
        except Exception as e: print(f"Ошибка загрузки: {e}.")
    st.session_state.web_search_enabled = False # Инициализируем поиск при ошибке/первом запуске
    return default_chats, default_name

def save_all_chats(chats_dict, active_chat_name, web_search_state):
    # ... (код save_all_chats с добавлением web_search_state) ...
    if isinstance(chats_dict, dict) and isinstance(active_chat_name, str):
        cleaned_chats = {}
        for name, history in chats_dict.items(): cleaned_chats[name] = [msg for msg in history if isinstance(msg, dict) and msg.get("role") and msg.get("content")] if isinstance(history, list) else []
        if not cleaned_chats: active_chat_name = None
        elif active_chat_name not in cleaned_chats: active_chat_name = list(cleaned_chats.keys())[0] if cleaned_chats else None
        if active_chat_name is None and cleaned_chats: active_chat_name = list(cleaned_chats.keys())[0]
        data_to_save = {"chats": cleaned_chats, "active_chat": active_chat_name, "web_search_enabled": web_search_state}
        try: localS.setItem(LOCAL_STORAGE_KEY, json.dumps(data_to_save)); return True
        except Exception as e: print(f"Ошибка сохранения: {e}"); return False
    return False

def generate_new_chat_name(existing_names):
    # ... (код generate_new_chat_name) ...
    i = 1; base_name = DEFAULT_CHAT_NAME
    while f"{base_name} {i}" in existing_names: i += 1
    return f"{base_name} {i}"

# --- Функция генерации поисковых запросов (без изменений) ---
def generate_search_queries(user_prompt, model_id):
    # ... (код generate_search_queries) ...
    try: api_key = st.secrets.get("OPENROUTER_API_KEY"); assert api_key
    except: print("API ключ не найден."); return []
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json", "HTTP-Referer": "http://localhost:8501", "X-Title": "Streamlit Toggle Search Chat AI"}
    generation_prompt = f"""Проанализируй запрос пользователя. Сгенерируй до {MAX_QUERIES_TO_GENERATE} эффективных и лаконичных поисковых запросов (на русском), которые помогут найти актуальную информацию в интернете. Выведи только запросы, каждый на новой строке. Запрос: "{user_prompt}" Запросы:"""
    payload = {"model": model_id, "messages": [{"role": "user", "content": generation_prompt}], "max_tokens": 100, "temperature": 0.3}
    generated_queries = []
    try:
        print(f"Генерация запросов для: '{user_prompt[:50]}...'"); response = requests.post(OPENROUTER_API_URL, headers=headers, json=payload, timeout=30)
        response.raise_for_status(); data = response.json(); raw_queries = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        if raw_queries:
            queries = [re.sub(r"^\s*[\d\.\-\*]+\s*", "", q.strip()) for q in raw_queries.split('\n') if q.strip()]
            generated_queries = [q for q in queries if q]; print(f"  Сгенерировано: {generated_queries}")
    except Exception as e: print(f"  Ошибка генерации запросов: {e}")
    return generated_queries[:MAX_QUERIES_TO_GENERATE]

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

# --- Функция стриминга (без изменений) ---
def stream_ai_response(model_id_func, chat_history_func):
    # ... (код stream_ai_response) ...
    try: api_key = st.secrets.get("OPENROUTER_API_KEY"); assert api_key
    except: st.error("⛔ API ключ не найден.", icon="🚨"); yield None; return
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json", "HTTP-Referer": "http://localhost:8501", "X-Title": "Streamlit Toggle Search Chat AI"}
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

# --- Инициализация состояния ---
if "all_chats" not in st.session_state: st.session_state.all_chats, st.session_state.active_chat = load_all_chats()
if "selected_mode" not in st.session_state: st.session_state.selected_mode = DEFAULT_MODE
if "web_search_enabled" not in st.session_state: st.session_state.web_search_enabled = False

# --- Определяем активный чат ---
if st.session_state.active_chat not in st.session_state.all_chats:
    if st.session_state.all_chats: st.session_state.active_chat = list(st.session_state.all_chats.keys())[0]
    else:
        new_name = generate_new_chat_name([]); st.session_state.all_chats[new_name] = []; st.session_state.active_chat = new_name
        save_all_chats(st.session_state.all_chats, st.session_state.active_chat, st.session_state.web_search_enabled)
active_chat_name = st.session_state.active_chat

# --- Сайдбар ---
with st.sidebar:
    st.markdown("## 💬 Чаты")
    chat_names = list(st.session_state.all_chats.keys())
    try: active_chat_index = chat_names.index(active_chat_name) if active_chat_name in chat_names else (0 if chat_names else -1)
    except ValueError: active_chat_index = 0 if chat_names else -1

    if active_chat_index != -1:
        selected_chat = st.radio("Выберите чат:", options=chat_names, index=active_chat_index, label_visibility="collapsed", key="chat_selector")
        if selected_chat is not None and selected_chat != active_chat_name:
            st.session_state.active_chat = selected_chat
            save_all_chats(st.session_state.all_chats, st.session_state.active_chat, st.session_state.web_search_enabled)
            st.rerun()
    else: st.write("Нет доступных чатов.")

    st.divider()
    if st.button("➕ Новый чат", key="new_chat_button"):
        new_name = generate_new_chat_name(list(st.session_state.all_chats.keys())); st.session_state.all_chats[new_name] = []; st.session_state.active_chat = new_name
        save_all_chats(st.session_state.all_chats, st.session_state.active_chat, st.session_state.web_search_enabled)
        st.rerun()

    if len(chat_names) > 0 and active_chat_index != -1:
        if st.button("🗑️ Удалить текущий чат", type="secondary", key="delete_chat_button"):
            current_chat_to_delete = st.session_state.active_chat
            if current_chat_to_delete in st.session_state.all_chats: del st.session_state.all_chats[current_chat_to_delete]; remaining_chats = list(st.session_state.all_chats.keys());
            st.session_state.active_chat = remaining_chats[0] if remaining_chats else None
            if not st.session_state.active_chat: new_name = generate_new_chat_name([]); st.session_state.all_chats = {new_name: []}; st.session_state.active_chat = new_name
            save_all_chats(st.session_state.all_chats, st.session_state.active_chat, st.session_state.web_search_enabled)
            st.rerun()

    st.divider()
    search_toggled = st.toggle("🌐 Веб-поиск", value=st.session_state.web_search_enabled, key="web_search_toggle")
    if search_toggled != st.session_state.web_search_enabled:
        st.session_state.web_search_enabled = search_toggled
        save_all_chats(st.session_state.all_chats, st.session_state.active_chat, st.session_state.web_search_enabled)
        st.rerun()

    st.divider()
    mode_options = list(MODES.keys()); current_mode_index = mode_options.index(st.session_state.selected_mode) if st.session_state.selected_mode in mode_options else 0
    selected_mode_radio = st.radio("Режим работы:", options=mode_options, index=current_mode_index, key="mode_selector")
    if selected_mode_radio is not None and selected_mode_radio != st.session_state.selected_mode: st.session_state.selected_mode = selected_mode_radio; st.rerun()


# --- Основная область: Чат ---
current_mode_name = st.session_state.get("selected_mode", DEFAULT_MODE)
current_model_id = MODES.get(current_mode_name, MODES[DEFAULT_MODE])

# Отображение чата (перед полем ввода)
chat_display_container = st.container()
with chat_display_container:
    # Проверка перед отрисовкой
    if active_chat_name in st.session_state.all_chats:
        current_display_history = list(st.session_state.all_chats[active_chat_name])
        for message in current_display_history:
            avatar = "🧑‍💻" if message["role"] == "user" else "💡"
            with st.chat_message(message["role"], avatar=avatar):
                st.markdown(message["content"], unsafe_allow_html=True)
    else:
        st.warning("Активный чат не найден.") # Сообщение если чат пропал

# --- Поле ввода пользователя ---
if prompt := st.chat_input(f"Спроси {current_mode_name}..."):
    if active_chat_name in st.session_state.all_chats:
        st.session_state.all_chats[active_chat_name].append({"role": "user", "content": prompt})
        save_all_chats(st.session_state.all_chats, st.session_state.active_chat, st.session_state.web_search_enabled)
        st.rerun()
    else: st.error("Ошибка: Активный чат не найден для добавления сообщения.")


# --- Логика ответа ИИ (УПРОЩЕННАЯ) ---
# Проверка на существование чата перед получением истории
if active_chat_name in st.session_state.all_chats:
    current_chat_state = st.session_state.all_chats[active_chat_name]

    # Выполняем, если история не пуста и последнее сообщение от пользователя
    if current_chat_state and current_chat_state[-1]["role"] == "user":

        last_user_prompt = current_chat_state[-1]["content"]
        print(f"\n--- Обработка: '{last_user_prompt[:100]}...' | Поиск: {'ВКЛ' if st.session_state.web_search_enabled else 'ВЫКЛ'} ---")
        current_date = datetime.datetime.now().strftime("%Y-%m-%d")

        search_results_str = ""
        context_for_ai = list(current_chat_state)
        needs_search = st.session_state.web_search_enabled

        # --- Этапы поиска (только если needs_search == True) ---
        if needs_search:
            print(">>> Веб-поиск включен.")
            generated_queries = []
            with st.spinner("Подбираю запросы... 🧐"): generated_queries = generate_search_queries(last_user_prompt, current_model_id)

            # ИСПРАВЛЕННЫЙ БЛОК
            if generated_queries:
                with st.spinner(f"Ищу в сети... 🌐"):
                    search_results_str = perform_web_search(generated_queries)
            else:
                print("Запросы не сгенерированы, поиск по исходному.")
                # Выносим st.spinner наружу
                with st.spinner("Ищу в сети... 🌐"):
                    search_results_str = perform_web_search([last_user_prompt], max_results_per_query=MAX_SEARCH_RESULTS_PER_QUERY)
            # КОНЕЦ ИСПРАВЛЕННОГО БЛОКА

            is_search_successful = not ("Ошибка" in search_results_str or "не найдено" in search_results_str or "Нет запросов" in search_results_str)
            system_prompt = {"role": "system"}
            if is_search_successful and search_results_str:
                 system_prompt["content"] = f"ВАЖНО: Сегодня {current_date}. Веб-поиск ВКЛЮЧЕН. Результаты ниже. Используй их как ОСНОВНОЙ источник для актуального ответа.\n\n{search_results_str}\n--- Конец результатов ---\n\nИнструкция: Приоритет поиска > твои знания. Синтезируй ответ. Без ссылок. Ответь на запрос пользователя."
                 print("Контекст поиска добавлен.")
            else:
                 system_prompt["content"] = f"(Примечание: Веб-поиск ВКЛЮЧЕН, но не дал результатов ({search_results_str}). Сегодня {current_date}. Отвечай на основе знаний, предупреди о неактуальности.)"
                 print("Добавлено уведомление о неудачном поиске.")
            context_for_ai.insert(-1, system_prompt)

        else: # needs_search == False
            print(">>> Веб-поиск выключен.")
            system_prompt = {"role": "system", "content": f"Сегодня {current_date}. Веб-поиск ВЫКЛЮЧЕН. Отвечай на запрос пользователя, основываясь на своих общих знаниях."}
            context_for_ai.insert(-1, system_prompt)
            print("Добавлен промпт без поиска.")

        # --- ЕДИНЫЙ вызов ИИ со стримингом ---
        final_response_to_save = None
        # Отображаем сообщение ассистента СРАЗУ, чтобы стриминг шел в него
        with st.chat_message("assistant", avatar="💡"):
            placeholder = st.empty() # Создаем место для стриминга
            spinner_message = "Генерирую ответ..."
            if needs_search: spinner_message = "Анализирую веб-данные..." if is_search_successful and search_results_str else "Поиск не помог, отвечаю..."
            print("Запрос финального ответа...");
            with placeholder.container(), st.spinner(spinner_message): # Используем placeholder
                 response_generator = stream_ai_response(current_model_id, context_for_ai)
                 # Пишем стрим в placeholder
                 full_response_chunks = []
                 for chunk in response_generator:
                      if chunk:
                           full_response_chunks.append(chunk)
                           placeholder.markdown("".join(full_response_chunks) + "▌") # Добавляем курсор для индикации
                 final_response_to_save = "".join(full_response_chunks)
                 if final_response_to_save:
                      placeholder.markdown(final_response_to_save) # Отображаем финальный ответ без курсора
                 else:
                      placeholder.markdown("Не удалось получить ответ.") # Если ответ пустой
            print("Ответ получен.")

        # --- Сохранение ответа ---
        if final_response_to_save:
            if active_chat_name in st.session_state.all_chats:
                 current_history_for_save = st.session_state.all_chats[active_chat_name]
                 # Добавляем проверку, чтобы не сохранить пустое сообщение, если последнее уже от ассистента
                 if not current_history_for_save or current_history_for_save[-1].get("role") != "assistant" or current_history_for_save[-1].get("content") != final_response_to_save:
                      current_history_for_save.append({"role": "assistant", "content": final_response_to_save})
                      save_all_chats(st.session_state.all_chats, st.session_state.active_chat, st.session_state.web_search_enabled)
                      print("Ответ ассистента сохранен.")
                 else: print("Ответ ассистента уже присутствует, сохранение пропущено.")
            else: print("Ошибка сохранения: чат исчез.")
        else: print("Пустой ответ от ИИ, не сохранено.")

        print("--- Обработка завершена ---")
        # НЕ rerun() в конце блока обработки

# --- Футер ---
# Убран
