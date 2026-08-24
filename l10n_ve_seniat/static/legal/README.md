# Referencia normativa — l10n_ve_seniat

Índice de leyes y providencias administrativas del SENIAT usadas o relacionadas con este
módulo y con la localización venezolana (`l10n-venezuela`).

> **Aviso:** El texto transcrito es de apoyo al desarrollo. La fuente oficial prevalece
> (Gaceta Oficial, portal fiscal del SENIAT). No sustituye asesoría legal.
>
> Cada providencia tiene un único archivo `articulos.md` con el texto íntegro de todos
> sus artículos, disposiciones transitorias y finales.

## Providencias administrativas (facturación)

| Carpeta                                 | Código SENIAT    | G.O.                | Alcance en Odoo                                          |
| --------------------------------------- | ---------------- | ------------------- | -------------------------------------------------------- |
| [SNAT-2011-00071](./SNAT-2011-00071/)   | SNAT/2011/00071  | 39.795 (08/11/2011) | **Núcleo** — forma libre, MF, NC/ND, talonario, terceros |
| [SNAT-2024-000102](./SNAT-2024-000102/) | SNAT/2024/000102 | 43.032 (19/12/2024) | Facturación digital, contingencia digital, anulación     |
| [SNAT-2018-0141](./SNAT-2018-0141/)     | SNAT/2018/0141   | 41.518 (06/11/2018) | Máquinas fiscales, DTD, imprentas autorizadas            |
| [SNAT-2024-000121](./SNAT-2024-000121/) | SNAT/2024/000121 | 43.032 (19/12/2024) | Homologación de software (ERP/implementador)             |
| [SNAT-2022-000013](./SNAT-2022-000013/) | SNAT/2022/000013 | 42.339 (17/03/2022) | Aviso IGTF 3% en pagos en divisas                        |

## Leyes y reglamentos (IVA e impuestos conexos)

| Carpeta                                   | Norma                                                     | Alcance en Odoo                                                           |
| ----------------------------------------- | --------------------------------------------------------- | ------------------------------------------------------------------------- |
| [LEY-IVA](./LEY-IVA/)                     | Decreto Constituyente IVA (G.O. 6.507 Extra., 29/01/2020) | Hecho imponible, alícuotas, terceros (Art. 10), facturación (Arts. 54–58) |
| [RLIVA](./RLIVA/)                         | Reglamento General Ley IVA                                | Libros de compra/venta (Arts. 75–78)                                      |
| [SNAT-2025-000054](./SNAT-2025-000054/)   | SNAT/2025/000054                                          | Retenciones IVA (módulo `l10n_ve_withholding`)                            |
| [LEY-IGTF](./LEY-IGTF/)                   | Ley IGTF + PA 2022/000013                                 | Percepción 3% (`l10n_ve_igtf`)                                            |
| [ISLR-DECRETO-1808](./ISLR-DECRETO-1808/) | Decreto 1808 retenciones ISLR                             | Referencia; módulos de nómina/retención                                   |

## Otras providencias históricas (contexto)

| Código         | Estado                   | Nota                                               |
| -------------- | ------------------------ | -------------------------------------------------- |
| SNAT/2014/0032 | Derogada por PA 102      | Prestadores masivos / medios distintos (histórico) |
| SNAT/2015/0049 | Derogada por PA 054/2025 | Retenciones IVA (histórico)                        |

## Mapa rápido: módulo → norma principal

| Funcionalidad Odoo                            | Norma principal   | Artículos clave                              |
| --------------------------------------------- | ----------------- | -------------------------------------------- |
| Talonario / N° control                        | PA 0071           | Art. 13, 27, 29–31                           |
| Medio emisión (libre/MF/digital/contingencia) | PA 0071 + PA 102  | Art. 6–8, 11; PA102 Art. 16                  |
| NC / ND                                       | PA 0071           | Art. 22–24                                   |
| Ventas por cuenta de terceros                 | Ley IVA + PA 0071 | Art. 10 LIVA; Art. 11, 32 PA71               |
| Tipo de cambio en factura                     | PA 0071 + Ley IVA | Art. 13.14 PA71; Art. 15 LIVA; Art. 38 RLIVA |
| Leyenda IGTF                                  | PA 2022/000013    | —                                            |
| Guías de despacho no facturadas               | PA 0071 + PA 102  | Art. 21 PA71; Art. 10 PA102                  |
| Anulación con motivo                          | PA 102            | Art. 18                                      |
| Implementador / homologación                  | PA 102 + PA 121   | Art. 18–19 PA102; PA121 completa             |
| Integración máquina fiscal                    | PA 0141 + PA 121  | Art. 14–15 DTD                               |
| Libros fiscales                               | RLIVA             | Art. 75–78                                   |
| Retenciones IVA                               | PA 2025/000054    | Art. 4–5                                     |

## Enlaces oficiales y repositorios

- Portal fiscal SENIAT: https://www.seniat.gob.ve/
- Listado sistemas homologados (PA 121): consultar portal fiscal SENIAT
- IVECOFI (texto PA 102):
  https://tributos.ivecofi.net/informacion/legislacion/providencias/pa-2024-102
- IVECOFI (Ley IVA, G.O. 6.507/2020):
  https://tributos.ivecofi.net/informacion/legislacion/leyes/ley-impuesto-valor-agregado/

## Correcciones frecuentes (vs. resúmenes genéricos)

1. **Contingencia PA 0071:** Art. **10** (sistemas inoperantes → formato imprenta +
   «serie»); Art. **11** (usuarios MF → casos excepcionales incl. terceros). La
   contingencia **digital** está en PA **102 Art. 16**.
2. **Terceros + máquina fiscal:** Art. **11** numeral **4** PA 0071 obliga formato
   imprenta autorizada; no factura MF estándar.
3. **PA 102 vs PA 121:** PA 102 regula al **contribuyente emisor digital**; PA 121
   regula al **proveedor de software** (homologación Odoo/ERP).

## Mantenimiento

Al agregar validaciones o campos fiscales en código/vistas:

1. Identificar artículo en la carpeta correspondiente (`articulos.md`).
2. Documentar en docstring estilo pandas (`Notes`) o comentario XML.
3. Actualizar la columna «Implementación» en `articulos.md` si aplica.
