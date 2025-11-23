# app.py

import streamlit as st
import pandas as pd
import numpy as np
from openai import OpenAI
from xgboost import XGBRegressor
from sklearn.preprocessing import OneHotEncoder

from prompts import final_prompt  # <-- tu prompt de rol

# ==========================
# CONFIGURACIÓN OPENAI
# ==========================
client = OpenAI(api_key=st.secrets["openai_api_key"])

# ==========================
# CARGA DE DATOS
# ==========================
@st.cache_data
def cargar_datos():
    df = pd.read_parquet("data_config/df_proc.parquet")
    return df

df_proc = cargar_datos()

# ==========================
# MODELO DE PREDICCIÓN
# ==========================

def prediccion_siniestralidad(df_proc, giro_usuario, entidad_usuario, min_obs=3):
    """
    Entrena un modelo XGBoost "al vuelo" para un giro+entidad.
    Si no hay suficientes datos a ese nivel, hace fallback a sector+entidad.
    Devuelve: (dict{año: predicción}, nivel_usado: "giro" | "sector")
    """
    lag_features = [
        'prima_emitida_neta', 'prima_retenida', 'prima_devengada',
        'monto_de_siniestro', 'gasto_de_ajuste', 'salvamento',
        'monto_pagado', 'monto_de_deducible', 'monto_coaseguro',
        'n_mero_de_siniestros', 'recuperacion_de_terceros',
        'recuperacion_de_reaseguro', 'suma_asegurada', 'cuota_millar',
        'sin_index', 'siniestro_neto', 'net_sin_index'
    ]
    
    def _ajustar_y_predecir(df_base, cat_col, valor_cat, nivel_desc):
        """
        df_base: DF ya filtrado al nivel deseado (giro+entidad o sector+entidad)
        cat_col: 'giro' o 'sector'
        valor_cat: valor del giro o sector usado para OHE
        nivel_desc: solo para mensajes de error
        """
        df = df_base.copy()
        df = df.sort_values(['entidad', 'año'])

        # Asegurar numérico en columnas base
        cols_num = [c for c in lag_features if c in df.columns]
        if cols_num:
            df[cols_num] = df[cols_num].apply(pd.to_numeric, errors='coerce')

        # Crear lags
        for col in lag_features:
            if col in df.columns:
                df[f'{col}_lag1'] = df.groupby([cat_col, 'entidad'])[col].shift(1)

        # Asegurar numérico en lags
        lag1_cols = [f'{c}_lag1' for c in lag_features if f'{c}_lag1' in df.columns]
        if lag1_cols:
            df[lag1_cols] = df[lag1_cols].apply(pd.to_numeric, errors='coerce')

        # Limpieza de target y lags
        df = df[df['net_sin_index'].notna()]
        df = df.replace([np.inf, -np.inf], np.nan)
        df_model = df.dropna(subset=lag1_cols + ['net_sin_index'])

        if df_model.shape[0] < min_obs:
            raise ValueError(
                f"No hay suficientes datos limpios a nivel {nivel_desc} "
                f"para {cat_col}={valor_cat}, entidad={entidad_usuario}"
            )

        # One-hot de categoría (giro/sector) + entidad
        ohe = OneHotEncoder(sparse_output=False, handle_unknown='ignore')
        encoded = ohe.fit_transform(df_model[[cat_col, 'entidad']])
        ohe_cols = list(ohe.get_feature_names_out())
        encoded_df = pd.DataFrame(encoded, columns=ohe_cols, index=df_model.index)

        # Unir lags + OHE
        df_model_enc = pd.concat([df_model, encoded_df], axis=1)

        # Features: solo lags + OHE
        lag1_cols = [c for c in df_model_enc.columns if c.endswith('_lag1')]
        feature_cols = lag1_cols + ohe_cols

        X = df_model_enc[feature_cols]
        y = df_model_enc['net_sin_index']

        if y.isna().any():
            raise ValueError(f"y (net_sin_index) aún tiene NaNs a nivel {nivel_desc}.")

        model = XGBRegressor(
            n_estimators=600,
            learning_rate=0.05,
            max_depth=5,
            subsample=0.9,
            colsample_bytree=0.9
        )
        model.fit(X, y)

        # Base para predicción: última observación
        base = df.sort_values('año').iloc[-1].copy()
        last_year = int(base['año'])

        predicciones = {}
        current = base.copy()

        for step in [1, 2]:
            año_futuro = last_year + step

            # OHE para valor actual + entidad_usuario
            encoded_row = ohe.transform([[valor_cat, entidad_usuario]])
            encoded_row_df = pd.DataFrame(encoded_row, columns=ohe_cols)

            # Usar solo lags actuales
            row_lags = current[lag1_cols].to_frame().T.reset_index(drop=True)

            # Unir lags + OHE
            row = pd.concat(
                [row_lags, encoded_row_df.reset_index(drop=True)],
                axis=1
            )

            # Alinear columnas
            row = row.reindex(columns=feature_cols, fill_value=0).astype(float)

            pred = model.predict(row)[0]
            predicciones[año_futuro] = float(pred)

            # Actualizar lag de net_sin_index para el siguiente paso
            if 'net_sin_index_lag1' in current.index:
                current['net_sin_index_lag1'] = pred

        return predicciones

    # =========================
    # NIVEL 1: GIRO + ENTIDAD
    # =========================
    df_ge = df_proc[(df_proc['giro'] == giro_usuario) &
                    (df_proc['entidad'] == entidad_usuario)].copy()

    if df_ge.shape[0] >= min_obs:
        try:
            preds_giro = _ajustar_y_predecir(
                df_ge, cat_col='giro',
                valor_cat=giro_usuario,
                nivel_desc='giro'
            )
            # Si no son todas ~0, usamos este nivel
            if not all(abs(v) < 1e-9 for v in preds_giro.values()):
                return preds_giro, "giro"
        except ValueError:
            pass  # Intentaremos sector

    # =========================
    # NIVEL 2: SECTOR + ENTIDAD
    # =========================
    subset_giro = df_proc[df_proc['giro'] == giro_usuario]
    if subset_giro.empty or subset_giro['sector'].isna().all():
        raise ValueError(f"No se encontró sector asociado al giro={giro_usuario}")

    sector_usuario = subset_giro['sector'].mode().iloc[0]

    df_se = df_proc[(df_proc['sector'] == sector_usuario) &
                    (df_proc['entidad'] == entidad_usuario)].copy()

    if df_se.shape[0] < min_obs:
        raise ValueError(
            "No hay suficientes datos ni a nivel giro ni a nivel sector para "
            f"giro={giro_usuario}, entidad={entidad_usuario}, sector={sector_usuario}"
        )

    preds_sector = _ajustar_y_predecir(
        df_se, cat_col='sector',
        valor_cat=sector_usuario,
        nivel_desc='sector'
    )

    return preds_sector, "sector"


