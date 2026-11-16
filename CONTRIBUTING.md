# Contribuir

EnergyHub es un proyecto abierto. Las áreas donde más ayuda hace falta:

- Añadir proveedores de precios y tarifas de otros países (la arquitectura está preparada).
- Mejorar el catálogo de dispositivos y los perfiles típicos.
- Implementar el historial real de entidades de Home Assistant y los sensores nativos.
- Añadir el comparador Pepe vs PVPC/ESIOS.
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
