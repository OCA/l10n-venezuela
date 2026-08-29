This addon stores the fiscal control number, its assignment date, and the
emission medium used for Venezuelan customer documents.

The emission medium is copied from the sales journal when a document is posted,
so later journal configuration changes do not alter its fiscal history. Posted
customer fiscal identification is immutable; supplier document data remains
correctable.

Existing posted or cancelled customer documents are also locked at installation,
without attempting to infer missing historical fiscal data.

The addon does not allocate control numbers, manage paper batches, print fiscal
documents, or communicate with fiscal machines or digital printers.
