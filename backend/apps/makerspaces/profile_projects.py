"""Replace the account profile's showcase projects, preserving image cleanup."""
from django.utils.translation import gettext
from rest_framework.exceptions import ValidationError

from apps.makerspaces.models_account_profile import AccountProject


def save_projects(profile, rows):
    """Replace the project list.

    Replace rather than merge, matching every other list-shaped save here: with a merge there is
    no way to express deleting one. An id the caller does not own is a **400, not a silent
    drop** -- a save that quietly discards part of the submission leaves the member believing it
    was stored. Imported projects (`source_submission_id`) are ordinary rows and may be edited or
    removed; removing one frees that submission to be imported again.
    """
    existing = {project.pk: project for project in profile.projects.all()}
    seen = set()
    for position, row in enumerate(rows):
        project_id = row.get("id")
        if project_id is not None:
            project = existing.get(project_id)
            if project is None:
                raise ValidationError({"projects": gettext("Unknown project id {project_id}.").format(project_id=project_id)})
            project.title = row["title"]
            project.description = row.get("description", "")
            project.links = row.get("links", [])
            for field in ("subtitle", "tags", "public_visible"):
                if field in row:
                    setattr(project, field, row[field])
            project.position = position
            project.save(update_fields=["title", "subtitle", "tags", "public_visible", "description",
                                        "links", "position", "updated_at"])
            seen.add(project_id)
            continue
        AccountProject.objects.create(
            profile=profile, title=row["title"], subtitle=row.get("subtitle", ""), tags=row.get("tags", []),
            public_visible=row.get("public_visible", True), description=row.get("description", ""),
            links=row.get("links", []), position=position,
        )
    removed = [project for pk, project in existing.items() if pk not in seen]
    from apps.makerspaces import profile_images

    for project in removed:
        # Freed through the image service so the storage counter and the bucket stay in step.
        profile_images.clear_project_image(profile, project)
    AccountProject.objects.filter(pk__in=[project.pk for project in removed]).delete()
