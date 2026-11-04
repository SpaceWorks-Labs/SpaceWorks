from apps.hardware_requests.display import requester_label


def _staff_summary(request):
    lines = [
        f"Status: {request.status}",
        f"Requester: {requester_label(request, fallback='Unknown requester')}",
    ]
    if request.requester_contact_email:
        lines.append(f"Email: {request.requester_contact_email}")
    if request.requester_contact_phone:
        lines.append(f"Phone: {request.requester_contact_phone}")
    if request.assigned_box_id:
        lines.append(f"Box: {request.assigned_box.code}")
    if request.return_due_at:
        lines.append(f"Return due: {request.return_due_at}")
    if request.rejection_reason:
        lines.append(f"Reason: {request.rejection_reason}")
    return "\n".join(lines)
