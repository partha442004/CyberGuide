"""
Regression tests for JobSource enum additions (cutshort, foundit).

These sources were missing from the enum, so the model's ``_coerce_job_source``
validator silently stored their jobs as ``unknown`` — the discovery endpoint
reported "saved: 4" while the dashboard showed zero jobs from the new source.
Adding the values keeps stored sources accurate.
"""


def test_job_source_has_cutshort_and_foundit():
    from interntrack.domain.enums import JobSource

    assert JobSource.CUTSHORT.value == "cutshort"
    assert JobSource.FOUNDIT.value == "foundit"


def test_job_source_coerces_cutshort_and_foundit():
    from sqlalchemy import Enum

    from interntrack.domain.enums import JobSource
    from interntrack.domain.models import Job

    column_enum = Enum(
        JobSource,
        native_enum=False,
        values_callable=lambda e: [m.value for m in e],
    )
    values = {v.value if hasattr(v, "value") else v for v in column_enum.enums}
    assert "cutshort" in values
    assert "foundit" in values

    job = Job(source=JobSource.CUTSHORT)
    assert job.source == JobSource.CUTSHORT
    job = Job(source="cutshort")
    assert job.source == JobSource.CUTSHORT
    job = Job(source="foundit")
    assert job.source == JobSource.FOUNDIT
