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
    if gdf.crs is None:
        gdf = gdf.set_crs(epsg=32635)
    elif gdf.crs.to_epsg() != 32635:
        gdf = gdf.to_crs(epsg=32635)
        
    gdf.geometry = gdf.geometry.buffer(0)
    gdf = gdf[~gdf.is_empty & (gdf.geometry.type.isin(['Polygon', 'MultiPolygon']))].reset_index(drop=True)
    gdf['BINA_ID'] = gdf.index + 1
    gdf['ALAN_m2'] = gdf.geometry.area.round(2)
    return gdf

def akilli_konum_analizi(gdf):
    gdf_wgs84 = gdf.to_crs(epsg=4326)
    bbox = gdf_wgs84.total_bounds
    try:
        
        tags = {
            "building": ["commercial", "industrial", "retail", "warehouse", "supermarket", "factory", "office"],
            "landuse": ["commercial", "industrial"],
            "shop": True,
            "office": True,
            "amenity": ["restaurant", "cafe", "fast_food", "bank", "clinic", "hospital", "pharmacy", "marketplace", "fuel", "car_wash"]
        }
        area_features = ox.features_from_bbox(bbox[3], bbox[1], bbox[2], bbox[0], tags=tags)
        area_features = area_features[area_features.geometry.type.isin(['Polygon', 'MultiPolygon'])]
    except: 
        area_features = gpd.GeoDataFrame()

    tipler = []
    for i, row in gdf_wgs84.iterrows():
        res = "Konut"
        if not area_features.empty:
            nearby = area_features[area_features.geometry.distance(row.geometry.centroid) < 0.0002]
            if not nearby.empty: 
                res = "Ticari/Fabrika"
                
        # Alan çok büyükse ticari diyelim
        if res == "Konut" and row['ALAN_m2'] > 1000: 
            res = "Ticari/Fabrika"
            
        tipler.append(res)
    return tipler

def taskin_analizini_yap(gdf_binalar, df_h, df_d, buffer_size=6.0):
    gdf_halkalar = gpd.GeoDataFrame(gdf_binalar[['BINA_ID']], geometry=gdf_binalar.buffer(buffer_size), crs=gdf_binalar.crs)
    
    pts_h = gpd.GeoDataFrame(df_h, geometry=gpd.points_from_xy(df_h['X'], df_h['Y']), crs=gdf_binalar.crs)
    pts_d = gpd.GeoDataFrame(df_d, geometry=gpd.points_from_xy(df_d['X'], df_d['Y']), crs=gdf_binalar.crs)
        
    join_h = gpd.sjoin(pts_h, gdf_halkalar, predicate='within')
    if len(join_h) == 0:
        st.error("⚠️ HIZ NOKTALARI BİNALARLA KESİŞMEDİ! Lütfen aşağıdaki tablodan sistemin CSV dosyanızdan hangi sütunları okuduğunu kontrol edin:")
        if not df_h.empty: st.dataframe(df_h.head())
        
    res_h = join_h[join_h['Z'] != 0].groupby('BINA_ID')['Z'].mean().round(2).reset_index().rename(columns={'Z': 'HIZ'})
    
    join_d = gpd.sjoin(pts_d, gdf_halkalar, predicate='within')
    if len(join_d) == 0:
        st.error("⚠️ DERİNLİK NOKTALARI BİNALARLA KESİŞMEDİ! Lütfen aşağıdaki tablodan sistemin CSV dosyanızdan hangi sütunları okuduğunu kontrol edin:")
        if not df_d.empty: st.dataframe(df_d.head())
        
    res_d = join_d[join_d['Z'] != 0].groupby('BINA_ID')['Z'].mean().round(2).reset_index().rename(columns={'Z': 'DERIN'})
    
    return pd.merge(res_h, res_d, on='BINA_ID', how='outer').fillna(0)

def yapisal_risk(d):
    if d <= 0.01: return "Yok"
    elif d <= 0.6: return "H1-Dusuk"
    elif d <= 1.0: return "H2-Orta"
    elif d <= 3.5: return "H3-Yuksek"
    else: return "H4-Asiri"

