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
import logging
from html import unescape # Для очистки HTML сущностей

# --- Настройка логирования ---
# Убедимся, что уровень INFO, чтобы видеть все шаги
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Ключ API из секретов ---
OPENROUTER_API_KEY = st.secrets.get("OPENROUTER_API_KEY")

# --- Константы ---
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"
MODES = {
    "Стандарт (V3)": "deepseek/deepseek-chat-v3-0324:free",
    "DeepThink (R1)": "deepseek/deepseek-r1:free",
}
DEFAULT_MODE = "Стандарт (V3)"
LOCAL_STORAGE_KEY = "multi_chat_storage_v15" # Сменил ключ на случай несовместимости старых данных
DEFAULT_CHAT_NAME = "Новый чат"
MAX_SEARCH_RESULTS_PER_QUERY = 4 # Уменьшил немного для скорости и релевантности
MAX_QUERIES_TO_GENERATE = 3
MAX_SNIPPET_LENGTH = 300 # Немного увеличил для большего контекста
REQUEST_TIMEOUT = 35 # Немного увеличил таймаут
STREAM_TIMEOUT = 180

# --- Настройка страницы ---
st.set_page_config(
    page_title="Улучшенный Чат ИИ с Поиском", page_icon="💡", layout="wide", initial_sidebar_state="expanded"
)

# --- Инициализация LocalStorage ---
try:
    localS = LocalStorage()
except Exception as e:
    logging.error(f"Критическая ошибка инициализации LocalStorage: {e}", exc_info=True)
    st.error("Не удалось инициализировать локальное хранилище. История чатов не будет сохраняться.", icon="🚨")
    localS = None

# --- Минимальный CSS ---
# (Оставлен без изменений, т.к. проблема была не в нем)
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
    [data-testid="stStatusWidget"] div[role="status"] {{ text-align: center; }}
