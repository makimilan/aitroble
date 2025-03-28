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
# Используем старый ключ v12, чтобы не терять историю чатов из предыдущей версии
LOCAL_STORAGE_KEY = "multi_chat_storage_v12"
DEFAULT_CHAT_NAME = "Новый чат"
MAX_SEARCH_RESULTS_PER_QUERY = 5
MAX_QUERIES_TO_GENERATE = 3
MAX_SNIPPET_LENGTH = 250

# --- Настройка страницы ---
st.set_page_config(
    page_title="Умный Чат ИИ", page_icon="🧠", layout="wide", initial_sidebar_state="expanded"
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
    data_str = localS.getItem(LOCAL_STORAGE_KEY)
    if data_str:
        try:
            data = json.loads(data_str)
            if isinstance(data, dict) and "chats" in data and "active_chat" in data and isinstance(data["chats"], dict):
                for chat_name, history in data["chats"].items():
                    if not isinstance(history, list): data["chats"][chat_name] = []
                    else: data["chats"][chat_name] = [msg for msg in history if isinstance(msg, dict) and "role" in msg and "content" in msg and msg["content"]]
                if data["active_chat"] not in data["chats"]: data["active_chat"] = list(data["chats"].keys())[0] if data["chats"] else None
                if data["active_chat"] is None: raise ValueError("No active chat found.")
                return data["chats"], data["active_chat"]
        except Exception as e: print(f"Ошибка загрузки: {e}.")
    first_chat_name = f"{DEFAULT_CHAT_NAME} 1"; default_chats = {first_chat_name: []}
    return default_chats, first_chat_name

def save_all_chats(chats_dict, active_chat_name):
    # ... (код save_all_chats) ...
    if isinstance(chats_dict, dict) and isinstance(active_chat_name, str):
        cleaned_chats = {}
        for name, history in chats_dict.items():
            if isinstance(history, list): cleaned_chats[name] = [msg for msg in history if isinstance(msg, dict) and "role" in msg and "content" in msg and msg["content"]]
            else: cleaned_chats[name] = []
        if active_chat_name not in cleaned_chats: active_chat_name = list(cleaned_chats.keys())[0] if cleaned_chats else None
        if active_chat_name is None: return False
        data_to_save = {"chats": cleaned_chats, "active_chat": active_chat_name}
        try: localS.setItem(LOCAL_STORAGE_KEY, json.dumps(data_to_save)); return True
        except Exception as e: print(f"Ошибка сохранения: {e}"); return False
    return False

def generate_new_chat_name(existing_names):
    # ... (код generate_new_chat_name) ...
    i = 1; base_name = DEFAULT_CHAT_NAME
    while f"{base_name} {i}" in existing_names: i += 1
    return f"{base_name} {i}"

# --- ОБНОВЛЕННАЯ Функция для принятия решения о поиске ---
def should_perform_search(user_prompt, model_id):
    """Определяет, нужен ли веб-поиск для ответа на запрос пользователя."""
    greetings = ["привет", "здравствуй", "здравствуйте", "добрый день", "добрый вечер", "доброе утро", "hi", "hello", "хелло", "хай", "даров"]
    common_phrases = ["как дела", "что нового", "спасибо", "пожалуйста", "хорошо", "ладно", "ок", "окей", "пока", "до свидания"]
    prompt_lower = user_prompt.lower().strip(" !?.")

    # Правило 1: Приветствия и короткие фразы
    if prompt_lower in greetings or prompt_lower in common_phrases or len(user_prompt.split()) <= 1:
         print(f"Простая фраза/приветствие ('{user_prompt}') - поиск не требуется.")
         return False
    # Правило 2: Простая арифметика
    if re.fullmatch(r"^\s*[\d\s\+\-\*\/\(\)\.]+\s*=?\s*$", user_prompt):
         print(f"Арифметический запрос ('{user_prompt}') - поиск не требуется.")
         return False

    try: api_key = st.secrets.get("OPENROUTER_API_KEY"); assert api_key
    except: print("API ключ не найден для решения о поиске."); return False

    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    # Слегка доработанный промпт
    decision_prompt = f"""Проанализируй запрос пользователя. Нужен ли для ответа на него поиск АКТУАЛЬНОЙ (новее 2023 года) информации в интернете?

Критерии для ответа "ДА" (нужен поиск):
- Запрос касается недавних событий, новостей, происшествий.
- Запрос требует конкретных фактов, которые могли измениться (текущий президент, статус проекта, дата выхода, погода, статистика).
- Запрос явно просит найти что-то в сети ("найди", "поищи", "что нового о").

Критерии для ответа "НЕТ" (поиск НЕ нужен):
- Это ОБЫЧНОЕ приветствие, прощание или общая фраза ("привет", "спасибо", "как дела?", "пока").
- Запрос касается ОБЩИХ знаний, определений, истории (до 2023 года), науки.
- Это ТВОРЧЕСКИЙ запрос (напиши стих, код, рассказ, идею).
- Это вопрос о тебе (ИИ), нашем диалоге или простой small talk.
- Это простая арифметика или логическая задача, не требующая внешних фактов.

Запрос пользователя: "{user_prompt}"

ОТВЕТЬ ТОЛЬКО ОДНИМ СЛОВОМ: ДА или НЕТ."""

    payload = {"model": model_id, "messages": [{"role": "user", "content": decision_prompt}], "max_tokens": 3, "temperature": 0.0}

    try:
        print(f"Решение о поиске для: '{user_prompt[:50]}...'")
        response = requests.post(OPENROUTER_API_URL, headers=headers, json=payload, timeout=10)
        response.raise_for_status()
        data = response.json()
        decision = data.get("choices", [{}])[0].get("message", {}).get("content", "").strip().upper()
        print(f"  Решение ИИ: {decision}")
        return decision == "ДА" # Строгая проверка
    except Exception as e:
        print(f"  Ошибка при принятии решения о поиске: {e}")
        return False

# --- Функция генерации поисковых запросов (без изменений) ---
def generate_search_queries(user_prompt, model_id):
    # ... (код generate_search_queries) ...
    try: api_key = st.secrets.get("OPENROUTER_API_KEY"); assert api_key
    except: print("API ключ не найден."); return []
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json", "HTTP-Referer": "http://localhost:8501", "X-Title": "Streamlit Smart Chat AI"}
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

# --- Инициализация состояния (без изменений) ---
if "all_chats" not in st.session_state: st.session_state.all_chats, st.session_state.active_chat = load_all_chats()
if "selected_mode" not in st.session_state: st.session_state.selected_mode = DEFAULT_MODE

# --- Определяем активный чат (без изменений) ---
active_chat_name = st.session_state.active_chat

# --- Сайдбар (без изменений) ---
with st.sidebar:
    # ... (код сайдбара) ...
    st.markdown("## 💬 Чаты"); chat_names = list(st.session_state.all_chats.keys())
    try: active_chat_index = chat_names.index(active_chat_name)
    except ValueError: active_chat_index = 0 if chat_names else -1
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

# --- ИЗМЕНЕНИЕ: Переносим отображение чата ПОСЛЕ обработки ввода/вывода ---
# Это гарантирует, что мы всегда рисуем самое последнее состояние

# --- Поле ввода пользователя и ОБРАБОТКА ---
user_prompt_submitted = False
if prompt := st.chat_input(f"Спроси {current_mode_name}..."):
    if active_chat_name in st.session_state.all_chats:
        # Добавляем сообщение пользователя в state
        st.session_state.all_chats[active_chat_name].append({"role": "user", "content": prompt})
        # Сохраняем состояние
        save_all_chats(st.session_state.all_chats, active_chat_name)
        # Устанавливаем флаг, что было отправлено сообщение пользователя
        user_prompt_submitted = True
        # НЕ ВЫЗЫВАЕМ st.rerun() ЗДЕСЬ
    else:
        st.error("Ошибка: Активный чат не найден.")

# --- Логика ответа ИИ (выполняется, если было отправлено сообщение пользователя) ---
# Получаем актуальное состояние чата *после* возможного добавления сообщения пользователя
current_chat_state = st.session_state.all_chats.get(active_chat_name, [])

# Выполняем логику ответа ТОЛЬКО если последнее сообщение от пользователя
# (это условие также сработает после добавления сообщения выше)
if current_chat_state and current_chat_state[-1]["role"] == "user":

    last_user_prompt = current_chat_state[-1]["content"]
    print(f"\n--- Обработка: '{last_user_prompt[:100]}...' ---")
    current_date = datetime.datetime.now().strftime("%Y-%m-%d")

    # --- Этап 0: Принятие решения о поиске ---
    needs_search = False
    # Простое правило для коротких/общих фраз
    prompt_lower_check = last_user_prompt.lower().strip(" !?.")
    simple_phrases = ["привет", "здравствуй", "здравствуйте", "добрый день", "добрый вечер", "доброе утро", "hi", "hello", "хелло", "хай", "даров", "как дела", "что нового", "спасибо", "пожалуйста", "хорошо", "ладно", "ок", "окей", "пока", "до свидания"]
    is_simple_phrase = prompt_lower_check in simple_phrases or len(last_user_prompt.split()) <= 1 or re.fullmatch(r"^\s*[\d\s\+\-\*\/\(\)\.]+\s*=?\s*$", last_user_prompt)

    if not is_simple_phrase:
         # Только если не простое правило, обращаемся к ИИ для решения
         with st.spinner("Анализирую запрос... 🤔"):
             needs_search = should_perform_search(last_user_prompt, current_model_id)
    else:
         print("Простое правило сработало - поиск не требуется.")

    search_results_str = ""
    # Создаем копию контекста ДЛЯ ПЕРЕДАЧИ В ИИ
    context_for_final_answer = list(current_chat_state)

    if needs_search:
        print(">>> Требуется веб-поиск.")
        generated_queries = []
        with st.spinner("Подбираю запросы... 🧐"): generated_queries = generate_search_queries(last_user_prompt, current_model_id)
        if generated_queries:
            with st.spinner(f"Ищу в сети... 🌐"): search_results_str = perform_web_search(generated_queries)
        else:
            print("Запросы не сгенерированы, поиск по исходному."); with st.spinner("Ищу в сети... 🌐"): search_results_str = perform_web_search([last_user_prompt], max_results_per_query=MAX_SEARCH_RESULTS_PER_QUERY)

        is_search_successful = not ("Ошибка" in search_results_str or "не найдено" in search_results_str or "Нет запросов" in search_results_str)

        if is_search_successful and search_results_str:
            search_context_message = {"role": "system", "content": f"ВАЖНО: Сегодня {current_date}. Выполнен веб-поиск. Результаты ниже. Используй их как ОСНОВНОЙ источник для актуального ответа.\n\n{search_results_str}\n--- Конец результатов ---\n\nИнструкция: Приоритет поиска > твои знания. Синтезируй ответ. Без ссылок. Ответь на запрос пользователя."}
            context_for_final_answer.insert(-1, search_context_message); print("Контекст поиска добавлен.")
        else:
             fallback_context_message = {"role": "system", "content": f"(Примечание: Поиск инициирован, но не дал результатов ({search_results_str}). Сегодня {current_date}. Отвечай на основе знаний, предупреди о неактуальности.)"}
             context_for_final_answer.insert(-1, fallback_context_message); print("Добавлено уведомление о неудачном поиске.")

    else: # needs_search == False
        print(">>> Веб-поиск не требуется.")
        no_search_context_message = {"role": "system", "content": f"Сегодня {current_date}. Веб-поиск не выполнялся. Отвечай на запрос пользователя, основываясь на своих общих знаниях."}
        context_for_final_answer.insert(-1, no_search_context_message); print("Добавлен промпт без поиска.")

    # --- Этап 4: Генерация и отображение финального ответа ---
    # Отображение будет происходить ВНУТРИ этого блока
    # Важно: Не используем chat_display_container здесь, т.к. он был выше
    # Вместо этого, st.chat_message само создаст контейнер для сообщения ассистента
    with st.chat_message("assistant", avatar="🧠"):
        print("Запрос финального ответа..."); spinner_message = "Формулирую ответ..."
        if needs_search and search_results_str and is_search_successful: spinner_message = "Анализирую веб-данные... ✍️"
        elif needs_search: spinner_message = "Поиск не дал результатов, отвечаю... 🤔"

        # Запускаем стриминг и получаем ответ
        with st.spinner(spinner_message):
             response_generator = stream_ai_response(current_model_id, context_for_final_answer)
             full_response = st.write_stream(response_generator)
        print("Ответ получен.")

    # --- Этап 5: Сохранение ответа ИИ ---
    # Сохраняем ТОЛЬКО если ответ был получен
    if full_response:
        # Добавляем ответ ассистента в ОСНОВНОЙ state
        if active_chat_name in st.session_state.all_chats:
             st.session_state.all_chats[active_chat_name].append({"role": "assistant", "content": full_response})
             save_all_chats(st.session_state.all_chats, active_chat_name)
             print("Ответ ассистента сохранен.")
        else: print("Ошибка сохранения: чат исчез.")
    else:
        print("Пустой ответ от ИИ, сохранение не требуется.")
        # Можно добавить сообщение об ошибке пользователю, если нужно
        # st.error("Не удалось получить ответ от ИИ.")

    print("--- Обработка завершена ---")
    # ВАЖНО: Мы не вызываем rerun здесь. Streamlit обновит UI после завершения скрипта.

# --- Отображение чата (перенесено сюда) ---
# Этот блок теперь рисует ВСЮ историю, включая сообщение пользователя
# и ответ ассистента (если он был сгенерирован выше)
chat_display_container = st.container()
with chat_display_container:
    # Получаем самую последнюю версию истории для отрисовки
    final_display_history = list(st.session_state.all_chats.get(active_chat_name, []))
    for message in final_display_history:
        avatar = "🧑‍💻" if message["role"] == "user" else "🧠"
        with st.chat_message(message["role"], avatar=avatar):
            st.markdown(message["content"], unsafe_allow_html=True)


# --- Футер ---
# Убран
