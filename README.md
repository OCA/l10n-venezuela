[![Runbot Status](https://runbot.odoo-community.org/runbot/badge/flat/189/14.0.svg)](https://runbot.odoo-community.org/runbot/repo/github-com-oca-web-189)
[![Build Status](https://travis-ci.org/OCA/l10n-venezuela.svg?branch=14.0)](https://travis-ci.org/OCA/l10n-venezuela)
[![codecov](https://codecov.io/gh/OCA/l10n-venezuela/branch/14.0/graph/badge.svg)](https://codecov.io/gh/OCA/l10n-venezuela)

# Localización venezolana de Odoo

Repositorio de código del proyecto de la localización venezolana para el software
de gestión integral Odoo.

La localización venezolana de Odoo incluye:

* Módulos para adaptar el sistema a los requisitos fiscales y contables
  venezolanas.
* Traducciones a los términos oficiales del país.

Para más información, dirigirse a [Mastercore Sinapsys Global Team](https://github.com/odoo-mastercore/odoo-venezuela/tree/14.0).

<!-- prettier-ignore-start -->

[//]: # (addons)

# Available addons

addon | version | maintainers | summary
---   | ---     | ---         | ---
[l10n_ve_account_financial_amount](l10n_ve_account_financial_amount/) | 14.0.1.0.0 | <a href="https://github.com/odoo-mastercore" title="Mastercore Sinapsys Global"><img src="https://avatars.githubusercontent.com/u/33432708?v=4" alt="Mastercore Sinapsys Global" width="30px" height="30px"></a> | Accounting Financial Amounts
[l10n_ve_account_payment_fix](l10n_ve_account_payment_fix/) | 14.0.1.0.0 | <a href="https://github.com/odoo-mastercore" title="Mastercore Sinapsys Global"><img src="https://avatars.githubusercontent.com/u/33432708?v=4" alt="Mastercore Sinapsys Global" width="30px" height="30px"></a> | Account Payment Fix
[l10n_ve_account_payment_group](l10n_ve_account_payment_group/) | 14.0.1.0.0 | <a href="https://github.com/odoo-mastercore" title="Mastercore Sinapsys Global"><img src="https://avatars.githubusercontent.com/u/33432708?v=4" alt="Mastercore Sinapsys Global" width="30px" height="30px"></a> | Account Payment with Multiple methods
[l10n_ve_account_payment_group_document](l10n_ve_account_payment_group_document/) | 14.0.1.0.0 | <a href="https://github.com/odoo-mastercore" title="Mastercore Sinapsys Global"><img src="https://avatars.githubusercontent.com/u/33432708?v=4" alt="Mastercore Sinapsys Global" width="30px" height="30px"></a> | Payment Groups with Accounting Documents
[l10n_ve_account_withholding](l10n_ve_account_withholding/) | 14.0.1.0.0 | <a href="https://github.com/odoo-mastercore" title="Mastercore Sinapsys Global"><img src="https://avatars.githubusercontent.com/u/33432708?v=4" alt="Mastercore Sinapsys Global" width="30px" height="30px"></a> | Withholdings on Payments
[l10n_ve_account_withholding_automatic](l10n_ve_account_withholding_automatic/) | 14.0.1.0.0 | <a href="https://github.com/odoo-mastercore" title="Mastercore Sinapsys Global"><img src="https://avatars.githubusercontent.com/u/33432708?v=4" alt="Mastercore Sinapsys Global" width="30px" height="30px"></a> | Automatic Withholdings on Payments
[l10n_ve_base](l10n_ve_base/) | 14.0.1 | <a href="https://github.com/odoo-mastercore" title="Mastercore Sinapsys Global"><img src="https://avatars.githubusercontent.com/u/33432708?v=4" alt="Mastercore Sinapsys Global" width="30px" height="30px"></a> | Localización Venezuela Base
[l10n_ve_vat_ledger](l10n_ve_vat_ledger/) | 14.0.2 | <a href="https://github.com/odoo-mastercore" title="Mastercore Sinapsys Global"><img src="https://avatars.githubusercontent.com/u/33432708?v=4" alt="Mastercore Sinapsys Global" width="30px" height="30px"></a> | Localización Vat Ledger Venezuela
[l10n_ve_withholding](l10n_ve_withholding/) | 14.0.1 | <a href="https://github.com/odoo-mastercore" title="Mastercore Sinapsys Global"><img src="https://avatars.githubusercontent.com/u/33432708?v=4" alt="Mastercore Sinapsys Global" width="30px" height="30px"></a> | Localización Withholding Venezuela
[territorial_pd](territorial_pd/) | 14.0.1 | <a href="https://github.com/odoo-mastercore" title="Mastercore Sinapsys Global"><img src="https://avatars.githubusercontent.com/u/33432708?v=4" alt="Mastercore Sinapsys Global" width="30px" height="30px"></a> | Venezuela Municipalities and Parishes

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

This repository is licensed under [GNU AFFERO GENERAL PUBLIC LICENSE](LICENSE.txt).

However, each module can have a totally different license. Consult each module's
`__manifest__.py` file, which contains a `license` key that explains its license.

# Autor

<a href="https://github.com/odoo-mastercore" title="Mastercore Sinapsys Global"><img src="https://avatars.githubusercontent.com/u/33432708?v=4" alt="Mastercore Sinapsys Global" width="100px" height="100px"/></a>

# Colaboradores

-   Mastercore Sinapsys Global
    -   Reydi Hernández  \<<rhe@sinapsys.global>\>
    -   Freddy Arraez  \<<far@sinapsys.global>\>
-   Venezuelan Odoo Community
    - Leonardo J. Caballero G. \<<leonardocaballero@gmail.com>\>