# ==========================
# INTERFAZ STREAMLIT
# ==========================

st.set_page_config(page_title="Suscriptor 360: Tu asistente virtual", layout="wide")

st.title("🛡️ Suscriptor 360: Tu asistente virtual")

st.markdown("""
Esta herramienta apoya al área de suscripción daños.
Permite:
- Seleccionar **Entidad, Sector y Giro**.
- Obtener una **predicción de siniestralidad (net_sin_index)** para los próximos años.
- Consultar a un **asistente inteligente** especializado en riesgos asegurables.
""")

# Dos columnas; el chat quedará al lado, tipo panel derecho
col1, col2 = st.columns([1, 1])

with col1:
    st.subheader("📥 Parámetros de entrada")

    # Dropdown entidad
    entidades = sorted(df_proc['entidad'].dropna().unique())
    entidad = st.selectbox("Entidad", entidades)

    # Dropdown sector
    sectores = sorted(df_proc['sector'].dropna().unique())
    sector = st.selectbox("Sector", sectores)

    # Dropdown giro dependiente del sector
    giros_filtrados = (
        df_proc[df_proc['sector'] == sector]['giro']
        .dropna()
        .sort_values()
        .unique()
        .tolist()
    )
    giro = st.selectbox("Giro", giros_filtrados)

    # Botón de predicción
    if st.button("🔮 Generar predicción de siniestralidad"):
        with st.spinner("Entrenando modelo y generando predicción..."):
            try:
                preds, nivel = prediccion_siniestralidad(df_proc, giro, entidad)
                df_pred = (
                    pd.DataFrame(
                        [{"Año": año, "Indice siniestralidad neta": val}
                         for año, val in preds.items()]
                    )
                    .sort_values("Año")
                )
                st.success(f"Predicción generada usando modelo a nivel **{nivel.upper()}**")
                st.dataframe(df_pred, hide_index=True)
            except Exception as e:
                st.error(f"Error al generar la predicción: {e}")

