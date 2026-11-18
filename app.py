import streamlit as st
import pandas as pd
import numpy as np

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

# Lector inteligente de archivos
def leer_archivo_inteligente(archivo, es_ml=False):
    if archivo.name.endswith('.xlsx'):
        xl = pd.ExcelFile(archivo)
        hoja = 1 if (es_ml and len(xl.sheet_names) > 1) else 0
        df_raw = pd.read_excel(archivo, sheet_name=hoja, header=None)
    else:
        df_raw = pd.read_csv(archivo, sep=None, engine='python', header=None)
    
    fila_header = 0
    for i in range(min(15, len(df_raw))):
        valores_fila = [str(x).lower() for x in df_raw.iloc[i].values]
        if any(palabra in val for val in valores_fila for palabra in ["sku", "precio", "costo", "título", "publicación"]):
            fila_header = i
            break
            
    df_limpio = df_raw.iloc[fila_header + 1:].copy()
    df_limpio.columns = [str(c).strip() for c in df_raw.iloc[fila_header].values]
    return df_limpio.reset_index(drop=True)

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
with st.expander("🔗 Paso rápido: Confirmá qué columna es cada dato", expanded=True):
    c_ml, c_uni = st.columns(2)
    with c_ml:
        st.markdown("**Mercado Libre:**")
        COL_ID_ML = st.selectbox("ID Publicación (MLA):", cols_ml, index=idx_aprox(cols_ml, ["número", "id", "publicación"]))
        COL_SKU_ML = st.selectbox("SKU en ML:", cols_ml, index=idx_aprox(cols_ml, ["sku", "código"]))
        COL_TITULO_ML = st.selectbox("Título:", cols_ml, index=idx_aprox(cols_ml, ["título", "nombre", "producto"]))
        COL_PRECIO_ML = st.selectbox("Precio venta ($):", cols_ml, index=idx_aprox(cols_ml, ["precio"]))
        COL_TIPO_PUB = st.selectbox("Tipo publicación:", cols_ml, index=idx_aprox(cols_ml, ["tipo", "exposición", "cuotas"]))
        COL_COMISION_ML = st.selectbox("Comisión ML ($):", cols_ml, index=idx_aprox(cols_ml, ["cargo", "comisión", "vender"]))
        COL_FORMA_ENVIO = st.selectbox("Forma envío:", cols_ml, index=idx_aprox(cols_ml, ["forma", "logística", "envío"]))
        COL_ENVIO_GRATIS = st.selectbox("¿Envío gratis?:", cols_ml, index=idx_aprox(cols_ml, ["gratis"]))
        COL_COSTO_ENVIO_ML = st.selectbox("Costo envío ML ($):", cols_ml, index=idx_aprox(cols_ml, ["costo de envío", "envío"]))
    with c_uni:
        st.markdown("**Unidrop:**")
        COL_SKU_UNI = st.selectbox("SKU en Unidrop:", cols_uni, index=idx_aprox(cols_uni, ["sku", "código"]))
        COL_COSTO_UNI = st.selectbox("Costo producto ($):", cols_uni, index=idx_aprox(cols_uni, ["costo", "precio"]))

# 5. CRUCE Y CÁLCULOS
df_ml["SKU_LIMPIO"] = df_ml[COL_SKU_ML].astype(str).str.strip().str.upper()
df_uni["SKU_LIMPIO"] = df_uni[COL_SKU_UNI].astype(str).str.strip().str.upper()
df_uni[COL_COSTO_UNI] = pd.to_numeric(df_uni[COL_COSTO_UNI], errors='coerce').fillna(0)

df_cruce = pd.merge(
    df_ml,
    df_uni[["SKU_LIMPIO", COL_COSTO_UNI]].drop_duplicates(subset=["SKU_LIMPIO"]),
    on="SKU_LIMPIO",
    how="left"
)

df_cruce[COL_PRECIO_ML] = pd.to_numeric(df_cruce[COL_PRECIO_ML], errors='coerce').fillna(0)
df_cruce[COL_COMISION_ML] = pd.to_numeric(df_cruce[COL_COMISION_ML], errors='coerce').fillna(0).abs()

def calc_envio(fila):
    forma = str(fila.get(COL_FORMA_ENVIO, "")).lower()
    gratis = str(fila.get(COL_ENVIO_GRATIS, "")).lower()
    costo_ml = float(pd.to_numeric(fila.get(COL_COSTO_ENVIO_ML, 0), errors='coerce') or 0)
    if "flex" in forma:
        return costo_moto_flex - costo_ml if costo_ml < 0 else costo_moto_flex
    if "sí" in gratis or "si" in gratis or "gratis" in gratis:
        return abs(costo_ml)
    return 0.0

df_cruce["Envío Real ($)"] = df_cruce.apply(calc_envio, axis=1)
df_cruce["IIBB Estimado ($)"] = df_cruce[COL_PRECIO_ML] * (porcentaje_iibb / 100)
df_cruce["Tasa_Comision_ML"] = np.where(df_cruce[COL_PRECIO_ML] > 0, df_cruce[COL_COMISION_ML] / df_cruce[COL_PRECIO_ML], 0.15)

df_cruce["Ganancia Neta ($)"] = (
    df_cruce[COL_PRECIO_ML]
    - df_cruce[COL_COMISION_ML]
    - df_cruce["Envío Real ($)"]
    - df_cruce["IIBB Estimado ($)"]
    - df_cruce[COL_COSTO_UNI]
)
df_cruce["Margen (%)"] = np.where(df_cruce[COL_PRECIO_ML] > 0, (df_cruce["Ganancia Neta ($)"] / df_cruce[COL_PRECIO_ML]) * 100, 0)

