# Sinfo — Motor de Predicción de Insumos

Sistema de predicción de insumos para **Inversiones Pulso S.A.S.** desarrollado como parte de la Historia de Usuario HU-01.

## Descripción

Procesa el histórico de ventas (11 000+ registros) para generar de forma automática una sugerencia numérica de las cantidades de materia prima necesarias por insumo, vinculando las ventas proyectadas con la receta estándar de cada producto.

## Estructura del proyecto

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

## Requisitos

```bash
pip install -r requirements.txt
```

## Uso

```bash
# Ejecución con parámetros por defecto (4 semanas de proyección)
python main.py

# Personalizar horizonte de predicción y rutas
python main.py --weeks 8 --sales data/historico_ventas_sample.csv \
               --recipe data/receta_estandar.csv \
               --output data/sugerencia_insumos.csv
```

### Argumentos

| Argumento  | Descripción                                         | Valor por defecto                      |
|------------|-----------------------------------------------------|----------------------------------------|
| `--sales`  | Ruta al CSV del histórico de ventas                 | `data/historico_ventas_sample.csv`     |
| `--recipe` | Ruta al CSV de la receta estándar                   | `data/receta_estandar.csv`             |
| `--output` | Ruta de salida para el CSV de sugerencias           | `data/sugerencia_insumos.csv`          |
| `--weeks`  | Número de semanas a proyectar                       | `4`                                    |

## Pipeline

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

## Pruebas

```bash
pip install pytest
python -m pytest tests/ -v
```

## Salida de ejemplo

```
              insumo unidad_medida  cantidad_requerida
             Gaseosa            ml           623766.50
          Papa frita        gramos           287724.50
 Carne de res molida        gramos           152299.50
    Aceite de cocina            ml            73586.10
```