with col2:
    # Contenedor general del panel de chat
    with st.container(border=True):
        st.subheader("💬 Asistente Inteligente de Suscripción")

        if "chat_mensajes" not in st.session_state:
            st.session_state.chat_mensajes = []

        # Construimos el HTML del historial de chat
        chat_html = """
        <div id="chat-box" style="
            height: 420px;
            overflow-y: auto;
            padding: 0.5rem;
            border-radius: 0.5rem;
            background-color: #11111111;
        ">
        """

        for msg in st.session_state.chat_mensajes:
            role = msg["role"]
            content = msg["content"].replace("\n", "<br>")  # saltos de línea simples

            if role == "user":
                bubble = f"""
                <div style="display: flex; justify-content: flex-end; margin-bottom: 0.5rem;">
                    <div style="
                        max-width: 80%;
                        background-color: #DCF8C6;
                        color: #000;
                        padding: 0.4rem 0.6rem;
                        border-radius: 0.6rem;
                        border-bottom-right-radius: 0.1rem;
                        font-size: 0.9rem;
                    ">
                        {content}
                    </div>
                </div>
                """
            else:  # assistant
                bubble = f"""
                <div style="display: flex; justify-content: flex-start; margin-bottom: 0.5rem;">
                    <div style="
                        max-width: 80%;
                        background-color: #FFFFFF;
                        color: #000;
                        padding: 0.4rem 0.6rem;
                        border-radius: 0.6rem;
                        border-bottom-left-radius: 0.1rem;
                        font-size: 0.9rem;
                        box-shadow: 0 0 2px rgba(0,0,0,0.1);
                    ">
                        {content}
                    </div>
                </div>
                """

            chat_html += bubble

        chat_html += "</div>"

        # Render del chat + script para hacer scroll al final
        st.markdown(chat_html, unsafe_allow_html=True)
        st.markdown(
            """
            <script>
            const chatBox = window.parent.document.getElementById('chat-box');
            if (chatBox) {
                chatBox.scrollTop = chatBox.scrollHeight;
            }
            </script>
            """,
            unsafe_allow_html=True,
        )

        # Input de chat (siempre debajo del cuadro, como en ChatGPT)
        user_input = st.chat_input("Haz una pregunta sobre el riesgo, siniestralidad o contexto...")

        if user_input:
            # Guardar mensaje del usuario
            st.session_state.chat_mensajes.append({
                "role": "user",
                "content": user_input
            })

            # Contexto dinámico del caso actual
            contexto_dinamico = f"""
INFORMACIÓN DEL CASO ACTUAL:
- Entidad: {entidad}
- Sector: {sector}
- Giro: {giro}
"""

            mensajes_openai = [
                {"role": "system", "content": final_prompt},
                {"role": "system", "content": contexto_dinamico},
            ] + st.session_state.chat_mensajes

            try:
                resp = client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=mensajes_openai,
                    temperature=0.3,
                    max_tokens=400
                )
                respuesta_texto = resp.choices[0].message.content

                st.session_state.chat_mensajes.append({
                    "role": "assistant",
                    "content": respuesta_texto
                })

            except Exception as e:
                st.error(f"Error al comunicarse con el asistente: {e}")
