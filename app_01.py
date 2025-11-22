import streamlit as st
import pandas as pd
from openai import OpenAI
import json
import os
import re # Necesario para la función estandarizar_columnas
from prompts import final_prompt

# --- Configuración Inicial y Carga de Datos ---

# Asume que API_KEY está cargada desde st.secrets
try:
    API_KEY = st.secrets["openai_api_key"]
    client = OpenAI(api_key=API_KEY)
except Exception as e:
    st.error(f"Error al inicializar OpenAI: {e}. Asegúrese de configurar 'openai_api_key' en st.secrets.")
    client = None

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
        st.error(f"Error crítico: Archivo de configuración no encontrado. Detalle: {e}")
        st.stop()
    except Exception as e:
        st.error(f"Error al leer archivos JSON: {e}")
        st.stop()

def guardar_configuracion(nuevas_tarifas):
    """Guarda la configuración actualizada de tarifas y apetito de riesgo en el archivo JSON."""
    try:
        with open('data_config/tarifas_riesgo.json', 'w', encoding='utf-8') as f:
            json.dump(nuevas_tarifas, f, indent=4)
        return True
    except Exception as e:
        st.error(f"Error al guardar la configuración: {e}")
        return False

# Carga global de la configuración
CATALOGOS, TARIFAS = cargar_configuracion()
TASA_BASE = TARIFAS.get("tasa_base", {})
APETITO_RIESGO = TARIFAS.get("apetito_riesgo", {})


st.set_page_config(
    page_title="Underwriter 360 | Suscripción Inteligente",
    layout="wide"
)
st.title("🛡️ Underwriter 360: Suscripción Inteligente")
st.markdown("Herramienta de Ciencia de Datos para la evaluación de riesgos empresariales.")

# --- 1. Funciones del Chatbot y PLN ---

def buscar_resumir(giro_key, estado_key):
    """
    Obtener un resumen de riesgo con formato de extracción (solo para la primera consulta).
    """
    if not client:
        return "ERROR_API"
        
    giro = CATALOGOS["giro_industria"].get(giro_key, "Giro Desconocido")
    estado = CATALOGOS["ubicacion_estado"].get(estado_key, "Ubicación Desconocida")
    
    prompt_extraccion = f"""
    TAREA PRINCIPAL: Realiza una búsqueda exhaustiva en de noticias en internet de los últimos 3 años sobre siniestralidad,
    exposición catastrófica o riesgos regulatorios para la industria de '{giro}' en la región de '{estado}'.
    En caso de no encontrar noticias relevantes sobre la combinación Giro/Ubicación,
    busca información general sobre riesgos en la industria de '{giro}' en México.
    
    FORMATO DE SALIDA REQUERIDO (¡CRÍTICO PARA EL SISTEMA!):
    Genera el siguiente formato EXCLUSIVAMENTE al inicio de tu respuesta, sin texto introductorio, para que el código lo pueda parsear. Utiliza la tasa base (por mil) para el giro de '{giro}' en 'CUOTA_ESTIMADA'
    
    CLASIFICACION_RIESGO: [Bajo/Medio/Alto]
    CUOTA_ESTIMADA: [Número, tasa por mil]
    
    NOTICIAS:
    - [Fecha de publicación] [Título 1] [Enlace de la noticia]
    - [Fecha de publicación] [Título 2] [Enlace de la noticia]
    - [Fecha de publicación] [Título 3] [Enlace de la noticia]
    
    RESUMEN DE RIESGO: 
    [Genera un resumen conciso de 5 líneas sobre los principales riesgos agravantes encontrados.]
    
    Aplica el 'Rol principal' y el 'Estilo y Tono' definidos en tu mensaje de sistema.
    """
    
    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo", # Usamos un modelo estándar
            messages=[
                {"role": "system", "content": final_prompt}, # Carga el Rol, Seguridad y Estilo
                {"role": "user", "content": prompt_extraccion} # Da la tarea y el formato de extracción
            ],
            temperature=0.7
        )
        return response.choices[0].message.content
    except Exception as e:
        st.error(f"Error al conectar con OpenAI. Revisar API Key o permisos: {e}")
        return "ERROR_API"

