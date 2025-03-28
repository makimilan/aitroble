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
import re # Для очистки сгенерированных запросов

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
LOCAL_STORAGE_KEY = "multi_chat_storage_v9" # Новый ключ для избежания конфликтов
DEFAULT_CHAT_NAME = "Новый чат"
MAX_SEARCH_RESULTS_PER_QUERY = 2 # Результатов на один сгенерированный запрос
MAX_QUERIES_TO_GENERATE = 3 # Макс. кол-во запросов для генерации ИИ

# --- Настройка страницы ---
st.set_page_config(
    page_title="Умный Чат ИИ", # Изменено
    page_icon="🧠",
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


# --- Функции для работы с чатами (без изменений) ---
def load_all_chats():
    data_str = localS.getItem(LOCAL_STORAGE_KEY)
    if data_str:
        try:
            data = json.loads(data_str)
            if isinstance(data, dict) and "chats" in data and "active_chat" in data and isinstance(data["chats"], dict):
                # Проверка целостности истории каждого чата
                for chat_name, history in data["chats"].items():
                    if not isinstance(history, list):
                         data["chats"][chat_name] = [] # Исправляем, если история не список
                    else:
                         # Удаляем пустые или некорректные сообщения
                         data["chats"][chat_name] = [msg for msg in history if isinstance(msg, dict) and "role" in msg and "content" in msg and msg["content"]]
                # Проверка активного чата
                if data["active_chat"] not in data["chats"]:
                     data["active_chat"] = list(data["chats"].keys())[0] if data["chats"] else None

                if data["active_chat"] is None: # Если после проверок чатов не осталось
                    first_chat_name = f"{DEFAULT_CHAT_NAME} 1"
                    default_chats = {first_chat_name: []}
                    return default_chats, first_chat_name

                return data["chats"], data["active_chat"]
        except Exception as e: # Ловим более широкий спектр ошибок загрузки/парсинга
            print(f"Ошибка загрузки чатов: {e}. Возврат к стандартным.")
            pass # Возвращаемся к значениям по умолчанию ниже
    first_chat_name = f"{DEFAULT_CHAT_NAME} 1"
    default_chats = {first_chat_name: []}
    return default_chats, first_chat_name

def save_all_chats(chats_dict, active_chat_name):
    if isinstance(chats_dict, dict) and isinstance(active_chat_name, str):
        # Дополнительная проверка перед сохранением
        cleaned_chats = {}
        for name, history in chats_dict.items():
            if isinstance(history, list):
                 cleaned_chats[name] = [msg for msg in history if isinstance(msg, dict) and "role" in msg and "content" in msg and msg["content"]]
            else:
                 cleaned_chats[name] = [] # Сохраняем пустой список, если что-то не так

        if active_chat_name not in cleaned_chats:
             active_chat_name = list(cleaned_chats.keys())[0] if cleaned_chats else None

        if active_chat_name is None: return False # Нечего сохранять

        data_to_save = {"chats": cleaned_chats, "active_chat": active_chat_name}
        try:
            localS.setItem(LOCAL_STORAGE_KEY, json.dumps(data_to_save)); return True
        except Exception as e:
            print(f"Ошибка сохранения чатов: {e}")
            st.error(f"Не удалось сохранить состояние чата: {e}") # Уведомить пользователя
            return False
    return False

def generate_new_chat_name(existing_names):
    i = 1
    while f"{DEFAULT_CHAT_NAME} {i}" in existing_names: i += 1
    return f"{DEFAULT_CHAT_NAME} {i}"

# --- НОВАЯ Функция для генерации поисковых запросов ---
def generate_search_queries(user_prompt, model_id):
    """Запрашивает у ИИ генерацию поисковых запросов на основе запроса пользователя."""
    try:
        api_key = st.secrets.get("OPENROUTER_API_KEY")
        if not api_key:
            print("API ключ OpenRouter не найден для генерации запросов.")
            return [] # Возвращаем пустой список, если ключа нет
    except Exception as e:
         print(f"Ошибка доступа к секретам для генерации запросов: {e}")
         return []

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "http://localhost:8501", # Замените, если нужно
        "X-Title": "Streamlit Smart Chat AI"
    }

    # Промпт для ИИ, чтобы он сгенерировал запросы
    generation_prompt = f"""Проанализируй следующий запрос пользователя и определи основную суть вопроса. Сгенерируй до {MAX_QUERIES_TO_GENERATE} эффективных и лаконичных поисковых запросов (на русском языке), которые помогут найти самую релевантную и актуальную информацию в интернете для ответа на этот запрос. Выведи только сами запросы, каждый на новой строке, без нумерации или дополнительных пояснений.

Запрос пользователя:
"{user_prompt}"

Поисковые запросы:"""

    payload = {
        "model": model_id, # Используем ту же модель, что и для чата, или можно выбрать другую
        "messages": [{"role": "user", "content": generation_prompt}],
        "max_tokens": 100, # Ограничиваем длину ответа
        "temperature": 0.3, # Делаем генерацию более предсказуемой
    }

    generated_queries = []
    try:
        print(f"Генерация поисковых запросов для: '{user_prompt[:50]}...'")
        response = requests.post(OPENROUTER_API_URL, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        data = response.json()
        raw_queries = data.get("choices", [{}])[0].get("message", {}).get("content", "")

        if raw_queries:
            # Очищаем и разделяем запросы
            queries = [q.strip() for q in raw_queries.split('\n') if q.strip()]
            # Убираем возможную нумерацию или маркеры типа "-", "*"
            queries = [re.sub(r"^\s*[\d\.\-\*]+\s*", "", q) for q in queries]
            generated_queries = [q for q in queries if q] # Фильтруем пустые строки
            print(f"Сгенерированные запросы: {generated_queries}")

    except requests.exceptions.RequestException as e:
        print(f"Ошибка сети при генерации поисковых запросов: {e}")
    except Exception as e:
        print(f"Ошибка при генерации поисковых запросов: {e}")
        # traceback.print_exc()

    # Возвращаем список сгенерированных запросов (может быть пустым)
    return generated_queries[:MAX_QUERIES_TO_GENERATE] # Ограничиваем кол-во на всякий случай


# --- МОДИФИЦИРОВАННАЯ Функция веб-поиска ---
def perform_web_search(queries: list, max_results_per_query=MAX_SEARCH_RESULTS_PER_QUERY):
    """Выполняет веб-поиск по списку запросов и агрегирует результаты."""
    all_results_text = ""
    if not queries:
        return "Не было сгенерировано поисковых запросов."

    print(f"Выполнение поиска по запросам: {queries}")
    aggregated_results = []

    try:
        # Используем один менеджер контекста для всех запросов
        with DDGS(timeout=15) as ddgs: # Увеличим общий таймаут
            for query in queries:
                print(f"Поиск: '{query}'...")
                try:
                    search_results = list(ddgs.text(query, max_results=max_results_per_query))
                    if search_results:
                        aggregated_results.extend(search_results) # Добавляем найденное в общий список
                        print(f"  Найдено {len(search_results)} результатов.")
                    else:
                         print(f"  Результатов не найдено.")
                except Exception as e_inner:
                    print(f"Ошибка при поиске по запросу '{query}': {e_inner}")
                    continue # Продолжаем со следующим запросом

        if aggregated_results:
            # Убираем дубликаты по ссылкам, если они есть
            unique_results = {result['href']: result for result in aggregated_results}.values()

            all_results_text += "--- Результаты веб-поиска ---\n"
            for i, result in enumerate(unique_results, 1):
                title = result.get('title', 'Нет заголовка')
                body = result.get('body', 'Нет описания')
                href = result.get('href', '#')
                body_short = (body[:180] + '...') if len(body) > 180 else body
                all_results_text += f"{i}. [{title}]({href}): {body_short}\n"
            print(f"Всего уникальных результатов после агрегации: {len(unique_results)}")
        else:
             all_results_text = "По сгенерированным запросам ничего не найдено в сети."

        return all_results_text.strip()

    except Exception as e:
        print(f"Общая ошибка веб-поиска: {e}")
        # traceback.print_exc()
        return "Не удалось выполнить веб-поиск из-за ошибки."

# --- Инициализация состояния ---
if "all_chats" not in st.session_state:
    st.session_state.all_chats, st.session_state.active_chat = load_all_chats()
    # Дополнительная проверка после загрузки
    if not st.session_state.active_chat or st.session_state.active_chat not in st.session_state.all_chats:
         if st.session_state.all_chats:
             st.session_state.active_chat = list(st.session_state.all_chats.keys())[0]
         else: # Совсем все плохо, создаем заново
             new_name = generate_new_chat_name([])
             st.session_state.all_chats = {new_name: []}
             st.session_state.active_chat = new_name
             save_all_chats(st.session_state.all_chats, st.session_state.active_chat)


if "selected_mode" not in st.session_state:
    st.session_state.selected_mode = DEFAULT_MODE

# --- Определяем активный чат ДО обработки ввода/вывода ---
active_chat_name = st.session_state.active_chat
active_chat_history = list(st.session_state.all_chats.get(active_chat_name, []))

# --- Сайдбар (без изменений) ---
with st.sidebar:
    # ... (код сайдбара без изменений) ...
    st.markdown("## 💬 Чаты")
    chat_names = list(st.session_state.all_chats.keys())
    try: active_chat_index = chat_names.index(active_chat_name)
    except ValueError: active_chat_index = 0 if chat_names else -1 # Обработка пустого списка

    if active_chat_index != -1:
         selected_chat = st.radio(
            "Выберите чат:", options=chat_names, index=active_chat_index,
            label_visibility="collapsed", key="chat_selector"
        )

         if selected_chat != active_chat_name:
            st.session_state.active_chat = selected_chat
            save_all_chats(st.session_state.all_chats, st.session_state.active_chat)
            st.rerun()
    else:
        st.write("Нет доступных чатов.") # Сообщение, если чатов нет

    st.divider()

    if st.button("➕ Новый чат", key="new_chat_button"):
        new_name = generate_new_chat_name(list(st.session_state.all_chats.keys()))
        st.session_state.all_chats[new_name] = []
        st.session_state.active_chat = new_name
        save_all_chats(st.session_state.all_chats, st.session_state.active_chat)
        st.rerun()

    if len(chat_names) > 0 and active_chat_index != -1:
        if st.button("🗑️ Удалить текущий чат", type="secondary", key="delete_chat_button"):
            current_active_chat_to_delete = st.session_state.active_chat # Сохраняем перед возможным изменением
            if current_active_chat_to_delete in st.session_state.all_chats:
                del st.session_state.all_chats[current_active_chat_to_delete]
                remaining_chats = list(st.session_state.all_chats.keys())
                if remaining_chats: st.session_state.active_chat = remaining_chats[0]
                else:
                    # Если удалили последний чат, создаем новый
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
     welcome_message = {"role": "assistant", "content": f"👋 Привет! Я {current_mode_name}, ваш умный ассистент с доступом к веб-поиску. Задайте ваш вопрос."}
     # Убедимся, что активный чат существует перед добавлением
     if active_chat_name in st.session_state.all_chats:
         st.session_state.all_chats[active_chat_name] = [welcome_message]
         save_all_chats(st.session_state.all_chats, active_chat_name)
         active_chat_history = [welcome_message]
     else:
         # Если активного чата нет (маловероятно из-за проверок выше), создаем новый
         active_chat_name = generate_new_chat_name(list(st.session_state.all_chats.keys()))
         st.session_state.all_chats[active_chat_name] = [welcome_message]
         st.session_state.active_chat = active_chat_name
         save_all_chats(st.session_state.all_chats, active_chat_name)
         active_chat_history = [welcome_message]


# Контейнер для сообщений
chat_display_container = st.container()
with chat_display_container:
    # Перебираем копию истории, чтобы избежать ошибок при модификации
    for message in list(st.session_state.all_chats.get(active_chat_name, [])):
        avatar = "🧑‍💻" if message["role"] == "user" else "🤖"
        with st.chat_message(message["role"], avatar=avatar):
            st.markdown(message["content"], unsafe_allow_html=True)

# --- Функция стриминга (без изменений) ---
def stream_ai_response(model_id_func, chat_history_func):
    # ... (код stream_ai_response без изменений) ...
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
        "X-Title": "Streamlit Smart Chat AI" # Обновлено
    })

    payload = {"model": model_id_func, "messages": chat_history_func, "stream": True}

    try:
        response = requests.post(OPENROUTER_API_URL, headers=headers, json=payload, stream=True, timeout=180) # Увеличим таймаут еще
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
    # Проверяем, существует ли активный чат перед добавлением
    if active_chat_name in st.session_state.all_chats:
        st.session_state.all_chats[active_chat_name].append({"role": "user", "content": prompt})
        save_all_chats(st.session_state.all_chats, active_chat_name)
        st.rerun()
    else:
        st.error("Ошибка: Активный чат не найден. Попробуйте обновить страницу или создать новый чат.")


