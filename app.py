import streamlit as st
import pandas as pd
import numpy as np
import re

st.set_page_config(page_title="Suite Rentabilidad ML + Unidrop", page_icon="💰", layout="wide")

# 1. ACCESO PRIVADO
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

# 2. PANEL LATERAL
st.sidebar.header("⚙️ Parámetros de Cálculo")
porcentaje_iibb = st.sidebar.number_input("Retenciones / IIBB (%):", 0.0, 30.0, 3.5, 0.5)
costo_moto_flex = st.sidebar.number_input("Costo promedio moto Flex ($):", 0, 100000, 4500, 500)
margen_minimo_sano = st.sidebar.slider("Margen mínimo saludable (%):", 1, 50, 12)

# 3. CARGA DE PLANILLAS
st.title("💰 Centro de Control de Rentabilidad: ML + Unidrop")
col1, col2 = st.columns(2)
archivo_ml = col1.file_uploader("1️⃣ Subí tu reporte de Mercado Libre", type=["xlsx", "csv"])
archivo_unidrop = col2.file_uploader("2️⃣ Subí tu catálogo de Unidrop", type=["xlsx", "csv"])

if not archivo_ml or not archivo_unidrop:
    st.info("👆 Subí ambos archivos para comenzar el análisis.")
    st.stop()

def leer_archivo_inteligente(archivo, es_ml=False):
    if archivo.name.endswith('.xlsx'):
        xl = pd.ExcelFile(archivo)
        hoja = "Publicaciones" if (es_ml and "Publicaciones" in xl.sheet_names) else (1 if (es_ml and len(xl.sheet_names) > 1) else 0)
        df_raw = pd.read_excel(archivo, sheet_name=hoja, header=None)
    else:
        df_raw = pd.read_csv(archivo, sep=None, engine='python', header=None)
    
    fila_header = 0
    for i in range(min(15, len(df_raw))):
        valores_fila = [str(x).lower() for x in df_raw.iloc[i].values]
        if any(val.strip() == "sku" for val in valores_fila):
            fila_header = i
            break
            
    df_limpio = df_raw.iloc[fila_header + 1:].copy()
    
    cols_unicas = []
    contador = {}
    for c in df_raw.iloc[fila_header].values:
        nombre = str(c).strip()
        if nombre in contador:
            contador[nombre] += 1
            cols_unicas.append(f"{nombre}_{contador[nombre]}")
        else:
            contador[nombre] = 0
            cols_unicas.append(nombre)
            
    df_limpio.columns = cols_unicas
    return df_limpio.reset_index(drop=True)

# Función para limpiar precios con signos $, puntos de miles o comas decimales
def limpiar_moneda(serie):
    def convertir(val):
        if pd.isna(val):
            return 0.0
        if isinstance(val, (int, float)):
            return float(val)
        texto = re.sub(r'[^\d,.-]', '', str(val)).strip()
        if not texto:
            return 0.0
        # Si tiene coma y punto (ej: 15.500,50 -> formato argentino)
        if ',' in texto and '.' in texto:
            if texto.rfind(',') > texto.rfind('.'):
                texto = texto.replace('.', '').replace(',', '.')
            else:
                texto = texto.replace(',', '')
        elif ',' in texto:
            texto = texto.replace(',', '.')
        try:
            return float(texto)
        except:
            return 0.0
    return serie.apply(convertir)

df_ml = leer_archivo_inteligente(archivo_ml, es_ml=True)
df_uni = leer_archivo_inteligente(archivo_unidrop, es_ml=False)

cols_ml = list(df_ml.columns)
cols_uni = list(df_uni.columns)

def idx_aprox(lista, palabras):
    for i, col in enumerate(lista):
        for p in palabras:
            if p.lower() in str(col).lower():
                return i
    return 0

