# Usage

1. Instale el m�dulo `l10n_ve_bank_reconcile_ref`.
2. Vaya a **Facturaci�n ? Configuraci�n ? Modelos de conciliaci�n**.
3. Abra **VE: Match por referencia (pago ? factura)** o cree una regla tipo
   **Emparejar facturas/facturas de proveedor**.
4. Active:
   - Buscar en Etiqueta y/o Referencia del extracto
   - Match por sufijo de referencia
   - Longitudes (ej. `6,4`)
   - Priorizar pagos antes que facturas
   - Auto-validar
   - Matching �nico
5. Importe el extracto bancario y abra la conciliaci�n del diario.

Comportamiento:

- 1 candidato + monto compatible ? se auto-concilia (si Auto-validar est� activo).
- Varios candidatos ? solo se sugieren.
- Referencias poco fiables (`0`, vac�as o muy cortas) se ignoran.
