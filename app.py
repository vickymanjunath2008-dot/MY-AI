import streamlit as st
import time
import json
import uuid
from google import genai
from google.genai import types
from supabase import create_client, Client

# -------------------------------------------------------------
# 1. PAGE SETUP (Pure Void OLED #000000)
# -------------------------------------------------------------
st.set_page_config(
    page_title="ChatGPT",
    page_icon="💬",
    layout="wide",
    initial_sidebar_state="collapsed"
)

st.markdown("""
<style>
    /* Pure Black Void Theme */
    .stApp, [data-testid="stAppViewContainer"], [data-testid="stHeader"] {
        background-color: #000000 !important;
        color: #ECECEC !important;
    }
    
    /* Clean Sidebar */
    section[data-testid="stSidebar"] {
        background-color: #0d0d0d !important;
        border-right: 1px solid #1a1a1a !important;
    }

    /* Seamless Borderless Messages (1:1 ChatGPT) */
    div[data-testid="stChatMessage"] {
        background-color: transparent !important;
        border: none !important;
        padding: 12px 4px !important;
    }
    
    /* Subtle Thinking Box */
    .thinking-box {
        background: rgba(255, 255, 255, 0.04);
        border-left: 2px solid #555;
        padding: 8px 12px;
        margin-bottom: 12px;
        border-radius: 4px;
        font-size: 13px;
        color: #8e8e93;
        font-style: italic;
    }

    /* Rounded ChatGPT Settings Cards */
    .settings-card {
        background-color: #171717;
        border-radius: 12px;
        padding: 14px;
        margin-bottom: 10px;
        border: 1px solid #262626;
    }
    
    /* Utility Icons Bar under AI message */
    .msg-tools {
        display: flex;
        gap: 12px;
        margin-top: 6px;
        color: #666;
        font-size: 14px;
    }

    /* Streamlit UI cleanups */
    #MainMenu, footer {visibility: hidden;}
    .stDeployButton {display:none;}
</style>
""", unsafe_allow_html=True)

# -------------------------------------------------------------
# 2. STATE & SUPABASE CLIENT INITIALIZATION
# -------------------------------------------------------------
if "supabase_url" not in st.session_state:
    st.session_state.supabase_url = ""
if "supabase_key" not in st.session_state:
    st.session_state.supabase_key = ""
if "current_chat_id" not in st.session_state:
    st.session_state.current_chat_id = str(uuid.uuid4())
if "chats_list" not in st.session_state:
    st.session_state.chats_list = []
if "messages" not in st.session_state:
    st.session_state.messages = []
if "available_models" not in st.session_state:
    st.session_state.available_models = []
if "active_key_index" not in st.session_state:
    st.session_state.active_key_index = 0

def get_supabase() -> Client:
    if st.session_state.supabase_url and st.session_state.supabase_key:
        try:
            return create_client(st.session_state.supabase_url, st.session_state.supabase_key)
        except Exception:
            return None
    return None

def load_chats():
    sb = get_supabase()
    if sb:
        try:
            res = sb.table("chats").select("id, title, created_at").order("created_at", desc=True).execute()
            st.session_state.chats_list = res.data or []
        except Exception:
            pass

def save_current_chat(title_hint=None):
    sb = get_supabase()
    if sb and st.session_state.messages:
        try:
            title = title_hint
            if not title:
                # Use first user message as title preview
                title = st.session_state.messages[0]["content"][:28] + "..."
            data = {
                "id": st.session_state.current_chat_id,
                "title": title,
                "messages": st.session_state.messages,
                "custom_instructions": st.session_state.get("custom_instructions", "")
            }
            sb.table("chats").upsert(data).execute()
            load_chats()
        except Exception:
            pass

# -------------------------------------------------------------
# 3. SIDEBAR (1:1 ChatGPT Recents & Drawer Navigation)
# -------------------------------------------------------------
with st.sidebar:
    st.markdown("<h3 style='color:white; margin-top:0;'>ChatGPT</h3>", unsafe_allow_html=True)
    
    # + New Chat Action
    if st.button("✏️ New Chat", use_container_width=True):
        st.session_state.current_chat_id = str(uuid.uuid4())
        st.session_state.messages = []
        st.rerun()

    st.markdown("<p style='font-size:12px; color:#666; margin-top:15px; text-transform:uppercase; font-weight:bold;'>Recents</p>", unsafe_allow_html=True)
    
    # Render Saved Chats from Supabase
    if st.session_state.chats_list:
        for c in st.session_state.chats_list:
            btn_label = c.get("title", "Untitled Chat")
            if st.button(f"💬 {btn_label}", key=f"chat_{c['id']}", use_container_width=True):
                # Switch chat
                sb = get_supabase()
                res = sb.table("chats").select("*").eq("id", c["id"]).execute()
                if res.data:
                    st.session_state.current_chat_id = c["id"]
                    st.session_state.messages = res.data[0].get("messages", [])
                    st.rerun()
    else:
        st.caption("No recent chats found.")

    st.divider()

    # --- SETTINGS DRAWER (Card Layout) ---
    with st.expander("⚙️ Settings & Personalization", expanded=False):
        st.markdown("**Supabase Cloud Sync**")
        st.session_state.supabase_url = st.text_input("Supabase Project URL", value=st.session_state.supabase_url, type="password", placeholder="https://xxx.supabase.co")
        st.session_state.supabase_key = st.text_input("Supabase Anon Key", value=st.session_state.supabase_key, type="password", placeholder="eyJhbGci...")
        if st.button("Connect & Sync"):
            load_chats()
            st.success("Synced!")

        st.markdown("**API Key Pool (5 Projects)**")
        key1 = st.text_input("Key 1 (Primary)", type="password")
        key2 = st.text_input("Key 2 (Backup)", type="password")
        key3 = st.text_input("Key 3 (Backup)", type="password")
        key4 = st.text_input("Key 4 (Backup)", type="password")
        key5 = st.text_input("Key 5 (Backup)", type="password")
        api_pool = [k for k in [key1, key2, key3, key4, key5] if k.strip()]

        # Live model probing directly from Google
        if api_pool and not st.session_state.available_models:
            try:
                probe = genai.Client(api_key=api_pool[0])
                fetched = [m.name.replace("models/", "") for m in probe.models.list() if "gemini" in m.name]
                if fetched:
                    st.session_state.available_models = sorted(fetched)
            except Exception:
                pass

        dropdown_models = st.session_state.available_models or ["gemini-2.0-flash", "gemini-1.5-flash"]
        selected_model = st.selectbox("Model", dropdown_models, index=0)

        st.markdown("**Custom Instructions**")
        st.session_state.custom_instructions = st.text_area(
            "What would you like the AI to know?",
            value=st.session_state.get("custom_instructions", "You are a helpful, coherent assistant. Maintain strict continuity."),
            height=100
        )

        st.markdown("**Safety Filters**")
        safety_opt = st.select_slider("Content Filtering", options=["Block none", "Block few", "Block some", "Block most"], value="Block none")

