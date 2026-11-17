# Architecture

## Resumen

EnergyHub es una app de Home Assistant (add-on) que se ejecuta en un contenedor dentro de HA OS/Supervised y se muestra mediante Ingress. El frontend es una SPA de React; el backend es FastAPI con SQLite. Toda la información se guarda en `/data`.

```text
┌──────────────────────────── Home Assistant OS ────────────────────────────┐
│ Home Assistant Core                                                       │
│  ├── WebSocket / REST: estados, historial, registros, servicios             │
│  └── Ingress: /api/hassio_ingress/<token>/                                │
│                             ▲                                             │
│                             │ SUPERVISOR_TOKEN (solo backend)              │
│  ┌──────────────────────────┴───────────────────────────────────────────┐  │
│  │ EnergyHub                                                            │  │
│  │  React + Vite + Recharts  ──  FastAPI  ──  SQLite (/data)             │  │
│  │                                  ├── Motor de estimación              │  │
│  │                                  ├── Motor tarifario 2.0TD            │  │
│  │                                  ├── Proveedor Pepe                   │  │
│  │                                  ├── Referencia ESIOS                  │  │
│  │                                  └── Motor de recomendaciones         │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                             │                                              │
│                             └── Internet: API pública de Pepe (opcional)   │
└────────────────────────────────────────────────────────────────────────────┘
```

## Decisiones

- **Ingress only**: no se exponen puertos. El frontend usa rutas relativas (`api/...`) para funcionar bajo cualquier prefijo de Ingress.
- **SQLite**: suficiente para una vivienda y para las copias de seguridad de HA. El archivo está en `/data/energyhub.db`.
- **Sin dependencia de sensores**: el motor funciona con potencia, horas, ciclos y perfiles típicos. Si existe una entidad de energía acumulada en HA, su lectura mensual sustituye a la estimación; si falla, se vuelve al cálculo manual.
- **Precios de Pepe**: se leen de la API pública que usa su web y se guardan como propuesta pendiente. La app nunca cambia precios sin confirmación.
- **Precios por tramo**: la Tarifa Variable de Pepe publica precios mensuales de punta, llano y valle. No se usa el precio horario de ESIOS para calcular esa factura.
- **PVPC**: se obtiene de la API pública REData de REE y se factura hora a hora.
- **Catálogo de tarifas**: perfiles integrados de Pepe, PVPC y perfiles comunitarios/manuales. Los de mercado libre se marcan como orientativos.
- **Bono social**: descuento solo para PVPC, con categorías y límite anual; la financiación regulada es una línea aparte.
- **ESIOS**: se integra como referencia de mercado y como alternativa si el usuario tiene un sensor propio.
- **Open source**: licencia MIT, i18n preparada, catálogo y proveedores ampliables. Repositorio: [github.com/merchedev/EnergyHub](https://github.com/merchedev/EnergyHub).
- **Novedades**: la app consulta `GET /addons/self/info` y `GET /store/addons/<slug>/changelog` del Supervisor. Filtra las entradas por la versión instalada y solo muestra las posteriores; si el Supervisor no está disponible, usa GitHub y, como último recurso, el `CHANGELOG.md` incluido en la imagen.

## Backend

- `app/main.py`: lifespan, base de datos, montaje del frontend y CORS de desarrollo.
- `app/models.py`: contrato, versiones de tarifa, propuestas de precio, dispositivos, lecturas mensuales de energía, calibraciones, recomendaciones y automatizaciones creadas.
- `app/services/periods.py`: calendario 2.0TD, festivos, horas reales por periodo y ventanas valle.
- `app/services/tariff.py`: selección de precios por mes, término de potencia, cuotas, impuestos y factura.
- `app/services/estimation.py`: reparto de energía por tramo para cada modo de dispositivo.
- `app/services/energy_readings.py`: lectura de contadores de energía de Home Assistant y caché mensual.
- `app/services/pepe.py`: cliente y parser de la API pública de Pepe.
- `app/services/ha.py`: cliente REST y WebSocket de Home Assistant, entidades, historial, estadísticas, registro de áreas y automatizaciones.
- `app/services/recommendations.py`: reglas de ahorro, YAML y payload de automatización.
- `app/routers/api.py`: API JSON consumida por el frontend, incluido `GET /devices/{id}/hourly` con el perfil horario y el reparto por tramo de cada aparato.

### Estimación

Para cada dispositivo se construye una estimación mensual:

1. Se calcula la energía activa según el modo.
2. Se reparte entre tramos usando la franja típica de la categoría o las 24 h.
3. Se añade el standby si el aparato está siempre enchufado.
4. Se aplica el factor de calibración global.
5. Se multiplica por el precio de cada tramo del mes.

Los modos actuales son `always_on`, `hours_per_day`, `cycles` y `entity`. En `entity`, se usa la energía real de la entidad de Home Assistant; si hay estadísticas o historial horario, el reparto por tramos es exacto, y si solo hay total mensual, se reparte con la franja típica.

### Precios

- **Pepe**: `GET https://shared-api.pepeenergy.com/prices/electricity/last-month`. Es una API pública no documentada usada por la web de Pepe. Se cachea, se valida y se presenta para confirmación. Si falla, hay formulario manual.
- **Manual**: precios por tramo, potencia, cuotas e impuestos por mes.
- **ESIOS**: sensor de HA con unidad €/kWh. Solo referencia en el MVP.

## Frontend

- React 19 + TypeScript + Vite.
- CSS propio con tema claro/oscuro.
- Recharts para el ranking visual.
- HashRouter para evitar problemas de rutas con Ingress.
- `api.ts` centraliza las llamadas; en desarrollo Vite hace proxy a `127.0.0.1:8000`.
- `DeviceHourlyModal` muestra el consumo por hora, el detalle por día y el tramo tarifario con más uso.

## Seguridad y privacidad

- No hay telemetría.
- El token del Supervisor nunca llega al navegador.
- Las peticiones a Internet se limitan a la API de Pepe, la API pública de REE y GitHub cuando el usuario las solicita.
- Las automatizaciones se crean solo con confirmación, con ID propio y opción de deshacer.
- Las estimaciones se muestran como orientativas.

## Próximas fases

- Integración puente o MQTT para exponer sensores nativos en HA.
- Historial real de entidades on/off y estadísticas de largo plazo.
- Notificaciones móviles y presupuestos.
- Solar, excedentes y baterías.
- Más países, peajes y proveedores de precios.
