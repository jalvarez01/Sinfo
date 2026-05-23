# SIPS — Sistema Inteligente de Pedido Sugerido

Solución de inteligencia artificial desplegada en la nube para automatizar la generación de pedidos de insumos de **Inversiones Pulso S.A.S.**, empresa que administra los restaurantes Los Birria en sus cuatro sedes de Medellín: Gastrobar, Express, Bistro y Mekato.

El sistema analiza el histórico de ventas, lo cruza con las recetas estandarizadas para obtener el consumo real de insumos, aplica modelos predictivos con estacionalidad (Meta Prophet) y entrega sugerencias de pedido por sede que el Chef puede revisar, ajustar y aprobar desde su celular.

---

## Información de los Estudiantes
- **Nombres Completos:** Juan José Álvarez Ocampo, Emmanuel Castaño Sepúlveda, Santiago, Meneses Carvajal, Pablo José Benitez y Santiago Salazar Gilchrist

- **Clase:** SI2008
- **Curso:** Sistemas de Información
- **Profesora:** Liliana Gonzalez Palacio

## Ambiente de Producción
- **Sistema Operativo:** Windows 11 Pro, Version 10.0.22621, x64-based PC. And macOS Tahoe 26.0.1
- **Procesador:** Intel64 Family 6 Model 142 Stepping 10, ~2001 MHz, Apple Silicon M4, y Apple Silicon M2
- **Memoria:** 16 GB RAM, 512 GB 
- **Terminal:** PowerShell 5.1 and zsh 5.9 (arm64-apple-darwin25.0)

---

## Tabla de Contenidos

