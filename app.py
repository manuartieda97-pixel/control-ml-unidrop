import streamlit as st
import pandas as pd
import numpy as np

st.set_page_config(page_title="Suite Rentabilidad ML + Unidrop", page_icon="💰", layout="wide")

# ==========================================
# 1. ACCESO PRIVADO CON CONTRASEÑA
# ==========================================
if "autenticado" not in st.session_state:
    st.session_state.autenticado = False

if not st.session_state.autenticado:
    st.title("🔒 Acceso Privado - Suite ML + Unidrop")
    password = st.text_input("Ingresá tu clave secreta:", type="password")
    if st.button("Entrar"):
        if password == "1234": # Podés cambiar "1234" por tu contraseña
            st.session_state.autenticado = True
            st.rerun()
        else:
            st.error("❌ Contraseña incorrecta")
    st.stop()

# ==========================================
# 2. PANEL LATERAL DE PARÁMETROS
# ==========================================
st.sidebar.header("⚙️ Parámetros de Cálculo")

porcentaje_iibb = st.sidebar.number_input(
    "Retenciones / IIBB estimado (%):", 
    min_value=0.0, max_value=30.0, value=3.5, step=0.5,
    help="Porcentaje que te retiene ML sobre el precio bruto."
)

costo_moto_flex = st.sidebar.number_input(
    "Costo promedio moto/cadete Flex ($):", 
    min_value=0, value=4500, step=500
)

margen_minimo_sano = st.sidebar.slider(
    "Margen mínimo saludable (% Semáforo):", 
    min_value=1, max_value=50, value=12,
    help="Debajo de este % se pintará en amarillo."
)

# ==========================================
# 3. CARGA DE PLANILLAS
# ==========================================
st.title("💰 Centro de Control de Rentabilidad: ML + Unidrop")

col1, col2 = st.columns(2)
with col1:
    archivo_ml = st.file_uploader("1️⃣ Subí tu reporte de Mercado Libre", type=["xlsx", "csv"])
with col2:
    archivo_unidrop = st.file_uploader("2️⃣ Subí tu catálogo de Unidrop", type=["xlsx", "csv"])

