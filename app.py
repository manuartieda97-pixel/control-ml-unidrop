import streamlit as st
import pandas as pd
import numpy as np
import re
from difflib import SequenceMatcher

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

# PANEL LATERAL CON PARÁMETROS REALES DE ML ARGENTINA
st.sidebar.header("⚙️ Parámetros de Cálculo")
porcentaje_iibb = st.sidebar.number_input("Retenciones / IIBB (%):", 0.0, 30.0, 3.5, 0.5)
comision_clasica = st.sidebar.number_input("Comisión ML Sin Cuotas (%):", 0.0, 40.0, 15.5, 0.5)
comision_bajo_interes = st.sidebar.number_input("Comisión ML Cuotas Bajo Interés (%):", 0.0, 40.0, 20.0, 0.5)
comision_premium = st.sidebar.number_input("Comisión ML Con Cuotas (%):", 0.0, 40.0, 28.0, 0.5)
costo_envio_gratis_prom = st.sidebar.number_input("Costo promedio Envío Gratis ML ($):", 0, 100000, 6500, 500)
costo_moto_flex = st.sidebar.number_input("Costo promedio moto Flex ($):", 0, 100000, 4500, 500)
margen_minimo_sano = st.sidebar.slider("Margen mínimo saludable (%):", 1, 50, 12)
usar_costo_con_iva = st.sidebar.checkbox("Usar Costo Total con IVA de Unidrop", value=True)

st.title("💰 Centro de Control de Rentabilidad: ML + Unidrop")
col1, col2 = st.columns(2)
archivo_ml = col1.file_uploader("1️⃣ Subí tu reporte de Mercado Libre", type=["xlsx", "csv"])
archivo_unidrop = col2.file_uploader("2️⃣ Subí tu catálogo de Unidrop", type=["xlsx", "csv"])

if not archivo_ml or not archivo_unidrop:
    st.info("👆 Subí ambos archivos para comenzar el análisis.")
    st.stop()

# LECTOR EXACTO PARA PLANILLA DE EDICIÓN MASIVA DE ML
def leer_ml(archivo):
    if archivo.name.endswith('.xlsx'):
        xl = pd.ExcelFile(archivo)
        hojas_candidatas = [h for h in xl.sheet_names if "publicacion" in h.lower()] + xl.sheet_names
    else:
        hojas_candidatas = [None]

    for hoja in hojas_candidatas:
        if hoja is not None:
            df_raw = pd.read_excel(archivo, sheet_name=hoja, header=None)
        else:
            df_raw = pd.read_csv(archivo, sep=None, engine='python', header=None)

        for i in range(min(60, len(df_raw))):
            vals = [str(x).strip().lower() for x in df_raw.iloc[i].values]
            if "número de publicación" in vals and "precio" in vals:
                df = df_raw.iloc[i + 1:].copy()
                df.columns = [str(c).strip() for c in df_raw.iloc[i].values]
                df = df[df["Número de publicación"].astype(str).str.startswith("MLA", na=False)].reset_index(drop=True)
                return df
    return pd.DataFrame()

df_ml = leer_ml(archivo_ml)
if df_ml.empty:
    st.error("❌ No se encontraron publicaciones válidas (MLA) con la columna 'Precio' en el archivo de Mercado Libre.")
    st.stop()

df_uni = pd.read_excel(archivo_unidrop) if archivo_unidrop.name.endswith('.xlsx') else pd.read_csv(archivo_unidrop, sep=None, engine='python')
df_uni.columns = [str(c).strip() for c in df_uni.columns]

# Limpieza de costos Unidrop
col_costo_elegida = "Costo total" if (usar_costo_con_iva and "Costo total" in df_uni.columns) else "Costo sin IVA"
df_uni["COSTO_NUM"] = pd.to_numeric(df_uni[col_costo_elegida], errors='coerce').fillna(0)
df_uni["DESC_NORM"] = df_uni["Descripción"].astype(str).str.lower().str.strip()

