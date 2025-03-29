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
from html import unescape

# --- Настройка логирования ---
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
LOCAL_STORAGE_KEY = "multi_chat_storage_v17" # Снова сменил ключ
DEFAULT_CHAT_NAME = "Новый чат"
MAX_SEARCH_RESULTS_PER_QUERY = 4
MAX_QUERIES_TO_GENERATE = 3
MAX_SNIPPET_LENGTH = 300
REQUEST_TIMEOUT = 35
STREAM_TIMEOUT = 180

# --- Настройка страницы ---
st.set_page_config(
    page_title="Чат ИИ со Стримингом v3 (st.write)", page_icon="💡", layout="wide", initial_sidebar_state="expanded"
)

# --- Инициализация LocalStorage ---
try:
    localS = LocalStorage()
except Exception as e:
    logging.error(f"Критическая ошибка инициализации LocalStorage: {e}", exc_info=True)
    st.error("Не удалось инициализировать локальное хранилище.", icon="🚨")
    localS = None

# --- Минимальный CSS ---
# Убрал стиль для streaming-placeholder, он больше не нужен
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
    st.error("⛔ Ключ API OpenRouter (`OPENROUTER_API_KEY`) не найден!", icon="🚨")
    logging.error("Ключ API OpenRouter не найден.")
    st.stop()

# --- Класс-обертка для генератора ---
class StreamWriteWrapper:
    """Обертка для генератора, чтобы получить полный ответ после st.write."""
    def __init__(self, generator):
        self._generator = generator
        self._buffer = []
        self._error_occurred = False

    def __iter__(self):
        self._buffer = [] # Очищаем буфер перед новой итерацией
        self._error_occurred = False
        try:
            for chunk in self._generator:
                if chunk is not None:
                    self._buffer.append(chunk)
                    yield chunk
                else:
                    # Если генератор вернул None, считаем это ошибкой
                    self._error_occurred = True
                    logging.error("StreamWriteWrapper: Генератор вернул None (ошибка).")
                    # Не прерываем yield, чтобы st.write мог завершиться,
                    # но флаг ошибки установлен
        except Exception as e:
            self._error_occurred = True
            logging.error(f"StreamWriteWrapper: Исключение при итерации генератора: {e}", exc_info=True)
            # Перевыбрасываем исключение, чтобы st.write мог его поймать (если он это делает)
            # Или просто логируем и устанавливаем флаг
            # Для большей стабильности просто установим флаг и не будем ничего yield'ить дальше
            yield f"\n\n**Произошла ошибка при генерации ответа: {e}**" # Отдаем текст ошибки

    @property
    def full_response(self):
        """Возвращает полный собранный ответ."""
        return "".join(self._buffer)

    @property
    def error_occurred(self):
        """Возвращает True, если во время итерации произошла ошибка."""
        # Ошибка, если флаг установлен ИЛИ если буфер пуст после итерации (т.к. контента не было)
        # Но ИИ мог просто вернуть пустой ответ без ошибки. Сложно отличить.
        # Будем полагаться на флаг _error_occurred.
        return self._error_occurred

# --- Функции для работы с чатами ---
# (load_all_chats, save_all_chats, generate_new_chat_name - без изменений)
def load_all_chats():
    default_chats = {f"{DEFAULT_CHAT_NAME} 1": []}; default_name = f"{DEFAULT_CHAT_NAME} 1"; initial_search_state = False
    if not localS: logging.warning("LocalStorage недоступен."); st.session_state.web_search_enabled = initial_search_state; return default_chats, default_name
    data_str = localS.getItem(LOCAL_STORAGE_KEY)
    if data_str:
        try:
            data = json.loads(data_str)
            if isinstance(data, dict) and "chats" in data and "active_chat" in data and isinstance(data["chats"], dict):
                cleaned_chats = {}; active_chat = data["active_chat"]
                for name, history in data["chats"].items(): cleaned_chats[name] = [msg for msg in history if isinstance(msg, dict) and msg.get("role") and msg.get("content")] if isinstance(history, list) else []
                if not cleaned_chats: st.session_state.web_search_enabled = initial_search_state; return default_chats, default_name
                if active_chat not in cleaned_chats: active_chat = list(cleaned_chats.keys())[0]; logging.warning(f"Активный чат '{data['active_chat']}' не найден, выбран '{active_chat}'.")
                st.session_state.web_search_enabled = data.get("web_search_enabled", initial_search_state)
                logging.info(f"Чаты загружены ({st.session_state.web_search_enabled=})."); return cleaned_chats, active_chat
            else: logging.warning("Структура данных в LS некорректна.")
        except Exception as e: logging.error(f"Ошибка загрузки чатов: {e}.", exc_info=True)
    else: logging.info("Данные в LS не найдены.")
    st.session_state.web_search_enabled = initial_search_state; return default_chats, default_name

