# Changelog

## 0.1.1 - 2026-11-16

- Repositorio público y URLs de instalación actualizadas.
- Nueva página **Novedades** que muestra solo las versiones posteriores a la instalada.
- El changelog se lee desde la tienda de Home Assistant o, si no está disponible, desde GitHub.
- Enlace al changelog completo para consultar versiones anteriores.
- Mejoras de validación en los formularios de tarifa y calibración.
- Corrección del desglose de factura en la pestaña Factura.
- Corrección de la etiqueta de precio de potencia (€/kW/día).
- Corrección de nombres al cambiar el tipo de dispositivo.
- Generación de automatizaciones con identificador más limpio y opción de deshacer.
- Añadido `hassio_api` para consultar la versión y el changelog desde Home Assistant.
- Documentación de arquitectura, estimación, tarifas y contribución.

## 0.1.0 - 2026-11-16

- Primera alpha de EnergyHub.
- Panel de resumen con factura estimada, coste por tramo y ranking de dispositivos.
- Contrato 2.0TD configurable con plantilla de Pepe Energy.
- Lectura de precios de Pepe desde su API pública con confirmación y fallback manual.
- Motor de estimación: siempre enchufado, horas al día, ciclos y entidad de HA.
- Calendario valle/llano/punta, festivos y ventanas baratas.
- Calibración con factura real.
- Recomendaciones y generación de YAML de automatización.
- Creación opcional de automatizaciones en Home Assistant con confirmación.
- Sensor ESIOS opcional como referencia de mercado.
- Modo demo y exportación JSON.
