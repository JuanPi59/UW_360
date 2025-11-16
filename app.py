

import streamlit as st
import pandas as pd
from openai import OpenAI
import json
import os
import time # Para simular procesos

# --- 0. Configuración Inicial y Carga de Datos ---

# **REEMPLAZA** "TU_API_KEY_AQUI" con tu clave de OpenAI. 
# En un entorno real, usa st.secrets["OPENAI_API_KEY"] para mayor seguridad.
API_KEY = st.secrets.get("openai_api_key") 

try:
    client = OpenAI(api_key=API_KEY)
except Exception as e:
    # Manejo de error si la clave no es válida o falta
    st.error(f"Error al inicializar OpenAI: {e}. Asegúrese de reemplazar 'TU_API_KEY_AQUI' con su clave real.")
    client = None # Aseguramos que el cliente sea None si falla

def cargar_configuracion():
    """Carga los catálogos y tarifas desde archivos JSON."""
    try:
        # Cargar Catálogos (Giro, Ubicación, Prevención)
        with open('data_config/catalogos.json', 'r', encoding='utf-8') as f:
            catalogos = json.load(f)
        
        # Cargar Tarifas y Apetito de Riesgo
        with open('data_config/tarifas_riesgo.json', 'r', encoding='utf-8') as f:
            tarifas = json.load(f)

        return catalogos, tarifas
    except FileNotFoundError as e:
        # Detiene la ejecución si los archivos de configuración no se encuentran
        st.error(f"Error crítico: Archivo de configuración no encontrado en data_config/. Asegúrese de crear la carpeta y los archivos JSON. Detalle: {e}")
        st.stop()
    except Exception as e:
        st.error(f"Error al leer archivos JSON: {e}")
        st.stop()

# Carga global de la configuración
CATALOGOS, TARIFAS = cargar_configuracion()
TASA_BASE = TARIFAS.get("tasa_base", {})
APETITO_RIESGO = TARIFAS.get("apetito_riesgo", {})


st.set_page_config(
    page_title="ASSIST-Seguros | Suscripción Inteligente",
    layout="wide"
)
st.title("🛡️ ASSIST-Seguros: Aplicación de Suscripción Inteligente")
st.markdown("Herramienta de Ciencia de Datos para la evaluación de riesgos empresariales.")

# --- 1. Funciones del Chatbot y PLN ---

def buscar_y_resumir_riesgo_openai(giro_key, estado_key):
    """
    Consulta a OpenAI para buscar (simular) noticias y obtener un resumen de riesgo.
    """
    if not client:
        return "ERROR_API"
        
    giro = CATALOGOS["giro_industria"].get(giro_key, "Giro Desconocido")
    estado = CATALOGOS["ubicacion_estado"].get(estado_key, "Ubicación Desconocida")
    
    prompt = f"""
    Eres un suscriptor experto en seguros de daños para empresas en México.
    Realiza una búsqueda exhaustiva (simulada) de noticias recientes sobre siniestralidad,
    exposición catastrófica o riesgos regulatorios para la industria de '{giro}'
    en la región de '{estado}'.
    
    Luego:
    1. Genera 3 títulos de noticias ficticias pero realistas que encuentres.
    2. Genera un resumen conciso de 5 líneas sobre los principales riesgos agravantes
       encontrados para esta combinación de Giro/Ubicación.
    3. Proporciona una clasificación de Riesgo 'IA' (Bajo, Medio, Alto) y una Cuota Estimada 'IA'
       (un número entre 0.5 y 4.0).
    
    Formato de Salida Requerido:
    NOTICIAS:
    - [Título 1]
    - [Título 2]
    - [Título 3]
    
    RESUMEN DE RIESGO: [Resumen]
    
    CLASIFICACION_IA: [Bajo/Medio/Alto]
    CUOTA_IA: [Número]
    """
    
    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "Actúa como un analista de riesgos experto."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7
        )
        return response.choices[0].message.content
    except Exception as e:
        st.error(f"Error al conectar con OpenAI. Revisar API Key o permisos: {e}")
        return "ERROR_API"

# --- 2. Secciones de Streamlit (Pestañas) ---