# --- 2. Secciones de Streamlit (Pestañas) ---

def inputs_usuario():
    """
    Define la sección 1: Entrada de datos del suscriptor y dispara la consulta a la IA (Cambio 1).
    """
    st.header("1. 📝 Input de Datos del Negocio")
    st.markdown("Ingrese los datos del riesgo a evaluar.")
    
    # Inicializa el estado de la sesión si no existe (para persistencia)
    if "submitted" not in st.session_state:
        st.session_state["submitted"] = False
    if "ia_response" not in st.session_state:
        st.session_state["ia_response"] = None
    if "messages" not in st.session_state:
        st.session_state["messages"] = []

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
            min_value=0,
            value=10000000, # Valor por defecto
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
        
        # Botón de Envío (Cambio 1)
        submit_button = st.form_submit_button("1. Evaluar Riesgo y Consultar IA")
        
    if submit_button:
        # Resetear la conversación anterior
        st.session_state["messages"] = []
        st.session_state["submitted"] = True
        
        datos_capturados = {
            "giro_key": st.session_state.get("giro_key"),
            "estado_key": st.session_state.get("estado_key"),
            "suma_asegurada": st.session_state.get("suma_asegurada"),
            "medidas_prevencion": st.session_state.get("medidas_prevencion")
        }

        # --- LÓGICA DE CONSULTA DIRECTA (Cambio 1) ---
        if client:
            with st.spinner(f"Consultando fuentes externas sobre {CATALOGOS['giro_industria'].get(datos_capturados['giro_key'])} en {CATALOGOS['ubicacion_estado'].get(datos_capturados['estado_key'])}..."):
                ai_output = buscar_resumir(datos_capturados['giro_key'], datos_capturados['estado_key'])
                st.session_state["ia_response"] = ai_output # Guarda la respuesta
                st.session_state["messages"].append(
                    {"role": "assistant", "content": "Hola! ¿Tienes alguna pregunta sobre el resumen de riesgo o los factores de siniestralidad encontrados?"}
                )
                
                if ai_output != "ERROR_API":
                    st.success("Análisis de Riesgo y contexto completado. Revise las pestañas 2 y 3.")
        else:
            st.error("No se puede contactar a OpenAI. Verifique su API Key.")
            
    # Devolver los datos capturados para su uso posterior
    return {
        "giro_key": st.session_state.get("giro_key"),
        "estado_key": st.session_state.get("estado_key"),
        "suma_asegurada": st.session_state.get("suma_asegurada"),
        "medidas_prevencion": st.session_state.get("medidas_prevencion")
    }