def save_all_chats(chats_dict, active_chat_name, web_search_state):
    if not localS: logging.warning("LocalStorage недоступен, сохранение невозможно."); return False
    if not isinstance(chats_dict, dict): logging.error("Неверный формат чатов для сохранения."); return False
    if not isinstance(active_chat_name, str) and active_chat_name is not None: logging.error("Неверный формат имени активного чата."); return False
    cleaned_chats = {}
    for name, history in chats_dict.items(): cleaned_chats[name] = [msg for msg in history if isinstance(msg, dict) and msg.get("role") and msg.get("content")] if isinstance(history, list) else []
    if not cleaned_chats: active_chat_name = None
    elif active_chat_name not in cleaned_chats: active_chat_name = list(cleaned_chats.keys())[0] if cleaned_chats else None; logging.warning(f"Активный чат для сохранения не найден, выбран: {active_chat_name}")
    data_to_save = {"chats": cleaned_chats, "active_chat": active_chat_name, "web_search_enabled": web_search_state}
    try: localS.setItem(LOCAL_STORAGE_KEY, json.dumps(data_to_save)); logging.info(f"Чаты сохранены."); return True
    except Exception as e: logging.error(f"Ошибка сохранения чатов: {e}", exc_info=True); st.toast("Ошибка сохранения!", icon="🚨"); return False

def generate_new_chat_name(existing_names):
    i = 1
    base_name = DEFAULT_CHAT_NAME
    while f"{base_name} {i}" in existing_names:
        i += 1
    return f"{base_name} {i}"

# --- Функции поиска и генерации запросов ---
# (generate_search_queries, clean_html, perform_web_search - без изменений)
def generate_search_queries(user_prompt, model_id):
    headers = {"Authorization": f"Bearer {OPENROUTER_API_KEY}","Content-Type": "application/json","HTTP-Referer": "http://localhost:8501","X-Title": "Streamlit Improved Search Chat AI"}
    current_date_str = datetime.datetime.now().strftime('%d %B %Y')
    generation_prompt = f"""Проанализируй следующий запрос пользователя. Твоя задача - сгенерировать до {MAX_QUERIES_TO_GENERATE} высококачественных, **полноценных поисковых вопросов на русском языке**. Эти вопросы должны быть сформулированы так, как их задал бы любопытный человек поисковой системе (например, Google, DuckDuckGo), чтобы найти наиболее релевантную и актуальную информацию по теме запроса.\n\n**Избегай простых ключевых слов.** Вместо этого формулируй естественные вопросы или описательные фразы.\nУчитывай возможную потребность в актуальной информации (сегодня {current_date_str}).\n\nПримеры хороших вопросов:\n- "Каковы последние разработки в области [тема]?"\n- "Как [сделать что-то] пошагово?"\n- "Сравнение [продукт А] и [продукт Б] в {datetime.datetime.now().year} году"\n- "Последние новости о [событие или компания]"\n- "Объяснение [сложный термин] простыми словами"\n- "Преимущества и недостатки [технология]"\n\nВыведи только сгенерированные вопросы, каждый на новой строке. Не используй нумерацию или маркеры списка (*, -).\n\nЗапрос пользователя:\n"{user_prompt}"\n\nПоисковые вопросы:"""
    payload = {"model": model_id, "messages": [{"role": "user", "content": generation_prompt}], "max_tokens": 150, "temperature": 0.4, "stop": ["\n\n"]}
    generated_queries = []
    try:
        logging.info(f"Генерация поисковых ВОПРОСОВ для: '{user_prompt[:50]}...'")
        response = requests.post(OPENROUTER_API_URL, headers=headers, json=payload, timeout=REQUEST_TIMEOUT); response.raise_for_status()
        data = response.json(); raw_queries = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        if raw_queries: queries = [re.sub(r"^\s*[\d\.\-\*]+\s*", "", q.strip()) for q in raw_queries.split('\n') if q.strip()]; generated_queries = [q for q in queries if q]; logging.info(f"  Сгенерировано вопросов: {generated_queries}")
        else: logging.warning("  API вернуло пустой ответ для генерации вопросов.")
    except requests.exceptions.Timeout: logging.error("  Ошибка генерации вопросов: Таймаут."); st.toast("Таймаут при подборе вопросов.", icon="⏱️")
    except requests.exceptions.RequestException as e: logging.error(f"  Ошибка сети при генерации вопросов: {e}"); st.toast(f"Ошибка сети: {e}", icon="🚨")
    except Exception as e: logging.error(f"  Неизвестная ошибка при генерации вопросов: {e}", exc_info=True); st.toast("Ошибка подбора вопросов.", icon="❓")
    return generated_queries[:MAX_QUERIES_TO_GENERATE]