# 4. ASIGNACIÓN DE COLUMNAS
with st.expander("🔗 Paso rápido: Confirmá qué columna es cada dato", expanded=False):
    c_ml, c_uni = st.columns(2)
    with c_ml:
        st.markdown("**Mercado Libre:**")
        COL_ID_ML = st.selectbox("ID Publicación (MLA):", cols_ml, index=idx_aprox(cols_ml, ["número", "id", "publicación"]))
        COL_SKU_ML = st.selectbox("SKU en ML:", cols_ml, index=idx_aprox(cols_ml, ["sku", "código"]))
        COL_TITULO_ML = st.selectbox("Título de la publicación:", cols_ml, index=idx_aprox(cols_ml, ["título", "nombre", "producto"]))
        COL_PRECIO_ML = st.selectbox("Precio venta ($):", cols_ml, index=idx_aprox(cols_ml, ["precio"]))
        COL_TIPO_PUB = st.selectbox("Tipo publicación (Clásica/Premium):", cols_ml, index=idx_aprox(cols_ml, ["tipo", "exposición", "cuotas"]))
        COL_COMISION_ML = st.selectbox("Comisión ML ($):", cols_ml, index=idx_aprox(cols_ml, ["cargo", "comisión", "vender"]))
        COL_FORMA_ENVIO = st.selectbox("Forma / Condición de envío:", cols_ml, index=idx_aprox(cols_ml, ["forma", "logística", "envío"]))
        COL_COSTO_ENVIO_ML = st.selectbox("Costo envío ML ($):", cols_ml, index=idx_aprox(cols_ml, ["costo de envío", "envío"]))
    with c_uni:
        st.markdown("**Unidrop:**")
        COL_SKU_UNI = st.selectbox("SKU en Unidrop:", cols_uni, index=idx_aprox(cols_uni, ["sku", "código"]))
        COL_COSTO_UNI = st.selectbox("Costo producto ($):", cols_uni, index=idx_aprox(cols_uni, ["costo", "precio"]))

# 5. CRUCE Y CÁLCULOS
df_ml["SKU_LIMPIO"] = df_ml[COL_SKU_ML].astype(str).str.strip().str.upper()
df_uni["SKU_LIMPIO"] = df_uni[COL_SKU_UNI].astype(str).str.strip().str.upper()
df_uni["COSTO_LIMPIO"] = limpiar_moneda(df_uni[COL_COSTO_UNI])

df_ml = df_ml[df_ml["SKU_LIMPIO"].notna() & (~df_ml["SKU_LIMPIO"].isin(["NAN", "NONE", ""]))]

df_cruce = pd.merge(
    df_ml,
    df_uni[["SKU_LIMPIO", "COSTO_LIMPIO"]].drop_duplicates(subset=["SKU_LIMPIO"]),
    on="SKU_LIMPIO",
    how="left"
)

df_cruce["PRECIO_LIMPIO"] = limpiar_moneda(df_cruce[COL_PRECIO_ML])
df_cruce["COMISION_LIMPIA"] = limpiar_moneda(df_cruce[COL_COMISION_ML]).abs()
df_cruce["ENVIO_ML_LIMPIO"] = limpiar_moneda(df_cruce[COL_COSTO_ENVIO_ML])

def calc_envio(fila):
    forma = str(fila.get(COL_FORMA_ENVIO, "")).lower()
    costo_ml = float(fila.get("ENVIO_ML_LIMPIO", 0))
    if "flex" in forma:
        return max(0.0, costo_moto_flex - abs(costo_ml)) if costo_ml != 0 else float(costo_moto_flex)
    if "gratis" in forma or "vendedor" in forma or abs(costo_ml) > 0:
        return abs(costo_ml)
    return 0.0

df_cruce["Envío Real ($)"] = df_cruce.apply(calc_envio, axis=1)
df_cruce["IIBB Estimado ($)"] = df_cruce["PRECIO_LIMPIO"] * (porcentaje_iibb / 100)
df_cruce["Tasa_Comision_ML"] = np.where(df_cruce["PRECIO_LIMPIO"] > 0, df_cruce["COMISION_LIMPIA"] / df_cruce["PRECIO_LIMPIO"], 0.15)

df_cruce["Recibís en ML ($)"] = (
    df_cruce["PRECIO_LIMPIO"]
    - df_cruce["COMISION_LIMPIA"]
    - df_cruce["Envío Real ($)"]
    - df_cruce["IIBB Estimado ($)"]
)

