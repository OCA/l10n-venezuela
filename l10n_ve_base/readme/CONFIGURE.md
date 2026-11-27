1.  Install official `l10n_ve` and set the company country to Venezuela.
    Official Odoo still links the country to obsolete VEF (symbol Bs.F).
    This module activates **VES** (symbol **Bs**) and uses it as
    Venezuela's currency; companies still on VEF are switched (VEF and
    VES are the same bolívar, 1:1). States, municipalities and parishes
    load with this module. `l10n_latam_base` is required and is
    installed automatically with this module (official Odoo 19 addons;
    do not install it by hand). The partner form then shows
    identification type + number (`vat`): **RIF**, **Cédula
    Venezolano**, **Cédula Extranjera** and **Pasaporte** (Contacts /
    Configuration / Identification Type). Generic LATAM VAT / Foreign ID
    are archived.
2.  Accounting \> Configuration \> Venezuelan Localization \> Tax Units
    (UT).
3.  Review SENIAT URLs if official endpoints change.
4.  Set the VES / BCV rate (or install `currency_rate_update_bcv`);
    posting and withholdings require it.
5.  `person_type` is under the identification number. A Venezuelan
    partner requires the number; type + letter must match person type (V
    → PNRE, E → PNNR, J/C/G → PJDO, P → PJND). Other partner fiscal data
    (VAT subject, IVA agent) is on the **Accounting** tab, same pattern
    as 19.0.
6.  IVA `appl_type` is assigned on install/update (Exento, reducido 8%,
    general 16%, adicional 31%). The company default sale/purchase tax
    is **IVA 16%**. Official `l10n_ve` still ships 12% / 22% until
    odoo#285425; those records are aligned in place to 16% / 31%. Mark
    **SDCF** yourself on the 0% taxes that have no tax credit; that
    cannot be inferred from the rate.
7.  Optionally mark fiscal printer usage on the company.
8.  SENIAT taxpayer type (Ordinary / Formal / Special) is on the partner
    form, under person type. Catalog: *Accounting \> Configuration \>
    Venezuelan Localization \> SENIAT Taxpayer Types*.
9.  Venezuelan banks (SUDEBAN code in BIC) are loaded on install. On a
    bank account, choosing a VE bank prefixes the number with the
    4-digit code if it is empty; set checking / savings / trust as
    needed.
