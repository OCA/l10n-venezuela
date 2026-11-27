[![Runboat](https://img.shields.io/badge/runboat-Try%20me-875A7B.png)](https://runboat.odoo-community.org/builds?repo=OCA/l10n-venezuela&target_branch=19.0)
[![Pre-commit Status](https://github.com/OCA/l10n-venezuela/actions/workflows/pre-commit.yml/badge.svg?branch=19.0)](https://github.com/OCA/l10n-venezuela/actions/workflows/pre-commit.yml?query=branch%3A19.0)
[![Build Status](https://github.com/OCA/l10n-venezuela/actions/workflows/test.yml/badge.svg?branch=19.0)](https://github.com/OCA/l10n-venezuela/actions/workflows/test.yml?query=branch%3A19.0)
[![codecov](https://codecov.io/gh/OCA/l10n-venezuela/branch/19.0/graph/badge.svg)](https://codecov.io/gh/OCA/l10n-venezuela)

# l10n-venezuela

<!-- /!\ do not modify above this line -->

## Español

Localización contable y fiscal de Venezuela para **Odoo 19**.

Continúa la estructura y la autoría de los módulos históricos de
[odoo-venezuela](https://github.com/odoo-venezuela/odoo-venezuela)
(Vauxoo y contribuidores de las ramas 7.0/8.0). Cada addon documenta
su configuración, su uso y quién lo mantiene.

El plan de cuentas no se duplica aquí: se usa el `l10n_ve` oficial, con
**códigos de 7 dígitos**.

### Qué cubre

Cada módulo describe su alcance en su propio README. Los aportes de
esta rama se listan en [Módulos](#módulos--modules).

### Instalación

Idioma del usuario: **Spanish (`es_ES`)**, no `es_VE`. El usuario
necesita las características de contabilidad completas.

1. Contabilidad oficial + `l10n_ve`. Compañía en Venezuela, moneda VES,
   RIF y al menos una tasa VES. Ventas y Compras solo si se van a usar
   pedidos.

El orden del resto de addons se agrega aquí, con la dependencia de cada
uno.

### Dependencias

Este repo **no trae** la contabilidad de Odoo ni el plan `l10n_ve`: hay
que tenerlos instalados. Odoo resuelve el resto en cadena al instalar
cada addon.

**Odoo 19 (oficial / Enterprise), fuera de este repo:**

- `account` — Contabilidad
- `base_vat` — validación de NIF/VAT
- `l10n_latam_base` — tipos de identificación LATAM (**oficial Odoo 19**,
  no hay que bajarla)
- `l10n_ve` — plan de cuentas y fiscalidad VE oficial

**Por módulo (este repo + externos):**

| Módulo | Depende de |
| ------ | ---------- |
| `l10n_ve_base` | `account`, `base_vat`, `l10n_latam_base`, `l10n_ve` |
| *Agregar el siguiente módulo* |  |

## English

Accounting and fiscal localization of Venezuela for **Odoo 19**.

It keeps the structure and authorship of the historical modules from
[odoo-venezuela](https://github.com/odoo-venezuela/odoo-venezuela)
(Vauxoo and contributors of the 7.0/8.0 branches). Each addon documents
its configuration, its usage and who maintains it.

This repo does not ship a custom chart of accounts: it uses official
`l10n_ve` with **7-digit codes**.

### What it covers

Each addon describes its scope in its own README. Contributions on this
branch are listed under [Modules](#módulos--modules).

### Installation

User language: **Spanish (`es_ES`)**, not `es_VE`. The user needs full
accounting features.

1. Official Accounting + `l10n_ve`. Company in Venezuela, VES currency,
   RIF and at least one VES rate. Sales and Purchase only if you use
   orders.

Add the remaining addons here, in dependency order.

### Dependencies

This repo **does not ship** Odoo Accounting nor the official `l10n_ve`
chart: install those first. Odoo then pulls the rest of the chain.

**Odoo 19 (official / Enterprise), not in this repo:**

- `account` — Accounting
- `base_vat` — Tax ID / VAT validation
- `l10n_latam_base` — LATAM identification types (**official Odoo 19**,
  do not download it)
- `l10n_ve` — official VE chart and fiscal pack

**Per addon (this repo + external):**

| Addon | Depends on |
| ----- | ---------- |
| `l10n_ve_base` | `account`, `base_vat`, `l10n_latam_base`, `l10n_ve` |
| *Add the next addon* |  |

## Módulos / Modules

| Módulo / Module | Español | English |
| --- | --- | --- |
| [l10n_ve_base](l10n_ve_base/) | Núcleo SENIAT: RIF/cédula/pasaporte, número de control, UT, consulta SENIAT, bancos SUDEBAN, tipo de contribuyente, estados, municipios y parroquias. En la 17.0 este módulo se llamaba `l10n_ve_fiscal_requirements`. | SENIAT core: RIF/ID/passport, control number, tax unit, SENIAT lookup, SUDEBAN banks, taxpayer type, states, municipalities and parishes. On 17.0 this addon was named `l10n_ve_fiscal_requirements`. |
| *Agregar el siguiente módulo* | Descripción en español. | English description. |

## Available addons

| addon | version | maintainers | summary |
| ----- | ------- | ----------- | ------- |
| [l10n_ve_base](l10n_ve_base/) | 19.0.1.19.0 | <a href="https://github.com/guillermm"><img src="https://github.com/guillermm.png?size=40" width="40" height="40" alt="guillermm"/></a> | Venezuelan Fiscal Requirements. Renamed from `l10n_ve_fiscal_requirements` (17.0). |
| *Add the next addon* | version | maintainers | summary |

## Licenses

This repository is licensed under [AGPL-3.0](LICENSE).

However, each module can have a totally different license, as long as they adhere to Odoo Community Association (OCA)
policy. Consult each module's `__manifest__.py` file, which contains a `license` key
that explains its license.

---

OCA, or the [Odoo Community Association](http://odoo-community.org/), is a nonprofit
organization whose mission is to support the collaborative development of Odoo features
and promote its widespread use.
