"""Build one chunk's output object and assemble the final result of a bulk job.

Parts live under `card-jobs/<ms>/<job>/part-<n>`; the result replaces them. Sheet and
per-person PDFs are merged with pypdf; the ZIP is rebuilt from the parts' entries.
"""
import io
import zipfile

from .cards import context_for, document_for
from .holders import spec_for
from .rendering import render_pdf
from .sheets import grid, render_sheets
from .storage import delete_quietly, get_bytes, put_bytes

CHUNK = 50


def chunk_size(job, first_document):
    if job.kind != "bulk_sheet":
        return CHUNK
    columns, rows, _left, _top = grid(job.params.get("paper", "a4"), first_document["front"]["page_width_mm"],
                                      first_document["front"]["page_height_mm"])
    per_page = columns * rows
    return max(per_page, (CHUNK // per_page) * per_page)


def part_key(job, index):
    return f"card-jobs/{job.makerspace_id}/{job.pk}/part-{index:05d}"


def render_chunk(job, kind, cards):
    """-> (bytes, content_type, failed_ids). One unreadable card never fails the chunk."""
    rendered, failed = [], []
    for card in cards:
        try:
            document = document_for(kind, card)
            rendered.append((card, document, context_for(kind, card, document)))
        except Exception:
            failed.append(card.pk)
    if not rendered:
        return None, "", failed
    if job.kind == "bulk_sheet":
        # One sheet grid needs one card size: cards whose design uses another stock are skipped.
        size = (rendered[0][1]["front"]["page_width_mm"], rendered[0][1]["front"]["page_height_mm"])
        failed += [card.pk for card, document, _c in rendered
                   if (document["front"]["page_width_mm"], document["front"]["page_height_mm"]) != size]
        rendered = [row for row in rendered if row[0].pk not in failed]
        params = job.params
        pdf = render_sheets([(document, context) for _card, document, context in rendered],
                            paper=params.get("paper", "a4"), order=params.get("order", "duplex"),
                            crop_marks=params.get("crop_marks", True))
        return pdf, "application/pdf", failed
    if job.kind == "bulk_per_person":
        from pypdf import PdfWriter
        writer = PdfWriter()
        for _card, document, context in rendered:
            writer.append(io.BytesIO(render_pdf(document, context)))
        buffer = io.BytesIO()
        writer.write(buffer)
        return buffer.getvalue(), "application/pdf", failed
    buffer = io.BytesIO()
    spec = spec_for(kind)
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for card, document, context in rendered:
            archive.writestr(f"{spec.filename(card)}.pdf", render_pdf(document, context))
    return buffer.getvalue(), "application/zip", failed


def store_part(job, index, data, content_type):
    from apps.tenant_migration.gate_runtime import assert_write_allowed
    assert_write_allowed(job.makerspace_id)
    key = part_key(job, index)
    put_bytes(key, data, content_type)
    return key


def assemble(job):
    """-> (key, size, content_type) for the final object; parts are deleted afterwards."""
    from apps.tenant_migration.gate_runtime import assert_write_allowed
    assert_write_allowed(job.makerspace_id)
    final = f"card-jobs/{job.makerspace_id}/{job.pk}/result"
    if job.kind == "zip":
        buffer, names = io.BytesIO(), set()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as out:
            for key in job.parts:
                with zipfile.ZipFile(io.BytesIO(get_bytes(key))) as part:
                    for name in part.namelist():
                        unique, n = name, 2
                        while unique in names:
                            unique, n = name.replace(".pdf", f"-{n}.pdf"), n + 1
                        names.add(unique)
                        out.writestr(unique, part.read(name))
        data, content_type = buffer.getvalue(), "application/zip"
    else:
        from pypdf import PdfWriter
        writer = PdfWriter()
        for key in job.parts:
            writer.append(io.BytesIO(get_bytes(key)))
        buffer = io.BytesIO()
        writer.write(buffer)
        data, content_type = buffer.getvalue(), "application/pdf"
    put_bytes(final, data, content_type)
    return final, len(data), content_type


def discard_parts(job_id):
    from .models import CardJob
    job = CardJob.objects.filter(pk=job_id).first()
    if job is None:
        return
    for key in job.parts or ():
        delete_quietly(key)
    CardJob.objects.filter(pk=job_id).update(parts=[])
