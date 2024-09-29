
[![Runboat](https://img.shields.io/badge/runboat-Try%20me-875A7B.png)](https://runboat.odoo-community.org/builds?repo=OCA/l10n-venezuela&target_branch=13.0)
[![Pre-commit Status](https://github.com/OCA/l10n-venezuela/actions/workflows/pre-commit.yml/badge.svg?branch=13.0)](https://github.com/OCA/l10n-venezuela/actions/workflows/pre-commit.yml?query=branch%3A13.0)
[![Build Status](https://github.com/OCA/l10n-venezuela/actions/workflows/test.yml/badge.svg?branch=13.0)](https://github.com/OCA/l10n-venezuela/actions/workflows/test.yml?query=branch%3A13.0)
[![codecov](https://codecov.io/gh/OCA/l10n-venezuela/branch/13.0/graph/badge.svg)](https://codecov.io/gh/OCA/l10n-venezuela)
[![Translation Status](https://translation.odoo-community.org/widgets/l10n-venezuela-13-0/-/svg-badge.svg)](https://translation.odoo-community.org/engage/l10n-venezuela-13-0/?utm_source=widget)

<!-- /!\ do not modify above this line -->

# Localización venezolana de Odoo

Repositorio de código del proyecto de la localización venezolana para el software
de gestión integral Odoo.

La localización venezolana de Odoo incluye:

* Módulos para adaptar el sistema a los requisitos fiscales y contables
  venezolanas.
* Traducciones a los términos oficiales del país.

Para más información, dirigirse a [SINAPSYS GLOBAL SA, MASTERCORE SAS Team](https://github.com/odoo-mastercore/odoo-venezuela/tree/13.0).

<!-- prettier-ignore-start -->

[//]: # (addons)

# Available addons

addon | version | maintainers | summary
---   | ---     | ---         | ---
[l10n_ve_account_financial_amount](l10n_ve_account_financial_amount/) | 13.0.1.0.0 | <a href="https://github.com/odoo-mastercore" title="SINAPSYS GLOBAL SA, MASTERCORE SAS"><img src="https://avatars.githubusercontent.com/u/33432708?v=4" alt="SINAPSYS GLOBAL SA, MASTERCORE SAS" width="30px" height="30px"></a> | Accounting Financial Amounts
[l10n_ve_account_payment_fix](l10n_ve_account_payment_fix/) | 13.0.1.0.0 | <a href="https://github.com/odoo-mastercore" title="SINAPSYS GLOBAL SA, MASTERCORE SAS"><img src="https://avatars.githubusercontent.com/u/33432708?v=4" alt="SINAPSYS GLOBAL SA, MASTERCORE SAS" width="30px" height="30px"></a> | Account Payment Fix
[l10n_ve_account_payment_group](l10n_ve_account_payment_group/) | 13.0.1.0.0 | <a href="https://github.com/odoo-mastercore" title="SINAPSYS GLOBAL SA, MASTERCORE SAS"><img src="https://avatars.githubusercontent.com/u/33432708?v=4" alt="SINAPSYS GLOBAL SA, MASTERCORE SAS" width="30px" height="30px"></a> | Account Payment with Multiple methods
[l10n_ve_account_payment_group_document](l10n_ve_account_payment_group_document/) | 13.0.1.0.0 | <a href="https://github.com/odoo-mastercore" title="SINAPSYS GLOBAL SA, MASTERCORE SAS"><img src="https://avatars.githubusercontent.com/u/33432708?v=4" alt="SINAPSYS GLOBAL SA, MASTERCORE SAS" width="30px" height="30px"></a> | Payment Groups with Accounting Documents
[l10n_ve_account_withholding](l10n_ve_account_withholding/) | 13.0.1.0.0 | <a href="https://github.com/odoo-mastercore" title="SINAPSYS GLOBAL SA, MASTERCORE SAS"><img src="https://avatars.githubusercontent.com/u/33432708?v=4" alt="SINAPSYS GLOBAL SA, MASTERCORE SAS" width="30px" height="30px"></a> | Withholdings on Payments
[l10n_ve_account_withholding_automatic](l10n_ve_account_withholding_automatic/) | 13.0.1.0.0 | <a href="https://github.com/odoo-mastercore" title="SINAPSYS GLOBAL SA, MASTERCORE SAS"><img src="https://avatars.githubusercontent.com/u/33432708?v=4" alt="SINAPSYS GLOBAL SA, MASTERCORE SAS" width="30px" height="30px"></a> | Automatic Withholdings on Payments
[l10n_ve_base](l10n_ve_base/) | 13.0.1 | <a href="https://github.com/odoo-mastercore" title="SINAPSYS GLOBAL SA, MASTERCORE SAS"><img src="https://avatars.githubusercontent.com/u/33432708?v=4" alt="SINAPSYS GLOBAL SA, MASTERCORE SAS" width="30px" height="30px"></a> | Localización Venezuela Base
[l10n_ve_vat_ledger](l10n_ve_vat_ledger/) | 13.0.2 | <a href="https://github.com/odoo-mastercore" title="SINAPSYS GLOBAL SA, MASTERCORE SAS"><img src="https://avatars.githubusercontent.com/u/33432708?v=4" alt="SINAPSYS GLOBAL SA, MASTERCORE SAS" width="30px" height="30px"></a> | Localización Vat Ledger Venezuela
[l10n_ve_withholding](l10n_ve_withholding/) | 13.0.1 | <a href="https://github.com/odoo-mastercore" title="SINAPSYS GLOBAL SA, MASTERCORE SAS"><img src="https://avatars.githubusercontent.com/u/33432708?v=4" alt="SINAPSYS GLOBAL SA, MASTERCORE SAS" width="30px" height="30px"></a> | Localización Withholding Venezuela
[territorial_pd](territorial_pd/) | 0.1 | <a href="https://github.com/odoo-mastercore" title="SINAPSYS GLOBAL SA, MASTERCORE SAS"><img src="https://avatars.githubusercontent.com/u/33432708?v=4" alt="SINAPSYS GLOBAL SA, MASTERCORE SAS" width="30px" height="30px"></a> | Venezuela Municipalities and Parishes

[//]: # (end addons)

<!-- prettier-ignore-end -->

## Instalación

Para instalar los módulos, debe seguir el siguiente orden:
- territorial_pd
- l10n_ve_base
- l10n_ve_account_payment_fix
- l10n_ve_account_financial_amount
- l10n_ve_account_payment_group
- l10n_ve_account_payment_group_document
- l10n_ve_account_withholding
- l10n_ve_account_withholding_automatic
- l10n_ve_withholding
- l10n_ve_vat_ledger

## Licenses

This repository is licensed under [AGPL-3.0](LICENSE.txt).

However, each module can have a totally different license, as long as they adhere to Odoo Community Association (OCA)
policy. Consult each module's `__manifest__.py` file, which contains a `license` key
that explains its license.

# Authors

<a href="https://github.com/odoo-mastercore" title="SINAPSYS GLOBAL SA, MASTERCORE SAS"><img src="https://avatars.githubusercontent.com/u/33432708?v=4" alt="SINAPSYS GLOBAL SA, MASTERCORE SAS" width="100px" height="100px"/></a>

# Contributors

-   SINAPSYS GLOBAL SA, MASTERCORE SAS
    -   Reydi Hernández  \<<rhe@sinapsys.global>\>
    -   Freddy Arraez  \<<far@sinapsys.global>\>
-   Venezuelan Odoo Community
    - Leonardo J. Caballero G. \<<leonardocaballero@gmail.com>\>

----
OCA, or the [Odoo Community Association](http://odoo-community.org/), is a nonprofit
organization whose mission is to support the collaborative development of Odoo features
and promote its widespread use.
