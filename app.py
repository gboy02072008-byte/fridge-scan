import streamlit as st

# --- 0. ตั้งค่า Page Config (ต้องอยู่บนสุด) ---
st.set_page_config(page_title="FridgeScan AI", page_icon="🍎", layout="centered")

import requests
import base64
import io
from PIL import Image
from supabase import create_client, Client
import datetime
import time

# --- 1. ตั้งค่า DB Connection ---
@st.cache_resource
def init_supabase() -> Client:
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

supabase = init_supabase()

# จัดเก็บ Session State
if "user" not in st.session_state:
    st.session_state.user = None
if "scanned_name" not in st.session_state:
    st.session_state.scanned_name = ""

# --- Helper Functions ---
def compress_and_encode_image(image, max_size=(800, 800)):
    img = image.copy()
    if img.mode in ("RGBA", "P"):
        img = img.convert("RGB")
    img.thumbnail(max_size)
    buffered = io.BytesIO()
    img.save(buffered, format="JPEG", quality=85)
    return base64.b64encode(buffered.getvalue()).decode("utf-8")

def analyze_image_with_github(api_key, image):
    """ใช้ GitHub Models (GPT-4o-mini) สแกนภาพฟรี พร้อมระบบตรวจสอบ Token"""
    base64_image = compress_and_encode_image(image)
    
    # ทำความสะอาดรหัส Token ป้องกันเครื่องหมายคำพูดหรือเว้นวรรคส่วนเกิน
    clean_key = api_key.strip().strip('"').strip("'")
    
    # ตรวจสอบรูปแบบคีย์เบื้องต้น
    if not clean_key.startswith("ghp_"):
        return False, f"[Token Error] GITHUB_TOKEN ใน Secrets ต้องขึ้นต้นด้วย 'ghp_' เท่านั้น (ปัจจุบัน: {clean_key[:8]}...)"

    url = "https://models.inference.ai.azure.com/chat/completions"
    headers = {
        "Authorization": f"Bearer {clean_key}",
        "Content-Type": "application/json"
    }
    
    prompt = (
        "วิเคราะห์ภาพนี้ แล้วระบุชื่อวัตถุดิบ อาหาร หรือเครื่องดื่มหลักในภาพเป็นภาษาไทย "
        "ระบุเฉพาะชื่อวัตถุดิบอย่างสั้น สรุปตรงประเด็นที่สุดเพียงชื่อเดียว เช่น นมสด, ไข่ไก่, สเต๊กเนื้อ, ผักกาดขาว, แอปเปิ้ล "
        "ห้ามตอบเป็นประโยคยาว และไม่ต้องมีคำเกริ่นใดๆ"
    )
    
    payload = {
        "model": "gpt-4o-mini",
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{base64_image}"
                        }
                    }
                ]
            }
        ]
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=15)
        
        if response.status_code == 200:
            res_data = response.json()
            if "choices" in res_data and len(res_data["choices"]) > 0:
                text = res_data["choices"][0]["message"]["content"]
                return True, text.strip().replace('"', '').replace("'", "").replace('.', '')
        
        # หากเกิดข้อผิดพลาด ให้ดึงข้อความตอบกลับจาก GitHub ออกมาแสดง
        return False, f"[HTTP {response.status_code}] {response.text[:200]}"
            
    except Exception as e:
        return False, f"เกิดข้อผิดพลาดในการเชื่อมต่อ: {e}"
# --- 2. ฟังก์ชันระบบสมาชิก (Auth) ---
def login(email, password):
    try:
        res = supabase.auth.sign_in_with_password({"email": email, "password": password})
        st.session_state.user = res.user
        st.toast("เข้าสู่ระบบสำเร็จ!", icon="🎉")
        st.rerun()
    except Exception as e:
        st.error(f"เข้าสู่ระบบไม่สำเร็จ: {e}")

def register(email, password):
    try:
        res = supabase.auth.sign_up({"email": email, "password": password})
        st.success("สมัครสมาชิกสำเร็จ! กรุณากดเข้าสู่ระบบ")
    except Exception as e:
        st.error(f"สมัครสมาชิกไม่สำเร็จ: {e}")

def logout():
    supabase.auth.sign_out()
    st.session_state.user = None
    st.session_state.scanned_name = ""
    st.rerun()

# --- 3. ฟังก์ชันจัดการตู้เย็น (Database) ---
def get_fridge_items(user_id):
    res = supabase.table("fridge_items").select("*").eq("user_id", user_id).order("expiry_date", desc=False).execute()
    return res.data

def add_item_to_fridge(name, category, quantity, expiry_date, user_id):
    data = {
        "name": name,
        "category": category,
        "quantity": quantity,
        "expiry_date": str(expiry_date),
        "user_id": user_id
    }
    supabase.table("fridge_items").insert(data).execute()

def delete_item(item_id):
    supabase.table("fridge_items").delete().eq("id", item_id).execute()

# --- 4. หน้าตาแอปพลิเคชัน (UI Flow) ---
st.title("🍎 แอปตู้เย็น FridgeScan")

# ถ้ายังไม่ได้ล็อกอิน -> แสดงหน้า Login / Register
if st.session_state.user is None:
    auth_tab1, auth_tab2 = st.tabs(["🔑 เข้าสู่ระบบ", "📝 สมัครสมาชิก"])
    
    with auth_tab1:
        email = st.text_input("อีเมล", key="login_email")
        password = st.text_input("รหัสผ่าน", type="password", key="login_pass")
        if st.button("เข้าสู่ระบบ", use_container_width=True):
            if email and password:
                login(email, password)
            else:
                st.warning("กรุณากรอกอีเมลและรหัสผ่าน")
                
    with auth_tab2:
        reg_email = st.text_input("อีเมล", key="reg_email")
        reg_password = st.text_input("รหัสผ่าน (อย่างน้อย 6 ตัว)", type="password", key="reg_pass")
        if st.button("สมัครสมาชิก", use_container_width=True):
            if reg_email and reg_password:
                register(reg_email, reg_password)
            else:
                st.warning("กรุณากรอกข้อมูลให้ครบถ้วน")