</style>
"""
st.markdown(custom_css, unsafe_allow_html=True)

# --- Проверка API ключа ---
if not OPENROUTER_API_KEY:
    st.error("⛔ Ключ API OpenRouter (`OPENROUTER_API_KEY`) не найден в секретах Streamlit! Пожалуйста, добавьте его.", icon="🚨")
    logging.error("Ключ API OpenRouter не найден.")
    st.stop()

# --- Функции для работы с чатами (без существенных изменений) ---
def load_all_chats():
    # ... (код load_all_chats как в предыдущей версии) ...
    default_chats = {f"{DEFAULT_CHAT_NAME} 1": []}
    default_name = f"{DEFAULT_CHAT_NAME} 1"
    initial_search_state = False
    if not localS: logging.warning("LocalStorage недоступен, используются значения по умолчанию."); st.session_state.web_search_enabled = initial_search_state; return default_chats, default_name
    data_str = localS.getItem(LOCAL_STORAGE_KEY)
    if data_str:
        try:
            data = json.loads(data_str)
            if isinstance(data, dict) and "chats" in data and "active_chat" in data and isinstance(data["chats"], dict):
                cleaned_chats = {}
                for name, history in data["chats"].items(): cleaned_chats[name] = [msg for msg in history if isinstance(msg, dict) and msg.get("role") and msg.get("content")] if isinstance(history, list) else []
                if not cleaned_chats: st.session_state.web_search_enabled = initial_search_state; return default_chats, default_name
                active_chat = data["active_chat"]
                if active_chat not in cleaned_chats: active_chat = list(cleaned_chats.keys())[0]; logging.warning(f"Активный чат '{data['active_chat']}' не найден, выбран первый: '{active_chat}'.")
                st.session_state.web_search_enabled = data.get("web_search_enabled", initial_search_state)
                logging.info(f"Чаты и состояние поиска ({st.session_state.web_search_enabled=}) успешно загружены.")
                return cleaned_chats, active_chat
            else: logging.warning("Структура данных в LocalStorage некорректна, используются значения по умолчанию.")
        except json.JSONDecodeError as e: logging.error(f"Ошибка декодирования JSON из LocalStorage: {e}. Используются значения по умолчанию.")
        except Exception as e: logging.error(f"Неизвестная ошибка при загрузке чатов: {e}. Используются значения по умолчанию.", exc_info=True)
    else: logging.info("Данные в LocalStorage не найдены, используются значения по умолчанию.")
    st.session_state.web_search_enabled = initial_search_state
    return default_chats, default_name

def save_all_chats(chats_dict, active_chat_name, web_search_state):
    # ... (код save_all_chats как в предыдущей версии) ...
    if not localS: logging.warning("LocalStorage недоступен, сохранение невозможно."); return False
    if not isinstance(chats_dict, dict): logging.error("Попытка сохранить неверный формат чатов (должен быть dict)."); return False
    if not isinstance(active_chat_name, str) and active_chat_name is not None: logging.error("Попытка сохранить неверный формат имени активного чата."); return False
    cleaned_chats = {}
    for name, history in chats_dict.items(): cleaned_chats[name] = [msg for msg in history if isinstance(msg, dict) and msg.get("role") and msg.get("content")] if isinstance(history, list) else []
    if not cleaned_chats: active_chat_name = None
    elif active_chat_name not in cleaned_chats: active_chat_name = list(cleaned_chats.keys())[0] if cleaned_chats else None; logging.warning(f"Активный чат для сохранения не найден, выбран первый: {active_chat_name}")
    data_to_save = {"chats": cleaned_chats, "active_chat": active_chat_name, "web_search_enabled": web_search_state}
    try: localS.setItem(LOCAL_STORAGE_KEY, json.dumps(data_to_save)); logging.info(f"Чаты сохранены. Активный: {active_chat_name}, Поиск: {web_search_state}"); return True
    except Exception as e: logging.error(f"Ошибка сохранения чатов в LocalStorage: {e}", exc_info=True); st.toast("Ошибка сохранения сессии чата!", icon="🚨"); return False

def generate_new_chat_name(existing_names):
    # ... (код generate_new_chat_name как в предыдущей версии) ...
    i = 1; base_name = DEFAULT_CHAT_NAME
    while f"{base_name} {i}" in existing_names: i += 1
    return f"{base_name} {i}"

# --- УЛУЧШЕННАЯ Функция генерации поисковых ВОПРОСОВ ---
def generate_search_queries(user_prompt, model_id):
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "http://localhost:8501", # Замените на ваш URL, если нужно
        "X-Title": "Streamlit Improved Search Chat AI" # Обновил заголовок
    }
    # === НОВЫЙ ПРОМПТ ===
    current_date_str = datetime.datetime.now().strftime('%d %B %Y')
    generation_prompt = f"""Проанализируй следующий запрос пользователя. Твоя задача - сгенерировать до {MAX_QUERIES_TO_GENERATE} высококачественных, **полноценных поисковых вопросов на русском языке**. Эти вопросы должны быть сформулированы так, как их задал бы любопытный человек поисковой системе (например, Google, DuckDuckGo), чтобы найти наиболее релевантную и актуальную информацию по теме запроса.

**Избегай простых ключевых слов.** Вместо этого формулируй естественные вопросы или описательные фразы.
Учитывай возможную потребность в актуальной информации (сегодня {current_date_str}).

Примеры хороших вопросов:
- "Каковы последние разработки в области [тема]?"
- "Как [сделать что-то] пошагово?"
- "Сравнение [продукт А] и [продукт Б] в {datetime.datetime.now().year} году"
- "Последние новости о [событие или компания]"
- "Объяснение [сложный термин] простыми словами"
- "Преимущества и недостатки [технология]"

Выведи только сгенерированные вопросы, каждый на новой строке. Не используй нумерацию или маркеры списка (*, -).

Запрос пользователя:
"{user_prompt}"

