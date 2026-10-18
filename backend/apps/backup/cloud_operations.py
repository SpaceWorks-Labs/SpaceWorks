"""Service-boundary capability refusals use the API's existing typed errors."""
from django.conf import settings
from rest_framework.exceptions import APIException


class HostSupervisorRequired(APIException):
    status_code = 409
    default_code = "host_supervisor_required"

    def __init__(self, code):
        super().__init__({"code": code, "detail": "Deploy through your cloud provider. This operation requires the supervised host."})


def require_host(code):
    if settings.SPACEWORKS_DEPLOYMENT_MODE == "managed":
        raise HostSupervisorRequired(code)
    from .managed.admission import ManagedAdmissionError, refuse_host_operation
    try:
        refuse_host_operation(code)
    except ManagedAdmissionError:
        raise HostSupervisorRequired(code) from None


def require_deployment_archive(scope):
    if scope == "deployment":
        require_host("deployment_backup_requires_host_supervisor")


def require_managed_tenant_capture():
    if getattr(settings, "SPACEWORKS_DEPLOYMENT_MODE", "host") != "managed":
        from apps.operations.cloud_runtime import check
        check()
        return
    from apps.storage_capabilities.runtime import configured_contracts
    contracts = configured_contracts()
    if any(contract.versioning != "enabled" for contract in contracts.values()):
        raise HostSupervisorRequired("managed_writer_drain_inventory_unqualified")
