[![Support the OCA](https://odoo-community.org/readme-banner-image)](https://odoo-community.org/get-involved?utm_source=repo-readme)

# Management Withholding ISLR Venezuelan Laws

[![License: AGPL-3](https://img.shields.io/badge/licence-AGPL--3-blue.svg)](https://www.gnu.org/licenses/agpl-3.0-standalone.html)
[![OCA/l10n-venezuela](https://img.shields.io/badge/github-OCA%2Fl10n--venezuela-lightgrey.png?logo=github)](https://github.com/OCA/l10n-venezuela)

Income Tax Withholding (Retención de ISLR) management for Venezuela. Supports legal withholding concepts, multi-tier rate tables (PNRE, PNNR, PJDO, PJND), automatic subtraction calculation based on Tax Units (UT), ARC certificates, and XML SENIAT export.

**Table of contents**

- [Configuration](#configuration)
- [Usage](#usage)
- [Bug Tracker](#bug-tracker)
- [Credits](#credits)
  - [Authors](#authors)
  - [Contributors](#contributors)
  - [Maintainers](#maintainers)

## Configuration

Go to *Accounting -> Configuration -> ISLR Concepts & Rates* to review and configure applicable withholding concepts and tax tables.

## Usage

1. On vendor bills, assign the corresponding ISLR Concept.
2. Validate the bill and click *Generate ISLR Retention*.
3. Go to *Accounting -> Reporting -> Generate XML SENIAT (ISLR)* to generate the monthly XML file for SENIAT submission.

## Bug Tracker

Bugs are tracked on [GitHub Issues](https://github.com/OCA/l10n-venezuela/issues). In case of trouble, please check there if your issue has already been reported. If you spotted it first, help us smashing it by providing a detailed and welcomed feedback.

Do not contact contributors directly about support or help with technical issues.

## Credits

### Authors

* Vauxoo
* OpenERP Venezuela

### Contributors

* Xavier Orlov <https://github.com/xavikveg>
* Guillermo Montoya <https://github.com/guillermm>
* Orlov Solutions LLC
* Nhomar Hernandez <nhomar@vauxoo.com>
* Humberto Arocha <hbto@vauxoo.com>
* Maria Gabriela Quilarque <gabriela@vauxoo.com>

### Maintainers

This module is maintained by the OCA.

<a href="https://odoo-community.org">
    <img src="https://odoo-community.org/logo.png" alt="Odoo Community Association" width="200" />
</a>

OCA, or the Odoo Community Association, is a nonprofit organization whose mission is to support the collaborative development of Odoo features and promote its widespread use.

This module is part of the [OCA/l10n-venezuela](https://github.com/OCA/l10n-venezuela/tree/14.0/l10n_ve_withholding_islr) project on GitHub.

You are welcome to contribute. To learn how please visit https://odoo-community.org/page/Contribute.
