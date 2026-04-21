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