def seccion_chatbot(datos):
    """
    Define la sección 2: Chatbot especializado (Cambios 2, 3, 4 y 5).
    """
    st.header("2. 🤖 Chatbot de Riesgos Empresariales (PLN)")
    st.markdown("Consulta para obtener contexto de riesgo externo y noticias recientes.")
    
    # Mostrar resultados de la IA
    if st.session_state.get("ia_response") and st.session_state["ia_response"] != "ERROR_API":
        resultado_pln = st.session_state["ia_response"]
        
        try:
            # Extracción del resumen y noticias
            partes = resultado_pln.split("RESUMEN DE RIESGO:")
            
            # La primera parte contiene CLASIFICACION_RIESGO, CUOTA_ESTIMADA, y NOTICIAS
            noticias_raw = partes[0].split("NOTICIAS:")[-1].strip()
            
            # La segunda parte contiene RESUMEN DE RIESGO
            resumen_section = partes[1].split("CLASIFICACION_RIESGO:")[0].strip()

            # --- Visualización de Noticias y Resumen (Cambio 4) ---
            st.subheader("📰 Noticias y Enlaces Encontrados")
            # Usamos markdown para renderizar las noticias con sus enlaces
            st.markdown(noticias_raw) # Muestra el texto tal como lo devuelve la IA
            
            st.subheader("🔍 Resumen de Riesgo Agravante")
            st.markdown(f"**{resumen_section}**")
            
            # --- Chat Interactivo (Cambios 2 y 3) ---
            st.divider()
            st.info("Ahora puedes usar el chatbot para hacer preguntas sobre el resumen de riesgo.")
            
            # CAMBIO 2: Contenedor de tamaño fijo para el chat
            chat_container = st.container(height=400) 
            
            # CAMBIO 3: Mostrar historial de mensajes (orden natural para que el input quede abajo)
            for message in st.session_state["messages"]:
                 with chat_container:
                     with st.chat_message(message["role"]):
                         st.markdown(message["content"])

            # Captura de input del usuario para el chat
            if prompt := st.chat_input("Escribe tu pregunta aquí..."):
                st.session_state["messages"].append({"role": "user", "content": prompt})
                # Volver a renderizar para mostrar el mensaje del usuario inmediatamente
                st.rerun() 
            
            # Si el último mensaje es del usuario, generar la respuesta
            if st.session_state["messages"] and st.session_state["messages"][-1]["role"] == "user":
                
                # 1. Definir el contexto inicial
                contexto_inicial = f"El resumen de riesgo es: {resumen_section}. Las noticias son: {noticias_raw}"
                
                # 2. CAMBIO 5: Modificar el prompt para incluir la búsqueda real, usando el contexto como referencia.
                chat_prompt = f"""
                Basándote en tu rol de UW 360, realiza una búsqueda externa sobre el tema: '{prompt}'.
                
                Luego, usa el siguiente contexto de riesgo inicial como referencia para contextualizar tu respuesta y asegurarte de que es relevante para la suscripción de seguros de daños:
                
                CONTEXTO INICIAL: {contexto_inicial}
                
                Responde la pregunta aplicando el estilo definido en tu mensaje de sistema.
                """
                
                with st.chat_message("assistant"):
                    with st.spinner("Analizando pregunta y realizando búsqueda contextualizada..."):
                        chat_response = client.chat.completions.create(
                            model="gpt-3.5-turbo",
                            messages=[
                                {"role": "system", "content": final_prompt},
                                {"role": "user", "content": chat_prompt} 
                            ],
                            temperature=0.44
                        )
                        respuesta_ia = chat_response.choices[0].message.content
                        st.markdown(respuesta_ia)
                        st.session_state["messages"].append({"role": "assistant", "content": respuesta_ia})
                        st.rerun() # Volver a renderizar para actualizar el historial
        
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
                # Extracción de valores de IA
                # Aseguramos la robustez buscando las etiquetas CLASIFICACION_RIESGO y CUOTA_ESTIMADA
                clasificacion_ia = resultado_pln.split("CLASIFICACION_RIESGO:")[1].split("\n")[0].strip()
                
                # La IA devuelve la TASA por mil, no la cuota total
                cuota_ia_tasa_str = resultado_pln.split("CUOTA_ESTIMADA:")[1].split("\n")[0].strip().replace('$', '').replace(',', '')
                cuota_ia_tasa = float(cuota_ia_tasa_str)
                cuota_ia_estimada = round((suma_asegurada / 1000) * cuota_ia_tasa, 2)
                
                # Cálculo de Delta para comparación
                delta_cuota = cuota_ia_estimada - cuota_calculada_base
                delta_color = "inverse" if delta_cuota > 0 else "normal" # Rojo si sube (mayor riesgo), Verde si baja
                
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
                st.warning("No se pudieron extraer los valores de la IA.")
                st.error(f"Error de extracción. Detalle: {e}")
                
        else:
            st.warning("Ejecute la consulta en la pestaña '1. Input de Datos' para obtener los resultados de la IA.")