1. [Requisitos previos](#requisitos-previos)
2. [Instalación local](#instalación-local)
3. [Configuración](#configuración)
4. [Uso del sistema](#uso-del-sistema)
   - [Opción A — Ejecución local](#opción-a--ejecución-local)
   - [Opción B — Consumo desde la nube (Cloud Run)](#opción-b--consumo-desde-la-nube-cloud-run)
5. [Despliegue en Google Cloud Run](#despliegue-en-google-cloud-run)
6. [Arquitectura y stack tecnológico](#arquitectura-y-stack-tecnológico)
7. [Pipeline de predicción](#pipeline-de-predicción)
8. [Estructura del proyecto](#estructura-del-proyecto)
9. [Pruebas](#pruebas)
10. [Restricciones y exclusiones](#restricciones-y-exclusiones)
11. [Equipo de trabajo](#equipo-de-trabajo)

---

## Requisitos previos

- Python 3.11 o superior
- Cuenta de Google con acceso al Google Sheet del cliente
- Service Account de Google Cloud con permisos sobre Google Sheets API y Google Drive API
- (Opcional) Google Cloud CLI (`gcloud`) si se desea desplegar en Cloud Run

---

## Instalación local

```bash
git clone <url-del-repositorio>
cd Sinfo
python -m venv venv
source venv/bin/activate          # Linux/macOS
# .\venv\Scripts\activate         # Windows
pip install --upgrade pip
pip install -r requirements.txt
```

---

## Configuración

### 1. Credenciales de Google

Coloque el archivo JSON de la Service Account en:

```
credentials/google_service_account.json
```

Comparta el Google Sheet del cliente con el correo electrónico del Service Account (`client_email` dentro del JSON) otorgándole permiso de **Editor**.

### 2. Variables de entorno

Cree un archivo `.env` en la raíz del proyecto con el siguiente contenido:

```env
GOOGLE_SHEET_ID=<id_del_google_sheet>
SHEET_HISTORICO=Consolidado_productos
SHEET_RECETA=Recetas_
SHEET_INVENTARIO=Inventario
SHEET_VENTAS=Ventas
```

El `GOOGLE_SHEET_ID` se obtiene de la URL del Sheet:

```
https://docs.google.com/spreadsheets/d/<ESTE_ES_EL_ID>/edit
```

---

## Uso del sistema

El sistema puede operarse de dos formas: en **local** (línea de comandos) o **desde la nube** mediante una API REST desplegada en Cloud Run.

---

### Opción A — Ejecución local

#### A.1. Predicción con datos en Google Sheets

```bash
python main.py --source sheets --weeks 4 --sedes Gastrobar,Express,Bistro,Mekato
```

#### A.2. Predicción con CSV local

```bash
python main.py --source csv --sales data/historico_ventas_sample.csv --weeks 4
```

#### A.3. Predicción con interfaz de revisión humana

```bash
python main.py --source sheets --review
```

Esto abre una sesión interactiva en consola donde el Administrador puede:
- Visualizar la tabla comparativa (cantidad sugerida por IA vs cantidad final).
- Ajustar manualmente las cantidades.
- Recibir alertas cuando una edición se desvía más del 20% de la sugerencia.
- Exportar la lista validada a CSV y/o PDF.

#### Argumentos disponibles

| Argumento | Descripción | Valor por defecto |
|-----------|-------------|-------------------|
| `--source` | Fuente de datos: `csv` o `sheets` | `csv` |
| `--sales` | Ruta al CSV del histórico (solo modo `csv`) | `data/historico_ventas_sample.csv` |
| `--inventory` | Ruta al CSV del inventario | `data/inventarioActual.csv` |
| `--output-dir` | Directorio para CSVs de salida | `data/` |
| `--weeks` | Semanas a proyectar | `4` |
| `--sedes` | Sedes a procesar (separadas por coma) | `Gastrobar,Express,Bistro,Mekato` |
| `--review` | Activa la interfaz interactiva HU-02 | False |
| `--export-pdf` | Exporta también en formato PDF | False |

---

### Opción B — Consumo desde la nube (Cloud Run)

El sistema está desplegado en Google Cloud Run y expone una API REST pública. Esta es la forma recomendada para uso productivo, ya que permite consumir el servicio desde cualquier dispositivo sin instalar Python.

**URL base:**

```
https://sips-api-778931316983.us-central1.run.app
```

#### Endpoints

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| `GET` | `/` | Información general del servicio |
| `GET` | `/health` | Verificación de estado |
| `GET` | `/detect-sales-schema` | Auto-detecta las columnas de la pestaña Ventas |
| `POST` | `/predict` | Predicción usando históricos de compras (modo legacy) |
| `POST` | `/predict-from-sales` | Predicción usando Ventas × Recetas (modo preciso) |
| `POST` | `/predict/sede/<sede>` | Predicción para una única sede |

#### Ejemplos de uso

**Verificar estado del servicio:**

```bash
curl https://sips-api-778931316983.us-central1.run.app/health
```

**Auto-detectar el esquema de la pestaña Ventas:**

```bash
curl https://sips-api-778931316983.us-central1.run.app/detect-sales-schema
```

**Generar predicciones (modo preciso):**

```bash
curl -X POST https://sips-api-778931316983.us-central1.run.app/predict-from-sales \
  -H "Content-Type: application/json" \
  -d '{"weeks": 4, "sedes": ["Gastrobar", "Express", "Bistro", "Mekato"]}'
```

**Predicción para una sola sede:**

```bash
curl -X POST https://sips-api-778931316983.us-central1.run.app/predict/sede/Gastrobar \
  -H "Content-Type: application/json" \
  -d '{"weeks": 4}'
```

Tras cada ejecución, el sistema escribe automáticamente los resultados en la pestaña **`SIPS_Sugerencias`** del Google Sheet del cliente, lista para que el Chef la revise desde AppSheet o directamente desde el navegador.

---

## Despliegue en Google Cloud Run

Si requiere desplegar el sistema en otra cuenta de Google Cloud, siga estos pasos:

```bash
# 1. Autenticar y seleccionar proyecto
gcloud auth login
gcloud config set project <PROJECT_ID>

# 2. Habilitar APIs necesarias
gcloud services enable \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  secretmanager.googleapis.com

# 3. Crear secret con las credenciales del Service Account
gcloud secrets create google-creds \
  --data-file=credentials/google_service_account.json

# 4. Otorgar permisos al servicio de Cloud Run
PROJECT_NUMBER=$(gcloud projects describe <PROJECT_ID> --format="value(projectNumber)")
gcloud secrets add-iam-policy-binding google-creds \
  --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"

# 5. Aumentar el timeout de Cloud Build (Prophet requiere compilación de cmdstan)
gcloud config set builds/timeout 1800

# 6. Desplegar
gcloud run deploy sips-api \
  --source . \
  --region us-central1 \
  --memory 2Gi \
  --cpu 2 \
  --timeout 540 \
  --allow-unauthenticated \
  --set-env-vars "GOOGLE_SHEET_ID=<sheet_id>,SHEET_HISTORICO=Consolidado_productos,SHEET_RECETA=Recetas_,SHEET_INVENTARIO=Inventario,SHEET_VENTAS=Ventas" \
  --set-secrets="/app/credentials/google_service_account.json=google-creds:latest"
```

El primer despliegue tarda aproximadamente 15-20 minutos debido a la compilación de Prophet y cmdstan. Los despliegues posteriores son significativamente más rápidos gracias al caché de capas Docker.

### Monitoreo

```bash
# Logs en tiempo real
gcloud run services logs tail sips-api --region us-central1

# Información del servicio
gcloud run services describe sips-api --region us-central1

# Historial de despliegues
gcloud run revisions list --service sips-api --region us-central1
```

También se pueden consultar logs, métricas y configuración desde la consola web: <https://console.cloud.google.com/run>

---

## Arquitectura y stack tecnológico

```
+-------------+      +------------------+      +--------------+
|  AppSheet   | ---> |  Google Cloud    | ---> | Google Sheet |
|  (Frontend) |      |  Run (Backend)   |      | (Datos)      |
|             |      |  - Prophet       |      |              |
|  Chef       | <--- |  - Flask API     | <--- |  Pestaña     |
|  aprueba    |      |  - Service Acc.  |      |  SIPS_Suger. |
+-------------+      +------------------+      +--------------+
       ^                     ^
   Webhook              Secret Manager
   "Predecir"           (credenciales)
```

| Componente | Tecnología |
|------------|------------|
| Lenguaje | Python 3.11 |
| Framework web | Flask + Gunicorn |
| Modelo predictivo principal | Meta Prophet (seasonality) |
| Modelo de respaldo | Mediana Robusta semanal |
| Filtros estadísticos | IQR outlier filter, Cap por percentil P95, Sanity Check |
| Datos | Google Sheets vía gspread |
| Despliegue | Google Cloud Run + Docker |
| Autenticación | Google Service Account + Secret Manager |
| Frontend operativo | AppSheet (Google Cloud) |
| Procesamiento | pandas, numpy, scikit-learn |
| Metodología | Scrum |

---

## Pipeline de predicción

1. **Carga de datos.** El sistema lee la pestaña de ventas con auto-detección de columnas (fecha, producto, cantidad, sede), tolerando cualquier estructura razonable mediante regex y validación de tipos.

2. **Limpieza.** Se eliminan registros duplicados, cantidades inválidas (negativas o nulas) y se normaliza el texto.

3. **Validación de calidad.** Se reporta el rango de fechas cubierto, huecos en el calendario, productos con datos insuficientes y outliers detectados mediante IQR. Cada predicción recibe un indicador de **confiabilidad** (ALTA, MEDIA, BAJA o MUY_BAJA) según la cantidad de semanas históricas disponibles.

4. **Conversión Ventas → Consumo.** Las ventas de platos se cruzan con la tabla de recetas para obtener el consumo real desglosado por insumo. Si los nombres no coinciden exactamente, se aplica fuzzy matching con un umbral mínimo del 70% de similitud.

5. **Predicción por sede.** Para cada combinación (sede × insumo), el sistema intenta primero entrenar un modelo Prophet con estacionalidad semanal activada. Si Prophet falla o no hay suficientes datos (mínimo 14 días), recurre automáticamente a una Mediana Robusta semanal.

6. **Filtros de seguridad.** Se aplican tres guardarraíles a toda predicción: filtro IQR antes de entrenar, cap por percentil P95 sobre el histórico semanal y sanity check que limita la predicción a un máximo de dos veces el valor histórico real.

7. **Escritura de resultados.** Las sugerencias se escriben en la pestaña `SIPS_Sugerencias` del Google Sheet del cliente, con identificadores UUID, metadatos y estado `PENDIENTE_REVISION` listos para ser consumidos por AppSheet.

---

## Estructura del proyecto

```
Sinfo/
├── app.py                              # API Flask para Cloud Run
├── main.py                             # Punto de entrada CLI (modo local)
├── Dockerfile                          # Imagen de despliegue
├── requirements.txt                    # Dependencias Python
├── .gcloudignore                       # Exclusiones para deploy
│
├── src/
│   ├── __init__.py
│   ├── data_cleaning.py                # Limpieza y normalización
│   ├── prediction_engine.py            # Motor de predicción base
│   ├── seasonal_predictor.py           # Prophet + Mediana Robusta
│   ├── validation.py                   # Validación de calidad del histórico
│   ├── ingredient_calculator.py        # Cálculo de requerimientos
│   ├── review_interface.py             # Interfaz CLI de validación humana
│   ├── sheets_loader.py                # Conexión Google Sheets
│   ├── sales_loader.py                 # Carga de ventas con auto-detect
│   └── sales_to_consumption.py         # Cruce ventas × recetas
│
├── tests/
│   ├── test_data_cleaning.py
│   ├── test_prediction_engine.py
│   ├── test_ingredient_calculator.py
│   └── test_review_interface.py
│
├── credentials/
│   └── google_service_account.json     # (gitignored)
│
└── data/
    ├── historico_ventas_sample.csv     # Muestra de pruebas
    ├── inventarioActual.csv
    └── sugerencia_insumos_*.csv        # Salidas generadas
```

---

## Pruebas

```bash
pip install pytest
python -m pytest tests/ -v
```

---

## Restricciones y exclusiones

- El sistema no ejecuta compras ni realiza transacciones financieras con proveedores. Su función termina al generar y persistir la lista validada.
- No incluye digitalización de facturas mediante OCR.
- No realiza integración directa con sistemas POS de terceros (Loggro u otros).
- No contempla alertas automáticas de stock crítico en esta fase.

---

## Equipo de trabajo

- Emmanuel Castaño Sepúlveda
- Juan José Álvarez
- Pablo Benítez
- Santiago Meneses
- Santiago Salazar
---

## Licencia

Proyecto académico desarrollado para Inversiones Pulso S.A.S. como parte del curso de Ingeniería de Sistemas.
