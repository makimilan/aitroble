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
import logging # Добавим логирование

# --- Настройка логирования ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Ключ API из секретов ---
# Попытка получить ключ API
OPENROUTER_API_KEY = st.secrets.get("OPENROUTER_API_KEY")

# --- Константы ---
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"
MODES = {
    "Стандарт (V3)": "deepseek/deepseek-chat-v3-0324:free",
    "DeepThink (R1)": "deepseek/deepseek-r1:free",
}
DEFAULT_MODE = "Стандарт (V3)"
LOCAL_STORAGE_KEY = "multi_chat_storage_v14"
DEFAULT_CHAT_NAME = "Новый чат"
MAX_SEARCH_RESULTS_PER_QUERY = 5
MAX_QUERIES_TO_GENERATE = 3
MAX_SNIPPET_LENGTH = 250
REQUEST_TIMEOUT = 30 # Таймаут для генерации запросов и поиска
STREAM_TIMEOUT = 180 # Таймаут для стриминга ответа ИИ

# --- Настройка страницы ---
st.set_page_config(
    page_title="Чат ИИ с Переключателем Поиска", page_icon="💡", layout="wide", initial_sidebar_state="expanded"
)

# --- Инициализация LocalStorage ---
try:
    localS = LocalStorage()
except Exception as e:
    logging.error(f"Ошибка инициализации LocalStorage: {e}")
    st.error("Не удалось инициализировать локальное хранилище. История чатов не будет сохраняться.", icon="🚨")
    localS = None # Устанавливаем в None, чтобы проверить позже

# --- Минимальный CSS ---
custom_css = f"""
<style>
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

# --- Проверка API ключа ---
if not OPENROUTER_API_KEY:
    st.error("⛔ Ключ API OpenRouter (`OPENROUTER_API_KEY`) не найден в секретах Streamlit! Пожалуйста, добавьте его.", icon="🚨")
    logging.error("Ключ API OpenRouter не найден.")
    st.stop() # Останавливаем выполнение скрипта

# --- Функции для работы с чатами ---
def load_all_chats():
    default_chats = {f"{DEFAULT_CHAT_NAME} 1": []}
    default_name = f"{DEFAULT_CHAT_NAME} 1"
    initial_search_state = False

    if not localS: # Проверяем, инициализирован ли localS
        logging.warning("LocalStorage недоступен, используются значения по умолчанию.")
        st.session_state.web_search_enabled = initial_search_state
        return default_chats, default_name

    data_str = localS.getItem(LOCAL_STORAGE_KEY)
    if data_str:
        try:
            data = json.loads(data_str)
            if isinstance(data, dict) and "chats" in data and "active_chat" in data and isinstance(data["chats"], dict):
                # Очистка истории
                cleaned_chats = {}
                for name, history in data["chats"].items():
                    if isinstance(history, list):
                        cleaned_chats[name] = [msg for msg in history if isinstance(msg, dict) and msg.get("role") and msg.get("content")]
                    else:
                        cleaned_chats[name] = [] # Пустой список, если история не список

                if not cleaned_chats:
                    logging.info("Загружены пустые чаты, возврат к значениям по умолчанию.")
                    st.session_state.web_search_enabled = initial_search_state
                    return default_chats, default_name

                active_chat = data["active_chat"]
                if active_chat not in cleaned_chats:
                    active_chat = list(cleaned_chats.keys())[0]
                    logging.warning(f"Активный чат '{data['active_chat']}' не найден, выбран первый: '{active_chat}'.")

                # Загружаем состояние поиска, по умолчанию False если не найдено
                st.session_state.web_search_enabled = data.get("web_search_enabled", initial_search_state)
                logging.info(f"Чаты и состояние поиска ({st.session_state.web_search_enabled=}) успешно загружены.")
                return cleaned_chats, active_chat
            else:
                logging.warning("Структура данных в LocalStorage некорректна, используются значения по умолчанию.")
        except json.JSONDecodeError as e:
            logging.error(f"Ошибка декодирования JSON из LocalStorage: {e}. Используются значения по умолчанию.")
        except Exception as e:
            logging.error(f"Неизвестная ошибка при загрузке чатов: {e}. Используются значения по умолчанию.")
    else:
        logging.info("Данные в LocalStorage не найдены, используются значения по умолчанию.")

    # Если что-то пошло не так или данных нет
    st.session_state.web_search_enabled = initial_search_state
    return default_chats, default_name

def save_all_chats(chats_dict, active_chat_name, web_search_state):
    if not localS:
        logging.warning("LocalStorage недоступен, сохранение невозможно.")
        return False
    if not isinstance(chats_dict, dict):
        logging.error("Попытка сохранить неверный формат чатов (должен быть dict).")
        return False
    if not isinstance(active_chat_name, str) and active_chat_name is not None:
         logging.error("Попытка сохранить неверный формат имени активного чата.")
         return False

    # Очистка перед сохранением (на всякий случай)
    cleaned_chats = {}
    for name, history in chats_dict.items():
        if isinstance(history, list):
            cleaned_chats[name] = [msg for msg in history if isinstance(msg, dict) and msg.get("role") and msg.get("content")]
        else:
            cleaned_chats[name] = []

    # Проверка активного чата
    if not cleaned_chats:
        active_chat_name = None # Нет чатов - нет активного
    elif active_chat_name not in cleaned_chats:
        active_chat_name = list(cleaned_chats.keys())[0] if cleaned_chats else None
        logging.warning(f"Активный чат для сохранения не найден, выбран первый: {active_chat_name}")

    data_to_save = {
        "chats": cleaned_chats,
        "active_chat": active_chat_name,
        "web_search_enabled": web_search_state
    }
    try:
        localS.setItem(LOCAL_STORAGE_KEY, json.dumps(data_to_save))
        logging.info(f"Чаты сохранены. Активный: {active_chat_name}, Поиск: {web_search_state}")
        return True
    except Exception as e:
        logging.error(f"Ошибка сохранения чатов в LocalStorage: {e}")
        st.toast("Ошибка сохранения сессии чата!", icon="🚨")
        return False

def generate_new_chat_name(existing_names):
    i = 1
    base_name = DEFAULT_CHAT_NAME
    while f"{base_name} {i}" in existing_names:
        i += 1
    return f"{base_name} {i}"

# --- Функция генерации поисковых запросов ---
def generate_search_queries(user_prompt, model_id):
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "http://localhost:8501", # Или ваш реальный URL, если деплоите
        "X-Title": "Streamlit Toggle Search Chat AI"
    }
    generation_prompt = f"""Проанализируй запрос пользователя. Сгенерируй до {MAX_QUERIES_TO_GENERATE} эффективных и лаконичных поисковых запросов (на русском), которые помогут найти актуальную информацию в интернете. Выведи только запросы, каждый на новой строке. Не нумеруй запросы.