# EMPAREJAMIENTO INTELIGENTE POR TÍTULO + VARIANTE DE COLOR
def buscar_mejor_match_unidrop(fila_ml):
    titulo_ml = str(fila_ml.get("Título", "")).lower()
    variante_ml = str(fila_ml.get("Variantes", "")).lower()
    texto_ml = f"{titulo_ml} {variante_ml}".strip()
    
    palabras_ml = set(re.findall(r'\b[a-z0-9]{2,}\b', texto_ml)) - {"de", "con", "para", "en", "el", "la", "los", "las", "por", "un", "una", "color"}
    
    mejor_score = 0
    mejor_fila = None
    
    for _, row_u in df_uni.iterrows():
        desc_u = row_u["DESC_NORM"]
        palabras_u = set(re.findall(r'\b[a-z0-9]{2,}\b', desc_u)) - {"de", "con", "para", "en", "el", "la", "los", "las", "por", "un", "una", "color"}
        
        if not palabras_ml or not palabras_u:
            continue
            
        coincidencias = len(palabras_ml.intersection(palabras_u))
        ratio_palabras = coincidencias / max(len(palabras_ml), 1)
        similitud_texto = SequenceMatcher(None, texto_ml, desc_u).ratio()
        score = (ratio_palabras * 0.7) + (similitud_texto * 0.3)
        
        for color in ["negro", "negra", "blanco", "blanca", "gris", "azul", "rojo", "verde", "naranja", "fucsia", "violeta", "plateado"]:
            if color in texto_ml and color in desc_u:
                score += 0.25
                
        if score > mejor_score:
            mejor_score = score
            mejor_fila = row_u
            
    if mejor_fila is not None and mejor_score >= 0.35:
        return pd.Series([mejor_fila["SKU"], mejor_fila["Descripción"], mejor_fila["COSTO_NUM"]])
    return pd.Series([None, None, np.nan])

df_ml[["SKU Unidrop", "Producto Unidrop", "Costo Unidrop ($)"]] = df_ml.apply(buscar_mejor_match_unidrop, axis=1)

# CÁLCULO FINANCIERO SEGÚN CUOTAS Y ENVÍO REAL DE TU PLANILLA ML
df_ml["Precio Venta ($)"] = pd.to_numeric(df_ml["Precio"], errors='coerce').fillna(0)
df_ml = df_ml[df_ml["Precio Venta ($)"] > 0].copy()

def calcular_finanzas_fila(fila):
    precio = fila["Precio Venta ($)"]
    cuotas_txt = str(fila.get("Cuotas", "")).lower()
    envio_txt = str(fila.get("Costo de envío", "")).lower()
    forma_txt = str(fila.get("Forma de entrega", "")).lower()
    
    if "agregar cuotas" in cuotas_txt and "no" not in cuotas_txt:
        tasa_com = comision_premium / 100
        badge_cuotas = "💳 Con Cuotas (Premium)"
    elif "bajo" in cuotas_txt:
        tasa_com = comision_bajo_interes / 100
        badge_cuotas = "💳 Cuotas Bajo Interés"
    else:
        tasa_com = comision_clasica / 100
        badge_cuotas = "💵 Sin Cuotas (Clásica)"
        
    comision_pesos = precio * tasa_com
    
    if "gratis" in envio_txt:
        costo_envio = float(costo_envio_gratis_prom)
        badge_envio = "📦 Envío Gratis (A tu cargo)"
    else:
        costo_envio = 0.0
        badge_envio = "🛒 Envío a cargo comprador"
        
    if "flex" in forma_txt:
        badge_envio += " + Flex"
        
    iibb_pesos = precio * (porcentaje_iibb / 100)
    recibis_ml = precio - comision_pesos - costo_envio - iibb_pesos
    costo_uni = fila["Costo Unidrop ($)"]
    ganancia = recibis_ml - costo_uni if pd.notna(costo_uni) else np.nan
    margen = (ganancia / precio * 100) if (pd.notna(ganancia) and precio > 0) else np.nan
    
    divisor = 1 - tasa_com - (porcentaje_iibb / 100) - (margen_minimo_sano / 100)
    precio_sug = ((costo_uni + costo_envio) / divisor) if (pd.notna(costo_uni) and divisor > 0.05) else 0.0
    
    return pd.Series([f"{badge_cuotas} | {badge_envio}", comision_pesos, costo_envio, iibb_pesos, recibis_ml, ganancia, margen, precio_sug, tasa_com])

