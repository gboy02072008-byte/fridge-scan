import streamlit as st

from supabase import create_client, Client

# เชื่อมต่อกับ Supabase โดยดึง URL และ KEY จาก Secrets ที่เราตั้งไว้
@st.cache_resource
def init_supabase() -> Client:
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

supabase = init_supabase()
# --------------------------------------------------
# ฟังก์ชันที่ 1: ดึงรายการของทั้งหมดในตู้เย็นมาแสดง
def get_fridge_items():
    response = supabase.table("fridge_items").select("*").order("expiry_date", desc=False).execute()
    return response.data

# ฟังก์ชันที่ 2: เพิ่มของใหม่ลงฐานข้อมูล (เรียกใช้ตอน AI สแกนเสร็จ)
def add_item_to_fridge(name, category, quantity, expiry_date):
    data = {
        "name": name,
        "category": category,
        "quantity": quantity,
        "expiry_date": str(expiry_date)
    }
    supabase.table("fridge_items").insert(data).execute()

# ฟังก์ชันที่ 3: ลบของออกจากตู้เย็น (เมื่อกดปุ่มกินหมดแล้ว)
def delete_item(item_id):
    supabase.table("fridge_items").delete().eq("id", item_id).execute()

# --------------------------------------------------
st.title("🍎 แอปตู้เย็น FridgeScan")

# สร้างแท็บสลับหน้า 2 หน้า
tab1, tab2 = st.tabs(["📦 ของในตู้เย็น", "📷 สแกนเพิ่มของ"])

# --- TAB 1: แสดงของในตู้เย็นถาวร ---
with tab1:
    st.subheader("รายการของที่อยู่ในตู้เย็น")
    
    # ดึงข้อมูลจริงจาก Supabase
    items = get_fridge_items()
    
    if not items:
        st.info("ตู้เย็นว่างเปล่า ลองไปที่แถบ '📷 สแกนเพิ่มของ' ได้เลยครับ")
    else:
        for item in items:
            col1, col2, col3 = st.columns([3, 2, 1])
            with col1:
                st.write(f"**{item['name']}** ({item['category']})")
            with col2:
                st.write(f"⏳ หมดอายุ: {item['expiry_date']}")
            with col3:
                # กดลบข้อมูลออกจากฐานข้อมูลจริง
                if st.button("ทานหมดแล้ว", key=f"del_{item['id']}"):
                    delete_item(item['id'])
                    st.success(f"ลบ {item['name']} ออกจากตู้เย็นแล้ว!")
                    st.rerun()

# --- TAB 2: สแกนภาพด้วย Gemini แล้วบันทึกลง Supabase ---
with tab2:
    st.subheader("สแกนวัตถุดิบด้วย AI")
    
    img_file = st.camera_input("ถ่ายรูปวัตถุดิบ") or st.file_uploader("หรือเลือกรูปภาพ", type=["jpg", "png", "jpeg"])
    
    if img_file:
        image = Image.open(img_file)
        st.image(image, caption="รูปถ่ายวัตถุดิบ", use_container_width=True)
        
        if st.button("🤖 ให้ AI สแกนบันทึกเข้าตู้เย็น"):
            model = genai.GenerativeModel('gemini-2.0-flash')
            prompt = "วิเคราะห์ภาพนี้ แล้วระบุชื่ออาหาร/วัตถุดิบสั้นๆ เป็นภาษาไทยเพียงชื่อเดียว เช่น นมสด, ไข่ไก่, ส้ม"
            
            with st.spinner("AI กำลังวิเคราะห์และบันทึกลงตู้เย็น..."):
                response = model.generate_content([prompt, image])
                food_name = response.text.strip()
                
                # คำนวณวันหมดอายุอัตโนมัติ (ตั้งไว้ล่วงหน้า 7 วัน)
                default_expiry = datetime.date.today() + datetime.timedelta(days=7)
                
                # บันทึกลง Supabase จริง!
                add_item_to_fridge(
                    name=food_name,
                    category="อาหาร/วัตถุดิบ",
                    quantity=1,
                    expiry_date=default_expiry
                )
                
                st.success(f"บันทึก '{food_name}' ลงตู้เย็นเรียบร้อยแล้ว!")
                st.rerun()




# 1. กำหนดระบบ Session State สำหรับเช็คสถานะการล็อกอิน
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

