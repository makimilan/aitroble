import streamlit as st
import requests
from duckduckgo_search import ddg

# Применяем кастомный CSS для улучшенного внешнего вида
st.markdown("""
    <style>
    body {
        background-color: #f0f2f6;
        font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
    }
    .chat-container {
        padding: 20px;
        background-color: #ffffff;
        border-radius: 10px;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        margin-bottom: 20px;
    }
    .user-message {
        background-color: #DCF8C6;
        padding: 10px;
        border-radius: 10px;
        margin-bottom: 10px;
        text-align: right;
    }
    .ai-message {
        background-color: #E6E6FA;
        padding: 10px;
        border-radius: 10px;
        margin-bottom: 10px;
        text-align: left;
    }
    </style>
""", unsafe_allow_html=True)

# Заголовок и вводная информация
st.title("Образовательный AI помощник")
st.markdown("Добро пожаловать! Этот чат-помощник поможет вам разобраться в школьных темах с подробными и доступными объяснениями.")

# Настройки в боковой панели
st.sidebar.header("Настройки модели")
model_choice = st.sidebar.selectbox("Выберите модель", 
                                    ["deepseek-chat-v3-0324:free", "deepseek-r1:free"])
enable_web_search = st.sidebar.checkbox("Включить автоматический веб поиск", value=False)

# Параметры API
API_KEY = "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"
API_URL = "https://api.openrouter.ai/v1/chat/completions"  # Предположительный URL

# Инициализация истории диалога в session_state
if 'conversation' not in st.session_state:
    st.session_state.conversation = []

def web_search(query):
    """
    Выполняет веб поиск через DuckDuckGo и возвращает отформатированные результаты.
    """
    try:
        results = ddg(query, max_results=3)
        return results
    except Exception as e:
        st.error(f"Ошибка веб поиска: {e}")
        return None

def call_ai_model(model, conversation):
    """
    Отправляет историю сообщений на API провайдера OpenRouter и возвращает ответ AI.
    Предполагается, что API возвращает JSON с полями 'response' (ответ модели) 
    и 'thinking' (описание процесса мышления модели).
    """
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}"
    }
    payload = {
        "model": model,
        "messages": conversation,
        "temperature": 0.7
        # Дополнительные параметры можно добавить по необходимости
    }
    try:
        response = requests.post(API_URL, headers=headers, json=payload)
        if response.status_code == 200:
            data = response.json()
            ai_response = data.get("response", "Нет ответа от модели.")
            thinking_process = data.get("thinking", "")
            return ai_response, thinking_process
        else:
            return f"Ошибка API: {response.status_code}", ""
    except Exception as e:
        return f"Ошибка запроса: {e}", ""

# Отображение истории чата
with st.container():
    st.markdown('<div class="chat-container">', unsafe_allow_html=True)
    for entry in st.session_state.conversation:
        if entry["role"] == "user":
            st.markdown(f'<div class="user-message"><b>Вы:</b> {entry["content"]}</div>', unsafe_allow_html=True)
        elif entry["role"] == "ai":
            st.markdown(f'<div class="ai-message"><b>AI:</b> {entry["content"]}</div>', unsafe_allow_html=True)
        elif entry["role"] == "system":
            # Системные сообщения (например, результаты веб поиска)
            st.markdown(f'<div class="ai-message"><i>{entry["content"]}</i></div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

# Форма для ввода нового сообщения
with st.form(key="chat_form", clear_on_submit=True):
    user_input = st.text_area("Ваше сообщение", height=100)
    submit_button = st.form_submit_button(label="Отправить")

if submit_button and user_input:
    # Добавляем сообщение пользователя в историю диалога
    st.session_state.conversation.append({"role": "user", "content": user_input})
    
    # Если включен веб поиск, выполняем его и добавляем результаты в историю как системное сообщение
    if enable_web_search:
        st.info("Выполняется веб поиск...")
        search_results = web_search(user_input)
        if search_results:
            search_context = "\n".join([f"{item.get('title', 'Без заголовка')}: {item.get('href', '')}" 
                                        for item in search_results])
            st.session_state.conversation.append({"role": "system", 
                                                  "content": f"Результаты веб поиска:\n{search_context}"})
    
    # Вызов AI модели
    with st.spinner("AI обрабатывает запрос..."):
        ai_reply, thinking = call_ai_model(model_choice, st.session_state.conversation)
    
    # Добавляем ответ AI в историю
    st.session_state.conversation.append({"role": "ai", "content": ai_reply})
    
    # Перезагружаем страницу для обновления отображения истории
    st.experimental_rerun()

# Отображение процесса мышления AI, если такая информация возвращается API
if "thinking" in locals() and thinking:
    st.markdown("### Процесс мышления AI")
    st.markdown(thinking)
