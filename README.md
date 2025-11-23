# UW_360
Repositorio para asistente virtual para suscripción de seguros de daños empresariales
# 🛡️ Suscriptor 360  
### Plataforma inteligente para apoyo en suscripción de seguros de daños empresariales

Suscriptor 360 es una aplicación web desarrollada en **Python + Streamlit** que apoya el proceso de suscripción en seguros de daños para empresas en México, combinando:

- Análisis histórico de siniestralidad.
- Modelos predictivos usando **XGBoost**.
- Un asistente conversacional con **OpenAI** especializado en riesgos asegurables.

---

## 🚀 Funcionalidades principales

✅ Selección dinámica de:
- **Entidad federativa**
- **Sector económico**
- **Giro del negocio**

✅ Visualización de:
- Histórico del **índice de siniestralidad neta** (`net_sin_index`)
- Predicción para los próximos **2 años** mediante modelo de machine learning.

✅ Chatbot especializado:
- Basado en un prompt diseñado para suscripción de seguros.
- Integra contexto del caso actual (entidad, sector, giro).
- Responde preguntas sobre riesgos, siniestralidad y entorno.

✅ Panel visual con:
- Layout tipo dashboard.
- Historial de chat con scroll automático.
- Predicciones persistentes entre interacciones.

---

## 🧱 Estructura del proyecto

Suscriptor360/
│
│── app.py # Aplicación principal en Streamlit
│── prompts.py # Prompt de sistema para el chatbot
├── data_cnsf/
│└── df_proc.parquet # Dataset final preprocesado
│
├── data_cnsf/ # Datos crudos descargados de la CNSF
│ └── *.xlsx
│
├── notebooks/
│ └── UW_360_V2.ipynb Notebook de web scraping y EDA
│
└── README.md

yaml
Copy code

---

## 🛠️ Requisitos

Necesitas tener Python 3.9 o superior.

Instala las dependencias:

```bash
pip install streamlit pandas numpy scikit-learn xgboost openai pyarrow beautifulsoup4 requests
🔐 Configuración de API OpenAI
En Streamlit debes configurar tu API Key en un archivo secrets.toml dentro de:

bash
Copy code
.streamlit/secrets.toml
Con el contenido:

toml
Copy code
openai_api_key = "TU_API_KEY_AQUI"
▶️ Cómo ejecutar la aplicación
Desde la raíz del proyecto:

bash
Copy code
streamlit run app.py
Luego abre en tu navegador:

👉 http://localhost:8501

🧠 Flujo de la aplicación
Se cargan los datos preprocesados (df_proc.parquet).

El usuario selecciona entidad, sector y giro.

El sistema:

Filtra datos históricos.

Ejecuta predicción con XGBoost.

Se genera una tabla: histórico + predicción.

El usuario puede interactuar con el chatbot para analizar el caso.

🧪 Tecnologías utilizadas
Tecnología	Uso
Python	Backend principal
Streamlit	Interfaz de usuario
Pandas / NumPy	Procesamiento de datos
XGBoost	Modelo predictivo
OpenAI API	Asistente conversacional
BeautifulSoup	Web Scraping CNSF
Scikit-Learn	Preprocesamiento ML

🎓 Contexto académico
Este proyecto fue desarrollado como parte de un trabajo académico enfocado en:

Aplicación de inteligencia artificial y modelos predictivos en el proceso de suscripción de seguros de daños empresariales en México.

Utiliza datos públicos de la Comisión Nacional de Seguros y Fianzas (CNSF).

📌 Notas importantes
El sistema no sustituye el criterio del suscriptor humano.

Las predicciones son un insumo de apoyo basado en información histórica.

El chatbot se enfoca en análisis cualitativo contextual, no emite decisiones finales.

👤 Autor
Proyecto desarrollado por:
Juan Pablo Guzmán