def clean_html(raw_html):
  if not isinstance(raw_html, str): return ""
  cleanr = re.compile('<.*?>'); cleantext = re.sub(cleanr, '', raw_html); cleantext = unescape(cleantext)
  return cleantext.strip()

def perform_web_search(queries: list, max_results_per_query=MAX_SEARCH_RESULTS_PER_QUERY):
    all_results_text = ""; aggregated_results = []; search_errors = []
    if not queries: logging.warning("Нет запросов для веб-поиска."); return "Нет запросов для поиска."
    logging.info(f"Начинаю веб-поиск по {len(queries)} запросам...")
    try:
        with DDGS(timeout=REQUEST_TIMEOUT) as ddgs:
            for idx, query in enumerate(queries, 1):
                logging.info(f"  Выполняю запрос {idx}/{len(queries)}: '{query}'...")
                try:
                    search_results = list(ddgs.text(query, max_results=max_results_per_query))
                    for result in search_results: result['body'] = clean_html(result.get('body', '')); result['title'] = clean_html(result.get('title', ''))
                    aggregated_results.extend(search_results); logging.info(f"    Найдено {len(search_results)} для '{query}'.")
                except Exception as e: logging.error(f"    Ошибка поиска по '{query}': {e}", exc_info=True); search_errors.append(query)
        if search_errors: st.toast(f"Проблемы при поиске: {', '.join(search_errors)}", icon="🕸️")
        if aggregated_results:
            unique_results_dict = {}
            for res in aggregated_results:
                body = res.get('body')
                if body and body not in unique_results_dict:
                    unique_results_dict[body] = res
            unique_results = list(unique_results_dict.values())
            logging.info(f"Уникальных результатов после фильтрации: {len(unique_results)}")
            if unique_results:
                result_lines = [f"{i}. {res.get('title', 'Без заголовка')}: {(res.get('body', '')[:MAX_SNIPPET_LENGTH] + '...') if len(res.get('body', '')) > MAX_SNIPPET_LENGTH else res.get('body', '')}" for i, res in enumerate(unique_results, 1)]
                all_results_text = "--- Результаты веб-поиска ---\n" + "\n\n".join(result_lines)
            else: all_results_text = "Не найдено уникальных результатов после фильтрации."; logging.info(all_results_text)
        else: all_results_text = "Поиск не дал результатов."; logging.info(all_results_text)
        return all_results_text.strip()
    except Exception as e: logging.error(f"Критическая ошибка веб-поиска: {e}", exc_info=True); st.error(f"Ошибка веб-поиска: {e}", icon="🕸️"); return f"Критическая ошибка веб-поиска: {e}"

