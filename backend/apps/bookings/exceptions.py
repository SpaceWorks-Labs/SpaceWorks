from rest_framework.exceptions import APIException


class BookingConflict(Exception):
    pass


class BookingInvalidTransition(Exception):
    pass


class MachineUnderRepair(BookingConflict, APIException):
    """A new booking on a machine that is out of service for repair (#93, trace gap 19).

    Still a `BookingConflict`, so callers that collect conflicts (weekly recurrence) keep doing so;
    as an APIException it answers 409 with its own `machine_under_repair` code.
    """
    status_code = 409
    default_code = 'machine_under_repair'
    default_detail = 'This machine is out of service for repair at that time.'

    def __init__(self):
        APIException.__init__(self, {'detail': self.default_detail, 'code': self.default_code}, self.default_code)

    def __str__(self):
        return self.default_detail


class BookerNamesRequiresAvailability(APIException):
    status_code = 400
    default_code = 'booker_names_requires_availability'
    default_detail = 'Booker names require public availability to be enabled.'

    def __init__(self):
        self.detail = {
            'detail': self.default_detail,
            'code': self.default_code,
        }