Запрос пользователя:
"{user_prompt}"

Поисковые запросы:"""
    payload = {
        "model": model_id,
        "messages": [{"role": "user", "content": generation_prompt}],
        "max_tokens": 100,
        "temperature": 0.3
    }
    generated_queries = []
    try:
        logging.info(f"Генерация поисковых запросов для: '{user_prompt[:50]}...'")
        response = requests.post(OPENROUTER_API_URL, headers=headers, json=payload, timeout=REQUEST_TIMEOUT)
        response.raise_for_status() # Проверка на HTTP ошибки (4xx, 5xx)
        data = response.json()
        raw_queries = data.get("choices", [{}])[0].get("message", {}).get("content", "")

        if raw_queries:
            # Удаляем нумерацию, точки, звездочки в начале строк
            queries = [re.sub(r"^\s*[\d\.\-\*]+\s*", "", q.strip()) for q in raw_queries.split('\n') if q.strip()]
            generated_queries = [q for q in queries if q] # Убираем пустые строки после очистки
            logging.info(f"  Сгенерировано запросов: {generated_queries}")
        else:
            logging.warning("  API вернуло пустой ответ для генерации запросов.")

    except requests.exceptions.Timeout:
        logging.error("  Ошибка генерации запросов: Таймаут соединения с OpenRouter.")
        st.toast("Таймаут при генерации поисковых запросов.", icon="⏱️")
    except requests.exceptions.RequestException as e:
        logging.error(f"  Ошибка генерации запросов: {e}")
        st.toast(f"Ошибка сети при генерации запросов: {e}", icon="🚨")
    except Exception as e:
        logging.error(f"  Неизвестная ошибка при генерации запросов: {e}")
        st.toast("Неизвестная ошибка при генерации запросов.", icon="❓")

    return generated_queries[:MAX_QUERIES_TO_GENERATE]

# --- Функция веб-поиска ---
def perform_web_search(queries: list, max_results_per_query=MAX_SEARCH_RESULTS_PER_QUERY):
    all_results_text = ""
    aggregated_results = []
    if not queries:
        logging.warning("Нет запросов для выполнения веб-поиска.")
        return "Нет запросов для поиска."

    logging.info(f"Начинаю веб-поиск по {len(queries)} запросам...")
    try:
        with DDGS(timeout=REQUEST_TIMEOUT) as ddgs:
            for idx, query in enumerate(queries, 1):
                logging.info(f"  Выполняю запрос {idx}/{len(queries)}: '{query}'...")
                try:
                    search_results = list(ddgs.text(query, max_results=max_results_per_query))
                    aggregated_results.extend(search_results)
                    logging.info(f"    Найдено {len(search_results)} результатов для '{query}'.")
                except Exception as e:
                    logging.error(f"    Ошибка при поиске по запросу '{query}': {e}")
                    st.toast(f"Ошибка поиска по запросу: {query}", icon="🕸️")
                    # Продолжаем со следующими запросами

        if aggregated_results:
            # Отбираем уникальные результаты по тексту (body)
            unique_results_dict = {}
            for res in aggregated_results:
                body = res.get('body')
                if body and body not in unique_results_dict:
                    unique_results_dict[body] = res

            unique_results = list(unique_results_dict.values())
            logging.info(f"Всего найдено уникальных результатов: {len(unique_results)}")

            if unique_results:
                result_lines = []
                for i, res in enumerate(unique_results, 1):
                    title = res.get('title', 'Без заголовка')
                    body = res.get('body', '')
                    snippet = (body[:MAX_SNIPPET_LENGTH] + '...') if len(body) > MAX_SNIPPET_LENGTH else body
                    result_lines.append(f"{i}. {title}: {snippet}")
                all_results_text = "--- Результаты веб-поиска ---\n" + "\n".join(result_lines)
            else:
                all_results_text = "Не найдено уникальных результатов после фильтрации."
                logging.info(all_results_text)
        else:
            all_results_text = "Поиск не дал результатов."
            logging.info(all_results_text)

        return all_results_text.strip()

    except Exception as e:
        logging.error(f"Критическая ошибка во время веб-поиска: {e}")
        st.error(f"Произошла ошибка во время веб-поиска: {e}", icon="🕸️")
        return f"Ошибка веб-поиска: {e}"

# --- Функция стриминга ---
def stream_ai_response(model_id_func, chat_history_func):
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "http://localhost:8501", # Или ваш реальный URL
        "X-Title": "Streamlit Toggle Search Chat AI"
    }
    if not isinstance(chat_history_func, list):
        logging.error("История чата для стриминга передана в неверном формате.")
        yield None # Сигнал об ошибке
        return

    payload = {"model": model_id_func, "messages": chat_history_func, "stream": True}
    stream_successful = False
    try:
        logging.info(f"Запрос стриминга к модели: {model_id_func}")
        response = requests.post(OPENROUTER_API_URL, headers=headers, json=payload, stream=True, timeout=STREAM_TIMEOUT)
        response.raise_for_status()
        logging.info("Стриминг начат успешно.")

        for line in response.iter_lines():
            if line:
                decoded_line = line.decode('utf-8')
                if decoded_line.startswith("data: "):
                    try:
                        json_data_str = decoded_line[len("data: "):].strip()
                        if json_data_str == "[DONE]":
                            logging.info("Стриминг завершен сигналом [DONE].")
                            break
                        if json_data_str: # Убедимся, что строка не пустая
                           chunk = json.loads(json_data_str)
                           delta = chunk.get("choices", [{}])[0].get("delta", {})
                           if delta and "content" in delta:
                               delta_content = delta["content"]
                               stream_successful = True
                               yield delta_content
                    except json.JSONDecodeError as e:
                        logging.warning(f"Ошибка декодирования JSON чанка: {e}. Строка: '{json_data_str}'")
                        continue # Пропускаем поврежденный чанк
                    except Exception as e:
                        logging.error(f"Ошибка обработки чанка стрима: {e}")
                        continue
        # Проверка, был ли хоть какой-то контент
        if not stream_successful:
             logging.warning("Стриминг завершился без передачи контента.")
             # Можно не возвращать None здесь, просто не было данных

    except requests.exceptions.Timeout:
        logging.error(f"Ошибка стриминга: Таймаут ({STREAM_TIMEOUT}s) соединения с OpenRouter.")
        st.error(f"Таймаут ({STREAM_TIMEOUT} сек) при ожидании ответа от ИИ.", icon="⏱️")
        yield None # Сигнал об ошибке
    except requests.exceptions.RequestException as e:
        logging.error(f"Ошибка стриминга: {e}")
        st.error(f"Ошибка сети при получении ответа от ИИ: {e}", icon="🚨")
        yield None # Сигнал об ошибке
    except Exception as e:
        logging.error(f"Неизвестная ошибка во время стриминга: {e}", exc_info=True)
        st.error("Произошла неизвестная ошибка при получении ответа от ИИ.", icon="❓")
        yield None # Сигнал об ошибке


# --- Инициализация состояния ---
if "all_chats" not in st.session_state:
    logging.info("Инициализация состояния сессии...")
    st.session_state.all_chats, st.session_state.active_chat = load_all_chats()
    # web_search_enabled устанавливается внутри load_all_chats
if "selected_mode" not in st.session_state:
    st.session_state.selected_mode = DEFAULT_MODE
if "web_search_enabled" not in st.session_state:
     # Эта строка нужна на случай, если load_all_chats не смогла установить состояние
     st.session_state.web_search_enabled = False
     logging.warning("Состояние web_search_enabled не было установлено при загрузке, установлено в False.")

# --- Определяем активный чат ---
# Проверка и восстановление, если активный чат некорректен
if st.session_state.active_chat not in st.session_state.all_chats:
    logging.warning(f"Активный чат '{st.session_state.active_chat}' не найден в списке чатов.")
    if st.session_state.all_chats:
        st.session_state.active_chat = list(st.session_state.all_chats.keys())[0]
        logging.info(f"Установлен первый доступный чат: '{st.session_state.active_chat}'")
    else:
        # Если вообще нет чатов, создаем новый
        new_name = generate_new_chat_name([])
        st.session_state.all_chats = {new_name: []}
        st.session_state.active_chat = new_name
        logging.info(f"Список чатов пуст. Создан новый чат: '{new_name}'")
        save_all_chats(st.session_state.all_chats, st.session_state.active_chat, st.session_state.web_search_enabled)

active_chat_name = st.session_state.active_chat # Теперь гарантированно существует

# --- Сайдбар ---
with st.sidebar:
    st.markdown("## 💬 Чаты")
    chat_names = list(st.session_state.all_chats.keys())

    # Выбор активного чата (только если есть чаты)
    if chat_names:
        try:
            active_chat_index = chat_names.index(active_chat_name)
        except ValueError:
            logging.error(f"Критическая ошибка: active_chat_name '{active_chat_name}' не найден в chat_names, хотя должен быть.")
            active_chat_index = 0 # Возвращаемся к первому на всякий случай

        selected_chat = st.radio(
            "Выберите чат:",
            options=chat_names,
            index=active_chat_index,
            label_visibility="collapsed",
            key="chat_selector"
            )

        # Если пользователь выбрал другой чат
        if selected_chat is not None and selected_chat != active_chat_name:
            st.session_state.active_chat = selected_chat
            logging.info(f"Пользователь выбрал чат: {selected_chat}")
            # Сохраняем только смену активного чата, история не менялась
            save_all_chats(st.session_state.all_chats, st.session_state.active_chat, st.session_state.web_search_enabled)
            st.rerun()
    else:
        st.write("Нет доступных чатов.")

    st.divider()

    # Кнопка "Новый чат"
    if st.button("➕ Новый чат", key="new_chat_button"):
        new_name = generate_new_chat_name(list(st.session_state.all_chats.keys()))
        st.session_state.all_chats[new_name] = []
        st.session_state.active_chat = new_name
        logging.info(f"Создан новый чат: {new_name}")
        save_all_chats(st.session_state.all_chats, st.session_state.active_chat, st.session_state.web_search_enabled)
        st.rerun()

    # Кнопка "Удалить текущий чат" (только если есть что удалять)
    if chat_names:
        if st.button("🗑️ Удалить текущий чат", type="secondary", key="delete_chat_button"):
            current_chat_to_delete = st.session_state.active_chat
            logging.info(f"Запрос на удаление чата: {current_chat_to_delete}")
            if current_chat_to_delete in st.session_state.all_chats:
                del st.session_state.all_chats[current_chat_to_delete]
                logging.info(f"Чат '{current_chat_to_delete}' удален.")
                remaining_chats = list(st.session_state.all_chats.keys())
                # Выбираем новый активный чат
                if remaining_chats:
                    st.session_state.active_chat = remaining_chats[0]
                else:
                    # Если удалили последний, создаем новый
                    new_name = generate_new_chat_name([])
                    st.session_state.all_chats = {new_name: []}
                    st.session_state.active_chat = new_name
                    logging.info("Удален последний чат, создан новый.")
                save_all_chats(st.session_state.all_chats, st.session_state.active_chat, st.session_state.web_search_enabled)
                st.rerun()
            else:
                 logging.warning(f"Попытка удалить несуществующий чат: {current_chat_to_delete}")


    st.divider()

    # Переключатель веб-поиска
    search_toggled = st.toggle(
        "🌐 Веб-поиск",
        value=st.session_state.web_search_enabled,
        key="web_search_toggle"
        )
    if search_toggled != st.session_state.web_search_enabled:
        st.session_state.web_search_enabled = search_toggled
        logging.info(f"Веб-поиск переключен в состояние: {search_toggled}")
        save_all_chats(st.session_state.all_chats, st.session_state.active_chat, st.session_state.web_search_enabled)
        # Не нужен rerun, изменение состояния сохранится и применится при следующем взаимодействии

    st.divider()

    # Выбор режима работы
    mode_options = list(MODES.keys())
    try:
        current_mode_index = mode_options.index(st.session_state.selected_mode)
    except ValueError:
        logging.warning(f"Выбранный режим '{st.session_state.selected_mode}' не найден в опциях. Установлен режим по умолчанию.")
        st.session_state.selected_mode = DEFAULT_MODE
        current_mode_index = 0

    selected_mode_radio = st.radio(
        "Режим работы:",
        options=mode_options,
        index=current_mode_index,
        key="mode_selector"
        )
    if selected_mode_radio is not None and selected_mode_radio != st.session_state.selected_mode:
        st.session_state.selected_mode = selected_mode_radio
        logging.info(f"Выбран режим работы: {selected_mode_radio}")
        # Не нужен rerun, изменение состояния сохранится

# --- Основная область: Чат ---
current_mode_name = st.session_state.get("selected_mode", DEFAULT_MODE)
current_model_id = MODES.get(current_mode_name, MODES[DEFAULT_MODE])

# Отображение истории чата
chat_display_container = st.container()
with chat_display_container:
    # Проверка, что активный чат все еще существует перед отрисовкой
    if active_chat_name in st.session_state.all_chats:
        current_display_history = st.session_state.all_chats[active_chat_name]
        for message in current_display_history:
            avatar = "🧑‍💻" if message["role"] == "user" else "💡"
            with st.chat_message(message["role"], avatar=avatar):
                st.markdown(message["content"], unsafe_allow_html=True)
    else:
        st.warning(f"Активный чат '{active_chat_name}' не найден. Возможно, он был удален.")
        logging.warning(f"Попытка отобразить историю несуществующего чата: {active_chat_name}")

# --- Поле ввода пользователя ---
if prompt := st.chat_input(f"Спроси {current_mode_name}..."):
    # Проверка существования чата перед добавлением
    if active_chat_name in st.session_state.all_chats:
        logging.info(f"Получен новый промпт от пользователя в чате '{active_chat_name}'.")
        st.session_state.all_chats[active_chat_name].append({"role": "user", "content": prompt})
        save_all_chats(st.session_state.all_chats, st.session_state.active_chat, st.session_state.web_search_enabled)
        st.rerun() # Перезапускаем скрипт для отображения сообщения пользователя и запуска логики ответа ИИ
    else:
        st.error("Ошибка: Активный чат не найден. Невозможно добавить сообщение.", icon="❌")
        logging.error(f"Ошибка добавления сообщения: активный чат '{active_chat_name}' не найден.")


# --- Логика ответа ИИ ---
# Выполняется только если скрипт был перезапущен после ввода пользователя (т.е., последнее сообщение - от user)

# Снова проверяем существование активного чата
if active_chat_name in st.session_state.all_chats:
    current_chat_state = st.session_state.all_chats[active_chat_name]

    # Выполняем, только если история не пуста и последнее сообщение от пользователя
    if current_chat_state and current_chat_state[-1]["role"] == "user":

        last_user_prompt = current_chat_state[-1]["content"]
        logging.info(f"\n--- Начало обработки ответа ИИ для чата '{active_chat_name}' ---")
        logging.info(f"Промпт: '{last_user_prompt[:100]}...' | Поиск: {'ВКЛ' if st.session_state.web_search_enabled else 'ВЫКЛ'}")

        current_date = datetime.datetime.now().strftime("%Y-%m-%d")
        search_results_str = ""
        search_performed_successfully = False # Флаг успешности поиска
        context_for_ai = list(current_chat_state) # Копируем историю для модификации
        needs_search = st.session_state.web_search_enabled

        # --- Этапы поиска (только если needs_search == True) ---
        if needs_search:
            logging.info(">>> Веб-поиск включен.")
            generated_queries = []
            search_results_str = "Поиск не выполнялся." # Значение по умолчанию

            # 1. Генерация запросов
            try:
                with st.spinner("Подбираю поисковые запросы... 🧐"):
                    generated_queries = generate_search_queries(last_user_prompt, current_model_id)
            except Exception as e:
                logging.error(f"Ошибка при вызове generate_search_queries: {e}", exc_info=True)
                st.error("Не удалось сгенерировать поисковые запросы.", icon="❓")
                # Попробуем искать по исходному запросу

            # 2. Выполнение поиска
            queries_to_search = generated_queries if generated_queries else [last_user_prompt]
            if not generated_queries:
                 logging.warning("Поисковые запросы не сгенерированы, используется исходный промпт.")

            try:
                spinner_text = f"Ищу в сети по {len(queries_to_search)} запросам... 🌐" if generated_queries else "Ищу в сети по вашему запросу... 🌐"
                with st.spinner(spinner_text):
                     search_results_str = perform_web_search(queries_to_search)
                # Проверяем успешность поиска (не содержит строк об ошибках/отсутствии результатов)
                if search_results_str and not any(err_msg in search_results_str for err_msg in ["Ошибка веб-поиска", "не дал результатов", "Нет запросов", "Не найдено уникальных"]):
                     search_performed_successfully = True
                     logging.info("Веб-поиск дал результаты.")
                else:
                     logging.warning(f"Веб-поиск не дал полезных результатов или произошла ошибка. Результат: '{search_results_str}'")

            except Exception as e:
                 logging.error(f"Ошибка при вызове perform_web_search: {e}", exc_info=True)
                 st.error("Произошла ошибка во время веб-поиска.", icon="🕸️")
                 search_results_str = f"Ошибка веб-поиска: {e}" # Записываем ошибку для системного промпта

            # 3. Формирование системного промпта с результатами поиска
            system_prompt = {"role": "system"}
            if search_performed_successfully:
                 system_prompt["content"] = f"Текущая дата: {current_date}. Веб-поиск был ВЫПОЛНЕН УСПЕШНО. Используй ПРЕДОСТАВЛЕННЫЕ НИЖЕ результаты веб-поиска как ОСНОВНОЙ ИСТОЧНИК для ответа на последний запрос пользователя. Не ссылайся на сам факт поиска, просто используй информацию. Не включай URL или прямые ссылки в ответ.\n\n{search_results_str}\n\n--- Конец результатов поиска ---\n\nОтветь на запрос пользователя, основываясь на этой информации."
                 logging.info("Системный промпт сформирован с результатами поиска.")
            else:
                 # Сообщаем ИИ, что поиск был, но не помог
                 system_prompt["content"] = f"Текущая дата: {current_date}. Веб-поиск был ВКЛЮЧЕН, но не дал полезных результатов (Возможная причина: '{search_results_str}'). Отвечай на последний запрос пользователя, основываясь на своих общих знаниях. Предупреди пользователя, что актуальность информации не гарантирована из-за неудачного поиска."
                 logging.info("Системный промпт сформирован с уведомлением о неудачном поиске.")
            # Вставляем системный промпт ПЕРЕД последним сообщением пользователя
            context_for_ai.insert(-1, system_prompt)

        else: # needs_search == False
            logging.info(">>> Веб-поиск выключен.")
            system_prompt = {"role": "system", "content": f"Текущая дата: {current_date}. Веб-поиск ВЫКЛЮЧЕН. Отвечай на последний запрос пользователя, основываясь только на своих общих знаниях."}
            context_for_ai.insert(-1, system_prompt) # Вставляем перед последним сообщением
            logging.info("Системный промпт сформирован без информации о поиске.")

        # --- ЕДИНЫЙ вызов ИИ со стримингом ---
        final_response_to_save = None
        ai_response_error = False

        # Отображаем контейнер для ответа ассистента
        with st.chat_message("assistant", avatar="💡"):
            placeholder = st.empty() # Место для стриминга
            spinner_message = "Генерирую ответ..."
            if needs_search:
                spinner_message = "Анализирую веб-данные..." if search_performed_successfully else "Поиск не помог, отвечаю на основе знаний..."

            logging.info("Запрос финального ответа от ИИ...")
            full_response_chunks = []
            try:
                # Используем placeholder.container() чтобы spinner был внутри него
                with placeholder.container():
                    with st.spinner(spinner_message):
                        response_generator = stream_ai_response(current_model_id, context_for_ai)
                        for chunk in response_generator:
                            if chunk is None: # Проверяем сигнал об ошибке из генератора
                                logging.error("Генератор стриминга вернул ошибку (None).")
                                ai_response_error = True
                                break # Прерываем цикл обработки чанков
                            if chunk:
                                full_response_chunks.append(chunk)
                                # Обновляем плейсхолдер с текущим текстом и индикатором
                                placeholder.markdown("".join(full_response_chunks) + "▌")

                # После завершения стриминга (или ошибки)
                final_response_to_save = "".join(full_response_chunks)

                if ai_response_error:
                     placeholder.error("Не удалось получить ответ от ИИ из-за ошибки.", icon="😔")
                     final_response_to_save = None # Не сохраняем ответ, если была ошибка
                elif final_response_to_save:
                     placeholder.markdown(final_response_to_save) # Показываем финальный ответ
                     logging.info("Ответ от ИИ успешно получен и отображен.")
                else:
                     # Стриминг завершился, но контента нет (и не было ошибки)
                     placeholder.warning("ИИ не предоставил ответ.", icon="🤷")
                     logging.warning("Ответ от ИИ пуст.")
                     final_response_to_save = None # Не сохраняем пустой ответ

            except Exception as e:
                 # Ловим ошибки, которые могли произойти вне генератора, но при его использовании
                 logging.error(f"Непредвиденная ошибка при обработке стрима ответа ИИ: {e}", exc_info=True)
                 placeholder.error("Произошла ошибка при обработке ответа ИИ.", icon="💥")
                 final_response_to_save = None
                 ai_response_error = True


        # --- Сохранение ответа ---
        if final_response_to_save:
            # Еще раз проверяем, что чат существует (на всякий случай)
            if active_chat_name in st.session_state.all_chats:
                 current_history_for_save = st.session_state.all_chats[active_chat_name]
                 # Убедимся, что не добавляем дубликат или пустое сообщение ассистента
                 if not current_history_for_save or current_history_for_save[-1].get("role") != "assistant":
                      current_history_for_save.append({"role": "assistant", "content": final_response_to_save})
                      save_all_chats(st.session_state.all_chats, st.session_state.active_chat, st.session_state.web_search_enabled)
                      logging.info("Ответ ассистента сохранен.")
                 else:
                      logging.warning("Попытка сохранить ответ ассистента, когда последнее сообщение уже от него. Сохранение пропущено.")
            else:
                 logging.error(f"Ошибка сохранения ответа: чат '{active_chat_name}' исчез во время генерации ответа.")
        elif ai_response_error:
             logging.info("Ответ ИИ не сохранен из-за ошибки.")
        else:
             logging.info("Пустой ответ от ИИ, не сохранено.")

        logging.info(f"--- Обработка ответа ИИ для чата '{active_chat_name}' завершена ---")
        # НЕ НУЖЕН rerun() здесь, так как этот блок выполняется в рамках rerun(), запущенного вводом пользователя.

# --- Футер не нужен ---