# 2. ฟังก์ชันตรวจสอบรหัสผ่าน
def login_page():
    st.title("🔒 เข้าสู่ระบบ FridgeScan")
    st.caption("กรุณาเข้าสู่ระบบเพื่อใช้งานแอปจัดการตู้เย็น")

    with st.form("login_form"):
        username = st.text_input("ชื่อผู้ใช้งาน (Username)")
        password = st.text_input("รหัสผ่าน (Password)", type="password")
        submit_button = st.form_submit_button("เข้าสู่ระบบ")

        if submit_button:
            # กำหนด Username และ Password ที่ต้องการใช้ตรงนี้
            if username == "admin" and password == "1234":
                st.session_state.logged_in = True
                st.success("เข้าสู่ระบบสำเร็จ!")
                st.rerun()  # รีโหลดหน้าเพื่อเข้าสู่หน้าแอปหลัก
            else:
                st.error("ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง")

# 3. ตรวจสอบสถานะการเข้าสู่ระบบ
if not st.session_state.logged_in:
    login_page()
    st.stop()  # หยุดการทำงานของโค้ดส่วนล่าง ถ้ายังไม่ได้ล็อกอิน

# --- ด้านล่างนี้คือโค้ดแอปเดิมของคุณ (Dashboard / สแกนอาหาร) ---
st.sidebar.button("ออกจากระบบ", on_click=lambda: st.session_state.update(logged_in=False))
st.title("🍎 แอปตู้เย็น FridgeScan")
# ... โค้ดเดิมของคุณต่อตรงนี้ได้เลย ...
import google.generativeai as genai
from PIL import Image
import json
import os
from datetime import datetime, date, timedelta

# --- 1. SET PAGE CONFIG & STYLING ---
st.set_page_config(
    page_title="FridgeScan - เครื่องสแกนตู้เย็นอัจฉริยะ",
    page_icon="📸",
    layout="centered"
)

# Custom CSS to make the app look like the mobile UI design
st.markdown("""
<style>
    /* Main Background & Fonts */
    .stApp {
        background-color: #f5f9fc;
    }
    h1, h2, h3 {
        color: #1e3d59;
        font-family: 'Helvetica Neue', Arial, sans-serif;
    }
    
    /* Custom FridgeScan Header */
    .header-container {
        text-align: center;
        padding: 20px 10px;
        background: linear-gradient(135deg, #17b978 0%, #086972 100%);
        color: white;
        border-radius: 15px;
        margin-bottom: 25px;
        box-shadow: 0 4px 15px rgba(8, 105, 114, 0.2);
    }
    .header-title {
        font-size: 2.2rem;
        font-weight: bold;
        margin: 0;
        color: white !important;
    }
    .header-subtitle {
        font-size: 1rem;
        opacity: 0.9;
        margin-top: 5px;
    }

    /* Food Cards styling */
    .food-card {
        background-color: white;
        padding: 15px 20px;
        border-radius: 12px;
        margin-bottom: 12px;
        box-shadow: 0 4px 8px rgba(0,0,0,0.03);
        display: flex;
        justify-content: space-between;
        align-items: center;
        border-left: 6px solid #cccccc;
        transition: transform 0.2s;
    }
    .food-card:hover {
        transform: translateY(-2px);
    }
    .status-red { border-left-color: #ff4d4d; }
    .status-yellow { border-left-color: #ffa600; }
    .status-green { border-left-color: #2ecc71; }
    
    .food-info {
        display: flex;
        flex-direction: column;
    }
    .food-name {
        font-size: 1.15rem;
        font-weight: bold;
        color: #1e3d59;
    }
    .food-date {
        font-size: 0.85rem;
        color: #7f8c8d;
        margin-top: 3px;
    }
    
    /* Traffic light badges */
    .badge {
        padding: 6px 12px;
        border-radius: 20px;
        color: white;
        font-weight: bold;
        font-size: 0.85rem;
        text-align: center;
        min-width: 90px;
    }
    .badge-red { background-color: #ff4d4d; }
    .badge-yellow { background-color: #ffa600; }
    .badge-green { background-color: #2ecc71; }

    /* Overview Stats widget */
    .stat-box {
        background-color: white;
        border-radius: 12px;
        padding: 15px;
        text-align: center;
        box-shadow: 0 4px 8px rgba(0,0,0,0.03);
    }
    .stat-number {
        font-size: 1.8rem;
        font-weight: bold;
    }
</style>
""", unsafe_allow_html=True)

