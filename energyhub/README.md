# EnergyHub

App de Home Assistant para estimar el consumo y la factura eléctrica por aparato.

## Instalación

Añade el repositorio de apps de EnergyHub en Home Assistant y instala esta app. Después, abre **EnergyHub** en la barra lateral.

En el primer arranque puedes:

- configurar un contrato de Pepe Energy Tarifa Variable con 2.0TD,
- cargar una casa de ejemplo para explorar el panel,
- o introducir los precios manualmente.

La app guarda los datos en `/data` y funciona dentro de Home Assistant con Ingress. No abre puertos adicionales.

## Notas

- Los precios de Pepe se obtienen de la API pública que usa su web. La app siempre pide confirmación antes de aplicarlos.
- Pepe publica el precio del mes pasado; la app lo marca como provisional hasta que se confirme el mes actual.
- PVPC se obtiene de la API pública de REE y se calcula hora a hora.
- Si un dispositivo tiene una entidad de energía acumulada en Home Assistant, se usa su consumo mensual real. Si no hay lectura, se mantiene la estimación manual como respaldo.
- El bono social solo se aplica a PVPC. Con tarifas de mercado libre se muestra la financiación regulada y un aviso.
- El catálogo comunitario de otras comercializadoras es orientativo; confirma precios y cuotas con tu factura.
- Las estimaciones son orientativas y no sustituyen a la factura oficial.
- La página **Novedades** y el diálogo de actualización de Home Assistant muestran únicamente las versiones posteriores a la instalada. El changelog completo está en el repositorio.
