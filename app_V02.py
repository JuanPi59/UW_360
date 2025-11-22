import streamlit as st
import pandas as pd
from openai import OpenAI
import json
import os
import re 
# El archivo prompts.py debe existir y contener la variable final_prompt
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

# ======================================================================
## 1. ⚙️ Nueva Función: Simulación de API CNSF (Siniestralidad)

def consultar_cnsf_api(giro_key, estado_key):
    """
    SIMULA la consulta a una API estructurada (CNSF, SIO, etc.)
    para obtener métricas de siniestralidad.

    Retorna un diccionario de datos estructurados para el análisis.
    """
    
    # Simulación de datos reales por Giro/Estado
    # Nota: En una implementación real, aquí iría el request a la API (requests.get(...)).
    
    # Base de Siniestralidad (Simulada, depende de la clave del giro)
    siniestralidad_base = {
        "GIRO01": 0.55, # Manufactura
        "GIRO02": 0.40, # Servicios
        "GIRO03": 0.65, # Construcción
    }
    
    # Ajuste por Estado (Simulada, penaliza estados con historial de catástrofes/delitos)
    ajuste_estado = {
        "EDO09": 1.15,  # CDMX (Alta concentración/delito)
        "EDO14": 1.20,  # Jalisco (Desastres naturales/incendios)
        "EDO19": 0.85,  # Nuevo León (Baja relativa, buena prevención)
    }
    
    siniestralidad_base_value = siniestralidad_base.get(giro_key, 0.50)
    ajuste_estado_value = ajuste_estado.get(estado_key, 1.0)
    
    siniestralidad_final = siniestralidad_base_value * ajuste_estado_value
    
    # ------------------------------------------------
    # Datos Estructurados que reemplazan la búsqueda de noticias
    # ------------------------------------------------
    datos_estructurados = {
        "siniestralidad_sector": round(siniestralidad_final, 3), # Tasa de Siniestralidad Histórica
        "factor_catastrofico": ajuste_estado_value,              # Factor de Riesgo Catastrófico por Estado
        "monto_siniestro_promedio": 1250000 + (siniestralidad_final * 500000), # Monto promedio de siniestro
        "observacion_tecnica": f"La Tasa de Siniestralidad del sector '{CATALOGOS['giro_industria'][giro_key]}' es de {siniestralidad_base_value * 100:.1f}%. El Estado '{CATALOGOS['ubicacion_estado'][estado_key]}' impone un factor de ajuste de {ajuste_estado_value:.2f} por riesgo catastrófico e histórico de incidentes."
    }
    
    return datos_estructurados

# ======================================================================

def generar_analisis_contextual(datos_api, datos_input):
    """
    Usa los datos de la API para pedirle a la IA que genere un análisis contextual 
    que sirva como el 'prompt inicial' para el chat.
    """
    if not client:
        return "ERROR_API"
    
    giro = CATALOGOS["giro_industria"][datos_input["giro_key"]]
    estado = CATALOGOS["ubicacion_estado"][datos_input["estado_key"]]
    tasa_base = TASA_BASE.get(datos_input["giro_key"], 1.0)

    prompt_analisis = f"""
    TAREA PRINCIPAL: Actúa como analista de riesgo de UW 360. Genera un análisis de riesgo inicial 
    para la suscripción del cliente. Utiliza EXCLUSIVAMENTE los datos estructurados proporcionados a continuación
    para justificar la clasificación de riesgo y la cuota estimada.
    
    DATOS ESTRUCTURADOS DE LA CNSF/SIO:
    - Giro Industrial: {giro}
    - Ubicación: {estado}
    - Siniestralidad Histórica del Sector (CNSF): {datos_api['siniestralidad_sector']:.2f}
    - Factor de Riesgo Catastrófico (Estado): {datos_api['factor_catastrofico']:.2f}
    - Monto de Siniestro Promedio: ${datos_api['monto_siniestro_promedio']:,.0f} MXN
    - Observación Técnica: {datos_api['observacion_tecnica']}
    - Tasa Base por Catálogo: {tasa_base:.2f} por mil.
    
    REGLAS DE CLASIFICACIÓN SUGERIDAS:
    - Si la Siniestralidad del Sector es < 0.45, CLASIFICACION_RIESGO: Bajo
    - Si la Siniestralidad del Sector está entre 0.45 y 0.60, CLASIFICACION_RIESGO: Medio
    - Si la Siniestralidad del Sector es > 0.60, CLASIFICACION_RIESGO: Alto
    
    CÁLCULO DE CUOTA ESTIMADA (TASA POR MIL):
    Cuota Estimada (Tasa por Mil) = (Tasa Base por Catálogo) * (1 + (Siniestralidad Sector - 0.50))
    
    FORMATO DE SALIDA REQUERIDO (¡CRÍTICO PARA EL SISTEMA!):
    Genera el siguiente formato EXCLUSIVAMENTE al inicio de tu respuesta, sin texto introductorio:
    
    CLASIFICACION_RIESGO: [Bajo/Medio/Alto]
    CUOTA_ESTIMADA: [Resultado del cálculo de Tasa por Mil (solo número)]
    
    ANÁLISIS TÉCNICO:
    [Genera un análisis conciso de 5 líneas justificando la clasificación y la cuota usando los datos estructurados. NO MENCIONES NOTICIAS.]
    
    Aplica el 'Rol principal' y el 'Estilo y Tono' definidos en tu mensaje de sistema.
    """
    
    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo", 
            messages=[
                {"role": "system", "content": final_prompt}, 
                {"role": "user", "content": prompt_analisis}
            ],
            temperature=0.3 # Baja temperatura para que se apegue a los datos
        )
        # La respuesta ahora incluye el contexto completo (ANÁLISIS TÉCNICO) y la extracción
        return response.choices[0].message.content, datos_api
    except Exception as e:
        st.error(f"Error al generar el análisis contextual: {e}")
        return "ERROR_API", datos_api


