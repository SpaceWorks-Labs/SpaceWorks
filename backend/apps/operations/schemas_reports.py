from drf_spectacular.utils import PolymorphicProxySerializer

from apps.operations.serializers import AnalyticsSummarySerializer
from apps.operations.serializers_reports import (
    ActiveLoansReportSerializer,
    DamagedLostReportSerializer,
    DamagedMissingReportSerializer,
    MostLentReportSerializer,
    QrScansReportSerializer,
    RecentlyAddedReportSerializer,
    ReturnsReportSerializer,
    TakenItemsReportSerializer,
    TopBorrowersReportSerializer,
    BookingUtilizationReportSerializer,
    EventAttendanceReportSerializer,
    FabLabHealthReportSerializer,
    MemberActivityReportSerializer,
    PaymentReconciliationReportSerializer,
)
from apps.operations.serializers_report_catalog import GenericAnalyticsReportSerializer
from .serializers_reports_machine_analytics import (
    MachineUsageV2ReportSerializer, MachineUsageMembersReportSerializer, MachineUsageHeatmapReportSerializer,
    MachineDowntimeReportSerializer, MaintenanceActivityV2ReportSerializer, MachineServiceV2ReportSerializer,
    ServiceQueueTimesReportSerializer, PrinterJobsReportSerializer, MachineErrorsReportSerializer, WarrantyExpiryReportSerializer,
)
from .serializers_reports_events_detail import EventRegistrationReportSerializer, EventFeedbackReportSerializer
from .serializers_reports_bookings import (
    BookingResourceUtilizationReportSerializer, BookingReservationReportSerializer, BookingAnswerReportSerializer,
)
from apps.operations.serializers_reports_payments import PaymentCashBookSerializer
from apps.operations.serializers_reports_membership import MemberRetentionReportSerializer, MembershipRevenueReportSerializer
from apps.operations.serializers_reports_finance import (
    PaymentsLedgerReportSerializer, RevenueOverTimeReportSerializer,
    CashBookReportSerializer, AccountingJournalReportSerializer,
)

ANALYTICS_REPORT_RESPONSE = PolymorphicProxySerializer(
    component_name="AnalyticsReportResponse",
    serializers=[
        AnalyticsSummarySerializer,
        TakenItemsReportSerializer,
        ActiveLoansReportSerializer,
        ReturnsReportSerializer,
        DamagedMissingReportSerializer,
        DamagedLostReportSerializer,
        QrScansReportSerializer,
        MostLentReportSerializer,
        TopBorrowersReportSerializer,
        RecentlyAddedReportSerializer,
        MachineUsageV2ReportSerializer,
        EventAttendanceReportSerializer,
        BookingUtilizationReportSerializer,
        MaintenanceActivityV2ReportSerializer,
        MachineUsageMembersReportSerializer, MachineUsageHeatmapReportSerializer, MachineDowntimeReportSerializer,
        MachineServiceV2ReportSerializer, ServiceQueueTimesReportSerializer, PrinterJobsReportSerializer,
        MachineErrorsReportSerializer, WarrantyExpiryReportSerializer,
        MemberActivityReportSerializer,
        FabLabHealthReportSerializer,
        PaymentReconciliationReportSerializer,
        PaymentCashBookSerializer,
        PaymentsLedgerReportSerializer,
        RevenueOverTimeReportSerializer,
        CashBookReportSerializer,
        AccountingJournalReportSerializer,
        GenericAnalyticsReportSerializer,
        MemberRetentionReportSerializer,
        MembershipRevenueReportSerializer,
        EventRegistrationReportSerializer,
        EventFeedbackReportSerializer,
        BookingResourceUtilizationReportSerializer,
        BookingReservationReportSerializer,
        BookingAnswerReportSerializer,
    ],
    resource_type_field_name=None,
)
