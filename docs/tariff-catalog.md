# Catálogo comunitario de tarifas

El catálogo vive en [`energyhub/tariffs/catalog.json`](../energyhub/tariffs/catalog.json). La app lo incluye en la imagen y lo muestra en el selector de compañía/tarifa.

Los perfiles integrados (Pepe Variable, Pepe Estable y PVPC) tienen precios automáticos. Los perfiles del catálogo comunitario son **orientativos**: el usuario debe confirmar los precios y la cuota con su factura.

## Añadir un perfil

Añade un objeto al array `profiles`:

```json
{
  "id": "mi_compania_fija_2026",
  "company": "Mi Compañía",
  "name": "Tarifa Fija 2026",
  "country": "ES",
  "kind": "period",
  "price_source": "manual",
  "access_toll": "2.0TD",
  "service_fee_eur_month": 0.0,
  "social_bond_eur_month": 0.908639,
  "meter_rent_eur_month": 0.81,
  "vat_rate": 0.21,
  "electricity_tax_rate": 0.0511269632,
  "power_p1_price": 0.075903,
  "power_p2_price": 0.001987,
  "supports_pepephone_discount": false,
  "bono_social_eligible": false,
  "requires_manual_prices": true,
  "notes": "Perfil comunitario. Confirma precios y cuota con tu factura.",
  "source_url": "https://ejemplo.com/tarifas",
  "last_updated": "2026-11-16"
}
```

- `kind`: `period` (tramos), `fixed` (precio fijo) o `hourly` (precio horario).
- `price_source`: `manual` para perfiles comunitarios. No se deben inventar precios: si no se conocen, se dejan a 0 y el usuario los introduce.
- `requires_manual_prices`: `true` si el usuario tiene que confirmar los precios.
- `source_url`: página pública de la tarifa.
- `last_updated`: fecha de revisión.
- No incluyas datos personales, números de contrato, CUPS, facturas, correos ni logos de terceros.

Los perfiles de mercado libre pueden cambiar con frecuencia. La app muestra la fecha y pide confirmación; no se presentan como precio garantizado.
