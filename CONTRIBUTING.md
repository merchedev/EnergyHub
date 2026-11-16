# Contribuir

EnergyHub es un proyecto abierto. Las áreas donde más ayuda hace falta:

- Añadir perfiles de tarifas al catálogo comunitario (`energyhub/tariffs/catalog.json`).
- Añadir proveedores de precios y tarifas de otros países.
- Mejorar el catálogo de dispositivos y los perfiles típicos.
- Implementar el historial real de entidades de Home Assistant y los sensores nativos.
- Añadir más comparativas de tarifas y simuladores.
- Traducciones y documentación.

## Desarrollo

```bash
make install
make test
make lint
make dev-backend
make dev-frontend
```

El backend usa FastAPI + SQLite y el frontend React + Vite. Los tests de backend están en `energyhub/backend/tests`. Para cambios de tarifas o estimación, añade tests que cubran el caso.

## Pull requests

- Mantén los cambios pequeños y explicados.
- Incluye tests cuando cambie el cálculo.
- No incluyas datos personales, tokens ni facturas reales.
- Respeta la licencia MIT.
