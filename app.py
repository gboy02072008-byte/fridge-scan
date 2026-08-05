import streamlit as st

# --- 0. ตั้งค่า Page Config (ต้องอยู่บนสุดก่อนคำสั่ง st. อื่นๆ ทั้งหมด) ---
st.set_page_config(page_title="FridgeScan AI", page_icon="🍎", layout="centered")

import google.generativeai as genai
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
    st.sidebar.caption("⚡ พลังประมวลผล: **Google Gemini AI**")
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

    # TAB 2: สแกนวัตถุดิบด้วย Gemini AI
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
            
            if st.button("⚡ ให้ Gemini AI สแกนรูปภาพ", use_container_width=True):
                with st.status("🚀 Gemini AI กำลังวิเคราะห์วัตถุดิบ...", expanded=True) as status:
                    gemini_key = st.secrets.get("GEMINI_API_KEY")
                    if not gemini_key:
                        status.update(label="❌ ไม่พบ GEMINI_API_KEY ใน Secrets", state="error", expanded=True)
                        st.error("กรุณาเพิ่ม GEMINI_API_KEY ใน Streamlit Secrets ก่อนใช้งาน")
                    else:
                        try:
                            genai.configure(api_key=gemini_key)
                            
                            # เลือกใช้โมเดลหลักมาตรฐาน
                            model = genai.GenerativeModel("gemini-2.0-flash")
                            
                            prompt = (
                                "วิเคราะห์ภาพนี้ แล้วระบุชื่อวัตถุดิบ อาหาร หรือเครื่องดื่มหลักในภาพเป็นภาษาไทย "
                                "ระบุเฉพาะชื่อวัตถุดิบอย่างสั้น สรุปตรงประเด็นที่สุดเพียงชื่อเดียว เช่น นมสด, ไข่ไก่, สเต๊กเนื้อ, ผักกาดขาว, แอปเปิ้ล "
                                "ห้ามตอบเป็นประโยคยาว และไม่ต้องมีคำเกริ่นใดๆ"
                            )
                            
                            response = model.generate_content([prompt, image])
                            result_text = response.text.strip().replace('"', '').replace("'", "").replace('.', '')
                            
                            st.session_state.scanned_name = result_text
                            status.update(label=f"✅ สแกนสำเร็จ: {result_text}", state="complete", expanded=False)
                            
                        except Exception as e:
                            err_str = str(e)
                            status.update(label="⚠️ เกิดข้อผิดพลาดในการสแกน", state="error", expanded=True)
                            if "429" in err_str or "quota" in err_str.lower():
                                st.error("❌ โควตา API Key นี้เป็น 0 (Quota Exceeded) กรุณาสร้าง API Key ใหม่ใน Google AI Studio โดยเลือก 'Create API key in new project'")
                            else:
                                st.error(f"ข้อผิดพลาด: {e}")

        st.divider()
        st.markdown("### 📝 ตรวจทานและบันทึกลงตู้เย็น")
        
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