df_ml[["Condiciones (Cuotas y Envío)", "Comisión Est. ($)", "Envío Est. ($)", "IIBB Est. ($)", "Recibís en ML ($)", "Ganancia Neta ($)", "Margen (%)", "Precio Sugerido ($)", "Tasa_Com"]] = df_ml.apply(calcular_finanzas_fila, axis=1)

df_ml["Semáforo"] = np.where(df_ml["Ganancia Neta ($)"].isna(), "⚪ SIN VINCULAR", np.where(df_ml["Ganancia Neta ($)"] < 0, "🔴 PÉRDIDA", np.where(df_ml["Margen (%)"] < margen_minimo_sano, "🟡 BAJO", "🟢 RENTABLE")))

df_vinculadas = df_ml.dropna(subset=["Costo Unidrop ($)"]).copy()
df_sin_vincular = df_ml[df_ml["Costo Unidrop ($)"].isna()].copy()

# INTERFAZ Y SEMÁFORO INTERACTIVO
vista = st.radio("Seleccioná una sección:", ["📊 1. Publicaciones Activas", "✏️ 2. Simular Precio", "🆕 3. Cotizar Nuevo"], horizontal=True)
st.divider()

if vista == "📊 1. Publicaciones Activas":
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("📦 Total Analizadas", len(df_vinculadas))
    m2.metric("🟢 Rentables", len(df_vinculadas[df_vinculadas["Semáforo"] == "🟢 RENTABLE"]))
    m3.metric("🟡 Margen Bajo", len(df_vinculadas[df_vinculadas["Semáforo"] == "🟡 BAJO"]))
    m4.metric("🔴 Dando Pérdida", len(df_vinculadas[df_vinculadas["Semáforo"] == "🔴 PÉRDIDA"]))

    c_col, c_ord, c_busq = st.columns(3)
    filtro_color = c_col.selectbox("🚦 Filtrar por Color:", ["Todos los colores", "🔴 Solo Pérdidas", "🟡 Solo Margen Bajo", "🟢 Solo Rentables"])
    orden = c_ord.selectbox("Ordenar tabla por:", ["Título (A - Z)", "Peor a mejor ganancia ($)", "Mejor a peor ganancia ($)", "Margen (%)"])
    filtro = c_busq.text_input("🔍 Buscar por Título o SKU:")

df_t = df_vinculadas.copy()
    if filtro_color == "🔴 Solo Pérdidas": df_t = df_t[df_t["Semáforo"] == "🔴 PÉRDIDA"]
    if filtro_color == "🟡 Solo Margen Bajo": df_t = df_t[df_t["Semáforo"] == "🟡 BAJO"]
    if filtro_color == "🟢 Solo Rentables": df_t = df_t[df_t["Semáforo"] == "🟢 RENTABLE"]
    if filtro: df_t = df_t[df_t["Título"].str.contains(filtro, case=False, na=False) | df_t["SKU Unidrop"].str.contains(filtro, case=False, na=False)]

    col_ord = "Título" if orden == "Título (A - Z)" else ("Margen (%)" if orden == "Margen (%)" else "Ganancia Neta ($)")
    df_t = df_t.sort_values(by=col_ord, ascending=(orden != "Mejor a peor ganancia ($)"))

    def pintar(f):
        c = 'rgba(255, 60, 60, 0.35)' if "🔴" in str(f["Semáforo"]) else ('rgba(255, 200, 0, 0.30)' if "🟡" in str(f["Semáforo"]) else 'rgba(40, 200, 100, 0.25)')
        return [f'background-color: {c}'] * len(f)

    cols_ver = ["Semáforo", "Título", "Variantes", "SKU Unidrop", "Condiciones (Cuotas y Envío)", "Precio Venta ($)", "Comisión Est. ($)", "Envío Est. ($)", "IIBB Est. ($)", "Recibís en ML ($)", "Costo Unidrop ($)", "Ganancia Neta ($)", "Margen (%)", "Precio Sugerido ($)"]
    st.dataframe(df_t[cols_ver].round(2).style.apply(pintar, axis=1), use_container_width=True, hide_index=True)

    if not df_sin_vincular.empty:
        st.warning(f"⚠️ {len(df_sin_vincular)} publicaciones no encontraron coincidencia automática en Unidrop:")
        st.dataframe(df_sin_vincular[["Número de publicación", "Título", "Variantes", "Precio Venta ($)"]], use_container_width=True, hide_index=True)
