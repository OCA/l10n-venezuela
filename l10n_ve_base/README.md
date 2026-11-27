[![Support the OCA](https://odoo-community.org/readme-banner-image)](https://odoo-community.org/get-involved?utm_source=repo-readme)

# Venezuelan Fiscal Requirements

[![License: AGPL-3](https://img.shields.io/badge/licence-AGPL--3-blue.svg)](https://www.gnu.org/licenses/agpl-3.0-standalone.html)
[![OCA/l10n-venezuela](https://img.shields.io/badge/github-OCA%2Fl10n--venezuela-lightgrey.png?logo=github)](https://github.com/OCA/l10n-venezuela)

Core fiscal module for Odoo 19. Depends on official `l10n_ve` (7-digit codes) and
official `l10n_latam_base`. Adds SENIAT control numbers, RIF `V/E/J/P/G/C`, Tax Units
(UT 43.00 from 2025-06-02), VES helpers that require an exchange rate, SENIAT partner
consultation, tax aliquot classification, SENIAT taxpayer type (Ordinary / Formal /
Special), Venezuelan bank catalog (SUDEBAN BIC) and invoice PDF with RIF / control
number. Fiscal printer fields are optional (no hardware driver).

**Table of contents**

- [Configuration](#configuration)
- [Usage](#usage)
- [Bug Tracker](#bug-tracker)
- [Credits](#credits)
  - [Authors](#authors)
  - [Contributors](#contributors)
  - [Maintainers](#maintainers)

## Configuration

1. Install official `l10n_ve` and set the company country to Venezuela. This module
   loads states, municipalities and parishes, and `l10n_latam_base` is installed
   automatically. The partner form then shows identification type + number (`vat`): RIF,
   Cédula Venezolano, Cédula Extranjera and Pasaporte.
2. _Accounting -> Configuration -> Venezuelan Localization -> Tax Units (UT)_.
3. Review SENIAT URLs if official endpoints change.
4. Set the VES / BCV rate (or install `currency_rate_update_bcv`); posting and
   withholdings require it.
5. Optionally mark fiscal printer usage on the company.
6. SENIAT taxpayer type is under person type. Banks (SUDEBAN code in BIC) load on
   install.

## Usage

When posting customer invoices or vendor bills:

1. Sales: Odoo never generates the control number. Type it from the pre-printed form, or
   let the printing house / fiscal machine connector write it back.
2. Purchases: enter the pre-printed SENIAT control number.
3. A Venezuelan partner cannot be saved without identification number. The type (RIF,
   cédula, passport) must match the person type (PNRE/PNNR/PJDO/PJND).
4. Invoice total cannot be zero; due date cannot be before the invoice date; credit
   notes need a source invoice; one aliquot per line.
5. Contacts can be checked via _Accounting -> Customers -> Consult Partner in SENIAT_.
6. Printed invoices show RIF, control number, municipality and parish when the company
   is Venezuelan.

## Bug Tracker

Bugs are tracked on [GitHub Issues](https://github.com/OCA/l10n-venezuela/issues). In
case of trouble, please check there if your issue has already been reported. If you
spotted it first, help us smashing it by providing a detailed and welcomed feedback.

Do not contact contributors directly about support or help with technical issues.

## Credits

### Authors

- Vauxoo
- OpenERP Venezuela
- SINAPSYS GLOBAL SA / MASTERCORE SAS (political division, bank catalog and SENIAT
  taxpayer types from `l10n_ve_base` 19.0)

### Contributors

- Guillermo Montoya <https://github.com/guillermm>
- Nhomar Hernandez <nhomar@vauxoo.com>
- Humberto Arocha <hbto@vauxoo.com>
- Maria Gabriela Quilarque <gabriela@vauxoo.com>

### Maintainers

This module is maintained by the OCA.

<a href="https://odoo-community.org">
    <img src="https://odoo-community.org/logo.png" alt="Odoo Community Association" width="200" />
</a>

OCA, or the Odoo Community Association, is a nonprofit organization whose mission is to
support the collaborative development of Odoo features and promote its widespread use.

This module is part of the
[OCA/l10n-venezuela](https://github.com/OCA/l10n-venezuela/tree/19.0/l10n_ve_base)
project on GitHub.

You are welcome to contribute. To learn how please visit
https://odoo-community.org/page/Contribute.
