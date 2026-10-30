"""Release-2 membership lifecycle routes (lane L4): financial year, plans, register,
import, renewals, titles, erasure. Mounted under the admin API prefix."""
from django.urls import path

from apps.admin_api.views_financial_year import FinancialYearView

urlpatterns = [
    path("makerspaces/<int:makerspace_id>/financial-year", FinancialYearView.as_view(),
         name="admin-financial-year"),
]
