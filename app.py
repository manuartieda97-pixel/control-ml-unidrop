import streamlit as st
import pandas as pd
import numpy as np
import re

st.set_page_config(page_title="Suite Rentabilidad ML + Unidrop", page_icon="💰", layout="wide")

if "autenticado" not in st.session_state:
    st.session_state.autenticado = False

if not st.session_state.autenticado:
    st.title("🔒 Acceso Privado - Suite ML + Unidrop")
    password = st.text_input("Ingresá tu clave secreta:", type="password")
    if st.button("Entrar"):
        if password == "1234":
            st.session_state.autenticado = True
            st.rerun()
        else:
            st.error("❌ Contraseña incorrecta")
    st.stop()

st.sidebar.header("⚙️ Parámetros de Cálculo")
porcentaje_iibb = st.sidebar.number_input("Retenciones / IIBB (%):", 0.0, 30.0, 3.5, 0.5)
costo_moto_flex = st.sidebar.number_input("Costo promedio moto Flex ($):", 0, 100000, 4500, 500)
margen_minimo_sano = st.sidebar.slider("Margen mínimo saludable (%):", 1, 50, 12)

st.title("💰 Centro de Control de Rentabilidad: ML + Unidrop")
col1, col2 = st.columns(2)
archivo_ml = col1.file_uploader("1️⃣ Subí tu reporte de Mercado Libre", type=["xlsx", "csv"])
archivo_unidrop = col2.file_uploader("2️⃣ Subí tu catálogo de Unidrop", type=["xlsx", "csv"])

if not archivo_ml or not archivo_unidrop:
    st.info("👆 Subí ambos archivos para comenzar el análisis.")
    st.stop()

def leer_ml(archivo):
    if archivo.name.endswith('.xlsx'):
        xl = pd.ExcelFile(archivo)
        hoja = next((h for h in xl.sheet_names if "publicacion" in h.lower()), xl.sheet_names[-1])
        df_raw = pd.read_excel(archivo, sheet_name=hoja, header=None)
    else:
        df_raw = pd.read_csv(archivo, sep=None, engine='python', header=None)
    fila_titulos = 2 if len(df_raw) > 3 else 0
    df = df_raw.iloc[fila_titulos + 1:].copy()
    cols, cont = [], {}
    for c in df_raw.iloc[fila_titulos].values:
        n = str(c).strip()
        cont[n] = cont.get(n, -1) + 1
        cols.append(f"{n}_{cont[n]}" if cont[n] > 0 else n)
    df.columns = cols
    return df.reset_index(drop=True)

def limpiar_moneda(serie):
    def convertir(val):
        if pd.isna(val): return 0.0
        if isinstance(val, (int, float)): return float(val)
        texto = re.sub(r'[^\d,.-]', '', str(val)).strip()
        if not texto: return 0.0
        if ',' in texto and '.' in texto:
            texto = texto.replace('.', '').replace(',', '.') if texto.rfind(',') > texto.rfind('.') else texto.replace(',', '')
        elif ',' in texto:
            texto = texto.replace(',', '.')
        try: return float(texto)
        except: return 0.0
    return serie.apply(convertir)

# Buscador exacto que evita confundir "Código universal" con "SKU" o "Número de producto" con "Título"
def idx_exacto(lista, exactas, parciales, excluir=[]):
    for i, col in enumerate(lista):
        c_low = str(col).lower().strip()
        if any(ex in c_low for ex in excluir): continue
        if c_low in exactas: return i
    for i, col in enumerate(lista):
        c_low = str(col).lower().strip()
        if any(ex in c_low for ex in excluir): continue
        if any(p in c_low for p in parciales): return i
    return 0

df_ml = leer_ml(archivo_ml)
df_uni = pd.read_excel(archivo_unidrop) if archivo_unidrop.name.endswith('.xlsx') else pd.read_csv(archivo_unidrop, sep=None, engine='python')
cols_ml, cols_uni = list(df_ml.columns), list(df_uni.columns)