# --- Функция стриминга ---
# (Без изменений)
def stream_ai_response(model_id_func, chat_history_func):
    headers = {"Authorization": f"Bearer {OPENROUTER_API_KEY}","Content-Type": "application/json","HTTP-Referer": "http://localhost:8501","X-Title": "Streamlit Improved Search Chat AI"}
    if not isinstance(chat_history_func, list): logging.error("Неверный формат истории для стриминга."); yield None; return
    payload = {"model": model_id_func, "messages": chat_history_func, "stream": True}; stream_successful = False
    try:
        logging.info(f"Запрос стриминга: {model_id_func}"); response = requests.post(OPENROUTER_API_URL, headers=headers, json=payload, stream=True, timeout=STREAM_TIMEOUT); response.raise_for_status(); logging.info("Стриминг начат.")
        for line in response.iter_lines():
            if line:
                decoded_line = line.decode('utf-8')
                if decoded_line.startswith("data: "):
                    try:
                        json_data_str = decoded_line[len("data: "):].strip()
                        if json_data_str == "[DONE]": logging.info("Стриминг [DONE]."); break
                        if json_data_str: chunk = json.loads(json_data_str); delta = chunk.get("choices", [{}])[0].get("delta", {});
                        if delta and "content" in delta: delta_content = delta["content"]; stream_successful = True; yield delta_content
                    except json.JSONDecodeError as e: logging.warning(f"Ошибка JSON чанка: {e}. Строка: '{json_data_str}'"); continue
                    except Exception as e: logging.error(f"Ошибка обработки чанка: {e}"); continue
        if not stream_successful: logging.warning("Стриминг без контента.")
    except requests.exceptions.Timeout: logging.error(f"Ошибка стриминга: Таймаут ({STREAM_TIMEOUT}s)."); yield None # Ошибка будет обработана в обертке
    except requests.exceptions.RequestException as e: logging.error(f"Ошибка стриминга: {e}"); yield None # Ошибка будет обработана в обертке
    except Exception as e: logging.error(f"Неизвестная ошибка стриминга: {e}", exc_info=True); yield None # Ошибка будет обработана в обертке


# --- Инициализация состояния ---
# (Без изменений)
if "all_chats" not in st.session_state: logging.info("Инициализация состояния."); st.session_state.all_chats, st.session_state.active_chat = load_all_chats()
if "selected_mode" not in st.session_state: st.session_state.selected_mode = DEFAULT_MODE
if "web_search_enabled" not in st.session_state: st.session_state.web_search_enabled = False; logging.warning("web_search_enabled не установлено, -> False.")

# --- Определяем активный чат ---
# (Без изменений)
if st.session_state.active_chat not in st.session_state.all_chats:
    logging.warning(f"Активный чат '{st.session_state.active_chat}' не найден.");
    if st.session_state.all_chats: st.session_state.active_chat = list(st.session_state.all_chats.keys())[0]; logging.info(f"Выбран первый: '{st.session_state.active_chat}'")
    else: new_name = generate_new_chat_name([]); st.session_state.all_chats = {new_name: []}; st.session_state.active_chat = new_name; logging.info(f"Создан новый чат: '{new_name}'"); save_all_chats(st.session_state.all_chats, st.session_state.active_chat, st.session_state.web_search_enabled)
active_chat_name = st.session_state.active_chat

