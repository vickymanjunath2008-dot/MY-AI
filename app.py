import streamlit as st
from google import genai
from google.genai import types

# -------------------------------------------------------------
# 1. PAGE SETUP (ChatGPT OLED Dark Palette)
# -------------------------------------------------------------
st.set_page_config(
    page_title="MY AI",
    page_icon="🐺",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    .stApp {
        background-color: #1e1e1e;
        color: #ECECEC;
    }
    section[data-testid="stSidebar"] {
        background-color: #171717;
        border-right: 1px solid #2d2d2d;
    }
    .stTextArea textarea {
        background-color: #262626;
        color: #ECECEC;
        border-radius: 8px;
    }
    .badge {
        display: inline-block;
        padding: 4px 8px;
        border-radius: 4px;
        font-size: 12px;
        font-weight: bold;
        background-color: #2e382e;
        color: #4ade80;
        margin-bottom: 10px;
    }
</style>
""", unsafe_allow_html=True)

# -------------------------------------------------------------
# 2. SESSION STATE (Persistence)
# -------------------------------------------------------------
if "messages" not in st.session_state:
    st.session_state.messages = []
if "active_key_index" not in st.session_state:
    st.session_state.active_key_index = 0
if "active_model_name" not in st.session_state:
    st.session_state.active_model_name = "gemini-3.8-flash"

# -------------------------------------------------------------
# 3. SIDEBAR: RUN SETTINGS & STORY VAULT
# -------------------------------------------------------------
with st.sidebar:
    st.title("Run settings")

    # --- MODEL SELECTION ---
    model_options = [
        "⚡ Auto-Cascade (3.8 ➔ 3.7 ➔ 3.1 ➔ Next Key)",
        "gemini-3.8-flash",
        "gemini-3.7-flash",
        "gemini-3.1-flash",
        "gemini-2.0-flash",
        "gemini-2.0-flash-lite",
        "gemini-1.5-flash"
    ]
    selected_model_option = st.selectbox("Model", model_options, index=0)
    st.caption("Our most intelligent Flash model, engineered for deep continuity and long context.")

    # --- SYSTEM INSTRUCTIONS ---
    st.write("**System instructions**")
    system_instruction = st.text_area(
        label="System instructions",
        label_visibility="collapsed",
        placeholder="Optional tone and style instructions (e.g. Gritty Fabletown noir, grounded physical weight)...",
        height=120,
        value="You are MY AI: a grounded, gritty storyteller. All fantasy elements must follow strict physical reality, exhaustion, weight, and realistic consequences. Maintain absolute continuity."
    )

    # --- STORY BIBLE VAULT (DIRECT PASTE + FILE UPLOAD) ---
    with st.expander("📖 Story Bible & Lore Vault (Paste Here)", expanded=True):
        st.caption("Paste your characters, world rules, Jersey Devil physiology, or past story arcs:")
        pasted_bible = st.text_area(
            label="Story Bible Input",
            label_visibility="collapsed",
            placeholder="Paste your story notes, character bios, or ongoing manuscript here...",
            height=180
        )
        uploaded_files = st.file_uploader("Or upload .txt / .md story files:", accept_multiple_files=True)
        
        file_vault_text = ""
        if uploaded_files:
            for uf in uploaded_files:
                file_vault_text += f"\n--- {uf.name} ---\n" + uf.read().decode("utf-8")
            st.success(f"Loaded {len(uploaded_files)} files into memory!")

    # Combined vault lore
    total_vault_lore = (pasted_bible + "\n" + file_vault_text).strip()

    st.divider()

    # --- SAFETY SETTINGS (Matched to Screenshot) ---
    with st.expander("🛡️ Run safety settings", expanded=False):
        st.caption("Adjust probability thresholds for content filtering.")
        safety_levels = ["Block none", "Block few", "Block some", "Block most"]
        harass_val = st.select_slider("Harassment", options=safety_levels, value="Block none")
        hate_val = st.select_slider("Hate", options=safety_levels, value="Block none")
        sex_val = st.select_slider("Sexually Explicit", options=safety_levels, value="Block none")
        danger_val = st.select_slider("Dangerous Content", options=safety_levels, value="Block none")

    st.divider()

    # --- 5-KEY POOL ENGINE ---
    with st.expander("🔑 API Key Pool (5 Projects)", expanded=False):
        key1 = st.text_input("Key 1 (Primary)", type="password")
        key2 = st.text_input("Key 2 (Backup)", type="password")
        key3 = st.text_input("Key 3 (Backup)", type="password")
        key4 = st.text_input("Key 4 (Backup)", type="password")
        key5 = st.text_input("Key 5 (Backup)", type="password")
        
        api_pool = [k for k in [key1, key2, key3, key4, key5] if k.strip()]
        
        key_modes = ["🔄 Auto-Failover (Smart)"] + [f"📌 Force Key {i+1}" for i in range(len(api_pool))]
        selected_key_mode = st.selectbox("Key Mode", key_modes if api_pool else ["No Keys Added"])

    # --- MILESTONE GAUGE (55 / 60 Turns) ---
    turn_count = len(st.session_state.messages)
    st.divider()
    st.write(f"**Memory Gauge:** {turn_count} / 60 messages")
    st.progress(min(turn_count / 60.0, 1.0))
    
    if turn_count >= 55:
        st.warning("⚠️ 55-Turn Milestone Reached! Compile Chapter Manuscript to lock memory.")
        if st.button("📖 Compile Chapter Manuscript"):
            st.info("Compiling deep manuscript...")

# -------------------------------------------------------------
# 4. CHAT DISPLAY & STATUS BADGE
# -------------------------------------------------------------
st.markdown(
    f'<div class="badge">🟢 Live: {st.session_state.active_model_name} | Active Key: #{st.session_state.active_key_index + 1}</div>', 
    unsafe_allow_html=True
)

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# -------------------------------------------------------------
# 5. EXECUTION & AUTO-CASCADE ENGINE
# -------------------------------------------------------------
if not api_pool:
    st.info("👈 Open the sidebar (tap > top left) and paste your API keys to begin!", icon="🔑")
    st.stop()

if prompt := st.chat_input("Message MY AI..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Safety mappings
    threshold_map = {
        "Block none": types.HarmBlockThreshold.BLOCK_NONE,
        "Block few": types.HarmBlockThreshold.BLOCK_ONLY_HIGH,
        "Block some": types.HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
        "Block most": types.HarmBlockThreshold.BLOCK_LOW_AND_ABOVE
    }
    
    safety_settings = [
        types.SafetySetting(category=types.HarmCategory.HARM_CATEGORY_HARASSMENT, threshold=threshold_map[harass_val]),
        types.SafetySetting(category=types.HarmCategory.HARM_CATEGORY_HATE_SPEECH, threshold=threshold_map[hate_val]),
        types.SafetySetting(category=types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT, threshold=threshold_map[sex_val]),
        types.SafetySetting(category=types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT, threshold=threshold_map[danger_val]),
    ]

    # Models list
    if "Auto-Cascade" in selected_model_option:
        models_to_try = ["gemini-3.8-flash", "gemini-3.7-flash", "gemini-3.1-flash", "gemini-2.0-flash", "gemini-1.5-flash"]
    else:
        models_to_try = [selected_model_option]

    # Key Sequence
    if "Force Key" in selected_key_mode:
        target_idx = int(selected_key_mode.split("Key ")[1]) - 1
        keys_to_try = [api_pool[target_idx]]
    else:
        keys_to_try = api_pool[st.session_state.active_key_index:] + api_pool[:st.session_state.active_key_index]

    # --- 60-MESSAGE VERBATIM + STORY BIBLE PAYLOAD ---
    ACTIVE_WINDOW = 60
    recent_turns = st.session_state.messages[-ACTIVE_WINDOW:]
    
    full_payload = []
    # Inject up to 3,000 tokens of your pasted Story Bible
    if total_vault_lore:
        full_payload.append(f"[STORY BIBLE & CORE LORE]:\n{total_vault_lore[:12000]}")
    
    for turn in recent_turns:
        full_payload.append(f"{turn['role'].capitalize()}: {turn['content']}")

    success = False
    response_text = ""

    with st.chat_message("assistant"):
        with st.spinner("Writing..."):
            for current_key in keys_to_try:
                if success:
                    break
                client = genai.Client(api_key=current_key)
                
                for model_candidate in models_to_try:
                    try:
                        config = types.GenerateContentConfig(
                            safety_settings=safety_settings,
                            system_instruction=system_instruction
                        )
                        resp = client.models.generate_content(
                            model=model_candidate,
                            contents=full_payload,
                            config=config
                        )
                        response_text = resp.text
                        st.session_state.active_model_name = model_candidate
                        st.session_state.active_key_index = api_pool.index(current_key)
                        success = True
                        break
                    except Exception as e:
                        if any(err in str(e) for err in ["429", "RESOURCE_EXHAUSTED", "404", "NOT_FOUND"]):
                            continue
                        else:
                            continue

            if success and response_text:
                st.markdown(response_text)
                st.session_state.messages.append({"role": "assistant", "content": response_text})
            else:
                st.error("All cascaded models across your keys have hit limits or are unavailable.")
