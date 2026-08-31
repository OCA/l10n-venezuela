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

The legal basis covered by this addon is:

- [Providencia Administrativa SNAT/2011/00071](https://tributos.ivecofi.net/informacion/legislacion/providencias/pa-2011-71), published in Official Gazette No. 39,795 of November 8, 2011, which regulates fiscal-document emission media and control numbers.
- [Providencia Administrativa SNAT/2024/000102](http://www.gacetaoficial.gob.ve/storage/2024/T028700051511-0-GO_43.032-000.pdf), published by Venezuela's Imprenta Nacional in Official Gazette No. 43,032 of December 19, 2024, especially articles 7.4 and 7.15 on digitally assigned control numbers and assignment dates.