def seccion_inputs_usuario():
    """Define la sección 1: Entrada de datos del suscriptor."""
    st.header("1. 📝 Input de Datos del Negocio")
    st.markdown("Seleccione las características clave de la empresa a suscribir.")
    
    # Inicializa el estado de la sesión si no existe (para persistencia)
    if "submitted" not in st.session_state:
        st.session_state["submitted"] = False
    if "ia_response" not in st.session_state:
        st.session_state["ia_response"] = None

    with st.form(key='formulario_suscripcion'):
        
        col1, col2 = st.columns(2)
        
        with col1:
            industria_seleccionada = st.selectbox(
                "**Giro / Industria (Clave SCIAN):**",
                options=list(CATALOGOS["giro_industria"].keys()),
                format_func=lambda x: CATALOGOS["giro_industria"][x],
                key="giro_key"
            )
        
        with col2:
            estado_seleccionado = st.selectbox(
                "**Ubicación (Estado):**",
                options=list(CATALOGOS["ubicacion_estado"].keys()),
                format_func=lambda x: CATALOGOS["ubicacion_estado"][x],
                key="estado_key"
            )
            
        st.subheader("Información Financiera y Prevención")
        
        suma_asegurada = st.number_input(
            "**Suma Asegurada Solicitada (MXN):**",
            min_value=1000000,
            value=10000000,
            step=1000000,
            key="suma_asegurada"
        )
        
        prevencion_seleccionada = st.multiselect(
            "**Medidas de Prevención Instaladas:**",
            options=list(CATALOGOS["medidas_prevencion"].keys()),
            format_func=lambda x: CATALOGOS["medidas_prevencion"][x],
            default=["MP001", "MP003"],
            key="medidas_prevencion"
        )
        
        # Botón de Envío
        submit_button = st.form_submit_button("1. Evaluar Riesgo y Consultar IA")
        
    if submit_button:
        # Guarda el estado de envío
        st.session_state["submitted"] = True
        
    datos_capturados = {
        "giro_key": st.session_state.get("giro_key"),
        "estado_key": st.session_state.get("estado_key"),
        "suma_asegurada": st.session_state.get("suma_asegurada"),
        "medidas_prevencion": st.session_state.get("medidas_prevencion")
    }
    
    return datos_capturados

def seccion_chatbot(datos):
    """Define la sección 2: Chatbot especializado."""
    st.header("2. 🤖 Chatbot de Riesgos Empresariales (PLN)")
    st.markdown("Consulta a la IA para obtener contexto de riesgo externo y noticias recientes.")
    
    # Botón para iniciar la consulta a la IA (Opción 4 y 5 del flujo)
    if st.button("Buscar Noticias y Contexto de Riesgo con IA", disabled=(st.session_state.get("ia_response") is not None)):
        if not client:
             st.error("No se puede contactar a OpenAI. Verifique su API Key.")
             return
        
        with st.spinner(f"Consultando fuentes externas sobre {CATALOGOS['giro_industria'].get(datos['giro_key'])} en {CATALOGOS['ubicacion_estado'].get(datos['estado_key'])}..."):
            ai_output = buscar_y_resumir_riesgo_openai(datos['giro_key'], datos['estado_key'])
            st.session_state["ia_response"] = ai_output # Guarda la respuesta

            if ai_output != "ERROR_API":
                st.success("Análisis de Riesgo Contextualizado por IA completado.")
            
    # Mostrar resultados de la IA (si ya se ejecutó)
    if st.session_state.get("ia_response") and st.session_state["ia_response"] != "ERROR_API":
        resultado_pln = st.session_state["ia_response"]
        
        st.subheader("Resumen de Riesgo y Noticias Ficticias")
        
        try:
            # Extracción del resumen y noticias
            partes = resultado_pln.split("RESUMEN DE RIESGO:")
            noticias_section = partes[0].replace("NOTICIAS:", "").strip()
            resumen_section = partes[1].split("CLASIFICACION_IA:")[0].strip()
            
            st.code(noticias_section, language='markdown')
            st.markdown(f"**Resumen de Riesgo Agravante (IA):** {resumen_section}")
            
            # --- Chat Interactivo ---
            st.divider()
            st.info("Ahora puedes usar el chatbot para hacer preguntas sobre el resumen de riesgo.")
            
            if "messages" not in st.session_state:
                st.session_state["messages"] = [
                    {"role": "assistant", "content": "Hola! ¿Tienes alguna pregunta sobre el resumen de riesgo o los factores de siniestralidad encontrados?"}
                ]
            
            # Mostrar historial de mensajes
            for message in st.session_state["messages"]:
                with st.chat_message(message["role"]):
                    st.markdown(message["content"])

            # Captura de input del usuario para el chat
            if prompt := st.chat_input("Escribe tu pregunta aquí..."):
                st.session_state["messages"].append({"role": "user", "content": prompt})
                with st.chat_message("user"):
                    st.markdown(prompt)
                
                contexto = f"El resumen de riesgo es: {resumen_section}. Las noticias son: {noticias_section}"
                chat_prompt = f"Basándote estrictamente en el siguiente contexto: '{contexto}', responde a la pregunta: '{prompt}'."
                
                with st.chat_message("assistant"):
                    with st.spinner("Analizando pregunta..."):
                        chat_response = client.chat.completions.create(
                            model="gpt-3.5-turbo",
                            messages=[
                                {"role": "system", "content": "Eres un asistente de suscripción que responde preguntas de un suscriptor basándose en un contexto de riesgo previamente generado."},
                                {"role": "user", "content": chat_prompt}
                            ],
                            temperature=0.5
                        )
                        respuesta_ia = chat_response.choices[0].message.content
                        st.markdown(respuesta_ia)
                st.session_state["messages"].append({"role": "assistant", "content": respuesta_ia})

        except Exception as e:
            st.error(f"Error al procesar la respuesta de la IA. Mensaje completo: {resultado_pln}")
            st.error(f"Detalle de error de procesamiento: {e}")


