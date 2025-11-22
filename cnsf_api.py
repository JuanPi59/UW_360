import requests
import json

# --- Configuración de la API (HIPOTÉTICA) ---

# URL Base: Usamos la URL conocida del SIO como base, aunque el endpoint específico
# puede requerir autenticación o ser diferente en un entorno de producción.
BASE_URL = "http://sio.cnsf.gob.mx/API" 

# Parámetros de la consulta que quieres probar (Inputs)
# La estructura de la API que proporcionaste es: /API/tendenciasmensuales/{operacion}/{cia}/{entidad}
# Nota: La API REAL puede requerir un parámetro de FECHA o PERIODO, que no está en tu estructura, 
# pero es esencial para datos de tendencia. Agregaremos una fecha de forma hipotética en headers.

OPERACION = '46'  # Incendio
CIA = '1948'      # AXA Seguros
ENTIDAD = 'EDO09' # CDMX (Asumiendo que usa un código similar a 'EDOXX')

# Endpoint completo
ENDPOINT = f"/tendenciasmensuales/{OPERACION}/{CIA}/{ENTIDAD}"
FULL_URL = BASE_URL + ENDPOINT

# --- Configuración de Petición ---

# La API del SIO (Sistema de Información Oportuna) de la CNSF requiere típicamente:
# 1. Una clave de API (Authorization) o Token, que NO tenemos públicamente.
# 2. Posiblemente un parámetro de fecha o periodo.

headers = {
    "Accept": "application/json",
    # Intento de simular un token (reemplazar con el real si lo obtienes)
    "Authorization": "Bearer YOUR_API_KEY_HERE", 
    "X-Periodo": "2024Q2" # Periodo necesario (hipotético)
}

# --- Función de Consulta ---

def consultar_api_cnsf_real(url, headers):
    print(f"Intentando conectar a: {url}")
    print(f"Usando headers (simulados): {headers}")
    
    # Intenta la petición HTTP real
    try:
        response = requests.get(url, headers=headers, timeout=15)
        
        # Verificar el código de estado HTTP
        if response.status_code == 200:
            print("\n✅ Conexión exitosa (código 200 OK).")
            return response.json()
        
        elif response.status_code == 401 or response.status_code == 403:
            print(f"\n❌ Error de autenticación (Código {response.status_code}).")
            print("Razón: La API de la CNSF (SIO) requiere una clave de API válida y/o registro formal.")
            return None
            
        else:
            print(f"\n❌ Error en la petición. Código de estado: {response.status_code}")
            print(f"Respuesta del servidor: {response.text[:200]}...")
            return None

    except requests.exceptions.RequestException as e:
        print(f"\n❌ Fallo de conexión o tiempo de espera agotado: {e}")
        print("Verifique la URL base y su conexión a internet.")
        return None

# --- Ejecución ---

# Ejecutar la consulta
datos_json = consultar_api_cnsf_real(FULL_URL, headers)

# --- Análisis del Formato de Salida ---

if datos_json:
    print("\n--- FORMATO DE SALIDA (OUTPUT JSON) ---")
    
    # 1. Impresión completa y formateada (Para ver la estructura)
    print("Estructura JSON Completa:")
    print(json.dumps(datos_json, indent=4, ensure_ascii=False))
    
    print("\n--- EXTRACCIÓN DE DATOS CLAVE (EJEMPLO) ---")
    
    # 2. Ejemplo de cómo iterar sobre una respuesta típica con resultados anidados
    # NOTA: La estructura real puede variar (ej: ['data'], ['resultados'], ['tendencias'])
    
    try:
        # ASUMIENDO que la respuesta es un arreglo de resultados:
        if isinstance(datos_json, list) and len(datos_json) > 0:
            primer_registro = datos_json[0]
            print(f"Primer Registro (Elemento clave: '{list(primer_registro.keys())[0] if primer_registro else 'N/A'}'):")
            
            # Buscar el campo que contenga el IDNIVEL (e.g., "IDNIVEL") y el Valor (e.g., "VALOR")
            id_nivel_key = next((k for k in primer_registro.keys() if 'IDNIVEL' in k.upper()), 'IDNIVEL_KEY')
            valor_key = next((k for k in primer_registro.keys() if 'VALOR' in k.upper() or 'MONTO' in k.upper()), 'VALOR_KEY')
            
            print(f"  > ID Nivel (Métrica): {primer_registro.get(id_nivel_key, 'N/A')}")
            print(f"  > Valor (Monto): {primer_registro.get(valor_key, 'N/A')}")
            
        elif isinstance(datos_json, dict):
            print("La respuesta es un diccionario (objeto JSON). Se buscará una clave de resultados ('data', 'results', etc.).")
            # En una API estructurada, buscaríamos la lista de resultados dentro del diccionario.
            
            # EJEMPLO HIPOTÉTICO de extracción si está bajo la clave 'data'
            resultados = datos_json.get('data', datos_json.get('resultados', []))
            
            if isinstance(resultados, list) and len(resultados) > 0:
                primer_registro = resultados[0]
                # Repetimos la lógica de extracción de claves para el primer resultado
                id_nivel_key = next((k for k in primer_registro.keys() if 'IDNIVEL' in k.upper()), 'IDNIVEL_KEY')
                valor_key = next((k for k in primer_registro.keys() if 'VALOR' in k.upper() or 'MONTO' in k.upper()), 'VALOR_KEY')

                print(f"  > Primer Registro (ID Nivel): {primer_registro.get(id_nivel_key, 'N/A')}")
                print(f"  > Primer Registro (Valor): {primer_registro.get(valor_key, 'N/A')}")
            else:
                 print("  No se encontró una lista de resultados válida en las claves comunes ('data', 'resultados').")

        
    except Exception as e:
        print(f"Error al intentar parsear el formato JSON: {e}")
        print("La estructura de la respuesta no coincide con el formato esperado.")