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

def calc_finanzas(fila):
    precio = fila["Precio Venta ($)"]
    cuotas = str(fila.get("Cuotas", "")).lower()
    envio = str(fila.get("Costo de envío", "")).lower()
    forma = str(fila.get("Forma de entrega", "")).lower()
    if "agregar cuotas" in cuotas and "no" not in cuotas:
        tasa, b_cuo = comision_premium / 100, "💳 Con Cuotas"
    elif "bajo" in cuotas:
        tasa, b_cuo = comision_bajo_interes / 100, "💳 Bajo Interés"
    else:
        tasa, b_cuo = comision_clasica / 100, "💵 Sin Cuotas"
    com_p = precio * tasa
    c_env = float(costo_envio_gratis_prom) if "gratis" in envio else 0.0
    b_env = "📦 Envío Gratis" if "gratis" in envio else "🛒 Envío Comprador"
    if "flex" in forma: b_env += " + Flex"
    iibb_p = precio * (porcentaje_iibb / 100)
    recibis = precio - com_p - c_env - iibb_p
    c_uni = fila["Costo Unidrop ($)"]
    ganancia = recibis - c_uni if pd.notna(c_uni) else np.nan
    margen = (ganancia / precio * 100) if (pd.notna(ganancia) and precio > 0) else np.nan
    div = 1 - tasa - (porcentaje_iibb / 100) - (margen_minimo_sano / 100)
    p_sug = ((c_uni + c_env) / div) if (pd.notna(c_uni) and div > 0.05) else 0.0
    return pd.Series([f"{b_cuo} | {b_env}", com_p, c_env, iibb_p, recibis, ganancia, margen, p_sug, tasa])

df_ml[["Condiciones", "Comisión ($)", "Envío ($)", "IIBB ($)", "Recibís en ML ($)", "Ganancia Neta ($)", "Margen Neto (%)", "Precio Sugerido ($)", "Tasa_Com"]] = df_ml.apply(calc_finanzas, axis=1)
df_ml["Semáforo"] = np.where(df_ml["Ganancia Neta ($)"].isna(), "⚪ SIN VINCULAR", np.where(df_ml["Ganancia Neta ($)"] < 0, "🔴 PÉRDIDA", np.where(df_ml["Margen Neto (%)"] < margen_minimo_sano, "🟡 BAJO", "🟢 RENTABLE")))

df_vinculadas = df_ml.dropna(subset=["Costo Unidrop ($)"]).copy()
df_sin_vincular = df_ml[df_ml["Costo Unidrop ($)"].isna()].copy()

vista = st.radio("Sección:", ["📊 1. Publicaciones Activas", "✏️ 2. Simular Precio", "🆕 3. Cotizar Nuevo"], horizontal=True)
st.divider()

if vista == "📊 1. Publicaciones Activas":
    c1, c2, c3 = st.columns(3)
    f_col = c1.selectbox("🚦 Filtrar por Color:", ["Todos", "🔴 Solo Pérdidas", "🟡 Solo Margen Bajo", "🟢 Solo Rentables"])
    orden = c2.selectbox("Ordenar por:", ["Título (A - Z)", "Peor a mejor ganancia ($)", "Mejor a peor ganancia ($)", "Margen Neto (%)"])
    filtro = c3.text_input("🔍 Buscar por Título o SKU:")

    df_t = df_vinculadas.copy()
    if f_col == "🔴 Solo Pérdidas": df_t = df_t[df_t["Semáforo"] == "🔴 PÉRDIDA"]
    if f_col == "🟡 Solo Margen Bajo": df_t = df_t[df_t["Semáforo"] == "🟡 BAJO"]
    if f_col == "🟢 Solo Rentables": df_t = df_t[df_t["Semáforo"] == "🟢 RENTABLE"]
    if filtro: df_t = df_t[df_t["Título"].str.contains(filtro, case=False, na=False) | df_t["SKU Unidrop"].str.contains(filtro, case=False, na=False)]

    col_ord = "Título" if orden == "Título (A - Z)" else ("Margen Neto (%)" if orden == "Margen Neto (%)" else "Ganancia Neta ($)")
    df_t = df_t.sort_values(by=col_ord, ascending=(orden != "Mejor a peor ganancia ($)"))

    def pintar_fila(f):
        s = str(f["Semáforo"])
        if "🔴" in s: return ['background-color: #ffcccc; color: #660000'] * len(f)
        if "🟡" in s: return ['background-color: #fff3cd; color: #664d03'] * len(f)
        return ['background-color: #d1e7dd; color: #0f5132'] * len(f)

    cols_ver = ["Semáforo", "Título", "Variantes", "Ganancia Neta ($)", "Margen Neto (%)", "Recibís en ML ($)", "Precio Venta ($)", "Costo Unidrop ($)", "Condiciones", "Comisión ($)", "Envío ($)", "IIBB ($)", "Precio Sugerido ($)", "SKU Unidrop"]
    st.dataframe(df_t[cols_ver].round(2).style.apply(pintar_fila, axis=1), use_container_width=True, hide_index=True, height=600)

    if not df_sin_vincular.empty:
        st.warning(f"⚠️ {len(df_sin_vincular)} publicaciones sin coincidencia en Unidrop:")
        st.dataframe(df_sin_vincular[["Número de publicación", "Título", "Variantes", "Precio Venta ($)"]], use_container_width=True, hide_index=True)

if vista == "✏️ 2. Simular Precio" and not df_vinculadas.empty:
    opciones = df_vinculadas["Número de publicación"].astype(str) + " || " + df_vinculadas["Título"].astype(str) + " (" + df_vinculadas["Variantes"].astype(str) + ")"
    sel = st.selectbox("Elegí publicación:", opciones)
    id_sel = next(iter(sel.split(" || ")))
    fila = next(iter(df_vinculadas[df_vinculadas["Número de publicación"].astype(str) == id_sel].to_dict('records')))
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Precio Actual ML", f"${fila['Precio Venta ($)']:,.2f}")
    c2.metric("Recibís Actual ML", f"${fila['Recibís en ML ($)']:,.2f}")
    c3.metric("Costo Unidrop", f"${fila['Costo Unidrop ($)']:,.2f}")
    c4.metric("Ganancia Neta Actual", f"${fila['Ganancia Neta ($)']:,.2f}", f"{fila['Margen Neto (%)']:.1f}%")
    nuevo_p = st.number_input("NUEVO precio de prueba ($):", min_value=1.0, value=max(float(fila['Precio Venta ($)']), 1.0), step=500.0)
    n_recibis = nuevo_p - (nuevo_p * fila["Tasa_Com"]) - fila["Envío ($)"] - (nuevo_p * (porcentaje_iibb / 100))
    n_ganancia = n_recibis - fila['Costo Unidrop ($)']
    n_margen = (n_ganancia / nuevo_p) * 100
    r1, r2, r3 = st.columns(3)
    r1.metric("Nuevo monto en ML", f"${n_recibis:,.2f}", delta=f"${(n_recibis - fila['Recibís en ML ($)']):,.2f}")
