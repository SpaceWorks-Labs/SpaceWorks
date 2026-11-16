"""Release-2 lane L13: a public Google Sheet as an import source (#74, #128 C-12/C-13).

Both keys are off by default and add a SOURCE only: the importers, their mapping,
preview, de-duplication and apply are the parents' (L4, L3). Off means a sheet request
answers 404 and the console shows the upload alone; there is no data of their own.

* `membership.import_sheets` -- import members from a public Google Sheet link
  (needs `membership.import`).
* `membership.id_programmes_import_sheets` -- import ID-programme people from a public
  Google Sheet link (needs `membership.id_programmes`).
"""


def definitions(feature):
    return (
        feature("membership.import_sheets", "membership", "Member import from Google Sheets",
                "Import members from a Google Sheet shared as “anyone with the link can view”.",
                requires_features=("membership.import",)),
        feature("membership.id_programmes_import_sheets", "membership", "ID-programme import from Google Sheets",
                "Import ID-programme people from a Google Sheet shared as “anyone with the link can view”.",
                requires_features=("membership.id_programmes",)),
    )