def defra_etiket(d, v):
    mf = 0 if (d <= 0.25 and v <= 2.0) else 1
    td = d * (v + 0.5) + mf
    if td < 0.75: return "T1-Dusuk"
    elif td < 1.25: return "T2-Hafif"
    elif td <= 2.5: return "T3-Yuksek"
    else: return "T4-CokYuk"

def maliyet_hesapla(row, k_fiyat, t_fiyat):
    d = float(row['DERIN'])
    if d <= 0.01: f = 0.0
    elif d <= 0.5: f = 0.15
    elif d <= 1.0: f = 0.18
    elif d <= 1.5: f = 0.20
    elif d <= 2.0: f = 0.21
    elif d <= 3.0: f = 0.48
    elif d <= 4.0: f = 0.70
    else: f = 1.00
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
        konut_f = st.number_input("Konut (TL/m²)", value=18200, step=1000)
        ticari_f = st.number_input("Ticari (TL/m²)", value=21500, step=1000)
    with st.expander("⚙️ Veri ve Analiz Ayarları", expanded=True):
        buffer_size = st.number_input("Tampon Bölge (Buffer) - Metre", value=6.0, step=1.0)
        has_header = st.checkbox("CSV dosyalarında X,Y,Z satırı var", value=False)
    st.markdown("---")
    st.info("📊 Verilerinizi yükledikten sonra 'Analizi Başlat' butonuna tıklayın.")