# --- 2. SETUP INITIAL SESSION STATE (Mock Database) ---
if "inventory" not in st.session_state:
    # Pre-populate with some realistic items for testing
    st.session_state.inventory = [
        {"name": "นมจืดเมจิ", "expiry_date": (date.today() + timedelta(days=1)).strftime("%Y-%m-%d")},
        {"name": "อกไก่ดิบ", "expiry_date": (date.today() + timedelta(days=3)).strftime("%Y-%m-%d")},
        {"name": "มะเขือเทศ", "expiry_date": (date.today() + timedelta(days=5)).strftime("%Y-%m-%d")},
        {"name": "ไข่ไก่", "expiry_date": (date.today() + timedelta(days=10)).strftime("%Y-%m-%d")}
    ]

# --- 3. SIDEBAR (API KEY & RESET SETTINGS) ---
st.sidebar.markdown("""
<div style='text-align: center; margin-bottom: 20px;'>
    <h2 style='color: #086972; margin: 0;'>⚙️ ตั้งค่าระบบ</h2>
</div>
""", unsafe_allow_html=True)

api_key = st.sidebar.text_input(
    "1. ใส่ Google Gemini API Key",
    type="password",
    value=os.environ.get("GEMINI_API_KEY", ""),
    help="สามารถขอ API Key ฟรีได้จาก Google AI Studio"
)

st.sidebar.markdown("""
<a href="https://aistudio.google.com/" target="_blank" style="text-decoration:none;">
    <button style="width:100%; padding:10px; background-color:#086972; color:white; border:none; border-radius:8px; cursor:pointer; font-weight:bold; margin-bottom:20px;">
        🔑 ขอ API Key ฟรีที่นี่
    </button>
</a>
""", unsafe_allow_html=True)

st.sidebar.markdown("---")

if st.sidebar.button("🧹 ล้างข้อมูลตู้เย็นทั้งหมด"):
    st.session_state.inventory = []
    st.sidebar.success("ล้างข้อมูลเรียบร้อยแล้ว!")
    st.rerun()

# --- 4. HEADER ---
st.markdown("""
<div class="header-container">
    <div class="header-title">📸 FridgeScan</div>
    <div class="header-subtitle">ระบบสแกนอาหารอัจฉริยะและแจ้งเตือนวันหมดอายุ</div>
</div>
""", unsafe_allow_html=True)

# --- 5. CAMERA & SCANNING SECTION ---
st.markdown("### 📸 เริ่มสแกนอาหาร")
st.info("กรุณาใส่ API Key ที่เมนูด้านซ้ายก่อน เพื่อเปิดใช้งานระบบสแกนด้วย AI")

# Provide choices for camera vs file upload (useful for testing on computers without cameras)
input_type = st.radio("เลือกช่องทางรับภาพ", ["📷 กล้องถ่ายรูปมือถือ/โน้ตบุ๊ก", "📁 อัปโหลดรูปภาพจากเครื่อง"], horizontal=True)

img_file = None
if input_type == "📷 กล้องถ่ายรูปมือถือ/โน้ตบุ๊ก":
    img_file = st.camera_input("กดถ่ายรูปเพื่อสแกนวัตถุดิบ")
else:
    img_file = st.file_uploader("เลือกรูปภาพอาหารเพื่อจำลองการสแกน", type=["jpg", "jpeg", "png"])

