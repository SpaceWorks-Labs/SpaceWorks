"""A managed-bound database cannot evade service gates by changing an env value."""


def assert_mode_binding(cursor, mode):
    from .admission import ManagedAdmissionError

    cursor.execute("SELECT to_regclass('public.backup_manageddeploymentstate')")
    if cursor.fetchone()[0] is None:
        if mode == "managed":
            raise ManagedAdmissionError("Managed deployment binding is unavailable.")
        return
    cursor.execute("SELECT EXISTS (SELECT 1 FROM public.backup_manageddeploymentstate)")
    bound = cursor.fetchone()[0]
    if mode == "host" and bound:
        raise ManagedAdmissionError("A managed-bound database requires managed admission.")