# VERİ HAZIRLAMA KILAVUZU 
with st.expander("📢 Veri Hazırlama Kılavuzu (Kritik Uyarılar)", expanded=False):
    c_k1, c_k2 = st.columns(2)
    with c_k1:
        st.markdown("""
        **🏢 Bina Verisi (ZIP):**
        - CBS yazılımları (QGIS, ArcGIS vb.) üzerinden **poligon** olarak çizilmiş binaları içermelidir.
        - Dosya içinde `.shp`, `.dbf`, `.shx`, `.prj` mutlaka bulunmalı.
        - Binalara, yan menüden belirlediğiniz **Tampon Bölge (Buffer)** değeri kadar (varsayılan 6 metre) etki alanı uygulanır.
        - Doğru analiz için sisteme yükleyeceğiniz bina verisinin projeksiyonu önceden **UTM Zone 35N (EPSG:32635)** formatına dönüştürülmüş olmalıdır.
        """)
    with c_k2:
        st.markdown("""
        **📊 Hız/Derinlik (CSV):**
        - Dosyanızdaki **ilk 3 sütun** sırasıyla **X, Y ve Z** verisi olarak otomatik okunur (Sütun başlığı zorunlu değildir).
        - Sistem; **boşluk, sekme (tab), virgül (,) veya noktalı virgül (;)** ayraçlarını otomatik algılar.
        - CSV içindeki X ve Y koordinatları bina verisiyle eşleşebilmesi için **EPSG:32635** formatında olmalıdır.
        - Ondalık sayılar için nokta veya virgül kullanabilirsiniz, sistem otomatik düzeltir.
        - *Akıllı Düzeltme:* X ve Y koordinatları ters girilirse sistem tarafından otomatik düzeltilir.
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
                    
                    def temizle(file, has_header_flag):
                        content = file.getvalue().decode('utf-8', errors='ignore').strip()
                        if not content:
                            return pd.DataFrame(columns=['X', 'Y', 'Z'])
                            
                        lines = content.split('\n')
                        
                        # Eğer kullanıcı başlık var dediyse, İLK SATIRI DİREKT ATLA. (İçinde X Y Z yazmasına gerek yok)
                        if has_header_flag and len(lines) > 0:
                            lines = lines[1:]
                            
                        import re
                        parsed_data = []
                        for line in lines:
                            line = line.strip().replace('"', '').replace("'", "")
                            if not line: continue
                          

                            if ';' in line:
                                parts = line.split(';')
                            elif '\t' in line:
                                parts = line.split('\t')
                            elif line.count(',') >= 2 and '.' in line:
                                parts = line.split(',')
                            else:
                                parts = re.split(r'\s+', line)
                                
                            # BAŞLIK, HARF VEYA BOŞLUK FARK ETMEKSİZİN İLK 3 SÜTUNU AL
                            if len(parts) >= 3:
                                parsed_data.append([parts[0], parts[1], parts[2]])
                                
                        if not parsed_data:
                            return pd.DataFrame(columns=['X', 'Y', 'Z'])
                            
                        df = pd.DataFrame(parsed_data, columns=['X', 'Y', 'Z'])

                        def safely_convert_to_float(val):
                            if pd.isna(val) or str(val).strip() == '': return 0.0
                            val = str(val).strip()
                            if '.' in val and ',' in val:
                                if val.rfind(',') > val.rfind('.'):
                                    val = val.replace('.', '').replace(',', '.')
                                else:
                                    val = val.replace(',', '')
                            elif ',' in val:
                                val = val.replace(',', '.')
                            elif val.count('.') > 1:
                                val = val.replace('.', '')
                            try:
                                return float(val)
                            except:
                                return 0.0
                                    
                        for col in ['X', 'Y', 'Z']:
                            df[col] = df[col].apply(safely_convert_to_float)
                            
                        # Türkiye koordinatlarında Y ekseni her zaman X ekseninden daha büyük bir sayıdır 
                        # Eğer kullanıcı X ve Y'yi ters kaydettiyse, otomatik olarak yerlerini değiştir!
                        if len(df) > 0 and df['X'].mean() > df['Y'].mean():
                            df['X'], df['Y'] = df['Y'], df['X']
                            
                        return df

                    df_h, df_d = temizle(hiz_csv, has_header), temizle(derin_csv, has_header)
                    gdf = onarma_ve_numaralandirma(gpd.read_file(z_path))
                    gdf['TIP'] = akilli_konum_analizi(gdf)
                    
                    analiz_res = taskin_analizini_yap(gdf, df_h, df_d, buffer_size=buffer_size)
                    final = gdf.merge(analiz_res, on='BINA_ID', how='left').fillna(0)
                    final['RISK'] = final.apply(lambda r: defra_etiket(r['DERIN'], r['HIZ']), axis=1)
                    final['YAPI_RISKI'] = final['DERIN'].apply(yapisal_risk)
                    final['MALIYET_TL'] = final.apply(lambda r: maliyet_hesapla(r, konut_f, ticari_f), axis=1)

                    st.session_state['analiz_final'] = final
                    st.session_state['analiz_tamam'] = True
                    st.rerun()

        except Exception as e:
            st.error(f"⚠️ Bir hata oluştu: {e}")
            st.info("Lütfen kılavuzdaki X, Y, Z (BÜYÜK HARF) ve CSV formatı kurallarına uyduğunuzdan emin olun.")

if st.session_state.get('analiz_tamam', False):
    final = st.session_state['analiz_final']
    
    st.markdown("---")
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
                    <span style="color: #94a3b8;">Hayati Risk:</span> <strong style="color: {color};">{r['RISK']}</strong><br>
                    <span style="color: #94a3b8;">Yapısal Hasar:</span> <strong style="color: white;">{r['YAPI_RISKI']}</strong><br>
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
        from branca.element import Template, MacroElement
        
        horizontal_legend_html = """
        <div style="display: flex; justify-content: center; align-items: center; padding: 15px; 
                    background-color: #0f172a; border-radius: 8px; margin-top: 10px; 
                    border: 1px solid rgba(255,255,255,0.1); flex-wrap: wrap; gap: 20px;">
            <strong style="color: #e2e8f0; font-size: 15px;">Risk Seviyeleri:</strong>
            <div style="display: flex; align-items: center;"><div style="width: 30px; height: 15px; background-color: gray; margin-right: 8px; border-radius: 3px;"></div> <span style="color: #e2e8f0; font-size: 14px;">Yok</span></div>
            <div style="display: flex; align-items: center;"><div style="width: 30px; height: 15px; background-color: #22c55e; margin-right: 8px; border-radius: 3px;"></div> <span style="color: #e2e8f0; font-size: 14px;">T1-Dusuk (Yeşil)</span></div>
            <div style="display: flex; align-items: center;"><div style="width: 30px; height: 15px; background-color: #eab308; margin-right: 8px; border-radius: 3px;"></div> <span style="color: #e2e8f0; font-size: 14px;">T2-Hafif (Sarı)</span></div>
            <div style="display: flex; align-items: center;"><div style="width: 30px; height: 15px; background-color: #f97316; margin-right: 8px; border-radius: 3px;"></div> <span style="color: #e2e8f0; font-size: 14px;">T3-Yuksek (Turuncu)</span></div>
            <div style="display: flex; align-items: center;"><div style="width: 30px; height: 15px; background-color: #ef4444; margin-right: 8px; border-radius: 3px;"></div> <span style="color: #e2e8f0; font-size: 14px;">T4-CokYuk (Kırmızı)</span></div>
        </div>
        """
        
        legend_template = """
        {% macro html(this, kwargs) %}
        <div style="position: absolute; bottom: 30px; left: 50%; transform: translateX(-50%); z-index: 9999; min-width: 600px; opacity: 0.9;">
        """ + horizontal_legend_html + """
        </div>
        {% endmacro %}
        """
        macro = MacroElement()
        macro._template = Template(legend_template)
        m.get_root().add_child(macro)
        
        st.components.v1.html(m._repr_html_(), height=650)
        
        # Lejantı Streamlit'te garantili görünmesi için doğrudan haritanın altına ekle
        st.markdown(horizontal_legend_html, unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)
        
        st.download_button(
            label="🗺️  Haritayı İndir (HTML)",
            data=m.get_root().render(),
            file_name="Taskin_Analiz_Haritasi.html",
            mime="text/html",
            use_container_width=True
        )

    with t2:
        st.info("💡 **Aşağıdaki tablodan 'TIP' sütununa çift tıklayarak** binanın kullanım türünü değiştirebilirsiniz.")
        
        display_df = final[['BINA_ID', 'TIP', 'ALAN_m2', 'HIZ', 'DERIN', 'RISK', 'YAPI_RISKI', 'MALIYET_TL']].copy()
        display_df['MALIYET_TL_STR'] = display_df['MALIYET_TL'].apply(lambda x: f"{x:,.0f}".replace(",", "."))
        
        edited_df = st.data_editor(
            display_df[['BINA_ID', 'TIP', 'ALAN_m2', 'HIZ', 'DERIN', 'RISK', 'YAPI_RISKI', 'MALIYET_TL_STR']],
            column_config={
                "TIP": st.column_config.SelectboxColumn("Bina Tipi", options=["Konut", "Ticari/Fabrika"], required=True),
                "BINA_ID": st.column_config.NumberColumn("Bina ID", disabled=True),
                "ALAN_m2": st.column_config.NumberColumn("Alan (m²)", disabled=True),
                "HIZ": st.column_config.NumberColumn("Hız (m/s)", disabled=True),
                "DERIN": st.column_config.NumberColumn("Derinlik (m)", disabled=True),
                "RISK": st.column_config.TextColumn("Hayati Risk (T1-T4)", disabled=True),
                "YAPI_RISKI": st.column_config.TextColumn("Yapısal Risk (H1-H4)", disabled=True),
                "MALIYET_TL_STR": st.column_config.TextColumn("Tahmini Hasar (TL)", disabled=True)
            },
            hide_index=True,
            use_container_width=True,
            key="bina_editor"
        )
        
        # Değişiklik varsa maliyeti tekrar hesapla
        if not final['TIP'].equals(edited_df['TIP']):
            final['TIP'] = edited_df['TIP']
            final['MALIYET_TL'] = final.apply(lambda r: maliyet_hesapla(r, konut_f, ticari_f), axis=1)
            st.session_state['analiz_final'] = final
            st.rerun()
            
        total_row = pd.DataFrame([{'BINA_ID': 'TOPLAM', 'MALIYET_TL': final['MALIYET_TL'].sum()}])
        excel_out = pd.concat([final[['BINA_ID', 'TIP', 'ALAN_m2', 'HIZ', 'DERIN', 'RISK', 'YAPI_RISKI', 'MALIYET_TL']], total_row], ignore_index=True)
        
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine='xlsxwriter') as writer:
            excel_out.to_excel(writer, index=False, sheet_name='AnalizRaporu')
            workbook  = writer.book
            worksheet = writer.sheets['AnalizRaporu']
            
            num_format = workbook.add_format({'num_format': '#,##0'}) 
            dec_format = workbook.add_format({'num_format': '0.00'})   
            
            worksheet.set_column('C:C', 12, dec_format) # Alan
            worksheet.set_column('D:E', 10, dec_format) # Hız ve Derinlik
            worksheet.set_column('H:H', 18, num_format) # Maliyet
            
        st.download_button("📥 Excel Raporunu İndir", buf.getvalue(), "Taskin_Analiz_Raporu.xlsx", use_container_width=True)
        
        # SHP Dışa Aktarma (Global Mapper Uyumlu)
        import zipfile
        def create_shp_zip(gdf):
            tmp_dir = tempfile.mkdtemp()
            shp_path = os.path.join(tmp_dir, "analiz_sonuclari.shp")
            
            export_gdf = gdf.copy()
            
            # Global Mapper için renk kodlarını belirle (COLOR kolonu GM tarafından otomatik tanınır)
            def get_gm_color(risk):
                c_map = {
                    'T4-CokYuk': 'RGB(239,68,68)',
                    'T3-Yuksek': 'RGB(249,115,22)',
                    'T2-Hafif': 'RGB(234,179,8)',
                    'T1-Dusuk': 'RGB(34,197,94)'
                }
                return c_map.get(risk, 'RGB(128,128,128)')
                
            export_gdf['COLOR'] = export_gdf['RISK'].apply(get_gm_color)
            export_gdf['LABEL'] = export_gdf['BINA_ID'].astype(str)
            
            istenen_kolonlar = ['BINA_ID', 'LABEL', 'TIP', 'ALAN_m2', 'HIZ', 'DERIN', 'RISK', 'YAPI_RISKI', 'MALIYET_TL', 'COLOR', 'geometry']
            mevcut_kolonlar = [c for c in istenen_kolonlar if c in export_gdf.columns]
            export_gdf = export_gdf[mevcut_kolonlar].copy()
            
            # Global Mapper'da sayılar string olarak ondalıklı düzgün görünsün
            if 'ALAN_m2' in export_gdf.columns: export_gdf['ALAN_m2'] = export_gdf['ALAN_m2'].apply(lambda x: f"{x:.2f}")
            if 'HIZ' in export_gdf.columns: export_gdf['HIZ'] = export_gdf['HIZ'].apply(lambda x: f"{x:.2f}")
            if 'DERIN' in export_gdf.columns: export_gdf['DERIN'] = export_gdf['DERIN'].apply(lambda x: f"{x:.2f}")
            if 'MALIYET_TL' in export_gdf.columns: export_gdf['MALIYET_TL'] = export_gdf['MALIYET_TL'].apply(lambda x: f"{x:,.0f}".replace(",", "."))
            
            for col in export_gdf.columns:
                if export_gdf[col].dtype == 'object':
                    export_gdf[col] = export_gdf[col].astype(str)
                    
            export_gdf.to_file(shp_path, driver="ESRI Shapefile")
            
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zipf:
                for root, dirs, files in os.walk(tmp_dir):
                    for file in files:
                        zipf.write(os.path.join(root, file), file)
            return zip_buffer.getvalue()

        shp_data = create_shp_zip(final)
        st.download_button("🗺️ Shapefile (SHP) İndir", shp_data, "Taskin_Analiz_SHP.zip", use_container_width=True)