def seccion_administracion():
    """Define la sección 4: Parametrización de Apetito de Riesgo y Tarifas Base."""
    
    st.header("4. ⚙️ Administración y Parametrización")
    st.warning("⚠️ **Advertencia:** Esta sección solo debe ser utilizada por administradores o actuarios. Los cambios afectan directamente la lógica de suscripción y la Cuota Base.")
    st.divider()

    global TARIFAS # Acceso a la variable global
    
    tab_riesgo, tab_tarifa = st.tabs(["Apetito de Riesgo (Umbrales)", "Factores de Tarifa Base"])

    # --- Pestaña 1: Gestión de Apetito de Riesgo (APETITO_RIESGO) ---
    with tab_riesgo:
        st.subheader("Clasificación de Riesgo Base por Giro")
        
        with st.form("form_apetito_riesgo"):
            nuevos_apetitos = {}
            giros_ordenados = sorted(APETITO_RIESGO.keys())
            
            for giro_key in giros_ordenados:
                giro_nombre = CATALOGOS["giro_industria"][giro_key]
                valor_actual = APETITO_RIESGO[giro_key]
                
                opciones = ["Bajo", "Medio", "Alto", "Riesgo Excluido"]
                nuevos_apetitos[giro_key] = st.selectbox(
                    f"**{giro_nombre} ({giro_key})**",
                    options=opciones,
                    index=opciones.index(valor_actual),
                    key=f"ap_riesgo_{giro_key}"
                )
            
            submit_riesgo = st.form_submit_button("Guardar Cambios de Apetito de Riesgo")
            
            if submit_riesgo:
                TARIFAS["apetito_riesgo"] = nuevos_apetitos
                if guardar_configuracion(TARIFAS):
                    st.success("✅ Apetito de Riesgo actualizado y guardado. Recargando...")
                    st.rerun() 
                else:
                    st.error("❌ No se pudieron guardar los cambios.")
    
    # --- Pestaña 2: Gestión de Tasas Base (TASA_BASE) ---
    with tab_tarifa:
        st.subheader("Tasa Base de Cuota por Mil (TASA_BASE)")
        
        with st.form("form_tasa_base"):
            
            nuevas_tasas = {}
            giros_ordenados = sorted(TASA_BASE.keys())

            for giro_key in giros_ordenados:
                giro_nombre = CATALOGOS["giro_industria"][giro_key]
                valor_actual = TASA_BASE[giro_key]

                nuevas_tasas[giro_key] = st.number_input(
                    f"Tasa Base (por mil) para **{giro_nombre} ({giro_key})**",
                    min_value=0.0,
                    max_value=100.0,
                    value=float(valor_actual),
                    step=0.1,
                    format="%.2f",
                    key=f"tasa_base_{giro_key}"
                )

            submit_tarifa = st.form_submit_button("Guardar Cambios de Tasa Base")

            if submit_tarifa:
                TARIFAS["tasa_base"] = nuevas_tasas
                if guardar_configuracion(TARIFAS):
                    st.success("✅ Tasas Base actualizadas y guardadas. Recargando...")
                    st.rerun()
                else:
                    st.error("❌ No se pudieron guardar los cambios.")


# --- 3. Función Principal de la Aplicación ---

if __name__ == "__main__":
    
    # 3.1. Sección 1: Input de Datos (Renderizada fuera de pestañas para mantener el estado del formulario)
    datos_suscripcion = inputs_usuario() 
    
    st.sidebar.subheader("Datos Capturados")
    st.sidebar.json({k: v for k, v in datos_suscripcion.items() if k != "submitted"})
    
    st.divider()

    # 3.2. Definición y Navegación de Pestañas
    tab2, tab3, tab4 = st.tabs(["2. 🤖 Chatbot Especializado", "3. 📊 Resultados Finales", "4. ⚙️ Administración"])
    
    
    if st.session_state.get("submitted"):
        
        # 3.3. Sección 2: Chatbot y PLN
        with tab2:
            seccion_chatbot(datos_suscripcion)
        
        # 3.4. Sección 3: Resultados
        with tab3:
            seccion_resultados(datos_suscripcion)
            
    else:
        # Mensaje si el usuario no ha enviado el formulario
        with tab2:
             st.info("Para ver el Chatbot y Resultados, complete el formulario en '1. Input de Datos' y presione el botón.")
        with tab3:
             st.info("Para ver el Chatbot y Resultados, complete el formulario en '1. Input de Datos' y presione el botón.")
    
    # 3.5. Sección 4: Administración (Siempre accesible)
    with tab4:
        seccion_administracion()