df_cruce["Ganancia Neta ($)"] = df_cruce["Recibís en ML ($)"] - df_cruce["COSTO_LIMPIO"]
df_cruce["Margen (%)"] = np.where(df_cruce["PRECIO_LIMPIO"] > 0, (df_cruce["Ganancia Neta ($)"] / df_cruce["PRECIO_LIMPIO"]) * 100, 0)

divisor_precio = 1 - df_cruce["Tasa_Comision_ML"] - (porcentaje_iibb / 100) - (margen_minimo_sano / 100)
df_cruce["Precio Sugerido ($)"] = np.where(
    divisor_precio > 0.05,
    (df_cruce["COSTO_LIMPIO"] + df_cruce["Envío Real ($)"]) / divisor_precio,
    0
)

def asignar_semaforo(fila):
    if fila["Ganancia Neta ($)"] < 0:
        return "🔴 PÉRDIDA"
    if fila["Margen (%)"] < margen_minimo_sano:
        return "🟡 BAJO"
    return "🟢 RENTABLE"

df_cruce["Semáforo"] = df_cruce.apply(asignar_semaforo, axis=1)
df_cruce["Características"] = df_cruce[COL_TIPO_PUB].astype(str) + " | " + df_cruce[COL_FORMA_ENVIO].astype(str)

df_match_total = df_cruce.dropna(subset=["COSTO_LIMPIO"]).copy()
sin_match = df_cruce[df_cruce["COSTO_LIMPIO"].isna()]

# 6. PESTAÑAS INTERACTIVAS
tab1, tab2, tab3 = st.tabs(["📊 1. Publicaciones Activas", "✏️ 2. Simular Precio", "🆕 3. Cotizar Nuevo"])

with tab1:
    c_ord, c_busq = st.columns(2)
    orden_elegido = c_ord.selectbox("Ordenar tabla por:", [
        "Título de la publicación (A - Z)",
        "Peor a mejor ganancia ($)",
        "Mejor a peor ganancia ($)",
        "Margen (%)"
    ])
    filtro_texto = c_busq.text_input("🔍 Buscar por Título o SKU:", placeholder="Escribí para filtrar...")

    con_match = df_match_total.copy()
    if filtro_texto:
        con_match = con_match[
            con_match[COL_TITULO_ML].astype(str).str.contains(filtro_texto, case=False, na=False) |
            con_match["SKU_LIMPIO"].str.contains(filtro_texto, case=False, na=False)
        ]

    if orden_elegido == "Título de la publicación (A - Z)":
        con_match = con_match.sort_values(by=COL_TITULO_ML, ascending=True)
    elif orden_elegido == "Peor a mejor ganancia ($)":
        con_match = con_match.sort_values(by="Ganancia Neta ($)", ascending=True)
    elif orden_elegido == "Mejor a peor ganancia ($)":
        con_match = con_match.sort_values(by="Ganancia Neta ($)", ascending=False)
    else:
        con_match = con_match.sort_values(by="Margen (%)", ascending=True)

    m1, m2, m3 = st.columns(3)
    m1.metric("🟢 Rentables", len(con_match[con_match["Semáforo"] == "🟢 RENTABLE"]))
    m2.metric("🟡 Margen Bajo", len(con_match[con_match["Semáforo"] == "🟡 BAJO"]))
    m3.metric("🔴 Dando Pérdida", len(con_match[con_match["Semáforo"] == "🔴 PÉRDIDA"]))

    def colorear_fila(fila):
        if "🔴" in str(fila["Semáforo"]):
            return ['background-color: rgba(255, 60, 60, 0.35)'] * len(fila)
        if "🟡" in str(fila["Semáforo"]):
            return ['background-color: rgba(255, 200, 0, 0.30)'] * len(fila)
        return ['background-color: rgba(40, 200, 100, 0.25)'] * len(fila)

    # Renombramos las columnas limpias para mostrarlas prolijas
    con_match["Precio Venta ($)"] = con_match["PRECIO_LIMPIO"]
    con_match["Comisión ML ($)"] = con_match["COMISION_LIMPIA"]
