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
- El comparador completo con PVPC/ESIOS llegará en una fase posterior. En esta versión, ESIOS solo se muestra como referencia de mercado.
- Las estimaciones son orientativas y no sustituyen a la factura oficial.
- La página **Novedades** muestra únicamente las versiones posteriores a la instalada. El changelog completo está en el repositorio.