Поисковые вопросы:"""
    # === КОНЕЦ НОВОГО ПРОМПТА ===

    payload = {
        "model": model_id,
        "messages": [{"role": "user", "content": generation_prompt}],
        "max_tokens": 150, # Немного больше для полных вопросов
        "temperature": 0.4, # Чуть выше для разнообразия вопросов
        "stop": ["\n\n"] # Попытка остановить генерацию лишнего текста
    }
    generated_queries = []
    try:
        logging.info(f"Генерация поисковых ВОПРОСОВ для: '{user_prompt[:50]}...'")
        response = requests.post(OPENROUTER_API_URL, headers=headers, json=payload, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        data = response.json()
        raw_queries = data.get("choices", [{}])[0].get("message", {}).get("content", "")

        if raw_queries:
            # Разделяем по новой строке, убираем пустые строки и лишние пробелы
            queries = [q.strip() for q in raw_queries.split('\n') if q.strip()]
            # Дополнительно убираем возможные маркеры, которые ИИ мог добавить вопреки инструкции
            queries = [re.sub(r"^\s*[\d\.\-\*]+\s*", "", q) for q in queries]
            generated_queries = [q for q in queries if q] # Финальная очистка от пустых
            logging.info(f"  Сгенерировано вопросов: {generated_queries}")
        else:
            logging.warning("  API вернуло пустой ответ для генерации вопросов.")

    except requests.exceptions.Timeout:
        logging.error("  Ошибка генерации вопросов: Таймаут соединения с OpenRouter.")
        st.toast("Таймаут при подборе поисковых вопросов.", icon="⏱️")
    except requests.exceptions.RequestException as e:
        logging.error(f"  Ошибка сети при генерации вопросов: {e}")
        st.toast(f"Ошибка сети при подборе вопросов: {e}", icon="🚨")
    except Exception as e:
        logging.error(f"  Неизвестная ошибка при генерации вопросов: {e}", exc_info=True)
        st.toast("Неизвестная ошибка при подборе вопросов.", icon="❓")

    return generated_queries[:MAX_QUERIES_TO_GENERATE]

# --- Функция веб-поиска (с очисткой) ---
def clean_html(raw_html):
  """Простая очистка HTML тегов и сущностей."""
  if not isinstance(raw_html, str): return ""
  cleanr = re.compile('<.*?>')
  cleantext = re.sub(cleanr, '', raw_html)
  cleantext = unescape(cleantext) # Декодирование HTML сущностей типа &
  return cleantext.strip()

def perform_web_search(queries: list, max_results_per_query=MAX_SEARCH_RESULTS_PER_QUERY):
    all_results_text = ""
    aggregated_results = []
    if not queries:
        logging.warning("Нет запросов для выполнения веб-поиска.")
        return "Нет запросов для поиска."

    logging.info(f"Начинаю веб-поиск по {len(queries)} запросам...")
    search_errors = []
    try:
        # Используем менеджер контекста для DDGS
        with DDGS(timeout=REQUEST_TIMEOUT) as ddgs:
            for idx, query in enumerate(queries, 1):
                logging.info(f"  Выполняю запрос {idx}/{len(queries)}: '{query}'...")
                try:
                    # Используем ddgs.text для получения текстовых результатов
                    search_results = list(ddgs.text(query, max_results=max_results_per_query))
                    # Очищаем полученные результаты
                    for result in search_results:
                         result['body'] = clean_html(result.get('body', ''))
                         result['title'] = clean_html(result.get('title', ''))
                    aggregated_results.extend(search_results)
                    logging.info(f"    Найдено и очищено {len(search_results)} результатов для '{query}'.")
                except Exception as e:
                    logging.error(f"    Ошибка при поиске по запросу '{query}': {e}", exc_info=True)
                    search_errors.append(query)
                    # Не прерываем весь поиск из-за одного запроса

        if search_errors:
             st.toast(f"Проблемы при поиске по запросам: {', '.join(search_errors)}", icon="🕸️")

        if aggregated_results:
            unique_results_dict = {}
            for res in aggregated_results:
                body = res.get('body')
                # Добавляем результат, только если есть тело и оно еще не встречалось
                if body and body not in unique_results_dict:
                    unique_results_dict[body] = res

            unique_results = list(unique_results_dict.values())
            logging.info(f"Всего найдено уникальных результатов после фильтрации: {len(unique_results)}")

            if unique_results:
                result_lines = []
                for i, res in enumerate(unique_results, 1):
                    title = res.get('title', 'Без заголовка')
                    body = res.get('body', '')
                    # Обрезаем сниппет, если он слишком длинный
                    snippet = (body[:MAX_SNIPPET_LENGTH] + '...') if len(body) > MAX_SNIPPET_LENGTH else body
                    result_lines.append(f"{i}. {title}: {snippet}")
                all_results_text = "--- Результаты веб-поиска ---\n" + "\n\n".join(result_lines) # Добавил пустую строку между результатами
            else:
                all_results_text = "Не найдено уникальных и релевантных результатов после фильтрации."
                logging.info(all_results_text)
        else:
            all_results_text = "Поиск не дал результатов."
            logging.info(all_results_text)

        return all_results_text.strip()

    except Exception as e:
        logging.error(f"Критическая ошибка во время инициализации или выполнения веб-поиска: {e}", exc_info=True)
        st.error(f"Произошла критическая ошибка во время веб-поиска: {e}", icon="🕸️")
        return f"Критическая ошибка веб-поиска: {e}"


# --- Функция стриминга (без существенных изменений) ---
def stream_ai_response(model_id_func, chat_history_func):
    # ... (код stream_ai_response как в предыдущей версии) ...
    headers = {"Authorization": f"Bearer {OPENROUTER_API_KEY}","Content-Type": "application/json","HTTP-Referer": "http://localhost:8501","X-Title": "Streamlit Improved Search Chat AI"}
    if not isinstance(chat_history_func, list): logging.error("История чата для стриминга передана в неверном формате."); yield None; return
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
                        if json_data_str == "[DONE]": logging.info("Стриминг завершен сигналом [DONE]."); break
                        if json_data_str:
                           chunk = json.loads(json_data_str)
                           delta = chunk.get("choices", [{}])[0].get("delta", {})
                           if delta and "content" in delta: delta_content = delta["content"]; stream_successful = True; yield delta_content
                    except json.JSONDecodeError as e: logging.warning(f"Ошибка декодирования JSON чанка: {e}. Строка: '{json_data_str}'"); continue
                    except Exception as e: logging.error(f"Ошибка обработки чанка стрима: {e}"); continue
        if not stream_successful: logging.warning("Стриминг завершился без передачи контента.")
    except requests.exceptions.Timeout: logging.error(f"Ошибка стриминга: Таймаут ({STREAM_TIMEOUT}s) соединения с OpenRouter."); st.error(f"Таймаут ({STREAM_TIMEOUT} сек) при ожидании ответа от ИИ.", icon="⏱️"); yield None
    except requests.exceptions.RequestException as e: logging.error(f"Ошибка стриминга: {e}"); st.error(f"Ошибка сети при получении ответа от ИИ: {e}", icon="🚨"); yield None
    except Exception as e: logging.error(f"Неизвестная ошибка во время стриминга: {e}", exc_info=True); st.error("Произошла неизвестная ошибка при получении ответа от ИИ.", icon="❓"); yield None

# --- Инициализация состояния ---
if "all_chats" not in st.session_state:
    logging.info("Инициализация состояния сессии...")
    st.session_state.all_chats, st.session_state.active_chat = load_all_chats()
if "selected_mode" not in st.session_state:
    st.session_state.selected_mode = DEFAULT_MODE
if "web_search_enabled" not in st.session_state:
     st.session_state.web_search_enabled = False
     logging.warning("Состояние web_search_enabled не было установлено при загрузке, установлено в False.")

# --- Определяем активный чат ---
# (Логика определения активного чата без изменений)
if st.session_state.active_chat not in st.session_state.all_chats:
    logging.warning(f"Активный чат '{st.session_state.active_chat}' не найден в списке чатов.")
    if st.session_state.all_chats: st.session_state.active_chat = list(st.session_state.all_chats.keys())[0]; logging.info(f"Установлен первый доступный чат: '{st.session_state.active_chat}'")
    else: new_name = generate_new_chat_name([]); st.session_state.all_chats = {new_name: []}; st.session_state.active_chat = new_name; logging.info(f"Список чатов пуст. Создан новый чат: '{new_name}'"); save_all_chats(st.session_state.all_chats, st.session_state.active_chat, st.session_state.web_search_enabled)
active_chat_name = st.session_state.active_chat

# --- Сайдбар ---
# (Код сайдбара без изменений)
with st.sidebar:
    st.markdown("## 💬 Чаты")
    chat_names = list(st.session_state.all_chats.keys())
    if chat_names:
        try: active_chat_index = chat_names.index(active_chat_name)
        except ValueError: logging.error(f"Критическая ошибка: active_chat_name '{active_chat_name}' не найден в chat_names."); active_chat_index = 0
        selected_chat = st.radio("Выберите чат:",options=chat_names,index=active_chat_index,label_visibility="collapsed",key="chat_selector")
        if selected_chat is not None and selected_chat != active_chat_name: st.session_state.active_chat = selected_chat; logging.info(f"Пользователь выбрал чат: {selected_chat}"); save_all_chats(st.session_state.all_chats, st.session_state.active_chat, st.session_state.web_search_enabled); st.rerun()
    else: st.write("Нет доступных чатов.")
    st.divider()
    if st.button("➕ Новый чат", key="new_chat_button"): new_name = generate_new_chat_name(list(st.session_state.all_chats.keys())); st.session_state.all_chats[new_name] = []; st.session_state.active_chat = new_name; logging.info(f"Создан новый чат: {new_name}"); save_all_chats(st.session_state.all_chats, st.session_state.active_chat, st.session_state.web_search_enabled); st.rerun()
    if chat_names:
        if st.button("🗑️ Удалить текущий чат", type="secondary", key="delete_chat_button"):
            current_chat_to_delete = st.session_state.active_chat; logging.info(f"Запрос на удаление чата: {current_chat_to_delete}")
            if current_chat_to_delete in st.session_state.all_chats:
                del st.session_state.all_chats[current_chat_to_delete]; logging.info(f"Чат '{current_chat_to_delete}' удален."); remaining_chats = list(st.session_state.all_chats.keys())
                if remaining_chats: st.session_state.active_chat = remaining_chats[0]
                else: new_name = generate_new_chat_name([]); st.session_state.all_chats = {new_name: []}; st.session_state.active_chat = new_name; logging.info("Удален последний чат, создан новый.")
                save_all_chats(st.session_state.all_chats, st.session_state.active_chat, st.session_state.web_search_enabled); st.rerun()
            else: logging.warning(f"Попытка удалить несуществующий чат: {current_chat_to_delete}")
    st.divider()
    search_toggled = st.toggle("🌐 Веб-поиск", value=st.session_state.web_search_enabled, key="web_search_toggle")
    if search_toggled != st.session_state.web_search_enabled: st.session_state.web_search_enabled = search_toggled; logging.info(f"Веб-поиск переключен в состояние: {search_toggled}"); save_all_chats(st.session_state.all_chats, st.session_state.active_chat, st.session_state.web_search_enabled)
    st.divider()
    mode_options = list(MODES.keys())
    try: current_mode_index = mode_options.index(st.session_state.selected_mode)
    except ValueError: logging.warning(f"Выбранный режим '{st.session_state.selected_mode}' не найден. Установлен режим по умолчанию."); st.session_state.selected_mode = DEFAULT_MODE; current_mode_index = 0
    selected_mode_radio = st.radio("Режим работы:", options=mode_options, index=current_mode_index, key="mode_selector")
    if selected_mode_radio is not None and selected_mode_radio != st.session_state.selected_mode: st.session_state.selected_mode = selected_mode_radio; logging.info(f"Выбран режим работы: {selected_mode_radio}")

# --- Основная область: Чат ---
current_mode_name = st.session_state.get("selected_mode", DEFAULT_MODE)
current_model_id = MODES.get(current_mode_name, MODES[DEFAULT_MODE])

# Отображение истории чата
# (Код отображения истории без изменений)
chat_display_container = st.container()
with chat_display_container:
    if active_chat_name in st.session_state.all_chats:
        current_display_history = st.session_state.all_chats[active_chat_name]
        for message in current_display_history:
            avatar = "🧑‍💻" if message["role"] == "user" else "💡"
            with st.chat_message(message["role"], avatar=avatar):
                st.markdown(message["content"], unsafe_allow_html=True) # unsafe_allow_html важно для отображения форматирования
    else: st.warning(f"Активный чат '{active_chat_name}' не найден."); logging.warning(f"Попытка отобразить историю несуществующего чата: {active_chat_name}")

# --- Поле ввода пользователя ---
# (Код поля ввода без изменений)
if prompt := st.chat_input(f"Спроси {current_mode_name}..."):
    if active_chat_name in st.session_state.all_chats:
        logging.info(f"Получен новый промпт от пользователя в чате '{active_chat_name}'.")
        st.session_state.all_chats[active_chat_name].append({"role": "user", "content": prompt})
        save_all_chats(st.session_state.all_chats, st.session_state.active_chat, st.session_state.web_search_enabled)
        st.rerun()
    else: st.error("Ошибка: Активный чат не найден.", icon="❌"); logging.error(f"Ошибка добавления сообщения: активный чат '{active_chat_name}' не найден.")


# --- Логика ответа ИИ (с улучшенным поиском и инструкциями) ---
if active_chat_name in st.session_state.all_chats:
    current_chat_state = st.session_state.all_chats[active_chat_name]

    if current_chat_state and current_chat_state[-1]["role"] == "user":

        last_user_prompt = current_chat_state[-1]["content"]
        logging.info(f"\n--- Начало обработки ответа ИИ для чата '{active_chat_name}' ---")
        logging.info(f"Промпт: '{last_user_prompt[:100]}...' | Поиск: {'ВКЛ' if st.session_state.web_search_enabled else 'ВЫКЛ'}")

        current_date = datetime.datetime.now().strftime("%Y-%m-%d")
        search_results_str = ""
        search_performed_successfully = False
        context_for_ai = list(current_chat_state)
        needs_search = st.session_state.web_search_enabled
        system_prompt = {"role": "system"} # Инициализируем здесь

        # --- Этапы поиска (если включен) ---
        if needs_search:
            logging.info(">>> Веб-поиск включен.")
            generated_queries = []
            search_results_str = "Поиск не выполнялся." # Начальное значение

            # 1. Генерация поисковых ВОПРОСОВ
            try:
                # Используем spinner для индикации
                with st.spinner("Подбираю поисковые вопросы... 🤔"):
                    generated_queries = generate_search_queries(last_user_prompt, current_model_id)
            except Exception as e:
                logging.error(f"Критическая ошибка при вызове generate_search_queries: {e}", exc_info=True)
                st.error("Не удалось сгенерировать поисковые вопросы.", icon="❓")
                # Не прерываем, попробуем искать по исходному запросу ниже

            # 2. Выполнение поиска
            queries_to_search = generated_queries if generated_queries else [last_user_prompt]
            if not generated_queries:
                 logging.warning("Поисковые вопросы не сгенерированы, используется исходный промпт пользователя.")

            search_spinner_text = f"Ищу в сети по {len(queries_to_search)} вопросам... 🌐" if generated_queries else "Ищу в сети по вашему запросу... 🌐"
            try:
                with st.spinner(search_spinner_text):
                     search_results_str = perform_web_search(queries_to_search)

                # Проверяем успешность поиска более строго
                if search_results_str and not any(err_msg in search_results_str for err_msg in ["Ошибка веб-поиска", "не дал результатов", "Нет запросов", "Не найдено уникальных", "Критическая ошибка"]):
                     search_performed_successfully = True
                     logging.info("Веб-поиск дал результаты.")
                else:
                     logging.warning(f"Веб-поиск не дал полезных результатов или произошла ошибка. Результат: '{search_results_str}'")
                     # Оставляем search_performed_successfully = False

            except Exception as e:
                 logging.error(f"Критическая ошибка при вызове perform_web_search: {e}", exc_info=True)
                 st.error("Произошла критическая ошибка во время веб-поиска.", icon="🕸️")
                 search_results_str = f"Критическая ошибка веб-поиска: {e}" # Записываем ошибку для промпта
                 search_performed_successfully = False

            # 3. Формирование УЛУЧШЕННОГО системного промпта
            if search_performed_successfully:
                 # === НОВЫЙ ПРОМПТ ДЛЯ УСПЕШНОГО ПОИСКА ===
                 system_prompt["content"] = f"""Текущая дата: {current_date}. Был выполнен веб-поиск по запросу пользователя. Результаты приведены ниже.