# -------------------------------------------------------------
# 4. CHAT AREA & OPTIONS MENU (Top Right)
# -------------------------------------------------------------
top_col1, top_col2 = st.columns([8, 2])
with top_col1:
    st.markdown(f"<span style='color:#555; font-size:12px;'>Model: {selected_model}</span>", unsafe_allow_html=True)
with top_col2:
    with st.popover("⋮"):
        if st.button("🗑️ Delete Chat"):
            sb = get_supabase()
            if sb:
                sb.table("chats").delete().eq("id", st.session_state.current_chat_id).execute()
                load_chats()
            st.session_state.messages = []
            st.session_state.current_chat_id = str(uuid.uuid4())
            st.rerun()
        if st.button("📤 Export (.txt)"):
            full_txt = "\n\n".join([f"{m['role'].upper()}:\n{m['content']}" for m in st.session_state.messages])
            st.download_button("Download File", data=full_txt, file_name="conversation.txt")

# Display Messages Word-by-Word Smoothly
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg["role"] == "assistant":
            st.markdown('<div class="msg-tools">📋 Copy | 🔄 Regenerate</div>', unsafe_allow_html=True)

# -------------------------------------------------------------
# 5. INPUT BAR & REAL-TIME STREAMING
# -------------------------------------------------------------
if not api_pool:
    st.info("👈 Open the sidebar (tap >) and enter your Gemini API Key & Supabase credentials under Settings to start.", icon="🔑")
    st.stop()

if prompt := st.chat_input("Reply to ChatGPT..."):
    # Append User Message
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Convert Safety
    safety_map = {
        "Block none": types.HarmBlockThreshold.BLOCK_NONE,
        "Block few": types.HarmBlockThreshold.BLOCK_ONLY_HIGH,
        "Block some": types.HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
        "Block most": types.HarmBlockThreshold.BLOCK_LOW_AND_ABOVE
    }
    safety_settings = [
        types.SafetySetting(category=types.HarmCategory.HARM_CATEGORY_HARASSMENT, threshold=safety_map[safety_opt]),
        types.SafetySetting(category=types.HarmCategory.HARM_CATEGORY_HATE_SPEECH, threshold=safety_map[safety_opt]),
        types.SafetySetting(category=types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT, threshold=safety_map[safety_opt]),
        types.SafetySetting(category=types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT, threshold=safety_map[safety_opt]),
    ]

    # Assemble 60-turn payload
    recent_history = [f"{m['role'].capitalize()}: {m['content']}" for m in st.session_state.messages[-60:]]

    # Active Execution
    with st.chat_message("assistant"):
        # Translucent Thinking Simulation
        thinking_placeholder = st.empty()
        thinking_placeholder.markdown('<div class="thinking-box">💭 Thinking: Analyzing context and formatting response...</div>', unsafe_allow_html=True)
        
        response_stream_text = ""
        success = False
        last_error = ""

        # Failover Pool Loop
        keys_to_try = api_pool[st.session_state.active_key_index:] + api_pool[:st.session_state.active_key_index]
        for current_key in keys_to_try:
            try:
                client = genai.Client(api_key=current_key)
                config = types.GenerateContentConfig(
                    safety_settings=safety_settings,
                    system_instruction=st.session_state.get("custom_instructions", "")
                )
                
                # Streaming Response Generator
                response = client.models.generate_content_stream(
                    model=selected_model,
                    contents=recent_history,
                    config=config
                )
                
                thinking_placeholder.empty() # Clear thinking box once words start flowing
                
                # Real-time typing stream directly onto the OLED black screen
                stream_placeholder = st.empty()
                for chunk in response:
                    if chunk.text:
                        response_stream_text += chunk.text
                        stream_placeholder.markdown(response_stream_text)
                
                st.session_state.active_key_index = api_pool.index(current_key)
                success = True
                break
            except Exception as e:
                last_error = str(e)
                if any(err in last_error for err in ["429", "RESOURCE_EXHAUSTED", "503", "UNAVAILABLE"]):
                    continue
                else:
                    break

        if success:
            st.session_state.messages.append({"role": "assistant", "content": response_stream_text})
            save_current_chat()
            st.markdown('<div class="msg-tools">📋 Copy | 🔄 Regenerate</div>', unsafe_allow_html=True)
        else:
            thinking_placeholder.empty()
            st.error(f"Error: {last_error}")