# --- Сайдбар ---
# (Без изменений)
with st.sidebar:
    st.markdown("## 💬 Чаты"); chat_names = list(st.session_state.all_chats.keys())
    if chat_names:
        try: active_chat_index = chat_names.index(active_chat_name)
        except ValueError: logging.error(f"Активный чат '{active_chat_name}' не найден в ключах."); active_chat_index = 0
        selected_chat = st.radio("Выберите чат:",options=chat_names,index=active_chat_index,label_visibility="collapsed",key="chat_selector")
        if selected_chat is not None and selected_chat != active_chat_name: st.session_state.active_chat = selected_chat; logging.info(f"Выбран чат: {selected_chat}"); save_all_chats(st.session_state.all_chats, st.session_state.active_chat, st.session_state.web_search_enabled); st.rerun()
    else: st.write("Нет чатов.")
    st.divider()
    if st.button("➕ Новый чат", key="new_chat_button"): new_name = generate_new_chat_name(list(st.session_state.all_chats.keys())); st.session_state.all_chats[new_name] = []; st.session_state.active_chat = new_name; logging.info(f"Создан чат: {new_name}"); save_all_chats(st.session_state.all_chats, st.session_state.active_chat, st.session_state.web_search_enabled); st.rerun()
    if chat_names:
        if st.button("🗑️ Удалить текущий чат", type="secondary", key="delete_chat_button"):
            current_chat_to_delete = st.session_state.active_chat; logging.info(f"Удаление чата: {current_chat_to_delete}")
            if current_chat_to_delete in st.session_state.all_chats:
                del st.session_state.all_chats[current_chat_to_delete]; logging.info(f"Чат удален."); remaining_chats = list(st.session_state.all_chats.keys())
                if remaining_chats: st.session_state.active_chat = remaining_chats[0]
                else: new_name = generate_new_chat_name([]); st.session_state.all_chats = {new_name: []}; st.session_state.active_chat = new_name; logging.info("Создан новый чат после удаления последнего.")
                save_all_chats(st.session_state.all_chats, st.session_state.active_chat, st.session_state.web_search_enabled); st.rerun()
            else: logging.warning(f"Попытка удалить несуществующий чат: {current_chat_to_delete}")
    st.divider()
    search_toggled = st.toggle("🌐 Веб-поиск", value=st.session_state.web_search_enabled, key="web_search_toggle")
    if search_toggled != st.session_state.web_search_enabled: st.session_state.web_search_enabled = search_toggled; logging.info(f"Веб-поиск: {search_toggled}"); save_all_chats(st.session_state.all_chats, st.session_state.active_chat, st.session_state.web_search_enabled)
    st.divider()
    mode_options = list(MODES.keys())
    try: current_mode_index = mode_options.index(st.session_state.selected_mode)
    except ValueError: logging.warning(f"Режим '{st.session_state.selected_mode}' не найден."); st.session_state.selected_mode = DEFAULT_MODE; current_mode_index = 0
    selected_mode_radio = st.radio("Режим работы:", options=mode_options, index=current_mode_index, key="mode_selector")
    if selected_mode_radio is not None and selected_mode_radio != st.session_state.selected_mode: st.session_state.selected_mode = selected_mode_radio; logging.info(f"Выбран режим: {selected_mode_radio}")

# --- Основная область: Чат ---
current_mode_name = st.session_state.get("selected_mode", DEFAULT_MODE)
current_model_id = MODES.get(current_mode_name, MODES[DEFAULT_MODE])

# --- Отображение истории чата ---
# Важно: Этот блок теперь отрисовывает ВСЮ историю, включая последнее сообщение ассистента ПОСЛЕ rerun
chat_container = st.container()
with chat_container:
    if active_chat_name in st.session_state.all_chats:
        for message in st.session_state.all_chats[active_chat_name]:
            avatar = "🧑‍💻" if message["role"] == "user" else "💡"
            with st.chat_message(message["role"], avatar=avatar):
                st.markdown(message["content"], unsafe_allow_html=True)
    else:
        st.warning(f"Активный чат '{active_chat_name}' не найден.")
        logging.warning(f"Попытка отобразить историю несуществующего чата: {active_chat_name}")

# --- Поле ввода пользователя ---
if prompt := st.chat_input(f"Спроси {current_mode_name}..."):
    if active_chat_name in st.session_state.all_chats:
        logging.info(f"Новый промпт в '{active_chat_name}'.")
        # Добавляем ТОЛЬКО сообщение пользователя перед rerun
        st.session_state.all_chats[active_chat_name].append({"role": "user", "content": prompt})
        save_all_chats(st.session_state.all_chats, st.session_state.active_chat, st.session_state.web_search_enabled)
        st.rerun() # Перезапуск для отображения промпта и запуска логики ответа
    else:
        st.error("Ошибка: Активный чат не найден.", icon="❌")
        logging.error(f"Ошибка добавления сообщения: чат '{active_chat_name}' не найден.")


