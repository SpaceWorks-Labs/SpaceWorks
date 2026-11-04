from django.urls import path

from apps.procurement.views import (
    ToBuyDetailView,
    ToBuyExportView,
    ToBuyListCreateView,
    ToBuyMachineTypeOptionsView,
    ToBuyMoveToInventoryView,
    ToBuyMoveToPrintingView,
    ToBuyRefillConsumableView,
    ToBuyReceiptDeleteView,
    ToBuyReceiptListCreateView,
    ToBuyReceiptPresignView,
    ToBuyReceiptUrlView,
)

from apps.procurement.views_vendors import ToBuyMarkBoughtView, VendorDetailView, VendorListCreateView

app_name = "procurement"

urlpatterns = [
    path(
        "makerspace/<int:makerspace_id>/to-buy",
        ToBuyListCreateView.as_view(),
        name="to-buy-list",
    ),
    path(
        "makerspace/<int:makerspace_id>/to-buy/export",
        ToBuyExportView.as_view(),
        name="to-buy-export",
    ),
    path(
        "makerspace/<int:makerspace_id>/to-buy/machine-types",
        ToBuyMachineTypeOptionsView.as_view(),
        name="to-buy-machine-type-options",
    ),
    path(
        "to-buy/<int:pk>/receipts/presign",
        ToBuyReceiptPresignView.as_view(),
        name="to-buy-receipt-presign",
    ),
    path(
        "to-buy/<int:pk>/receipts",
        ToBuyReceiptListCreateView.as_view(),
        name="to-buy-receipt-list",
    ),
    path(
        "to-buy/receipts/<int:pk>/url",
        ToBuyReceiptUrlView.as_view(),
        name="to-buy-receipt-url",
    ),
    path(
        "to-buy/receipts/<int:pk>",
        ToBuyReceiptDeleteView.as_view(),
        name="to-buy-receipt-detail",
    ),
    path(
        "to-buy/<int:pk>/move-to-inventory",
        ToBuyMoveToInventoryView.as_view(),
        name="to-buy-move-to-inventory",
    ),
    path(
        "to-buy/<int:pk>/move-to-printing",
        ToBuyMoveToPrintingView.as_view(),
        name="to-buy-move-to-printing",
    ),
    path(
        "to-buy/<int:pk>/refill-consumable",
        ToBuyRefillConsumableView.as_view(),
        name="to-buy-refill-consumable",
    ),
    path("to-buy/<int:pk>/mark-bought", ToBuyMarkBoughtView.as_view(), name="to-buy-mark-bought"),
    path("makerspace/<int:makerspace_id>/vendors", VendorListCreateView.as_view(), name="procurement-vendors"),
    path("makerspace/<int:makerspace_id>/vendors/<int:pk>", VendorDetailView.as_view(),
         name="procurement-vendor-detail"),
    path("to-buy/<int:pk>", ToBuyDetailView.as_view(), name="to-buy-detail"),
]