with st.expander("🔗 Verificación de columnas (revisá que SKU y Título estén bien)", expanded=True):
    c_ml, c_uni = st.columns(2)
    COL_ID_ML = c_ml.selectbox("ID Publicación (MLA):", cols_ml, index=idx_exacto(cols_ml, ["número de publicación"], ["publicación"]))
    COL_SKU_ML = c_ml.selectbox("SKU en ML:", cols_ml, index=idx_exacto(cols_ml, ["sku", "número de producto"], ["sku"], excluir=["universal"]))
    COL_TITULO_ML = c_ml.selectbox("Título de la publicación:", cols_ml, index=idx_exacto(cols_ml, ["título"], ["título"], excluir=["número"]))
    COL_PRECIO_ML = c_ml.selectbox("Precio venta ($):", cols_ml, index=idx_exacto(cols_ml, ["precio"], ["precio"]))
    COL_TIPO_PUB = c_ml.selectbox("Tipo publicación (Clásica/Premium):", cols_ml, index=idx_exacto(cols_ml, ["tipo de publicación"], ["tipo", "exposición"]))
    COL_COMISION_ML = c_ml.selectbox("Comisión ML ($):", cols_ml, index=idx_exacto(cols_ml, ["cargo por vender"], ["cargo", "comisión"]))
    COL_FORMA_ENVIO = c_ml.selectbox("Forma envío:", cols_ml, index=idx_exacto(cols_ml, ["forma de envío"], ["forma", "logística", "envío"]))
    COL_COSTO_ENVIO_ML = c_ml.selectbox("Costo envío ML ($):", cols_ml, index=idx_exacto(cols_ml, ["costo de envío"], ["costo de envío"]))
    COL_SKU_UNI = c_uni.selectbox("SKU en Unidrop:", cols_uni, index=idx_exacto(cols_uni, ["sku"], ["sku", "código"]))
    COL_COSTO_UNI = c_uni.selectbox("Costo producto ($):", cols_uni, index=idx_exacto(cols_uni, ["costo sin iva", "costo"], ["costo", "precio"]))

df_ml["SKU_LIMPIO"] = df_ml[COL_SKU_ML].astype(str).str.strip().str.upper()
df_uni["SKU_LIMPIO"] = df_uni[COL_SKU_UNI].astype(str).str.strip().str.upper()
df_uni["COSTO_LIMPIO"] = limpiar_moneda(df_uni[COL_COSTO_UNI])
df_ml = df_ml[df_ml["SKU_LIMPIO"].notna() & (~df_ml["SKU_LIMPIO"].isin(["NAN", "NONE", ""]))]

df_cruce = pd.merge(df_ml, df_uni[["SKU_LIMPIO", "COSTO_LIMPIO"]].drop_duplicates(subset=["SKU_LIMPIO"]), on="SKU_LIMPIO", how="left")
df_cruce["PRECIO_LIMPIO"] = limpiar_moneda(df_cruce[COL_PRECIO_ML])
df_cruce["COMISION_LIMPIA"] = limpiar_moneda(df_cruce[COL_COMISION_ML]).abs()
df_cruce["ENVIO_ML_LIMPIO"] = limpiar_moneda(df_cruce[COL_COSTO_ENVIO_ML])

def calc_envio(fila):
    forma = str(fila.get(COL_FORMA_ENVIO, "")).lower()
    costo_ml = float(fila.get("ENVIO_ML_LIMPIO", 0))
    if "flex" in forma: return max(0.0, costo_moto_flex - abs(costo_ml)) if costo_ml != 0 else float(costo_moto_flex)
    if "gratis" in forma or "vendedor" in forma or abs(costo_ml) > 0: return abs(costo_ml)
    return 0.0

df_cruce["Envío Real ($)"] = df_cruce.apply(calc_envio, axis=1)
df_cruce["IIBB Estimado ($)"] = df_cruce["PRECIO_LIMPIO"] * (porcentaje_iibb / 100)
df_cruce["Tasa_Comision_ML"] = np.where(df_cruce["PRECIO_LIMPIO"] > 0, df_cruce["COMISION_LIMPIA"] / df_cruce["PRECIO_LIMPIO"], 0.15)
df_cruce["Recibís en ML ($)"] = df_cruce["PRECIO_LIMPIO"] - df_cruce["COMISION_LIMPIA"] - df_cruce["Envío Real ($)"] - df_cruce["IIBB Estimado ($)"]
df_cruce["Ganancia Neta ($)"] = df_cruce["Recibís en ML ($)"] - df_cruce["COSTO_LIMPIO"]
df_cruce["Margen (%)"] = np.where(df_cruce["PRECIO_LIMPIO"] > 0, (df_cruce["Ganancia Neta ($)"] / df_cruce["PRECIO_LIMPIO"]) * 100, 0)