# --- Логика ответа ИИ (с использованием st.write и БЕЗ rerun в конце) ---
if active_chat_name in st.session_state.all_chats:
    current_chat_state = st.session_state.all_chats[active_chat_name]

    # Запускаем генерацию, если история не пуста и ПОСЛЕДНЕЕ сообщение от ПОЛЬЗОВАТЕЛЯ
    # Это важно, чтобы не запускать генерацию после rerun, когда последнее сообщение уже от ассистента
    if current_chat_state and current_chat_state[-1]["role"] == "user":

        last_user_prompt = current_chat_state[-1]["content"]
        logging.info(f"\n--- Начало обработки ответа ИИ для '{active_chat_name}' ---")
        logging.info(f"Промпт: '{last_user_prompt[:100]}...' | Поиск: {'ВКЛ' if st.session_state.web_search_enabled else 'ВЫКЛ'}")

        current_date = datetime.datetime.now().strftime("%Y-%m-%d")
        # Создаем КОПИЮ истории БЕЗ последнего сообщения пользователя для передачи в API
        # context_for_ai = list(current_chat_state[:-1]) # Неправильно, нужно все для контекста
        context_for_ai = list(current_chat_state) # Передаем всю историю
        needs_search = st.session_state.web_search_enabled
        system_prompt = {"role": "system"}

        # --- Этапы поиска (если включен) ---
        # (Логика поиска и формирования system_prompt без изменений)
        if needs_search:
            logging.info(">>> Веб-поиск включен.")
            generated_queries = []; search_results_str = "Поиск не выполнялся."; search_performed_successfully = False
            try:
                with st.spinner("Подбираю поисковые вопросы... 🤔"): generated_queries = generate_search_queries(last_user_prompt, current_model_id)
            except Exception as e: logging.error(f"Ошибка вызова generate_search_queries: {e}", exc_info=True); st.error("Ошибка подбора вопросов.", icon="❓")
            queries_to_search = generated_queries if generated_queries else [last_user_prompt]
            if not generated_queries: logging.warning("Используется исходный промпт для поиска.")
            search_spinner_text = f"Ищу в сети ({len(queries_to_search)})... 🌐"
            try:
                with st.spinner(search_spinner_text): search_results_str = perform_web_search(queries_to_search)
                if search_results_str and not any(err in search_results_str for err in ["Ошибка", "не дал", "Нет запросов", "Не найдено"]): search_performed_successfully = True; logging.info("Веб-поиск успешен.")
                else: logging.warning(f"Веб-поиск неудачен/пуст: '{search_results_str}'")
            except Exception as e: logging.error(f"Ошибка вызова perform_web_search: {e}", exc_info=True); st.error("Ошибка веб-поиска.", icon="🕸️"); search_results_str = f"Ошибка: {e}"

            if search_performed_successfully:
                 system_prompt["content"] = f"""Текущая дата: {current_date}. Был выполнен веб-поиск. **Твоя задача:** Изучи результаты ниже и **синтезируй из них единый, связный ответ** на исходный запрос пользователя. Приоритет отдавай информации из поиска. Не упоминай сам факт поиска и не включай URL.\n\n--- Результаты веб-поиска ---\n{search_results_str}\n--- Конец результатов ---\n\nОтветь на запрос пользователя, основываясь на этой информации."""
                 logging.info("Системный промпт с результатами поиска.")
            else:
                 system_prompt["content"] = f"""Текущая дата: {current_date}. Веб-поиск был включен, но **не дал релевантных результатов** (Причина: '{search_results_str}'). Отвечай на запрос пользователя, **основываясь только на своих знаниях**. **Обязательно предупреди пользователя**, что ответ может быть неактуальным."""
                 logging.info("Системный промпт с уведомлением о неудачном поиске.")
            # Вставляем системный промпт ПЕРЕД последним сообщением пользователя в КОПИИ истории
            context_for_ai.insert(-1, system_prompt)
        else: # Поиск выключен
            logging.info(">>> Веб-поиск выключен.")
            system_prompt["content"] = f"Текущая дата: {current_date}. Веб-поиск ВЫКЛЮЧЕН. Отвечай на запрос пользователя, основываясь только на своих общих знаниях."
            context_for_ai.insert(-1, system_prompt)
            logging.info("Системный промпт без поиска.")


        # === БЛОК: Стриминг с st.write и сохранение ===
        final_response_to_save = None
        ai_response_error = False # Флаг ошибки

        logging.info("Запрос и стриминг ответа ИИ с помощью st.write...")
        try:
            # 1. Получаем сырой генератор
            response_generator = stream_ai_response(current_model_id, context_for_ai)

            # 2. Оборачиваем его
            response_wrapper = StreamWriteWrapper(response_generator)

            # 3. Отображаем с помощью st.write внутри st.chat_message
            # Это создаст новое сообщение ассистента и заполнит его по мере поступления данных
            with st.chat_message("assistant", avatar="💡"):
                st.write(response_wrapper) # Streamlit обработает стриминг

            # 4. Получаем ПОЛНЫЙ ответ ПОСЛЕ того, как st.write отработал
            final_response_to_save = response_wrapper.full_response
            ai_response_error = response_wrapper.error_occurred # Проверяем флаг ошибки из обертки

            # 5. Проверяем результат
            if ai_response_error:
                 # Ошибка уже была залогирована или выведена в st.write(wrapper)
                 logging.error("Ошибка во время стриминга через st.write.")
                 # Можно дополнительно вывести st.error, если нужно
                 # st.error("Произошла ошибка при генерации ответа.", icon="🔥")
                 final_response_to_save = None # Не сохраняем ошибочный ответ
            elif not final_response_to_save:
                 logging.warning("Ответ от ИИ пуст после стриминга st.write.")
                 # Не выводим warning здесь, т.к. пустое сообщение уже отобразилось
                 pass # Просто не сохраняем
            else:
                 logging.info("Ответ ИИ успешно отображен через st.write и собран.")

        except Exception as e:
             # Ловим ошибки на случай проблем с созданием обертки или самим st.write
             logging.error(f"Ошибка при обработке ответа ИИ с st.write: {e}", exc_info=True)
             st.error(f"Произошла ошибка при отображении ответа ИИ: {e}", icon="💥")
             final_response_to_save = None
             ai_response_error = True

        # === Сохранение ответа (БЕЗ RERUN) ===
        if final_response_to_save and not ai_response_error:
            logging.info("Сохранение ответа в историю...")
            try:
                if active_chat_name in st.session_state.all_chats:
                     current_history_for_save = st.session_state.all_chats[active_chat_name]
                     # Добавляем сообщение, которое ТОЛЬКО ЧТО было отображено через st.write
                     # Проверка на дубликат важна, т.к. reruna нет
                     if not current_history_for_save or current_history_for_save[-1].get("role") != "assistant" or current_history_for_save[-1].get("content") != final_response_to_save:
                          current_history_for_save.append({"role": "assistant", "content": final_response_to_save})
                          save_all_chats(st.session_state.all_chats, st.session_state.active_chat, st.session_state.web_search_enabled)
                          logging.info("Ответ ассистента добавлен в session_state и сохранен.")
                          # --- RERUN НЕ НУЖЕН ---
                     else:
                          logging.warning("Попытка добавить дублирующее сообщение ассистента. Сохранение пропущено.")
                else:
                     logging.error(f"Ошибка сохранения: чат '{active_chat_name}' не найден.")
                     st.error("Ошибка: не удалось сохранить ответ.", icon="❌")
            except Exception as e:
                 logging.error(f"Ошибка при сохранении ответа: {e}", exc_info=True)
                 st.error(f"Ошибка сохранения ответа: {e}", icon="💾")

        # Логирование завершения обработки этого запроса
        logging.info(f"--- Обработка ответа ИИ для '{active_chat_name}' завершена ---")