divisor_precio = 1 - df_cruce["Tasa_Comision_ML"] - (porcentaje_iibb / 100) - (margen_minimo_sano / 100)
df_cruce["Precio Sugerido ($)"] = np.where(
    divisor_precio > 0.05,
    (df_cruce[COL_COSTO_UNI] + df_cruce["Envío Real ($)"]) / divisor_precio,
    0
)

con_match = df_cruce.dropna(subset=[COL_COSTO_UNI]).sort_values(by="Ganancia Neta ($)", ascending=True)
sin_match = df_cruce[df_cruce[COL_COSTO_UNI].isna()]

# 6. PESTAÑAS INTERACTIVAS
tab1, tab2, tab3 = st.tabs(["📊 1. Publicaciones Activas", "✏️ 2. Simular Precio", "🆕 3. Cotizar Nuevo"])

with tab1:
    def colorear_semaforo(fila):
        if fila["Ganancia Neta ($)"] < 0:
            return ['background-color: rgba(255, 75, 75, 0.25)'] * len(fila)
        if fila["Margen (%)"] < margen_minimo_sano:
            return ['background-color: rgba(255, 215, 0, 0.25)'] * len(fila)
        return ['background-color: rgba(46, 204, 113, 0.20)'] * len(fila)

    cols_tabla = [
        COL_ID_ML, "SKU_LIMPIO", COL_TITULO_ML, COL_TIPO_PUB, COL_PRECIO_ML, 
        COL_COMISION_ML, "Envío Real ($)", "IIBB Estimado ($)", COL_COSTO_UNI, 
        "Ganancia Neta ($)", "Margen (%)", "Precio Sugerido ($)"
    ]
    cols_unicas = list(dict.fromkeys(cols_tabla))
    df_ver = con_match[cols_unicas].round(2)
    st.dataframe(df_ver.style.apply(colorear_semaforo, axis=1), use_container_width=True, hide_index=True)

    if not sin_match.empty:
        st.warning(f"⚠️ Hay {len(sin_match)} publicaciones cuyo SKU no figura en Unidrop:")
        st.dataframe(sin_match[[COL_ID_ML, "SKU_LIMPIO", COL_TITULO_ML, COL_PRECIO_ML]], hide_index=True)

with tab2:
    if not con_match.empty:
        opciones_pub = con_match[COL_ID_ML].astype(str) + " | " + con_match["SKU_LIMPIO"] + " - " + con_match[COL_TITULO_ML].astype(str)
        seleccion = st.selectbox("Elegí publicación:", opciones_pub)
        id_sel = seleccion.split(" | ")[0]
        fila_sel = con_match[con_match[COL_ID_ML].astype(str) == id_sel].iloc[0]
        
        c1, c2, c3 = st.columns(3)
        c1.metric("Precio Actual ML", f"${fila_sel[COL_PRECIO_ML]:,.2f}")
        c2.metric("Costo Unidrop", f"${fila_sel[COL_COSTO_UNI]:,.2f}")
        c3.metric("Ganancia Actual", f"${fila_sel['Ganancia Neta ($)']:,.2f}", f"{fila_sel['Margen (%)']:.1f}%")

        nuevo_precio = st.number_input("NUEVO precio de prueba ($):", min_value=1.0, value=float(fila_sel[COL_PRECIO_ML]), step=500.0)
        nueva_comision = nuevo_precio * fila_sel["Tasa_Comision_ML"]
        nuevo_iibb = nuevo_precio * (porcentaje_iibb / 100)
        nueva_ganancia = nuevo_precio - nueva_comision - fila_sel["Envío Real ($)"] - nuevo_iibb - fila_sel[COL_COSTO_UNI]
        nuevo_margen = (nueva_ganancia / nuevo_precio) * 100

        r1, r2, r3 = st.columns(3)
        r1.metric("Comisión + IIBB", f"${(nueva_comision + nuevo_iibb):,.2f}")
        r2.metric("Nueva Ganancia", f"${nueva_ganancia:,.2f}", delta=f"${(nueva_ganancia - fila_sel['Ganancia Neta ($)']):,.2f}")
        r3.metric("Nuevo Margen", f"{nuevo_margen:.1f}%", delta=f"{(nuevo_margen - fila_sel['Margen (%)']):.1f}%")

with tab3:
    sku_buscar = st.selectbox("Seleccioná SKU de Unidrop:", df_uni["SKU_LIMPIO"].unique())
    prod_uni = df_uni[df_uni["SKU_LIMPIO"] == sku_buscar].iloc[0]
    costo_base = float(prod_uni[COL_COSTO_UNI])
    st.info(f"📦 **Costo en Unidrop para {sku_buscar}:** ${costo_base:,.2f}")

    col_a, col_b, col_c = st.columns(3)
    precio_tentativo = col_a.number_input("Precio estimado ML ($):", min_value=1.0, value=max(costo_base * 1.6, 100.0), step=500.0)
    comision_est = col_b.number_input("Comisión ML (%):", 0.0, 40.0, 15.5, 0.5)
    tipo_envio_nuevo = col_c.selectbox("Logística:", ["A cargo del comprador ($0)", "Envío Gratis Mercado Envíos", "Envío Flex"])

    costo_envio_me = st.number_input("Costo estimado Mercado Envíos ($):", 0, 100000, 5500, 500)
    costo_envio_sim = costo_envio_me if tipo_envio_nuevo == "Envío Gratis Mercado Envíos" else (costo_moto_flex if tipo_envio_nuevo == "Envío Flex" else 0.0)

