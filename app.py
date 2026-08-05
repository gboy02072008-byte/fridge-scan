import streamlit as st
import google.generativeai as genai
from PIL import Image
from supabase import create_client, Client
import datetime

# --- 1. ตั้งค่า API Key & DB Connection ---
genai.configure(api_key=st.secrets["GEMINI_API_KEY"])

@st.cache_resource
def init_supabase() -> Client:
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

supabase = init_supabase()

# จัดเก็บ Session การล็อกอิน
if "user" not in st.session_state:
    st.session_state.user = None

# --- 2. ฟังก์ชันระบบสมาชิก (Auth) ---
def login(email, password):
    try:
        res = supabase.auth.sign_in_with_password({"email": email, "password": password})
        st.session_state.user = res.user
        st.success("เข้าสู่ระบบสำเร็จ!")
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
    st.rerun()

# --- 3. ฟังก์ชันจัดการตู้เย็น (กรองตาม user_id) ---
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
        if st.button("เข้าสู่ระบบ"):
            if email and password:
                login(email, password)
            else:
                st.warning("กรุณากรอกอีเมลและรหัสผ่าน")
                
    with auth_tab2:
        reg_email = st.text_input("อีเมล", key="reg_email")
        reg_password = st.text_input("รหัสผ่าน (อย่างน้อย 6 ตัว)", type="password", key="reg_pass")
        if st.button("สมัครสมาชิก"):
            if reg_email and reg_password:
                register(reg_email, reg_password)
            else:
                st.warning("กรุณากรอกข้อมูลให้ครบถ้วน")

# ถ้าล็อกอินแล้ว -> แสดงหน้าแอปตู้เย็นหลัก
else:
    user_id = st.session_state.user.id
    user_email = st.session_state.user.email
    
    # แสดงแถบผู้ใช้งานด้านข้าง (Sidebar)
    st.sidebar.write(f"👤 ผู้ใช้งาน: **{user_email}**")
    if st.sidebar.button("ออกจากระบบ"):
        logout()

    tab1, tab2 = st.tabs(["📦 ตู้เย็นของฉัน", "📷 สแกนเพิ่มของ"])

    # TAB 1: รายการอาหารเฉพาะของ user คนนี้
    with tab1:
        st.subheader("รายการของในตู้เย็น")
        items = get_fridge_items(user_id)
        
        if not items:
            st.info("ตู้เย็นว่างเปล่า ลองไปที่แถบ '📷 สแกนเพิ่มของ' ดูครับ")
        else:
            for item in items:
                col1, col2, col3 = st.columns([3, 2, 1])
                with col1:
                    st.write(f"**{item['name']}** ({item['category']})")
                with col2:
                    st.write(f"⏳ หมดอายุ: {item['expiry_date']}")
                with col3:
                    if st.button("ทานหมดแล้ว", key=f"del_{item['id']}"):
                        delete_item(item['id'])
                        st.success(f"ลบ {item['name']} เรียบร้อย!")
                        st.rerun()

    # TAB 2: สแกนเพิ่มของเข้าตู้เย็นตัวเอง
    with tab2:
        st.subheader("สแกนวัตถุดิบด้วย AI")
        img_file = st.camera_input("ถ่ายรูปวัตถุดิบ") or st.file_uploader("เลือกรูปภาพ", type=["jpg", "png", "jpeg"])
        
        if img_file:
            image = Image.open(img_file)
            st.image(image, caption="รูปถ่าย", use_container_width=True)
            
            if st.button("🤖 ให้ AI สแกนบันทึกเข้าตู้เย็น"):
                model = genai.GenerativeModel('gemini-1.5-flash')
                prompt = "วิเคราะห์ภาพนี้ ระบุชื่ออาหาร/วัตถุดิบสั้นๆ ภาษาไทยเพียงชื่อเดียว เช่น นมสด, ไข่ไก่"
                
                with st.spinner("กำลังบันทึกลงตู้เย็นของคุณ..."):
                    response = model.generate_content([prompt, image])
                    food_name = response.text.strip()
                    default_expiry = datetime.date.today() + datetime.timedelta(days=7)
                    
                    add_item_to_fridge(
                        name=food_name,
                        category="อาหาร/วัตถุดิบ",
                        quantity=1,
                        expiry_date=default_expiry,
                        user_id=user_id
                    )
                    
                    st.success(f"บันทึก '{food_name}' เรียบร้อยแล้ว!")
                    st.rerun()
