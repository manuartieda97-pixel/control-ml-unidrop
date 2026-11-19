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

# ==========================================
# PANEL LATERAL: COMISIONES POR CATEGORÍA Y ESCALA COSTO FIJO
# ==========================================
st.sidebar.header("⚙️ Parámetros Generales")
porcentaje_iibb = st.sidebar.number_input("Retenciones / IIBB (%):", 0.0, 30.0, 3.5, 0.5)
costo_envio_gratis_prom = st.sidebar.number_input("Costo promedio Envío Gratis ML ($):", 0, 100000, 6500, 500)
costo_moto_flex = st.sidebar.number_input("Costo promedio moto Flex ($):", 0, 100000, 4500, 500)
margen_minimo_sano = st.sidebar.slider("Margen mínimo saludable (%):", 1, 50, 12)
usar_costo_con_iva = st.sidebar.checkbox("Usar Costo Total con IVA de Unidrop", value=True)

with st.sidebar.expander("📊 Comisiones Clásica por Categoría (%)", expanded=False):
    com_tecno = st.number_input("Tecnología / Audio / Celulares (%):", 0.0, 40.0, 14.5, 0.5)
    com_relojes = st.number_input("Smartwatches / Relojes (%):", 0.0, 40.0, 16.5, 0.5)
    com_hogar = st.number_input("Hogar / Cocina / Electro (%):", 0.0, 40.0, 15.5, 0.5)
    com_accesorios = st.number_input("Indumentaria / Mochilas / Gorras (%):", 0.0, 40.0, 17.0, 0.5)
    com_general = st.number_input("Otras Categorías (%):", 0.0, 40.0, 15.5, 0.5)
    recargo_bajo_int = st.number_input("Extra Cuotas Bajo Interés (+%):", 0.0, 30.0, 4.5, 0.5)
    recargo_premium = st.number_input("Extra Cuotas Premium (+%):", 0.0, 30.0, 12.5, 0.5)

with st.sidebar.expander("🏷️ Escala Costo Fijo por Unidad ML", expanded=False):
    st.caption("Se aplica automático según el precio del producto (debajo del umbral de envío gratis).")
    tope_tramo1 = st.number_input("Tramo 1 - Hasta ($):", 0, 100000, 15000, 1000)
    fijo_tramo1 = st.number_input("Costo Fijo Tramo 1 ($):", 0, 50000, 1000, 100)
    tope_tramo2 = st.number_input("Tramo 2 - Hasta ($):", 0, 100000, 25000, 1000)
    fijo_tramo2 = st.number_input("Costo Fijo Tramo 2 ($):", 0, 50000, 2000, 100)
    tope_tramo3 = st.number_input("Tramo 3 - Hasta ($):", 0, 100000, 33000, 1000)
    fijo_tramo3 = st.number_input("Costo Fijo Tramo 3 ($):", 0, 50000, 2400, 100)

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
        hojas = [h for h in xl.sheet_names if "publicacion" in h.lower()] + xl.sheet_names
    else:
        hojas = [None]
    for hoja in hojas:
        df_raw = pd.read_excel(archivo, sheet_name=hoja, header=None) if hoja is not None else pd.read_csv(archivo, sep=None, engine='python', header=None)
        for i in range(min(60, len(df_raw))):
            vals = [str(x).strip().lower() for x in df_raw.iloc[i].values]
            if "número de publicación" in vals and "precio" in vals:
                df = df_raw.iloc[i + 1:].copy()
                df.columns = [str(c).strip() for c in df_raw.iloc[i].values]
                return df[df["Número de publicación"].astype(str).str.startswith("MLA", na=False)].reset_index(drop=True)
    return pd.DataFrame()

df_ml = leer_ml(archivo_ml)
if df_ml.empty:
    st.error("❌ No se encontraron publicaciones válidas (MLA) en el archivo de Mercado Libre.")
    st.stop()

df_uni = pd.read_excel(archivo_unidrop) if archivo_unidrop.name.endswith('.xlsx') else pd.read_csv(archivo_unidrop, sep=None, engine='python')
df_uni.columns = [str(c).strip() for c in df_uni.columns]

col_costo = "Costo total" if (usar_costo_con_iva and "Costo total" in df_uni.columns) else "Costo sin IVA"
df_uni["COSTO_NUM"] = pd.to_numeric(df_uni[col_costo], errors='coerce').fillna(0)
df_uni["DESC_NORM"] = df_uni["Descripción"].astype(str).str.lower().str.strip()

def buscar_match(fila_ml):
    t_ml = f"{fila_ml.get('Título', '')} {fila_ml.get('Variantes', '')}".lower().strip()
    p_ml = set(re.findall(r'\b[a-z0-9]{2,}\b', t_ml)) - {"de", "con", "para", "en", "el", "la", "los", "las", "por", "un", "una", "color"}
    mejor_sc, mejor_f = 0, None
    for _, row_u in df_uni.iterrows():
        d_u = row_u["DESC_NORM"]
        p_u = set(re.findall(r'\b[a-z0-9]{2,}\b', d_u)) - {"de", "con", "para", "en", "el", "la", "los", "las", "por", "un", "una", "color"}
        if not p_ml or not p_u: continue
        sc = (len(p_ml.intersection(p_u)) / max(len(p_ml), 1)) * 0.7 + SequenceMatcher(None, t_ml, d_u).ratio() * 0.3
        for color in ["negro", "negra", "blanco", "blanca", "gris", "azul", "rojo", "verde", "naranja", "fucsia", "violeta", "plateado"]:
            if color in t_ml and color in d_u: sc += 0.25
        if sc > mejor_sc: mejor_sc, mejor_f = sc, row_u
    if mejor_f is not None and mejor_sc >= 0.35:
        return pd.Series([mejor_f["SKU"], mejor_f["Descripción"], mejor_f["COSTO_NUM"]])
    return pd.Series([None, None, np.nan])