# ======================================================================
# --- 2. Secciones de Streamlit (Pestañas) ---

def inputs_usuario():
    # ... (Se mantiene igual, solo cambia la función llamada en submit_button)
    st.header("1. 📝 Input de Datos del Negocio")
    st.markdown("Ingrese los datos del riesgo a evaluar.")
    
    # Inicializa el estado de la sesión si no existe (para persistencia)
    if "submitted" not in st.session_state:
        st.session_state["submitted"] = False
    if "ia_response" not in st.session_state:
        st.session_state["ia_response"] = None
    if "messages" not in st.session_state:
        st.session_state["messages"] = []
    if "api_data" not in st.session_state: # Nuevo estado para guardar los datos de la API
        st.session_state["api_data"] = None

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
        submit_button = st.form_submit_button("1. Evaluar Riesgo y Consultar Análisis CNSF")
        
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

        # --- LÓGICA DE CONSULTA DE API ESTRUCTURADA ---
        if client:
            with st.spinner(f"Consultando API CNSF y generando análisis contextual para {CATALOGOS['giro_industria'].get(datos_capturados['giro_key'])}..."):
                
                # 1. Consultar la API simulada (datos estructurados)
                api_data = consultar_cnsf_api(datos_capturados['giro_key'], datos_capturados['estado_key'])
                
                # 2. Generar el análisis contextual usando la IA
                ai_output, api_data_context = generar_analisis_contextual(api_data, datos_capturados)

                st.session_state["ia_response"] = ai_output # Guarda la respuesta de la IA
                st.session_state["api_data"] = api_data_context # Guarda los datos de la API para referencia

                st.session_state["messages"].append(
                    {"role": "assistant", "content": "Hola! ¿Tienes alguna pregunta sobre el análisis de siniestralidad de la CNSF que acabamos de generar?"}
                )
                
                if ai_output != "ERROR_API":
                    st.success("Análisis de Riesgo completado con datos CNSF. Revise las pestañas 2 y 3.")
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
    Define la sección 2: Chatbot especializado (ahora basado en el análisis estructurado de la CNSF).
    """
    st.header("2. 🤖 Chatbot de Riesgos Empresariales (PLN)")
    st.markdown("Consulta contextual basada en el análisis de siniestralidad (CNSF/SIO) y búsqueda web ampliada.")
    
    # Mostrar resultados de la IA
    if st.session_state.get("ia_response") and st.session_state["ia_response"] != "ERROR_API":
        resultado_pln = st.session_state["ia_response"]
        api_data = st.session_state["api_data"]
        
        try:
            # Extracción del análisis y la clasificación
            partes = resultado_pln.split("ANÁLISIS TÉCNICO:")
            
            # El análisis técnico
            analisis_tecnico = partes[1].split("CLASIFICACION_RIESGO:")[0].strip()

            # --- Visualización de Datos de la API ---
            st.subheader("📊 Datos Estructurados de Siniestralidad (CNSF/SIO)")
            col_sin, col_fac = st.columns(2)
            with col_sin:
                st.metric("Tasa de Siniestralidad del Sector", f"{api_data['siniestralidad_sector']:.2%}")
                st.metric("Monto Promedio de Siniestro", f"${api_data['monto_siniestro_promedio']:,.0f} MXN")
            with col_fac:
                st.metric("Factor de Riesgo Catastrófico (Estado)", f"{api_data['factor_catastrofico']:.2f}")
                st.info(api_data['observacion_tecnica'])


            st.subheader("🔍 Análisis Contextual del Riesgo")
            st.markdown(f"**{analisis_tecnico}**")
            
            # --- Chat Interactivo ---
            st.divider()
            st.info("Ahora puedes usar el chatbot para hacer preguntas sobre el análisis técnico o buscar información externa complementaria.")
            
            # Contenedor de tamaño fijo para el chat
            chat_container = st.container(height=400) 
            
            # Mostrar historial de mensajes
            for message in st.session_state["messages"]:
                 with chat_container:
                     with st.chat_message(message["role"]):
                         st.markdown(message["content"])

            # Captura de input del usuario para el chat
            if prompt := st.chat_input("Escribe tu pregunta aquí..."):
                st.session_state["messages"].append({"role": "user", "content": prompt})
                st.rerun() 
            
            # Generar la respuesta si el último mensaje es del usuario
            if st.session_state["messages"] and st.session_state["messages"][-1]["role"] == "user":
                
                # 1. Definir el contexto inicial
                contexto_inicial = f"El análisis de riesgo se basa en la Siniestralidad Histórica del Sector ({api_data['siniestralidad_sector']:.2f}) y el Factor Catastrófico del Estado ({api_data['factor_catastrofico']:.2f}). El Análisis Técnico es: {analisis_tecnico}"
                
                # 2. Modificar el prompt para incluir la búsqueda real, usando el contexto como referencia.
                chat_prompt = f"""
                Basándote en tu rol de UW 360, realiza una búsqueda externa sobre el tema: '{st.session_state["messages"][-1]["content"]}'.
                
                Luego, usa el siguiente contexto de datos de siniestralidad como referencia para contextualizar tu respuesta y asegurarte de que es relevante para la suscripción de seguros de daños:
                
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
                        st.rerun() 
        
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
        
    # 3.2. Resultados de la IA (Basados en Datos CNSF)
    with col_ia:
        st.subheader("Resultados Estimados por Análisis Técnico")
        
        if st.session_state.get("ia_response") and st.session_state["ia_response"] != "ERROR_API":
            resultado_pln = st.session_state["ia_response"]
            
            try:
                # Extracción de valores de IA
                clasificacion_ia = resultado_pln.split("CLASIFICACION_RIESGO:")[1].split("\n")[0].strip()
                
                # La IA devuelve la TASA por mil, no la cuota total
                cuota_ia_tasa_str = resultado_pln.split("CUOTA_ESTIMADA:")[1].split("\n")[0].strip().replace('$', '').replace(',', '')
                cuota_ia_tasa = float(cuota_ia_tasa_str)
                cuota_ia_estimada = round((suma_asegurada / 1000) * cuota_ia_tasa, 2)
                
                # Cálculo de Delta para comparación
                delta_cuota = cuota_ia_estimada - cuota_calculada_base
                delta_color = "inverse" if delta_cuota > 0 else "normal" 
                
                st.metric(
                    label="Cuota Estimada por Análisis (MXN)",
                    value=f"${cuota_ia_estimada:,.2f}",
                    delta=f"{delta_cuota:,.2f} vs Catálogo",
                    delta_color=delta_color
                )
                st.metric(
                    label="Clasificación de Riesgo Final",
                    value=clasificacion_ia,
                    delta="Basado en Siniestralidad Histórica CNSF/SIO"
                )
                
            except Exception as e:
                st.warning("No se pudieron extraer los valores de la IA.")
                st.error(f"Error de extracción. Detalle: {e}")
                
        else:
            st.warning("Ejecute la consulta en la pestaña '1. Input de Datos' para obtener los resultados del análisis.")

