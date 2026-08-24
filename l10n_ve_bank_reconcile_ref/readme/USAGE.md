1. Install the module ``l10n_ve_bank_reconcile_ref``.
2. Go to **Invoicing > Configuration > Reconciliation Models**.
3. Open **VE: Match by reference (payment then invoice)** or create an
   **Invoice Matching** rule.
4. Enable:

   - Search on Label and/or Reference of the statement
   - Match by reference suffix
   - Suffix lengths (for example ``6,4``)
   - Match payments before invoices
   - Auto-validate
   - Unique matching

5. Import the bank statement and open the journal reconciliation.

Behavior:

- One candidate and a compatible amount: auto-reconcile when Auto-validate
  is on.
- Several candidates: only suggestions.
- Unreliable references (``0``, empty, or too short) are ignored.