# Process Image when captured/uploaded
if img_file:
    st.image(img_file, caption="รูปภาพที่ได้รับ", use_container_width=True)
    
    if not api_key:
        st.error("⚠️ กรุณากรอก Gemini API Key ที่แถบเมนูด้านซ้ายเพื่อทำการวิเคราะห์ข้อมูลด้วย AI")
    else:
        # Trigger button to process to avoid repetitive API calls
        if st.button("🚀 ส่ง AI วิเคราะห์อาหาร", type="primary", use_container_width=True):
            with st.spinner("🤖 AI กำลังวิเคราะห์รูปภาพของคุณ..."):
                try:
                    # Open image
                    image = Image.open(img_file)
                    
                    # Setup Gemini
                    genai.configure(api_key=api_key)
                    # Using gemini-1.5-flash as it's the fast, cost-effective multimodal model
                    model = genai.GenerativeModel('gemini-3.5-flash')
                    
                    # Strict prompt to force JSON response
                    prompt = """
                    วิเคราะห์ภาพถ่ายอาหาร วัตถุดิบ หรือของสดที่เห็นในรูปนี้
                    ระบุรายการอาหาร/วัตถุดิบทั้งหมดที่คุณเห็นเป็นภาษาไทย
                    สำหรับอาหารแต่ละชนิด ให้ทำการคาดคะเนจำนวนวันที่สามารถเก็บรักษาในตู้เย็นได้นับจากวันนี้ (หน่วยเป็นจำนวนวัน) ก่อนที่จะเสื่อมสภาพหรือหมดอายุ
                    ให้ตอบกลับเฉพาะข้อมูล JSON ตามโครงสร้างด้านล่างนี้เท่านั้น ห้ามพิมพ์อธิบาย สรุป หรือทักทายใดๆ เด็ดขาด เพื่อให้โค้ดสามารถนำไป Parse ต่อได้ทันที:
                    
                    [
                      {"name": "อกไก่ดิบ", "days_to_expire": 3},
                      {"name": "นมจืดเมจิ", "days_to_expire": 1}
                    ]
                    
                    หากในรูปไม่ใช่ของกินหรืออาหาร ให้ตอบกลับเป็น [] เปล่าๆ
                    """
                    
                    # Call API
                    response = model.generate_content([prompt, image])
                    raw_text = response.text.strip()
                    
                    # Clean up json wrapping if AI added it
                    if raw_text.startswith("```json"):
                        raw_text = raw_text.split("```json")[1].split("```")[0].strip()
                    elif raw_text.startswith("```"):
                        raw_text = raw_text.split("```")[1].split("```")[0].strip()
                    
                    # Parse JSON
                    scanned_items = json.loads(raw_text)
                    
                    if scanned_items:
                        added_count = 0
                        for item in scanned_items:
                            # Calculate expiry date
                            days_to_add = int(item.get("days_to_expire", 3))
                            expiry_date = (date.today() + timedelta(days=days_to_add)).strftime("%Y-%m-%d")
                            
                            # Save to state
                            st.session_state.inventory.append({
                                "name": item.get("name"),
                                "expiry_date": expiry_date
                            })
                            added_count += 1
                        
                        st.success(f"🎉 สำเร็จ! ตรวจพบอาหาร {added_count} รายการ และบันทึกลงในตู้เย็นเรียบร้อยแล้ว!")
                        st.rerun() # Refresh page to update list
                    else:
                        st.warning("🔍 AI ไม่พบรายการอาหารใดๆ ในรูปภาพนี้ หรือไม่สามารถวิเคราะห์ได้ ลองมุมกล้องใหม่อีกครั้งนะครับ")
                        
                except Exception as e:
                    st.error(f"❌ เกิดข้อผิดพลาดในการวิเคราะห์: {str(e)}")
                    st.info("โปรดตรวจสอบให้แน่ใจว่า API Key ของคุณถูกต้องและไม่ติดปัญหาโควต้า")

# --- 6. MANUAL ENTRY OPTION ---
with st.expander("➕ เพิ่มรายการอาหารด้วยตัวเอง (หากสแกนไม่ได้)"):
    with st.form("manual_add_form"):
        manual_name = st.text_input("ชื่ออาหาร/วัตถุดิบ", placeholder="เช่น หมูสามชั้น, ผักกาดขาว")
        manual_days = st.number_input("จำนวนวันที่เก็บได้ (วัน)", min_value=1, max_value=365, value=3)
        submit_button = st.form_submit_button("บันทึก")
        
        if submit_button and manual_name:
            expiry_date = (date.today() + timedelta(days=int(manual_days))).strftime("%Y-%m-%d")
            st.session_state.inventory.append({
                "name": manual_name,
                "expiry_date": expiry_date
            })
            st.success(f"บันทึก {manual_name} เรียบร้อย!")
            st.rerun()

st.markdown("---")

# --- 7. OVERVIEW STATS (DASHBOARD WIDGETS) ---
st.markdown("### 📊 ภาพรวมวัตถุดิบในตู้เย็น")