def seccion_resultados(datos):
    """Define la sección 3: Resultados de la Suscripción."""
    
    st.header("3. 📊 Sección de Resultados")
    
    giro_key = datos.get("giro_key", "N/A")
    suma_asegurada = datos.get("suma_asegurada", 0)
    
    # 3.1. Resultados de Catálogo (Datos Históricos/Internos)
    tasa_base = TASA_BASE.get(giro_key, 1.0) # Tasa por mil
    cuota_calculada_base = round((suma_asegurada / 1000) * tasa_base, 2)
    clasificacion_riesgo_base = APETITO_RIESGO.get(giro_key, "Indefinido")

    col_base, col_ia = st.columns(2)
    
    with col_base:
        st.subheader("Resultados Basados en Catálogos de la Empresa")
        st.info("Estos resultados son directos de las tablas de riesgo y tarifas internas.")
        st.metric(
            label="Cuota Calculada (MXN)",
            value=f"${cuota_calculada_base:,.2f}",
        )
        st.metric(
            label="Clasificación de Riesgo Base",
            value=clasificacion_riesgo_base,
            delta="Apetito de Riesgo Fijo por Giro",
            delta_color="off"
        )
        
    # 3.2. Resultados de la IA (Basados en PLN)
    with col_ia:
        st.subheader("Resultados Estimados por IA (PLN y Contexto)")
        
        if st.session_state.get("ia_response") and st.session_state["ia_response"] != "ERROR_API":
            resultado_pln = st.session_state["ia_response"]
            
            try:
                # Extracción de valores de IA (utilizando las etiquetas CLASIFICACION_IA y CUOTA_IA)
                clasificacion_ia = resultado_pln.split("CLASIFICACION_IA:")[1].split("\n")[0].strip()
                cuota_ia_tasa = float(resultado_pln.split("CUOTA_IA:")[1].split("\n")[0].strip())
                cuota_ia_estimada = round((suma_asegurada / 1000) * cuota_ia_tasa, 2)
                
                # Cálculo de Delta para comparación
                delta_cuota = cuota_ia_estimada - cuota_calculada_base
                delta_color = "inverse" if delta_cuota > 0 else "normal" # Rojo si sube, Verde si baja
                
                st.metric(
                    label="Cuota Estimada por IA (MXN)",
                    value=f"${cuota_ia_estimada:,.2f}",
                    delta=f"{delta_cuota:,.2f} vs Catálogo",
                    delta_color=delta_color
                )
                st.metric(
                    label="Clasificación de Riesgo IA",
                    value=clasificacion_ia,
                    delta="Basado en Noticias y Contexto Externo"
                )
                
            except Exception as e:
                st.warning("No se pudieron extraer los valores de CUOTA_IA y CLASIFICACION_IA del resultado de la IA.")
                st.error(f"Error de extracción. Asegúrese que el modelo GPT devolvió el formato esperado.")
                
        else:
            st.warning("Ejecute la consulta en la pestaña 'Chatbot Especializado' para obtener los resultados de la IA.")

# --- 3. Función Principal de la Aplicación ---

if __name__ == "__main__":
    
    # 3.1. Sección 1: Input de Datos (Pestaña 1)
    # seccion_inputs_usuario() se ejecuta primero para inicializar y capturar datos
    datos_suscripcion = seccion_inputs_usuario() 
    
    st.sidebar.subheader("Datos Capturados")
    st.sidebar.json({k: v for k, v in datos_suscripcion.items() if k != "submitted"})
    
    # 3.2. Control de Flujo: Solo mostrar pestañas si se enviaron los datos
    if st.session_state.get("submitted"):
        
        tab2, tab3 = st.tabs(["2. Chatbot Especializado", "3. Resultados Finales"])
        
        # 3.3. Sección 2: Chatbot y PLN
        with tab2:
            seccion_chatbot(datos_suscripcion)
        
        # 3.4. Sección 3: Resultados
        with tab3:
            seccion_resultados(datos_suscripcion)
            
    else:
        st.info("Por favor, complete los datos en la pestaña '1. Input de Datos' y presione el botón para iniciar el análisis.")