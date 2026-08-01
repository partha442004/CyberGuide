"""
Dashboard components package.
"""

from dashboard.components.cards import (
    application_card,
    info_card,
    job_card,
    metric_card,
    section_header,
    skill_badge,
    warning_card,
)
from dashboard.components.charts import (
    create_application_status_bar,
    create_application_timeline,
    create_job_type_pie_chart,
    create_salary_distribution,
    create_skill_demand_chart,
    create_top_companies_bar,
)
from dashboard.components.forms import (
    application_form,
    filter_form,
    job_search_form,
    notification_settings_form,
    search_form,
    skill_assessment_form,
)

__all__ = [
    # Charts
    "create_job_type_pie_chart",
    "create_application_status_bar",
    "create_application_timeline",
    "create_top_companies_bar",
    "create_salary_distribution",
    "create_skill_demand_chart",
    # Cards
    "metric_card",
    "job_card",
    "application_card",
    "skill_badge",
    "section_header",
    "info_card",
    "warning_card",
    # Forms
    "search_form",
    "filter_form",
    "job_search_form",
    "application_form",
    "notification_settings_form",
    "skill_assessment_form",
]
