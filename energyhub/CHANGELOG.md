# Changelog

## 0.2.2
2026-11-16

- Changelog compatible con el filtro de Home Assistant: el diálogo de actualización muestra solo las versiones pendientes, no todo el historial.
- Enlaces directos desde las recomendaciones a Tarifa, calibración, precios, horarios o dispositivos según la acción.
- La propuesta de precios de Pepe indica su origen y enlaza a la tarifa oficial y a la API pública usada.
- El perfil de Pepe expone la URL de la API de precios y la página oficial de la tarifa.
- Tests del filtrado del changelog con el mismo patrón que usa Home Assistant.

## 0.2.1
2026-11-16

- La ficha de dispositivo oculta potencia, ciclo de trabajo y standby cuando usas el consumo anual.
- Resumen del consumo anual: media diaria y potencia media equivalente.
- La vista previa avisa si no hay precio confirmado y muestra el coste como «—» en lugar de 0 €.
- Acceso directo a Tarifa desde la vista previa para confirmar o actualizar precios.
- Tests de la vista previa sin precios y del cálculo por consumo anual.

## 0.2.0
2026-11-16

- Selector de compañía y tarifa con perfiles: Pepe Variable, Pepe Estable, PVPC y catálogo comunitario/manual.
- Autorelleno de cuota, financiación del bono social, alquiler de contador, impuestos y potencia.
- Toggle de cliente Pepephone: cuota de servicio de Pepe a 0 €/mes.
- PVPC 2.0TD con precios horarios de la API pública de REE, sin token.
- Coste de dispositivos calculado hora a hora, no solo por tramo.
- Curva PVPC de 48 h, ventanas baratas y planificador de cargas.
- Descuento del bono social para PVPC: 42,5 %, 57,5 % o 100 %, con límite anual de energía.
- Aviso y recomendación cuando el bono social no se aplica a una tarifa de mercado libre.
- Comparador Pepe vs PVPC con el mismo consumo, potencia, impuestos y bono social.
- Catálogo comunitario de perfiles de otras comercializadoras con precios orientativos y fecha de actualización.
- Migración automática de contratos de versiones anteriores.
- Tests de perfiles, Pepephone, PVPC, bono social, facturación horaria y comparador.

## 0.1.2
2026-11-16

- Corrige el arranque del contenedor cuando no existe `.env` y la ruta no tiene cuatro niveles de padres.
- Añade prueba de arranque real del contenedor Docker en CI.
- Mantiene la página Novedades filtrada por versión instalada.

## 0.1.1
2026-11-16

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

## 0.1.0
2026-11-16

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
