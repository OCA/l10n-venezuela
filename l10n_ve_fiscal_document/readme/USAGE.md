Enter the fiscal control number and assignment date on the invoice when they are
available. Integrations with fiscal machines or digital printers can write these
fields while the document is still in draft.

After a Venezuelan customer document is posted, it cannot be reset to draft or
deleted and its fiscal identification cannot be changed. Use a credit or debit
note to correct the transaction.

A fiscal machine or an authorized digital printing house connector normally
only learns the control number *after* the document is posted and totalled.
For that case, call ``account.move._l10n_ve_set_control_number(control_number,
control_date=False)`` on the posted document: it is the only supported way to
assign the control number once posting has locked the fiscal data, refuses to
run on a document that is still a draft, and refuses to overwrite a number
already assigned.