# --- МОДИФИЦИРОВАННАЯ Логика ответа ИИ ---
# Получаем актуальное состояние чата из session_state
current_chat_state = st.session_state.all_chats.get(active_chat_name, [])

# Проверяем, что история не пуста и последнее сообщение от пользователя
if current_chat_state and current_chat_state[-1]["role"] == "user":

    last_user_prompt = current_chat_state[-1]["content"]
    print(f"\n--- Обработка запроса: '{last_user_prompt[:100]}...' ---")

    # --- Этап 1: Генерация поисковых запросов ---
    # Используем текущую модель ИИ для генерации
    generated_queries = generate_search_queries(last_user_prompt, current_model_id)

    # --- Этап 2: Веб-поиск по сгенерированным запросам ---
    if generated_queries:
        # Если ИИ сгенерировал запросы, ищем по ним
        search_results_str = perform_web_search(generated_queries)
    else:
        # Если ИИ не сгенерировал запросы (ошибка или решил, что не нужно),
        # можно либо ничего не искать, либо искать по исходному запросу (как раньше)
        # Решение: ищем по исходному запросу для подстраховки
        print("ИИ не сгенерировал запросы, поиск по исходному запросу пользователя.")
        search_results_str = perform_web_search([last_user_prompt], max_results_per_query=MAX_SEARCH_RESULTS) # Ищем больше результатов, если запрос один

    # --- Этап 3: Подготовка контекста для финального ответа ---
    context_for_final_answer = list(current_chat_state) # Снова берем актуальную историю

    # Проверяем, были ли результаты поиска успешными
    is_search_successful = not ("Не удалось" in search_results_str or "не найдено" in search_results_str or "Не было сгенерировано" in search_results_str)

    if is_search_successful and search_results_str:
        # Обновленный системный промпт для финального ответа
        search_context_message = {
            "role": "system",
            "content": (
                f"Для ответа на последний запрос пользователя были выполнены следующие действия:\n"
                f"1. Сгенерированы поисковые запросы (если возможно).\n"
                f"2. Выполнен веб-поиск. Результаты представлены ниже.\n\n"
                f"{search_results_str}\n--- Конец результатов ---\n\n"
                "Инструкция: Проанализируй эти результаты веб-поиска. Используй найденную информацию, ЕСЛИ ОНА РЕЛЕВАНТНА И АКТУАЛЬНА, чтобы дать исчерпывающий и точный ответ на ОРИГИНАЛЬНЫЙ запрос пользователя. "
                "Не цитируй результаты напрямую, а интегрируй ключевые факты и данные в свой ответ. Если поиск не дал полезной информации или она не относится к делу, основывай ответ на своих знаниях. "
                "Оригинальный запрос пользователя указан последним в истории сообщений."
            )
        }
        # Вставляем перед последним сообщением пользователя
        context_for_final_answer.insert(-1, search_context_message)
        print("Результаты поиска добавлены в контекст для финального ответа.")

    elif search_results_str: # Если поиск не удался или ничего не нашел
         # Добавляем краткое уведомление об этом
         search_context_message = {
            "role": "system",
             "content": f"(Примечание: {search_results_str}. Отвечай на запрос пользователя, основываясь на своих знаниях.)"
         }
         context_for_final_answer.insert(-1, search_context_message)
         print("В контекст добавлено уведомление о неудачном поиске.")
    else:
        print("Результаты поиска не добавляются в контекст.")


    # --- Этап 4: Генерация и отображение финального ответа ---
    with chat_display_container:
        with st.chat_message("assistant", avatar="🤖"):
            print("Запрос финального ответа у ИИ...")
            response_generator = stream_ai_response(current_model_id, context_for_final_answer)
            full_response = st.write_stream(response_generator)
            print("Финальный ответ получен и отображен.")

    # --- Этап 5: Сохранение ответа ---
    if full_response:
        # Добавляем ответ ассистента в ОРИГИНАЛЬНУЮ историю в session_state
        # Убедимся, что активный чат все еще существует
        if active_chat_name in st.session_state.all_chats:
             st.session_state.all_chats[active_chat_name].append({"role": "assistant", "content": full_response})
             save_all_chats(st.session_state.all_chats, active_chat_name)
             print("Ответ ассистента сохранен.")
        else:
             print("Ошибка: Активный чат исчез перед сохранением ответа.")
             st.error("Произошла ошибка при сохранении ответа. Чат мог быть удален.")

    print("--- Обработка запроса завершена ---")


# --- Футер ---
# Убран