divisor = 1 - df_cruce["Tasa_Comision_ML"] - (porcentaje_iibb / 100) - (margen_minimo_sano / 100)
df_cruce["Precio Sugerido ($)"] = np.where(divisor > 0.05, (df_cruce["COSTO_LIMPIO"] + df_cruce["Envío Real ($)"]) / divisor, 0)
df_cruce["Semáforo"] = np.where(df_cruce["Ganancia Neta ($)"] < 0, "🔴 PÉRDIDA", np.where(df_cruce["Margen (%)"] < margen_minimo_sano, "🟡 BAJO", "🟢 RENTABLE"))
df_cruce["Características"] = df_cruce[COL_TIPO_PUB].astype(str) + " | " + df_cruce[COL_FORMA_ENVIO].astype(str)

df_match_total = df_cruce.dropna(subset=["COSTO_LIMPIO"]).copy()
sin_match = df_cruce[df_cruce["COSTO_LIMPIO"].isna()]

tab1, tab2, tab3 = st.tabs(["📊 1. Publicaciones Activas", "✏️ 2. Simular Precio", "🆕 3. Cotizar Nuevo"])

with tab1:
    c_ord, c_busq = st.columns(2)
    orden = c_ord.selectbox("Ordenar tabla por:", ["Título (A - Z)", "Peor a mejor ganancia ($)", "Mejor a peor ganancia ($)", "Margen (%)"])
    filtro = c_busq.text_input("🔍 Buscar por Título o SKU:")
    df_t = df_match_total.copy()
    if filtro:
        df_t = df_t[df_t[COL_TITULO_ML].astype(str).str.contains(filtro, case=False, na=False) | df_t["SKU_LIMPIO"].str.contains(filtro, case=False, na=False)]
    col_ord = COL_TITULO_ML if orden == "Título (A - Z)" else ("Margen (%)" if orden == "Margen (%)" else "Ganancia Neta ($)")
    df_t = df_t.sort_values(by=col_ord, ascending=(orden != "Mejor a peor ganancia ($)"))

    m1, m2, m3 = st.columns(3)
    m1.metric("🟢 Rentables", len(df_t[df_t["Semáforo"] == "🟢 RENTABLE"]))
    m2.metric("🟡 Margen Bajo", len(df_t[df_t["Semáforo"] == "🟡 BAJO"]))
    m3.metric("🔴 Dando Pérdida", len(df_t[df_t["Semáforo"] == "🔴 PÉRDIDA"]))

    def pintar(f):
        c = 'rgba(255, 60, 60, 0.35)' if "🔴" in str(f["Semáforo"]) else ('rgba(255, 200, 0, 0.30)' if "🟡" in str(f["Semáforo"]) else 'rgba(40, 200, 100, 0.25)')
        return [f'background-color: {c}'] * len(f)

    df_t["Precio Venta ($)"] = df_t["PRECIO_LIMPIO"]
    df_t["Comisión ML ($)"] = df_t["COMISION_LIMPIA"]
    df_t["Costo Unidrop ($)"] = df_t["COSTO_LIMPIO"]
    cols = list(dict.fromkeys(["Semáforo", COL_TITULO_ML, "SKU_LIMPIO", "Características", "Precio Venta ($)", "Comisión ML ($)", "Envío Real ($)", "IIBB Estimado ($)", "Recibís en ML ($)", "Costo Unidrop ($)", "Ganancia Neta ($)", "Margen (%)", "Precio Sugerido ($)"]))
    st.dataframe(df_t[cols].round(2).style.apply(pintar, axis=1), use_container_width=True, hide_index=True)

    if not sin_match.empty:
        st.warning(f"⚠️ Hay {len(sin_match)} publicaciones cuyo SKU no figura en Unidrop:")
        st.dataframe(sin_match[list(dict.fromkeys([COL_ID_ML, "SKU_LIMPIO", COL_TITULO_ML, COL_PRECIO_ML]))], use_container_width=True, hide_index=True)

with tab2:
    if not df_match_total.empty:
        opciones = df_match_total[COL_ID_ML].astype(str) + " || " + df_match_total[COL_TITULO_ML].astype(str) + " (" + df_match_total["SKU_LIMPIO"] + ")"
        sel = st.selectbox("Elegí publicación:", opciones)
        id_sel = next(iter(sel.split(" || ")))
        fila = next(iter(df_match_total[df_match_total[COL_ID_ML].astype(str) == id_sel].to_dict('records')))
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Precio Actual ML", f"${fila['PRECIO_LIMPIO']:,.2f}")
        c2.metric("Recibís Actual ML", f"${fila['Recibís en ML ($)']:,.2f}")
        c3.metric("Costo Unidrop", f"${fila['COSTO_LIMPIO']:,.2f}")
