import streamlit as st
import google.generativeai as genai
from PIL import Image
from supabase import create_client, Client
import datetime
import time

# --- 1. ตั้งค่า API Key & DB Connection ---
genai.configure(api_key=st.secrets["GEMINI_API_KEY"])

@st.cache_resource
def init_supabase() -> Client:
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

supabase = init_supabase()

# Session State สำหรับเก็บข้อมูล
if "user" not in st.session_state:
    st.session_state.user = None
if "scanned_name" not in st.session_state:
    st.session_state.scanned_name = ""

# --- Helper Function: ย่อขนาดรูปภาพเพื่อความรวดเร็ว ---
def compress_image(image, max_size=(800, 800)):
    img = image.copy()
    img.thumbnail(max_size)
    return img

# --- 2. ฟังก์ชัน Auth ---
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

# --- 3. ฟังก์ชัน Database ---
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

# --- 4. หน้าตาแอปพลิเคชัน (UX/UI Polish) ---
st.set_page_config(page_title="FridgeScan", page_icon="🍎", layout="centered")

st.title("🍎 แอปตู้เย็น FridgeScan")

# กรณีไม่ได้ล็อกอิน
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

# กรณีล็อกอินเรียบร้อย
else:
    user_id = st.session_state.user.id
    user_email = st.session_state.user.email
    
    st.sidebar.write(f"👤 **{user_email}**")
    if st.sidebar.button("ออกจากระบบ"):
        logout()

    tab1, tab2 = st.tabs(["📦 ตู้เย็นของฉัน", "➕ เพิ่มของเข้าตู้เย็น"])

    # TAB 1: แสดงของในตู้เย็น
    with tab1:
        st.subheader("รายการของในตู้เย็น")
        items = get_fridge_items(user_id)
        
        if not items:
            st.info("ตู้เย็นยังว่างเปล่า ลองไปที่แถบ '➕ เพิ่มของเข้าตู้เย็น' ดูครับ")
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

    # TAB 2: สแกน/เพิ่มของ (มีระบบ AI + Fallback กรอกมือ)
    with tab2:
        st.subheader("เลือกวิธีเพิ่มวัตถุดิบ")
        
        img_file = st.camera_input("ถ่ายรูปวัตถุดิบ") or st.file_uploader("หรืออัปโหลดรูปภาพ", type=["jpg", "png", "jpeg"])
        
        if img_file:
            image = Image.open(img_file)
            compressed_img = compress_image(image) # ย่อรูปเพื่อประมวลผลเร็ว
            st.image(compressed_img, caption="รูปถ่ายวัตถุดิบ", width=300)
            
            if st.button("🤖 ให้ AI ช่วยวิเคราะห์รูป", use_container_width=True):
                with st.status("🔍 AI กำลังวิเคราะห์รูปภาพ...", expanded=True) as status:
                    try:
                        model = genai.GenerativeModel('gemini-1.5-flash')
                        prompt = "วิเคราะห์ภาพนี้ ระบุชื่ออาหารหรือวัตถุดิบเป็นภาษาไทยสั้นๆ เพียงชื่อเดียว เช่น นมสด, ไข่ไก่, หมูสับ"
                        
                        response = model.generate_content([prompt, compressed_img])
                        st.session_state.scanned_name = response.text.strip()
                        status.update(label="✅ วิเคราะห์สำเร็จ!", state="complete", expanded=False)
                    except Exception as e:
                        status.update(label="⚠️ AI ไม่สามารถอ่านรูปได้ชั่วคราว", state="error", expanded=False)
                        st.toast("ระบบ AI ติดขัดโควตาชั่วคราว คุณสามารถพิมพ์ชื่อวัตถุดิบเองได้เลยครับ", icon="💡")

        st.divider()
        st.markdown("### 📝 ตรวจทานและบันทึกข้อมูล")
        
        # ฟอร์มบันทึกข้อมูล (รับค่าจาก AI หรือกรอกมือก็ได้)
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
                    st.session_state.scanned_name = "" # ล้างค่าที่สแกน
                    st.toast(f"บันทึก '{item_name}' เรียบร้อย!", icon="✅")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.warning("กรุณาระบุชื่อวัตถุดิบก่อนบันทึก")
