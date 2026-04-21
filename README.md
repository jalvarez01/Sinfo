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
│   ├── ingredient_calculator.py     # Cálculo de requerimientos de insumos
│   └── review_interface.py          # Interfaz de ajuste y validación humana (HU-02)
├── tests/
│   ├── test_data_cleaning.py
│   ├── test_prediction_engine.py
│   ├── test_ingredient_calculator.py
│   └── test_review_interface.py
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

---

## HU-02: Interfaz de Ajuste y Validación Humana (Implementación)

Permite al Administrador Operativo revisar las cantidades sugeridas por la IA, aplicar
ajustes manuales (override), detectar desviaciones significativas (> 20 %) y exportar
la lista validada a CSV y/o PDF para enviarla al proveedor.

> **Importante:** el sistema **no ejecuta compras automáticamente**. Su función termina
> al generar la lista validada para que el usuario proceda con el proveedor externamente.

### Módulo `src/review_interface.py`

| Función | Descripción |
|---|---|
| `prepare_review_table(requirements_df)` | Construye la tabla comparativa con `cantidad_sugerida_ia` y `cantidad_final` |
| `apply_override(review_df, insumo, nueva_cantidad)` | Aplica una cantidad final personalizada para un insumo |
| `flag_significant_deviations(review_df, threshold=0.20)` | Marca filas cuya edición difiere > 20 % de la sugerencia IA |
| `finalize_review(review_df)` | Congela la lista (marcándola como finalizada) |
| `export_to_csv(review_df, output_path)` | Exporta la lista validada a CSV |
| `export_to_pdf(review_df, output_path)` | Exporta la lista validada a PDF |
| `print_review_table(review_df)` | Imprime la tabla comparativa en consola con marcas de alerta |

### Uso

```bash
# Ejecutar pipeline + abrir revisión interactiva
python main.py --review

# Revisar sugerencias ya generadas y exportar también en PDF
python main.py --review --suggestions data/sugerencia_insumos.csv --export-pdf
```

#### Argumentos adicionales para la revisión

| Argumento | Descripción |
|---|---|
| `--review` | Activa la interfaz interactiva de revisión humana (HU-02) |
| `--suggestions` | Ruta al CSV de sugerencias a revisar (por defecto usa `--output`) |
| `--export-pdf` | Exporta también la lista validada en formato PDF |

#### Ejemplo de sesión interactiva

```
============================================================
  HU-02: Interfaz de Ajuste y Validación Humana
============================================================

===========================================================================
  TABLA COMPARATIVA DE INSUMOS — REVISIÓN HUMANA
===========================================================================
Insumo                         Unidad         Cant. IA  Cant. Final  Alerta
---------------------------------------------------------------------------
Gaseosa                        ml           623,766.50   623,766.50
Papa frita                     gramos       287,724.50   287,724.50
...

Introduzca los ajustes manuales. Escriba 'listo' para finalizar la revisión.
Formato: <nombre_insumo> <nueva_cantidad>

> Gaseosa 700000
  ✔ Gaseosa: 700,000.00

> Papa frita 200000
  ✔ Papa frita: 200,000.00  ⚠  Desviación > 20 % respecto a la sugerencia de la IA

> listo

✔  Lista validada exportada a CSV: data/lista_validada.csv
✔  Revisión finalizada. La lista está lista para enviar al proveedor.
   (El sistema NO ejecuta compras automáticamente.)
```

### Archivos de salida

| Archivo | Descripción |
|---|---|
| `data/lista_validada.csv` | Lista de insumos validada en formato CSV |
| `data/lista_validada.pdf` | Lista de insumos validada en formato PDF (requiere `--export-pdf`) |

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
