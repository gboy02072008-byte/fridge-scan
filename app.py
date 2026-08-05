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

# --- 2. ฟังก์ชันจัดการฐานข้อมูล ---
def get_fridge_items():
    res = supabase.table("fridge_items").select("*").order("expiry_date", desc=False).execute()
    return res.data

def add_item_to_fridge(name, category, quantity, expiry_date):
    data = {
        "name": name,
        "category": category,
        "quantity": quantity,
        "expiry_date": str(expiry_date)
    }
    supabase.table("fridge_items").insert(data).execute()

def delete_item(item_id):
    supabase.table("fridge_items").delete().eq("id", item_id).execute()

# --- 3. หน้าตาแอปพลิเคชัน (UI) ---
st.title("🍎 แอปตู้เย็น FridgeScan")

# แถบเมนูย่อย
tab1, tab2 = st.tabs(["📦 ของในตู้เย็น", "📷 สแกนเพิ่มของ"])

# --- TAB 1: แสดงรายการของในตู้เย็น ---
with tab1:
    st.subheader("รายการของที่อยู่ในตู้เย็นตอนนี้")
    
    # ดึงข้อมูลจริงจาก Supabase
    items = get_fridge_items()
    
    if not items:
        st.info("ตู้เย็นว่างเปล่า ลองไปที่แถบสแกนเพื่อเพิ่มของดูครับ!")
    else:
        for item in items:
            col1, col2, col3 = st.columns([3, 2, 1])
            with col1:
                st.write(f"**{item['name']}** ({item['category']})")
            with col2:
                st.write(f"⏳ หมดอายุ: {item['expiry_date']}")
            with col3:
                # ปุ่มลบข้อมูลออกจากฐานข้อมูลจริง
                if st.button("ทานหมดแล้ว", key=f"del_{item['id']}"):
                    delete_item(item['id'])
                    st.success(f"ลบ {item['name']} แล้ว!")
                    st.rerun()

# --- TAB 2: สแกนรูปภาพด้วย AI แล้วบันทึกลง DB ---
with tab2:
    st.subheader("สแกนรูปภาพอาหาร/วัตถุดิบ")
    img_file = st.camera_input("ถ่ายรูปวัตถุดิบ") or st.file_uploader("อัปโหลดรูปภาพ", type=["jpg", "png", "jpeg"])
    
    if img_file:
        image = Image.open(img_file)
        st.image(image, caption="รูปที่เลือก", use_container_width=True)
        
        if st.button("🤖 ให้ AI สแกน"):
            model = genai.GenerativeModel('gemini-1.5-flash')
            prompt = "วิเคราะห์ภาพนี้ บอกชื่ออาหาร/วัตถุดิบ (ภาษาไทย) และหมวดหมู่ คืนค่าเป็นข้อความสั้นๆ เช่น: นมสด, เครื่องดื่ม"
            
            with st.spinner("กำลังวิเคราะห์ภาพ..."):
                response = model.generate_content([prompt, image])
                st.write("ผลการวิเคราะห์:", response.text)
                
                # ตัวอย่าง: บันทึกลง Supabase (หรือตั้งค่าเพิ่มวันหมดอายุอัตโนมัติ 7 วัน)
                default_expiry = datetime.date.today() + datetime.timedelta(days=7)
                add_item_to_fridge(
                    name=response.text.strip(),
                    category="อาหาร/วัตถุดิบ",
                    quantity=1,
                    expiry_date=default_expiry
                )
                st.success("บันทึกลงตู้เย็นเรียบร้อยแล้ว!")
                st.rerun()