**Твоя задача:** Внимательно изучи результаты поиска и **синтезируй из них единый, связный и информативный ответ** на исходный запрос пользователя. Не просто перечисляй найденные фрагменты. Используй информацию из поиска как основу для своего ответа, но изложи ее своими словами. **Приоритет отдавай информации из поиска**, особенно если она кажется более актуальной, чем твои внутренние знания. Не включай URL или прямые ссылки в свой ответ. Не упоминай сам факт проведения поиска.

--- Результаты веб-поиска ---
{search_results_str}
--- Конец результатов поиска ---

Ответь на запрос пользователя, основываясь на предоставленной информации из поиска."""
                 logging.info("Системный промпт сформирован с результатами поиска и инструкцией синтеза.")
            else:
                 # === НОВЫЙ ПРОМПТ ДЛЯ НЕУДАЧНОГО ПОИСКА ===
                 system_prompt["content"] = f"""Текущая дата: {current_date}. Веб-поиск был включен, но, к сожалению, **не дал релевантных результатов** (Причина: '{search_results_str}').

**Твоя задача:** Ответь на запрос пользователя, **основываясь исключительно на своих внутренних знаниях**. Поскольку актуальная информация из веба недоступна, **обязательно предупреди пользователя**, что твой ответ может быть не самым последним или не учитывать недавние события/изменения."""
                 logging.info("Системный промпт сформирован с уведомлением о неудачном поиске и инструкцией предупредить.")
            # Вставляем системный промпт ПЕРЕД последним сообщением пользователя
            context_for_ai.insert(-1, system_prompt)

        else: # needs_search == False
            logging.info(">>> Веб-поиск выключен.")
            system_prompt["content"] = f"Текущая дата: {current_date}. Веб-поиск ВЫКЛЮЧЕН. Отвечай на последний запрос пользователя, основываясь только на своих общих знаниях."
            context_for_ai.insert(-1, system_prompt) # Вставляем перед последним сообщением
            logging.info("Системный промпт сформирован без информации о поиске.")

        # === Блок сбора, отображения и сохранения ответа (без изменений, использует st.spinner) ===
        final_response_to_save = None
        ai_response_error = False
        full_response_chunks = []

        spinner_message = "Генерирую ответ..."
        if needs_search:
            spinner_message = "Анализирую веб-данные..." if search_performed_successfully else "Поиск не помог, отвечаю..." # Обновил текст

        logging.info("Запрос и сбор финального ответа от ИИ...")
        try:
            with st.spinner(spinner_message):
                response_generator = stream_ai_response(current_model_id, context_for_ai)
                for chunk in response_generator:
                    if chunk is None:
                        logging.error("Генератор стриминга вернул ошибку (None).")
                        ai_response_error = True
                        break
                    if chunk:
                        full_response_chunks.append(chunk)

            if not ai_response_error:
                final_response_to_save = "".join(full_response_chunks)
                if final_response_to_save:
                    logging.info("Ответ от ИИ успешно собран.")
                else:
                    logging.warning("Ответ от ИИ пуст после стриминга.")
                    st.warning("ИИ не предоставил ответ.", icon="🤷")
                    final_response_to_save = None

            if ai_response_error:
                 st.error("Ошибка при получении ответа от ИИ!", icon="😔")

        except Exception as e:
             logging.error(f"Непредвиденная ошибка при сборе стрима ответа ИИ: {e}", exc_info=True)
             st.error(f"Произошла ошибка при обработке ответа ИИ: {e}", icon="💥")
             final_response_to_save = None
             ai_response_error = True

        # Отображение и Сохранение
        if final_response_to_save and not ai_response_error:
            logging.info("Отображение полного ответа ассистента...")
            try:
                with st.chat_message("assistant", avatar="💡"):
                    st.markdown(final_response_to_save, unsafe_allow_html=True)
                logging.info("Полный ответ ассистента успешно отображен.")

                if active_chat_name in st.session_state.all_chats:
                     current_history_for_save = st.session_state.all_chats[active_chat_name]
                     if not current_history_for_save or current_history_for_save[-1].get("role") != "assistant" or current_history_for_save[-1].get("content") != final_response_to_save:
                          current_history_for_save.append({"role": "assistant", "content": final_response_to_save})
                          save_all_chats(st.session_state.all_chats, st.session_state.active_chat, st.session_state.web_search_enabled)
                          logging.info("Ответ ассистента сохранен.")
                     else:
                          logging.warning("Обнаружено дублирование ответа ассистента. Сохранение пропущено.")
                else:
                     logging.error(f"Ошибка сохранения ответа: чат '{active_chat_name}' исчез.")

            except Exception as render_error:
                 logging.error(f"Ошибка при рендеринге финального сообщения markdown: {render_error}", exc_info=True)
                 st.error(f"Не удалось отобразить ответ ИИ из-за ошибки рендеринга: {render_error}", icon="🖼️")

        elif ai_response_error:
             logging.info("Ответ ИИ не отображен и не сохранен из-за ошибки.")
        else:
             logging.info("Пустой ответ от ИИ, не отображено и не сохранено.")

        logging.info(f"--- Обработка ответа ИИ для чата '{active_chat_name}' завершена ---")