def seccion_administracion():
    """Define la sección 4: Parametrización de Apetito de Riesgo y Tarifas Base."""
    
    st.header("4. ⚙️ Administración y Parametrización")
    st.warning("⚠️ **Advertencia:** Esta sección solo debe ser utilizada por administradores o actuarios. Los cambios afectan directamente la lógica de suscripción y la Cuota Base.")
    st.divider()

    global TARIFAS 
    
    tab_riesgo, tab_tarifa = st.tabs(["Apetito de Riesgo (Umbrales)", "Factores de Tarifa Base"])

    # --- Pestaña 1: Gestión de Apetito de Riesgo (APETITO_RIESGO) ---
    with tab_riesgo:
        st.subheader("Clasificación de Riesgo Base por Giro")
        
        with st.form("form_apetito_riesgo"):
            nuevos_apetitos = {}
            giros_ordenados = sorted(APETITO_RIESGO.keys())
            
            # Lista completa de opciones, incluyendo posibles valores anteriores para evitar errores.
            opciones = ["Bajo", "Medio", "Medio-Alto", "Alto", "Riesgo Excluido"] 
            
            for giro_key in giros_ordenados:
                giro_nombre = CATALOGOS["giro_industria"][giro_key]
                valor_actual = APETITO_RIESGO[giro_key]
                
                # Manejo de error para valores que puedan venir del JSON pero que no están en la lista de opciones
                try:
                    indice_seleccionado = opciones.index(valor_actual)
                except ValueError:
                    indice_seleccionado = opciones.index("Medio")
                    st.warning(f"El valor '{valor_actual}' en el JSON para {giro_nombre} no es estándar. Seleccione un valor nuevo.")

                # Crear un selectbox para cada giro
                nuevos_apetitos[giro_key] = st.selectbox(
                    f"**{giro_nombre} ({giro_key})**",
                    options=opciones,
                    index=indice_seleccionado, 
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
    
    # 3.1. Sección 1: Input de Datos
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