# Automatización Los Birria - Sistema de Pedido Sugerido

## Introducción
Este proyecto surge de la necesidad de optimizar la gestión de suministros de Inversiones Pulso S.A.S., empresa que administra el restaurante Los Birria. El proceso actual de abastecimiento se realiza de forma manual y empírica, lo que genera riesgos de desabastecimiento o exceso de inventario. El sistema propuesto utiliza inteligencia artificial para asistir en la toma de decisiones operativas.

## Objetivo del Proyecto
Desarrollar una herramienta tecnológica basada en el análisis de datos históricos para generar sugerencias automáticas de pedidos de insumos. El sistema busca estandarizar el proceso de compras en las sedes de Manila, El Poblado y Laureles, basándose en patrones de consumo reales y proyecciones de demanda.

## Alcance del Sistema

### Funcionalidades Incluidas
* Procesamiento y limpieza de datos históricos (más de 11,000 registros).
* Generación de sugerencias de pedido mediante modelos predictivos.
* Segmentación de la demanda y sugerencias por sede.
* Interfaz de validación manual para que el administrador ajuste las cantidades sugeridas.
* Exportación de listas de pedidos validadas.

### Restricciones y Exclusiones
* El sistema no realiza compras automáticas ni transacciones financieras con proveedores.
* No se incluye la digitalización de facturas mediante OCR.
* No se contempla la automatización de alertas de stock crítico en esta fase.

## Arquitectura y Tecnologías
* Plataforma de desarrollo: AppSheet (Google Cloud).
* Almacenamiento de datos: Google Sheets con integración de históricos de Loggro.
* Motor de IA: AppSheet Smart Prediction para modelos de aprendizaje automático (Machine Learning).
* Metodología de trabajo: Scrum bajo un enfoque de ingeniería de sistemas.

## Estructura del Proyecto
El desarrollo se centra en tres pilares técnicos:
1. Limpieza y preparación de la base de datos de consumo.
2. Implementación del modelo de predicción basado en la receta estándar y el volumen de ventas.
3. Diseño de la experiencia de usuario para la supervisión y ajuste del pedido sugerido.

## Equipo de Trabajo
* Emmanuel Castaño Sepúlveda
* Juan José Álvarez
* Pablo Benítez
* Santiago Meneses
* Santiago Salazar
* Diego Angarita

---

## HU-01: Motor de Predicción de Insumos (Implementación)

Procesa el histórico de ventas (11 000+ registros) para generar de forma automática una sugerencia numérica de las cantidades de materia prima necesarias por insumo, vinculando las ventas proyectadas con la receta estándar de cada producto.

### Estructura de archivos

```
Sinfo/
├── data/
│   ├── historico_ventas_sample.csv  # Histórico de ventas de muestra (11 530 registros)
│   └── receta_estandar.csv          # Receta estándar por producto
├── src/
│   ├── data_cleaning.py             # Limpieza y normalización de datos
│   ├── prediction_engine.py         # Motor de predicción (regresión lineal semanal)
│   └── ingredient_calculator.py     # Cálculo de requerimientos de insumos
├── tests/
│   ├── test_data_cleaning.py
│   ├── test_prediction_engine.py
│   └── test_ingredient_calculator.py
├── main.py                          # Punto de entrada del pipeline
└── requirements.txt
```

### Requisitos

```bash
pip install -r requirements.txt
```

### Uso

```bash
# Ejecución con parámetros por defecto (4 semanas de proyección)
python main.py

# Personalizar horizonte de predicción y rutas
python main.py --weeks 8 --sales data/historico_ventas_sample.csv \
               --recipe data/receta_estandar.csv \
               --output data/sugerencia_insumos.csv
```

#### Argumentos

| Argumento  | Descripción                                         | Valor por defecto                      |
|------------|-----------------------------------------------------|----------------------------------------|
| `--sales`  | Ruta al CSV del histórico de ventas                 | `data/historico_ventas_sample.csv`     |
| `--recipe` | Ruta al CSV de la receta estándar                   | `data/receta_estandar.csv`             |
| `--output` | Ruta de salida para el CSV de sugerencias           | `data/sugerencia_insumos.csv`          |
| `--weeks`  | Número de semanas a proyectar                       | `4`                                    |

### Pipeline

1. **Limpieza de datos** (`src/data_cleaning.py`)
   - Elimina registros duplicados exactos.
   - Elimina registros con cantidades inválidas (negativas o nulas).
   - Normaliza texto (espacios, capitalización).

2. **Predicción de ventas** (`src/prediction_engine.py`)
   - Agrega ventas por semana y producto.
   - Aplica regresión lineal sobre la serie temporal de cada producto.
   - Proyecta el volumen de ventas para el horizonte indicado.

3. **Cálculo de insumos** (`src/ingredient_calculator.py`)
   - Vincula las predicciones con la receta estándar.
   - Multiplica ventas proyectadas × cantidad por unidad.
   - Agrega el total de cada insumo y lo exporta a CSV.

### Pruebas

```bash
pip install pytest
python -m pytest tests/ -v
```

### Salida de ejemplo

```
              insumo unidad_medida  cantidad_requerida
             Gaseosa            ml           623766.50
          Papa frita        gramos           287724.50
 Carne de res molida        gramos           152299.50
    Aceite de cocina            ml            73586.10
```