df_ml[["SKU Unidrop", "Producto Unidrop", "Costo Unidrop ($)"]] = df_ml.apply(buscar_match, axis=1)
df_ml["Precio Venta ($)"] = pd.to_numeric(df_ml["Precio"], errors='coerce').fillna(0)
df_ml = df_ml[df_ml["Precio Venta ($)"] > 0].copy()

# DETECTOR AUTOMÁTICO DE CATEGORÍA Y ESCALA DE COSTO FIJO
def detectar_cat_y_fijo(fila):
    titulo = str(fila.get("Título", "")).lower()
    precio = fila["Precio Venta ($)"]
    cuotas = str(fila.get("Cuotas", "")).lower()

    # 1. Clasificación automática de categoría por palabras clave
    if any(k in titulo for k in ["smartwatch", "reloj", "smartband", "zl138", "z69"]):
        cat_nombre, tasa_base = "Relojes", com_relojes
    elif any(k in titulo for k in ["auricular", "parlante", "micrófono", "microfono", "cargador", "power bank", "memoria", "pendrive", "trípode", "tripode", "bluetooth"]):
        cat_nombre, tasa_base = "Tecnología", com_tecno
    elif any(k in titulo for k in ["mochila", "gorra", "antifaz"]):
        cat_nombre, tasa_base = "Accesorios", com_accesorios
    elif any(k in titulo for k in ["freidora", "batidora", "licuadora", "minipimer", "anafe", "humidificador", "difusor", "termo", "botella", "cuchillo", "afilador", "olla", "cubiertos", "dispenser", "espejo", "secador", "arbol", "árbol"]):
        cat_nombre, tasa_base = "Hogar/Electro", com_hogar
    else:
        cat_nombre, tasa_base = "General", com_general

    # 2. Sumar recargo por cuotas
    if "agregar cuotas" in cuotas and "no" not in cuotas:
        tasa_total = tasa_base + recargo_premium
        b_cuo = "💳 Con Cuotas"
    elif "bajo" in cuotas:
        tasa_total = tasa_base + recargo_bajo_int
        b_cuo = "💳 Bajo Interés"
    else:
        tasa_total = tasa_base
        b_cuo = "💵 Sin Cuotas"

    # 3. Escala automática de Costo Fijo por Unidad Vendida
    if precio <= tope_tramo1:
        costo_fijo = float(fijo_tramo1)
    elif precio <= tope_tramo2:
        costo_fijo = float(fijo_tramo2)
    elif precio <= tope_tramo3:
        costo_fijo = float(fijo_tramo3)
    else:
        costo_fijo = 0.0

    envio = str(fila.get("Costo de envío", "")).lower()
    forma = str(fila.get("Forma de entrega", "")).lower()
    c_env = float(costo_envio_gratis_prom) if "gratis" in envio else 0.0
    b_env = "📦 Envío Gratis" if "gratis" in envio else "🛒 Envío Comprador"
    if "flex" in forma: b_env += " + Flex"

    return pd.Series([cat_nombre, tasa_total, costo_fijo, c_env, f"{b_cuo} | {b_env}"])

df_ml[["Categoría Est.", "Comisión (%)", "Costo Fijo ($)", "Envío ($)", "Condiciones"]] = df_ml.apply(detectar_cat_y_fijo, axis=1)

def recalcular_fila(fila):
    precio = fila["Precio Venta ($)"]
    tasa = fila["Comisión (%)"] / 100
    com_p = precio * tasa
    c_fijo = fila["Costo Fijo ($)"]
    c_env = fila["Envío ($)"]
    iibb_p = precio * (porcentaje_iibb / 100)
    recibis = precio - com_p - c_fijo - c_env - iibb_p
    c_uni = fila["Costo Unidrop ($)"]
    ganancia = recibis - c_uni if pd.notna(c_uni) else np.nan
    margen = (ganancia / precio * 100) if (pd.notna(ganancia) and precio > 0) else np.nan
    div = 1 - tasa - (porcentaje_iibb / 100) - (margen_minimo_sano / 100)
    p_sug = ((c_uni + c_fijo + c_env) / div) if (pd.notna(c_uni) and div > 0.05) else 0.0
    return pd.Series([com_p, iibb_p, recibis, ganancia, margen, p_sug])

df_ml[["Comisión ($)", "IIBB ($)", "Recibís en ML ($)", "Ganancia Neta ($)", "Margen Neto (%)", "Precio Sugerido ($)"]] = df_ml.apply(recalcular_fila, axis=1)
df_ml["Semáforo"] = np.where(df_ml["Ganancia Neta ($)"].isna(), "⚪ SIN VINCULAR", np.where(df_ml["Ganancia Neta ($)"] < 0, "🔴 PÉRDIDA", np.where(df_ml["Margen Neto (%)"] < margen_minimo_sano, "🟡 BAJO", "🟢 RENTABLE")))

df_vinculadas = df_ml.dropna(subset=["Costo Unidrop ($)"]).copy()
df_sin_vincular = df_ml[df_ml["Costo Unidrop ($)"].isna()].copy()

vista = st.radio("Sección:", ["📊 1. Publicaciones Activas", "✏️ 2. Simular Precio", "🆕 3. Cotizar Nuevo"], horizontal=True)
st.divider()

if vista == "📊 1. Publicaciones Activas":
    c1, c2, c3 = st.columns(3)
    f_col = c1.selectbox("🚦 Filtrar por Color:", ["Todos", "🔴 Solo Pérdidas", "🟡 Solo Margen Bajo", "🟢 Solo Rentables"])
