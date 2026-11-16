# Estimación y tarifas

## 2.0TD

EnergyHub implementa el peaje doméstico 2.0TD:

| Periodo | Días laborables | Fines de semana y festivos |
|---|---|---|
| Punta (P1) | 10:00–14:00 y 18:00–22:00 | — |
| Llano (P2) | 08:00–10:00, 14:00–18:00 y 22:00–24:00 | — |
| Valle (P3) | 00:00–08:00 | Todo el día |

Los festivos se calculan con la librería `holidays`. En el contrato se puede elegir la comunidad autónoma; por defecto se usan los festivos nacionales. La app recalcula las horas reales de cada mes, incluyendo los cambios de hora.

## Factura

La factura estimada se compone de:

```text
energía     = Σ kWh_tramo × precio_tramo
potencia    = (kW_P1 × precio_P1 + kW_P2 × precio_P2) × días
cuotas      = cuota_servicio + bono_social + alquiler_contador + otras
impuesto    = max((energía + potencia) × 5,113 %, kWh × 0,001 €)
IVA         = (energía + potencia + impuesto) × 21 %
total       = energía + potencia + cuotas + impuesto + IVA
```

La cuota de servicio y el bono social de Pepe se guardan con impuestos incluidos, tal y como los publica la comercializadora. El alquiler de contador y otras cuotas también se tratan como importes finales. Los tipos son configurables por contrato y por versión de precio.

Con un contrato de ejemplo (P1 4,6 kW y P2 4,6 kW, precios de octubre de 2026) el término de potencia es de aproximadamente 10,75 €/mes sin impuestos, y el fijo completo con cuotas e impuestos ronda los 19,39 €/mes incluyendo 0,81 € de alquiler de contador.

## PVPC

El PVPC 2.0TD se obtiene de la API pública REData de REE (`apidatos.ree.es`). La serie llega en €/MWh y se convierte a €/kWh. El coste se calcula hora a hora con la curva de consumo estimada del hogar.

- El término de potencia es regulado y editable.
- El bono social solo se aplica al PVPC.
- Si faltan horas del mes (por ejemplo, porque aún no se han publicado), la app usa el precio medio disponible y lo indica.
- El comparador usa el mismo consumo y la misma potencia para Pepe y PVPC.

## Bono social

El descuento del bono social solo se aplica al PVPC y a potencias de hasta 10 kW. Para 2026:

- Consumidor vulnerable: **42,5 %**.
- Consumidor vulnerable severo: **57,5 %**.
- Riesgo de exclusión social: **100 %**.

Se aplica al término de energía y al término de potencia. La energía con derecho a descuento tiene un límite anual que se prorratea por los días de la factura. La app permite seleccionar el límite de 1.587, 2.222, 2.698 o 4.761 kWh/año y calcula una estimación; el límite real se ajusta con la energía no consumida de los 12 meses anteriores.

La línea **financiación del bono social** (~0,91 €/mes en Península/Baleares) es un coste regulado distinto del descuento y se aplica a todas las tarifas.

## Precios de Pepe

La Tarifa Variable de Pepe publica un precio mensual para punta, llano y valle. La app consulta la API pública usada por su web:

```text
https://shared-api.pepeenergy.com/prices/electricity/last-month
```

Es una API no documentada. Por eso:

- se consulta solo cuando el usuario lo pide o al configurar el contrato,
- se guarda una propuesta y se pide confirmación,
- se muestra el mes publicado (Pepe suele publicar el mes pasado),
- si falla, se puede introducir el precio a mano.

El mes actual se marca como **provisional** si se está usando el último precio publicado. Cuando Pepe publique el mes correspondiente o llegue la factura, la app actualiza el cálculo. La factura real se puede usar para calibrar el consumo.

## Estimación por dispositivo

### Siempre enchufado

```text
P_media = P_activa × ciclo + P_standby × (1 − ciclo)
kWh_mes = P_media × 24 × días / 1000
```

Si se introduce el consumo anual de la etiqueta, se usa directamente:

```text
kWh_mes = kWh_año / 365 × días
```

El consumo se reparte entre las 24 h y se aplica el precio de cada tramo.

### Horas al día

```text
kWh_activo = P_activa × horas_día × días / 1000
kWh_standby = P_standby × (24 − horas_día) × días / 1000
```

La energía activa se reparte con la franja típica de la categoría (por ejemplo, cocina a las 13:00–15:00 y 20:00–22:00). La app calcula también el rango mínimo/máximo: todo en valle o todo en punta.

### Ciclos

```text
kWh_ciclo = kWh_por_ciclo o P_activa × minutos / 60 / 1000
kWh_mes = kWh_ciclo × ciclos_semana × días / 7
```

Los ciclos se reparten entre los días y la franja típica. El standby se calcula por las horas restantes si el aparato está siempre enchufado.

### Calibración

Si la factura real consume `kWh_real` y la app estima `kWh_estimado`:

```text
factor = kWh_real / kWh_estimado
```

El factor se aplica a las estimaciones de los dispositivos. Se muestra siempre en la app y se puede volver a calibrar.

## Limitaciones

- Sin medición, la precisión depende de la potencia, las horas y los ciclos introducidos.
- El precio de Pepe es mensual por tramo; no se debe usar el precio horario de ESIOS para esa factura.
- La app no crea entidades de Home Assistant en esta versión; solo lee las existentes y puede crear automatizaciones con confirmación.
- Las estimaciones son orientativas y no sustituyen a la factura oficial.