# Calculate metrics based on remaining days
red_count = 0
yellow_count = 0
green_count = 0

processed_inventory = []
for item in st.session_state.inventory:
    try:
        expiry_dt = datetime.strptime(item["expiry_date"], "%Y-%m-%d").date()
        days_left = (expiry_dt - date.today()).days
    except:
        days_left = 3 # Fallback
    
    if days_left <= 2:
        status_class = "status-red"
        badge_class = "badge-red"
        badge_text = f"🚨 {days_left} วัน" if days_left >= 0 else "❌ หมดอายุแล้ว"
        red_count += 1
    elif 3 <= days_left <= 5:
        status_class = "status-yellow"
        badge_class = "badge-yellow"
        badge_text = f"⚠️ {days_left} วัน"
        yellow_count += 1
    else:
        status_class = "status-green"
        badge_class = "badge-green"
        badge_text = f"✅ {days_left} วัน"
        green_count += 1
        
    processed_inventory.append({
        "name": item["name"],
        "expiry_date": item["expiry_date"],
        "days_left": days_left,
        "status_class": status_class,
        "badge_class": badge_class,
        "badge_text": badge_text
    })

# Render 3 Columns for Stat Summary
col1, col2, col3 = st.columns(3)
with col1:
    st.markdown(f"""
    <div class="stat-box">
        <div style="color:#ff4d4d; font-weight:bold;">🔴 ใกล้หมดอายุ</div>
        <div class="stat-number" style="color:#ff4d4d;">{red_count}</div>
    </div>
    """, unsafe_allow_html=True)
with col2:
    st.markdown(f"""
    <div class="stat-box">
        <div style="color:#ffa600; font-weight:bold;">🟡 ใกล้หมด (3-5 วัน)</div>
        <div class="stat-number" style="color:#ffa600;">{yellow_count}</div>
    </div>
    """, unsafe_allow_html=True)
with col3:
    st.markdown(f"""
    <div class="stat-box">
        <div style="color:#2ecc71; font-weight:bold;">🟢 ปกติ (>5 วัน)</div>
        <div class="stat-number" style="color:#2ecc71;">{green_count}</div>
    </div>
    """, unsafe_allow_html=True)

# --- 8. INVENTORY LIST VIEW ---
st.markdown("### 📋 รายการอาหารในตู้เย็นปัจจุบัน")

if not processed_inventory:
    st.info("📭 ยังไม่มีวัตถุดิบใดๆ ในตู้เย็นของคุณเลย ลองใช้ปุ่มกล้องถ่ายรูปด้านบนเพื่อเพิ่มอาหารสิ!")
else:
    # Sort inventory so that items near expiration (lowest days left) appear first!
    sorted_inventory = sorted(processed_inventory, key=lambda x: x["days_left"])
    
    for idx, item in enumerate(sorted_inventory):
        # We can also add a delete button next to each item using Streamlit columns
        col_card, col_delete = st.columns([6, 1])
        
        with col_card:
            st.markdown(f"""
            <div class="food-card {item['status_class']}">
                <div class="food-info">
                    <span class="food-name">{item['name']}</span>
                    <span class="food-date">วันที่คาดว่าหมดอายุ: {item['expiry_date']}</span>
                </div>
                <div class="badge {item['badge_class']}">
                    {item['badge_text']}
                </div>
            </div>
            """, unsafe_allow_html=True)
            
        with col_delete:
            # Render small spacing to center the button vertically
            st.markdown("<div style='height:12px;'></div>", unsafe_allow_html=True)
            # Find index in the original list to delete correctly
            if st.button("🗑️", key=f"del_{idx}"):
                # Find the matched item in original state list
                original_index = next((i for i, orig in enumerate(st.session_state.inventory) if orig["name"] == item["name"] and orig["expiry_date"] == item["expiry_date"]), None)
                if original_index is not None:
                    st.session_state.inventory.pop(original_index)
                    st.success("ลบรายการแล้ว")
                    st.rerun()

st.markdown("""
<div style='text-align: center; margin-top: 50px; color: #95a5a6; font-size: 0.8rem;'>
    FridgeScan MVP • พัฒนาด้วย Python & Streamlit • ขับเคลื่อนโดย Google Gemini 1.5 Flash
</div>
""", unsafe_allow_html=True)
