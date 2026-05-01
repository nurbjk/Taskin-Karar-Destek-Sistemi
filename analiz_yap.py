import streamlit as st
import geopandas as gpd
import pandas as pd
import osmnx as ox
import folium
import warnings
import io
import tempfile
import os
import base64

# --- AYARLAR VE ÖZEL TASARIM (CSS) ---
warnings.filterwarnings("ignore")
st.set_page_config(page_title="Taşkın Karar Destek Sistemi", layout="wide", page_icon="🌊")


st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;800&display=swap');
    
    html, body, [class*="css"]  {
        font-family: 'Outfit', sans-serif;
    }
    
    /* Ana Arka Plan ve Metin Rengi */
    .stApp {
        background-color: #0B1120 !important;
        color: #e2e8f0 !important;
    }
    
    /* Üst Başlık Tasarımı */
    .header-container {
        padding: 40px;
        border-radius: 20px;
        margin-bottom: 30px;
        text-align: center;
        box-shadow: 0 10px 30px rgba(0, 0, 0, 0.5);
        border: 1px solid rgba(255, 255, 255, 0.1);
        position: relative;
        overflow: hidden;
    }
    
    /* Başlık İçeriği */
    .header-content {
        position: relative;
        z-index: 2;
        background: rgba(11, 17, 32, 0.65);
        backdrop-filter: blur(10px);
        -webkit-backdrop-filter: blur(10px);
        padding: 20px;
        border-radius: 15px;
        border: 1px solid rgba(255, 255, 255, 0.05);
        display: inline-block;
    }
    
    .header-content h1 {
        margin: 0;
        font-size: 3em;
        font-weight: 800;
        background: linear-gradient(90deg, #38bdf8, #818cf8);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        letter-spacing: -1px;
    }
    
    .header-content p {
        font-size: 1.3em;
        color: #cbd5e1;
        margin-top: 10px;
        font-weight: 300;
    }
    
    /* Metrik Kartları - Glassmorphism */
    div[data-testid="stMetric"] {
        background: rgba(30, 41, 59, 0.7);
        backdrop-filter: blur(12px);
        border: 1px solid rgba(255, 255, 255, 0.1);
        padding: 25px;
        border-radius: 16px;
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.2);
        border-top: 4px solid #38bdf8;
        transition: transform 0.3s ease, box-shadow 0.3s ease;
    }
    
    div[data-testid="stMetric"]:hover {
        transform: translateY(-5px);
        box-shadow: 0 12px 40px rgba(56, 189, 248, 0.2);
    }
    
    div[data-testid="stMetricValue"] {
        color: #f8fafc !important;
        font-weight: 800;
        font-size: 2.5em;
    }
    
    div[data-testid="stMetricLabel"] {
        color: #94a3b8 !important;
        font-weight: 600;
        font-size: 1.1em;
        text-transform: uppercase;
        letter-spacing: 1px;
    }
    
    /* Buton Tasarımı */
    .stButton>button {
        width: 100%;
        border-radius: 12px;
        height: 3.8em;
        background: linear-gradient(135deg, #0284c7 0%, #3b82f6 100%);
        color: white;
        font-weight: 600;
        font-size: 1.1em;
        border: none;
        box-shadow: 0 4px 15px rgba(59, 130, 246, 0.4);
        transition: all 0.3s ease;
        text-transform: uppercase;
        letter-spacing: 1px;
    }
    
    .stButton>button:hover {
        background: linear-gradient(135deg, #0369a1 0%, #2563eb 100%);
        box-shadow: 0 6px 20px rgba(59, 130, 246, 0.6);
        transform: translateY(-2px);
    }
    
    /* Dosya Yükleme Alanları */
    [data-testid="stFileUploadDropzone"] {
        background-color: rgba(30, 41, 59, 0.4);
        border: 2px dashed rgba(148, 163, 184, 0.4);
        border-radius: 16px;
        transition: all 0.3s ease;
    }
    
    [data-testid="stFileUploadDropzone"]:hover {
        background-color: rgba(30, 41, 59, 0.8);
        border-color: #38bdf8;
    }
    
    /* Sidebar Tasarımı */
    [data-testid="stSidebar"] {
        background-color: rgba(15, 23, 42, 0.95) !important;
        border-right: 1px solid rgba(255, 255, 255, 0.05);
    }
    
    /* Expander ve Kutular */
    .streamlit-expanderHeader {
        background-color: rgba(30, 41, 59, 0.5);
        border-radius: 8px;
        color: #e2e8f0;
        border: 1px solid rgba(255, 255, 255, 0.1);
    }
    
    /* Uyarı ve Bilgi Kutuları */
    .stAlert {
        background: rgba(30, 41, 59, 0.6);
        border: 1px solid rgba(255, 255, 255, 0.1);
        backdrop-filter: blur(10px);
        border-radius: 12px;
        color: #e2e8f0;
    }
    
    /* Çizgiler */
    hr {
        border-color: rgba(255, 255, 255, 0.1);
    }
    </style>
    """, unsafe_allow_html=True)

# --- ANALİZ FONKSİYONLARI ---
def onarma_ve_numaralandirma(gdf):
    if gdf.crs is None or gdf.crs.to_epsg() != 32635:
        gdf = gdf.set_crs(epsg=32635, allow_override=True)
    gdf.geometry = gdf.geometry.buffer(0)
    gdf = gdf[~gdf.is_empty & (gdf.geometry.type == 'Polygon')].reset_index(drop=True)
    gdf['BINA_ID'] = gdf.index + 1
    gdf['ALAN_m2'] = gdf.geometry.area.round(2)
    return gdf

def akilli_konum_analizi(gdf):
    gdf_wgs84 = gdf.to_crs(epsg=4326)
    bbox = gdf_wgs84.total_bounds
    try:
        tags = {"building": True}
        area_features = ox.features_from_bbox(bbox[3], bbox[1], bbox[2], bbox[0], tags=tags)
        area_features = area_features[area_features.geometry.type.isin(['Polygon', 'MultiPolygon'])]
    except: area_features = gpd.GeoDataFrame()

    tipler = []
    for i, row in gdf_wgs84.iterrows():
        res = "Konut"
        if not area_features.empty:
            nearby = area_features[area_features.geometry.distance(row.geometry.centroid) < 0.0001]
            if not nearby.empty: res = "Ticari/Fabrika"
        if res == "Konut" and row['ALAN_m2'] > 600: res = "Ticari/Fabrika (*)"
        tipler.append(res)
    return tipler

def taskin_analizini_yap(gdf_binalar, df_h, df_d):
    gdf_halkalar = gpd.GeoDataFrame(gdf_binalar[['BINA_ID']], geometry=gdf_binalar.buffer(1), crs=gdf_binalar.crs)
    pts_h = gpd.GeoDataFrame(df_h, geometry=gpd.points_from_xy(df_h.X, df_h.Y), crs=gdf_binalar.crs)
    pts_d = gpd.GeoDataFrame(df_d, geometry=gpd.points_from_xy(df_d.X, df_d.Y), crs=gdf_binalar.crs)
    res_h = gpd.sjoin(pts_h, gdf_halkalar, predicate='within').groupby('BINA_ID')['Z'].mean().round(2).reset_index().rename(columns={'Z': 'HIZ'})
    res_d = gpd.sjoin(pts_d, gdf_halkalar, predicate='within').groupby('BINA_ID')['Z'].mean().round(2).reset_index().rename(columns={'Z': 'DERIN'})
    return pd.merge(res_h, res_d, on='BINA_ID', how='outer').fillna(0)

def defra_etiket(d, v):
    td = d * (v + 0.5) + (1 if d > 0.25 else 0)
    if td < 0.75: return "T1-Dusuk"
    elif td < 1.25: return "T2-Hafif"
    elif td <= 2.5: return "T3-Yuksek"
    else: return "T4-CokYuk"

def maliyet_hesapla(row, k_fiyat, t_fiyat):
    d = float(row['DERIN'])
    f = 0.0 if d <= 0.01 else 0.15 if d <= 0.5 else 0.18 if d <= 1.0 else 0.21 if d <= 2.0 else 0.70 if d <= 4.0 else 1.0
    birim = t_fiyat if "Ticari" in str(row['TIP']) else k_fiyat
    return int(row['ALAN_m2'] * f * birim * 0.8)

# --- ARAYÜZ BAŞLANGICI ---

def get_base64_of_bin_file(bin_file):
    try:
        with open(bin_file, 'rb') as f:
            data = f.read()
        return base64.b64encode(data).decode()
    except:
        return ""

img_b64 = get_base64_of_bin_file("banner.png")
if img_b64:
    bg_style = f"background-image: url('data:image/png;base64,{img_b64}'); background-size: cover; background-position: center;"
else:
    bg_style = "background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);"

st.markdown(f"""
    <div class="header-container" style="{bg_style}">
        <div class="header-content">
            <h1>🌊 Taşkın Karar Destek Sistemi</h1>
            <p>Mekânsal Analiz ve Otomatik Hasar Maliyetlendirme Modülü</p>
        </div>
    </div>
    """, unsafe_allow_html=True)

# PARAMETRE AYARLARI 
with st.sidebar:
    st.markdown("### 🛠️ Sistem Ayarları")
    with st.expander("💰 Birim Maliyetleri Düzenle", expanded=True):
        konut_f = st.number_input("Konut (TL/m²)", value=30000, step=1000)
        ticari_f = st.number_input("Ticari (TL/m²)", value=45000, step=1000)
    st.markdown("---")
    st.info("📊 Verilerinizi yükledikten sonra 'Analizi Başlat' butonuna tıklayın.")

# VERİ HAZIRLAMA KILAVUZU 
with st.expander("📢 Veri Hazırlama Kılavuzu (Kritik Uyarılar)", expanded=False):
    c_k1, c_k2 = st.columns(2)
    with c_k1:
        st.markdown("""
        **🏢 Bina Verisi (ZIP):**
        - Google Earth vb. üzerinden **poligon** olarak çizilmiş binaları içermelidir.
        - Sisteme yüklenen binalara arka planda otomatik **1 metre buffer** uygulanır.
        - Dosya içinde `.shp`, `.dbf`, `.shx`, `.prj` mutlaka bulunmalı.
        - Koordinat sistemi **EPSG:32635** olmalıdır.
        """)
    with c_k2:
        st.markdown("""
        **📊 Hız/Derinlik (CSV):**
        - Sütun başlıkları kesinlikle büyük harf **X, Y, Z** olmalıdır.
        - Ayraç olarak **noktalı virgül ( ; )** kullanılmalıdır.
        - Ondalık sayılar için virgül (0,50) kullanılabilir.
        """)

# Dosya Yükleme Paneli
st.subheader("📂 Veri Yükleme")
u1, u2, u3 = st.columns(3)
with u1: bina_zip = st.file_uploader("Binalar (ZIP/Shapefile)", type=['zip'])
with u2: hiz_csv = st.file_uploader("Hız Verisi (CSV)", type=['csv'])
with u3: derin_csv = st.file_uploader("Derinlik Verisi (CSV)", type=['csv'])

# --- ANALİZ AKIŞI ---
if bina_zip and hiz_csv and derin_csv:
    st.markdown("---")
    if st.button("🚀 ANALİZİ BAŞLAT"):
        try:
            with st.spinner('Hesaplamalar yapılıyor, lütfen bekleyin...'):
                with tempfile.TemporaryDirectory() as tmpdir:
                    z_path = os.path.join(tmpdir, "data.zip")
                    with open(z_path, "wb") as f: f.write(bina_zip.getbuffer())
                    
                    def temizle(file):
                        df = pd.read_csv(file, sep=';')
                       
                        df.columns = [c.strip().upper() for c in df.columns]
                        for col in ['X', 'Y', 'Z']:
                            if col in df.columns:
                                df[col] = df[col].astype(str).str.replace(',', '.').astype(float)
                        return df

                    df_h, df_d = temizle(hiz_csv), temizle(derin_csv)
                    gdf = onarma_ve_numaralandirma(gpd.read_file(z_path))
                    gdf['TIP'] = akilli_konum_analizi(gdf)
                    
                    analiz_res = taskin_analizini_yap(gdf, df_h, df_d)
                    final = gdf.merge(analiz_res, on='BINA_ID', how='left').fillna(0)
                    final['RISK'] = final.apply(lambda r: defra_etiket(r['DERIN'], r['HIZ']), axis=1)
                    final['MALIYET_TL'] = final.apply(lambda r: maliyet_hesapla(r, konut_f, ticari_f), axis=1)

                  
                    total_m = final['MALIYET_TL'].sum()
                    st.subheader("📌 Analiz Özeti")
                    m_col1, m_col2 = st.columns(2)
                    m_col1.metric("Toplam Bina Sayısı", f"{len(final)} Adet")
                    m_col2.metric("Toplam Tahmini Hasar", f"{total_m:,.0f} TL".replace(",", "."))

               

                    t1, t2 = st.tabs(["🗺️ Analiz Haritası", "📑 Detaylı Veri Tablosu"])
                    
                    with t1:
                        gw = final.to_crs(epsg=4326)
                        m = folium.Map(location=[gw.geometry.centroid.y.mean(), gw.geometry.centroid.x.mean()], 
                                       zoom_start=18, tiles='CartoDB Positron')
                        
                        for _, r in gw.iterrows():
                            color = {'T4-CokYuk': '#ef4444', 'T3-Yuksek': '#f97316', 'T2-Hafif': '#eab308', 'T1-Dusuk': '#22c55e'}.get(r['RISK'], 'gray')
                            
                            m_fmt = "{:,.0f}".format(r['MALIYET_TL']).replace(",", ".")
                            h_fmt = "{:.2f}".format(r['HIZ'])
                            d_fmt = "{:.2f}".format(r['DERIN'])
                            
                            html = f"""
                            <div style="font-family: 'Outfit', sans-serif; width: 250px; background-color: #0f172a; color: #e2e8f0; padding: 15px; border-radius: 12px; border: 1px solid rgba(255,255,255,0.1); box-shadow: 0 10px 25px rgba(0,0,0,0.5);">
                                <h4 style="margin: 0 0 10px 0; color: #38bdf8; font-size: 16px; border-bottom: 1px solid rgba(255,255,255,0.1); padding-bottom: 8px;">
                                    🏢 Bina ID: {r['BINA_ID']}
                                </h4>
                                <div style="font-size: 13px; line-height: 1.6;">
                                    <span style="color: #94a3b8;">Kullanım:</span> <strong style="color: white;">{r['TIP']}</strong><br>
                                    <span style="color: #94a3b8;">Alan:</span> <strong style="color: white;">{r['ALAN_m2']} m²</strong><br>
                                    <span style="color: #94a3b8;">Hız:</span> <strong style="color: white;">{h_fmt} m/s</strong><br>
                                    <span style="color: #94a3b8;">Derinlik:</span> <strong style="color: white;">{d_fmt} m</strong><br>
                                    <span style="color: #94a3b8;">Risk Durumu:</span> <strong style="color: {color};">{r['RISK']}</strong><br>
                                </div>
                                <div style="margin-top: 12px; padding: 10px; background: rgba(239, 68, 68, 0.1); border-radius: 8px; border: 1px solid rgba(239, 68, 68, 0.2); text-align: center;">
                                    <span style="color: #94a3b8; font-size: 12px; display: block;">Tahmini Hasar</span>
                                    <strong style="color: #ef4444; font-size: 18px;">₺ {m_fmt}</strong>
                                </div>
                            </div>
                            """
                            
                            
                            iframe = folium.IFrame(html=html, width=290, height=260)
                            popup = folium.Popup(iframe, max_width=300)
                            
                            folium.GeoJson(r.geometry, style_function=lambda x, c=color: {'fillColor': c, 'color': c, 'weight': 1, 'fillOpacity': 0.6},
                                           popup=popup).add_to(m)
                        st.components.v1.html(m._repr_html_(), height=650)

                    with t2:
                        excel_df = final[['BINA_ID', 'TIP', 'ALAN_m2', 'HIZ', 'DERIN', 'RISK', 'MALIYET_TL']].copy()
                        
                        
                        st.dataframe(excel_df.style.format({
                            "MALIYET_TL": "{:,.0f}", 
                            "ALAN_m2": "{:.2f}",
                            "HIZ": "{:.2f}",
                            "DERIN": "{:.2f}"
                        }, decimal=',', thousands='.'), use_container_width=True)
                        
                        
                        total_m = excel_df['MALIYET_TL'].sum()
                        total_row = pd.DataFrame([{'BINA_ID': 'TOPLAM', 'MALIYET_TL': total_m}])
                        excel_out = pd.concat([excel_df, total_row], ignore_index=True)
                        
                        buf = io.BytesIO()
                        with pd.ExcelWriter(buf, engine='xlsxwriter') as writer:
                            excel_out.to_excel(writer, index=False, sheet_name='AnalizRaporu')
                            workbook  = writer.book
                            worksheet = writer.sheets['AnalizRaporu']
                            
                            
                            num_format = workbook.add_format({'num_format': '#,##0'}) 
                            dec_format = workbook.add_format({'num_format': '0.00'})   
                            
                         
                            worksheet.set_column('C:C', 12, dec_format) # Alan
                            worksheet.set_column('D:E', 10, dec_format) # Hız ve Derinlik
                            worksheet.set_column('G:G', 18, num_format) # Maliyet [cite: 104]
                            
                        st.download_button("📥 Excel Raporunu İndir", buf.getvalue(), "Taskin_Analiz_Raporu.xlsx", use_container_width=True)

        except Exception as e:
            st.error(f"⚠️ Bir hata oluştu: {e}")
            st.info("Lütfen kılavuzdaki X, Y, Z (BÜYÜK HARF) ve CSV formatı kurallarına uyduğunuzdan emin olun.")