# ถ้าล็อกอินแล้ว -> แสดงหน้าแอปตู้เย็นหลัก
else:
    user_id = st.session_state.user.id
    user_email = st.session_state.user.email
    
    st.sidebar.write(f"👤 ผู้ใช้งาน: **{user_email}**")
    st.sidebar.caption("⚡ พลังประมวลผล: **Google Gemini Vision API**")
    if st.sidebar.button("ออกจากระบบ"):
        logout()

    tab1, tab2 = st.tabs(["📦 ตู้เย็นของฉัน", "➕ เพิ่มของเข้าตู้เย็น"])

    # TAB 1: รายการอาหารในตู้เย็น
    with tab1:
        st.subheader("รายการของในตู้เย็น")
        items = get_fridge_items(user_id)
        
        if not items:
            st.info("ตู้เย็นว่างเปล่า ลองไปที่แถบ '➕ เพิ่มของเข้าตู้เย็น' ดูครับ")
        else:
            for item in items:
                with st.container():
                    col1, col2, col3 = st.columns([3, 2, 1.5])
                    with col1:
                        st.markdown(f"**{item['name']}**")
                        st.caption(f"หมวดหมู่: {item['category']}")
                    with col2:
                        st.markdown(f"⏳ `{item['expiry_date']}`")
                    with col3:
                        if st.button("ทานแล้ว", key=f"del_{item['id']}"):
                            delete_item(item['id'])
                            st.toast(f"ลบ {item['name']} แล้ว", icon="🗑️")
                            st.rerun()
                    st.divider()

    # TAB 2: สแกนวัตถุดิบด้วย AI
    with tab2:
        st.subheader("สแกนวัตถุดิบด้วย Gemini AI")
        
        # ทางลัดเลือกวัตถุดิบบ่อย
        st.caption("⚡ ทางลัดด่วน (ไม่ต้องสแกน):")
        shortcut_cols = st.columns(4)
        if shortcut_cols[0].button("🥛 นมสด", use_container_width=True):
            st.session_state.scanned_name = "นมสด"
        if shortcut_cols[1].button("🥚 ไข่ไก่", use_container_width=True):
            st.session_state.scanned_name = "ไข่ไก่"
        if shortcut_cols[2].button("🍞 ขนมปัง", use_container_width=True):
            st.session_state.scanned_name = "ขนมปัง"
        if shortcut_cols[3].button("🐷 หมูสับ", use_container_width=True):
            st.session_state.scanned_name = "หมูสับ"

        st.markdown("---")
        
        img_file = st.camera_input("ถ่ายรูปวัตถุดิบ") or st.file_uploader("หรือเลือกรูปภาพ", type=["jpg", "png", "jpeg"])
        
        if img_file:
            image = Image.open(img_file)
            st.image(image, caption="รูปถ่ายวัตถุดิบ", width=300)
            
            if st.button("⚡ ให้ AI สแกนรูปภาพ", use_container_width=True):
                with st.status("🚀 Gemini AI กำลังวิเคราะห์วัตถุดิบ...", expanded=True) as status:
                    gemini_key = st.secrets.get("GEMINI_API_KEY")
                    
                    if not gemini_key:
                        status.update(label="❌ ไม่พบ GEMINI_API_KEY ใน Secrets", state="error", expanded=True)
                        st.error("กรุณาเพิ่ม GEMINI_API_KEY ใน Streamlit Secrets ก่อนใช้งาน")
                    else:
                        success, result = analyze_image_with_github(st.secrets["GITHUB_TOKEN"], image)
                        if success:
                            st.session_state.scanned_name = result
                            status.update(label=f"✅ สแกนสำเร็จ: {result}", state="complete", expanded=False)
                        else:
                            status.update(label="⚠️ เกิดข้อผิดพลาดในการสแกน", state="error", expanded=True)
                            st.error(f"รายละเอียดข้อผิดพลาด: {result}")

        st.divider()
        st.markdown("### 📝 ตรวจทานและบันทึกลลงตู้เย็น")
        
        with st.form("add_fridge_form", clear_on_submit=True):
            item_name = st.text_input("ชื่อวัตถุดิบ / อาหาร", value=st.session_state.scanned_name, placeholder="เช่น นมสด, ไข่ไก่")
            category = st.selectbox("หมวดหมู่", ["อาหารสด/วัตถุดิบ", "เครื่องดื่ม", "ขนม/ของหวาน", "เครื่องปรุง", "อื่นๆ"])
            expiry_date = st.date_input("วันหมดอายุ (โดยประมาณ)", value=datetime.date.today() + datetime.timedelta(days=7))
            
            submit_btn = st.form_submit_button("💾 บันทึกลงตู้เย็น", use_container_width=True)
            
            if submit_btn:
                if item_name.strip():
                    add_item_to_fridge(
                        name=item_name.strip(),
                        category=category,
                        quantity=1,
                        expiry_date=expiry_date,
                        user_id=user_id
                    )
                    st.session_state.scanned_name = ""
                    st.toast(f"บันทึก '{item_name}' เรียบร้อย!", icon="✅")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.warning("กรุณาระบุชื่อวัตถุดิบก่อนบันทึก")
