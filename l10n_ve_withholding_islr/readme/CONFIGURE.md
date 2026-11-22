1. In Accounting settings, configure the liability account used for ISLR
   withholdings payable and the miscellaneous journal of the withholding
   entries. Posting a bill subject to withholding fails until both are set.
2. In Accounting > Configuration > Tax Unit, maintain each official tax unit
   value and its effective date.
3. Maintain a VES exchange rate for every withholding and export date when
   neither the company nor the bill currency is VES: posting such a bill
   converts its base to bolivars and fails without the rate.
4. On each vendor, select the ISLR person type and, optionally, a default
   withholding concept. A vendor bill with at least one line carrying a
   withholding concept cannot be posted unless the vendor has a valid RIF: one
   letter V, E, J, P, or G, eight digits, and the SENIAT modulo-11 check digit
   (hyphens and spaces are ignored). The normalized 10-character value is the
   one written in `RifRetenido`. Bills without a concept are not checked.
5. On products, optionally set the withholding concept; it takes precedence
   over the vendor's.
6. On each concept, maintain the SENIAT code, rate, and taxable base
   percentage of each person type (100 when the base is not presumptive) and,
   for non-domiciled legal entities, whether the concept uses a fixed rate or
   Tarifa N° 2. The Tarifa N° 2 brackets are the `TARIFA2_BRACKETS` constant
   of `models/islr_concept.py`, in tax units. A concept applies to a person
   type only when it has a SENIAT code for it (not `000` and not empty); the
   concept list and form show the person types it applies to.
7. On a non-resident individual or non-domiciled legal entity covered by a
   double taxation treaty, enable the treaty, set its rate (0 to 100, 0
   allowed) and the reference of the fiscal residence certificate. Non-resident
   vendors need the RIF assigned by SENIAT like any other vendor.

Lines without a withholding concept do not generate an ISLR withholding or
voucher. Invoicing users can read concepts, tax units, and vouchers, and post
bills that issue vouchers; only accounting managers can change concepts and
tax units or manage vouchers.