# ==========================================
# 4. ASIGNACIÓN DE COLUMNAS Y PROCESAMIENTO
# ==========================================
if archivo_ml and archivo_unidrop:
    try:
        df_ml = pd.read_excel(archivo_ml) if archivo_ml.name.endswith('.xlsx') else pd.read_csv(archivo_ml)
        df_uni = pd.read_excel(archivo_unidrop) if archivo_unidrop.name.endswith('.xlsx') else pd.read_csv(archivo_unidrop)

        cols_ml = list(df_ml.columns)
        cols_uni = list(df_uni.columns)

        def idx_aprox(lista, palabras):
            for i, col in enumerate(lista):
                for p in palabras:
                    if p.lower() in str(col).lower():
                        return i
            return 0

        with st.expander("🔗 Paso rápido: Confirmá qué columna es cada dato en tus archivos", expanded=True):
            c_ml, c_uni = st.columns(2)
            with c_ml:
                st.markdown("**Columnas de Mercado Libre:**")
                COL_ID_ML = st.selectbox("ID Publicación (MLA):", cols_ml, index=idx_aprox(cols_ml, ["número", "id", "publicación"]))
                COL_SKU_ML = st.selectbox("SKU en ML:", cols_ml, index=idx_aprox(cols_ml, ["sku", "código"]))
                COL_TITULO_ML = st.selectbox("Título del producto:", cols_ml, index=idx_aprox(cols_ml, ["título", "nombre", "producto"]))
                COL_PRECIO_ML = st.selectbox("Precio de venta ($):", cols_ml, index=idx_aprox(cols_ml, ["precio"]))
                COL_TIPO_PUB = st.selectbox("Tipo publicación (Clásica/Premium):", cols_ml, index=idx_aprox(cols_ml, ["tipo", "exposición", "cuotas"]))
                COL_COMISION_ML = st.selectbox("Cargo/Comisión por vender ($):", cols_ml, index=idx_aprox(cols_ml, ["cargo", "comisión", "vender"]))
                COL_FORMA_ENVIO = st.selectbox("Forma de envío (Flex/Mercado Envíos):", cols_ml, index=idx_aprox(cols_ml, ["forma", "logística", "envío"]))
                COL_ENVIO_GRATIS = st.selectbox("¿Envío gratis? (Sí/No):", cols_ml, index=idx_aprox(cols_ml, ["gratis"]))
                COL_COSTO_ENVIO_ML = st.selectbox("Costo de envío ML ($):", cols_ml, index=idx_aprox(cols_ml, ["costo de envío", "envío"]))

            with c_uni:
                st.markdown("**Columnas de Unidrop:**")
                COL_SKU_UNI = st.selectbox("SKU en Unidrop:", cols_uni, index=idx_aprox(cols_uni, ["sku", "código"]))
                COL_COSTO_UNI = st.selectbox("Costo del producto ($):", cols_uni, index=idx_aprox(cols_uni, ["costo", "precio"]))

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
            elif "sí" in gratis or "si" in gratis or "gratis" in gratis:
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

        tab1, tab2, tab3 = st.tabs([
            "📊 1. Publicaciones Activas", 
            "✏️ 2. Simular Cambio de Precio", 
            "🆕 3. Cotizar Producto Nuevo (Sin Publicar)"
        ])

        with tab1:
            st.subheader("Rentabilidad Real de tus Publicaciones")
            
            def colorear_semaforo(fila):
                if fila["Ganancia Neta ($)"] < 0:
                    return ['background-color: rgba(255, 75, 75, 0.25)'] * len(fila)
                elif fila["Margen (%)"] < margen_minimo_sano:
                    return ['background-color: rgba(255, 215, 0, 0.25)'] * len(fila)
                else:
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
                st.warning(f"⚠️ Hay {len(sin_match)} publicaciones en ML cuyo SKU no se encontró en Unidrop:")
                st.dataframe(sin_match[[COL_ID_ML, "SKU_LIMPIO", COL_TITULO_ML, COL_PRECIO_ML]], hide_index=True)

        with tab2:
            st.subheader("Simulador de Precio antes de editar en Mercado Libre")
            if not con_match.empty:
                opciones_pub = con_match[COL_ID_ML].astype(str) + " | " + con_match["SKU_LIMPIO"] + " - " + con_match[COL_TITULO_ML].astype(str)
                seleccion = st.selectbox("Elegí la publicación que querés probar:", opciones_pub)
                
                if seleccion:
                    id_sel = seleccion.split(" | ")
                    fila_sel = con_match[con_match[COL_ID_ML].astype(str) == id_sel].iloc
                    
                    c1, c2, c3 = st.columns(3)
                    c1.metric("Precio Actual ML", f"${fila_sel[COL_PRECIO_ML]:,.2f}")
                    c2.metric("Costo Unidrop", f"${fila_sel[COL_COSTO_UNI]:,.2f}")
                    c3.metric("Ganancia Actual", f"${fila_sel['Ganancia Neta ($)']:,.2f}", f"{fila_sel['Margen (%)']:.1f}%")

                    nuevo_precio = st.number_input("Probá un NUEVO precio de venta ($):", min_value=1.0, value=float(fila_sel[COL_PRECIO_ML]), step=500.0)
                    
                    nueva_comision = nuevo_precio * fila_sel["Tasa_Comision_ML"]
                    nuevo_iibb = nuevo_precio * (porcentaje_iibb / 100)
                    nueva_ganancia = nuevo_precio - nueva_comision - fila_sel["Envío Real ($)"] - nuevo_iibb - fila_sel[COL_COSTO_UNI]
                    nuevo_margen = (nueva_ganancia / nuevo_precio) * 100

                    st.markdown("### Resultado de la Simulación:")
                    r1, r2, r3 = st.columns(3)
                    r1.metric("Nueva Comisión + IIBB", f"${(nueva_comision + nuevo_iibb):,.2f}")
