"""
Tests for the Streamlit dashboard components.

Streamlit and plotly are not required to run the backend test suite, so this
module injects lightweight fakes into ``sys.modules`` before importing the
dashboard components and exercises their rendering / data-shaping logic.
"""

import sys
import types
from datetime import date

import pytest

# ---------------------------------------------------------------------------
# Fake streamlit module
# ---------------------------------------------------------------------------


class _FakeColumn:
    """Context-manager stand-in for ``st.columns`` entries."""

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class FakeStreamlit(types.ModuleType):
    """Configurable fake of the streamlit module surface used by components."""

    def __init__(self):
        super().__init__("streamlit")
        self.markdown_calls: list[str] = []
        self.subheader_calls: list[str] = []
        self.values: dict[str, object] = {}

    def _get(self, key, default):
        return self.values.get(key, default)

    def markdown(self, body, unsafe_allow_html=False):
        self.markdown_calls.append(body)

    def subheader(self, text):
        self.subheader_calls.append(text)

    def columns(self, spec):
        n = spec if isinstance(spec, int) else len(spec)
        return [_FakeColumn() for _ in range(n)]

    def text_input(self, label=None, key=None, **kwargs):
        return self._get(key, "")

    def button(self, label=None, key=None, **kwargs):
        return self._get(key, False)

    def selectbox(self, label=None, options=None, index=0, key=None, **kwargs):
        if key in self.values:
            return self.values[key]
        if options is None or index >= len(options):
            return None
        return options[index]

    def multiselect(self, label=None, options=None, default=None, key=None, **kwargs):
        return self._get(key, default if default is not None else [])

    def number_input(self, label=None, value=None, key=None, **kwargs):
        return self._get(key, value if value is not None else 0)

    def date_input(self, label=None, value=None, key=None, **kwargs):
        return self._get(key, value)

    def checkbox(self, label=None, value=False, key=None, **kwargs):
        return self._get(key, value)

    def slider(self, label=None, value=None, key=None, **kwargs):
        return self._get(key, value if value is not None else 0)

    def text_area(self, label=None, key=None, **kwargs):
        return self._get(key, "")


# ---------------------------------------------------------------------------
# Fake plotly modules
# ---------------------------------------------------------------------------


class FakeTrace:
    """Stand-in for ``go.Pie`` / ``go.Bar`` traces: stores constructor kwargs."""

    def __init__(self, **kwargs):
        for name, value in kwargs.items():
            setattr(self, name, value)


class FakeFigure:
    """Minimal ``go.Figure`` stand-in recording traces and layout."""

    def __init__(self, data=None):
        self.data = list(data) if data else []
        self.layout: dict = {}

    def add_trace(self, trace):
        self.data.append(trace)
        return self

    def update_layout(self, **kwargs):
        self.layout.update(kwargs)
        return self


def _fake_line(*args, **kwargs):
    return FakeFigure()


_ST = FakeStreamlit()
_GO = types.ModuleType("plotly.graph_objects")
_PX = types.ModuleType("plotly.express")
_PLOTLY = types.ModuleType("plotly")

# Assignments to module attributes are intentionally dynamic (fake modules).
_GO.Figure = FakeFigure  # type: ignore[attr-defined]
_GO.Pie = FakeTrace  # type: ignore[attr-defined]
_GO.Bar = FakeTrace  # type: ignore[attr-defined]
_PX.line = _fake_line  # type: ignore[attr-defined]
_PLOTLY.graph_objects = _GO  # type: ignore[attr-defined]
_PLOTLY.express = _PX  # type: ignore[attr-defined]

# Inject fakes (intentionally persistent for this module's session) and import
# the real components.
sys.modules["streamlit"] = _ST
sys.modules["plotly"] = _PLOTLY
sys.modules["plotly.graph_objects"] = _GO
sys.modules["plotly.express"] = _PX

import dashboard.components.cards as cards  # noqa: E402
import dashboard.components.charts as charts  # noqa: E402
import dashboard.components.forms as forms  # noqa: E402


@pytest.fixture(autouse=True)
def _reset_fakes():
    """Reset fake state before every test."""
    _ST.markdown_calls.clear()
    _ST.subheader_calls.clear()
    _ST.values.clear()


# ---------------------------------------------------------------------------
# cards.py
# ---------------------------------------------------------------------------
class TestMetricCard:
    def test_renders_title_value_and_icon(self):
        cards.metric_card("Total Jobs", 42, icon="💼")
        html = _ST.markdown_calls[-1]
        assert "Total Jobs" in html
        assert "42" in html
        assert "💼" in html

    def test_positive_delta_is_green(self):
        cards.metric_card("Jobs", 42, delta="+5")
        html = _ST.markdown_calls[-1]
        assert "+5" in html
        assert "color: green" in html

    def test_negative_delta_is_red(self):
        cards.metric_card("Jobs", 42, delta="↓ 3")
        html = _ST.markdown_calls[-1]
        assert "color: red" in html

    def test_no_delta_renders_no_delta_block(self):
        cards.metric_card("Jobs", 42)
        html = _ST.markdown_calls[-1]
        assert "color: green" not in html


class TestJobCard:
    def test_renders_title_company_and_location(self):
        cards.job_card("Python Dev", "TechCorp", location="Remote")
        html = _ST.markdown_calls[-1]
        assert "Python Dev" in html
        assert "TechCorp" in html
        assert "📍 Remote" in html

    def test_defaults_to_remote_without_location(self):
        cards.job_card("Python Dev", "TechCorp")
        html = _ST.markdown_calls[-1]
        assert "📍 Remote" in html

    def test_salary_range_formatting(self):
        cards.job_card("Dev", "Co", salary_min=80000, salary_max=120000)
        html = _ST.markdown_calls[-1]
        assert "$80,000 - $120,000" in html

    def test_salary_min_only(self):
        cards.job_card("Dev", "Co", salary_min=80000)
        html = _ST.markdown_calls[-1]
        assert "From $80,000" in html

    def test_no_salary_message(self):
        cards.job_card("Dev", "Co")
        html = _ST.markdown_calls[-1]
        assert "Salary not specified" in html

    def test_tags_rendered(self):
        cards.job_card(
            "Dev",
            "Co",
            tags=["python", "fastapi", "x", "y", "z", "extra"],
        )
        html = _ST.markdown_calls[-1]
        assert "python" in html
        assert "fastapi" in html
        # Only first 5 tags are rendered
        assert "extra" not in html

    def test_source_badge_color(self):
        cards.job_card("Dev", "Co", source="linkedin")
        html = _ST.markdown_calls[-1]
        assert "#0077b5" in html


class TestApplicationCard:
    def test_status_offer_style(self):
        cards.application_card("SWE", "Co", status="offer")
        html = _ST.markdown_calls[-1]
        assert "🎉" in html
        assert "Offer" in html

    def test_unknown_status_falls_back(self):
        cards.application_card("SWE", "Co", status="weird")
        html = _ST.markdown_calls[-1]
        assert "Weird" in html

    def test_notes_and_applied_at(self):
        cards.application_card(
            "SWE",
            "Co",
            status="applied",
            applied_at="2026-01-01",
            notes="call back",
        )
        html = _ST.markdown_calls[-1]
        assert "2026-01-01" in html
        assert "call back" in html


class TestSkillBadge:
    def test_category_color_and_proficiency(self):
        cards.skill_badge("Python", category="programming", proficiency=3)
        html = _ST.markdown_calls[-1]
        assert "Python" in html
        assert "#3b82f6" in html
        assert "●●●" in html

    def test_unknown_category_default_color(self):
        cards.skill_badge("Mystery")
        html = _ST.markdown_calls[-1]
        assert "#6b7280" in html


class TestSectionHeader:
    def test_renders_title_only(self):
        cards.section_header("Overview")
        html = _ST.markdown_calls[-1]
        assert "Overview" in html

    def test_renders_subtitle(self):
        cards.section_header("Overview", subtitle="Sub text")
        html = _ST.markdown_calls[-1]
        assert "Sub text" in html


class TestInfoAndWarningCards:
    def test_info_card(self):
        cards.info_card("Tip", "Do the thing", icon="💡")
        html = _ST.markdown_calls[-1]
        assert "Tip" in html
        assert "Do the thing" in html
        assert "💡" in html

    def test_warning_card(self):
        cards.warning_card("Careful", "Watch out")
        html = _ST.markdown_calls[-1]
        assert "Careful" in html
        assert "Watch out" in html
        assert "⚠️" in html


# ---------------------------------------------------------------------------
# forms.py
# ---------------------------------------------------------------------------
class TestSearchForm:
    def test_returns_query_without_submit(self):
        _ST.values["search_input"] = "python"
        result = forms.search_form()
        assert result == "python"

    def test_on_submit_called_when_button_pressed(self):
        _ST.values["search_input"] = "react"
        _ST.values["search_button"] = True
        calls = []
        result = forms.search_form(on_submit=lambda q: calls.append(q))
        assert result == "react"
        assert calls == ["react"]


class TestFilterForm:
    def test_select_filter_defaults_to_all(self):
        result = forms.filter_form(
            [
                {
                    "name": "job_type",
                    "type": "select",
                    "options": ["full_time", "remote"],
                },
            ],
        )
        assert result["job_type"] == "All"

    def test_select_filter_with_default(self):
        _ST.values["filter_job_type"] = "remote"
        result = forms.filter_form(
            [
                {
                    "name": "job_type",
                    "type": "select",
                    "options": ["full_time", "remote"],
                    "default": "remote",
                },
            ],
        )
        assert result["job_type"] == "remote"

    def test_multiselect_filter(self):
        _ST.values["filter_skills"] = ["python"]
        result = forms.filter_form(
            [{"name": "skills", "type": "multiselect", "options": ["python", "go"]}],
        )
        assert result["skills"] == ["python"]

    def test_number_filter_uses_default(self):
        _ST.values["filter_min_salary"] = 50000
        result = forms.filter_form(
            [{"name": "min_salary", "type": "number", "min": 0, "max": 200000}],
        )
        assert result["min_salary"] == 50000

    def test_date_filter(self):
        _ST.values["filter_date"] = date(2026, 8, 1)
        result = forms.filter_form([{"name": "date", "type": "date"}])
        assert result["date"] == date(2026, 8, 1)

    def test_checkbox_filter(self):
        _ST.values["filter_remote"] = True
        result = forms.filter_form([{"name": "remote", "type": "checkbox"}])
        assert result["remote"] is True


class TestJobSearchForm:
    def test_returns_dict_with_defaults(self):
        result = forms.job_search_form()
        assert result["query"] == ""
        assert result["location"] == ""
        assert result["job_type"] is None  # "All" maps to None
        assert result["salary_min"] is None
        assert result["is_remote"] is False

    def test_custom_values(self):
        _ST.values["job_search_query"] = "python"
        _ST.values["job_search_salary_min"] = 100
        _ST.values["job_search_remote"] = True
        result = forms.job_search_form()
        assert result["query"] == "python"
        assert result["salary_min"] == 100
        assert result["is_remote"] is True


class TestApplicationForm:
    def test_returns_dict(self):
        _ST.values["application_status"] = "interview"
        _ST.values["application_priority"] = 3
        result = forms.application_form()
        assert result["status"] == "interview"
        assert result["priority"] == 3
        assert result["notes"] == ""
        assert result["resume_version"] == ""


class TestNotificationSettingsForm:
    def test_no_channels_selected(self):
        result = forms.notification_settings_form()
        assert result["channels"] == []
        assert result["settings"] == {}

    def test_telegram_channel(self):
        _ST.values["notification_channels"] = ["Telegram"]
        _ST.values["notification_telegram_token"] = "tok123"
        result = forms.notification_settings_form()
        assert result["channels"] == ["Telegram"]
        assert result["settings"]["telegram_token"] == "tok123"


class TestSkillAssessmentForm:
    def test_parses_skills_per_line(self):
        _ST.values["skill_skills"] = "python\njavascript\n\nreact"
        result = forms.skill_assessment_form()
        assert result["skills"] == ["python", "javascript", "react"]
        assert result["target_role"] == ""


# ---------------------------------------------------------------------------
# charts.py
# ---------------------------------------------------------------------------
class TestJobTypePieChart:
    def test_empty_data_returns_empty_figure(self):
        fig = charts.create_job_type_pie_chart([])
        assert fig.data == []

    def test_labels_and_values(self):
        fig = charts.create_job_type_pie_chart(
            [{"type": "full_time", "count": 5}, {"type": "remote", "count": 3}],
        )
        assert len(fig.data) == 1
        trace = fig.data[0]
        assert trace.labels == ["full_time", "remote"]
        assert trace.values == [5, 3]
        assert trace.hole == 0.4


class TestApplicationStatusBar:
    def test_empty_data_returns_empty_figure(self):
        fig = charts.create_application_status_bar({})
        assert fig.data == []

    def test_statuses_and_counts(self):
        fig = charts.create_application_status_bar({"saved": 2, "applied": 1})
        assert len(fig.data) == 1
        trace = fig.data[0]
        assert trace.x == ["saved", "applied"]
        assert trace.y == [2, 1]


class TestApplicationTimeline:
    def test_empty_data_returns_empty_figure(self):
        fig = charts.create_application_timeline([])
        assert fig.data == []

    def test_line_chart_built(self):
        fig = charts.create_application_timeline(
            [{"date": "2026-08-01", "count": 1, "status": "applied"}],
        )
        assert isinstance(fig, FakeFigure)
        assert fig.layout["height"] == 350


class TestTopCompaniesBar:
    def test_empty_data_returns_empty_figure(self):
        fig = charts.create_top_companies_bar([])
        assert fig.data == []

    def test_companies_and_counts(self):
        fig = charts.create_top_companies_bar(
            [{"company": "Acme", "jobs": 4}, {"company": "Globex", "jobs": 2}],
        )
        trace = fig.data[0]
        assert trace.y == ["Acme", "Globex"]
        assert trace.x == [4, 2]


class TestSalaryDistribution:
    def test_no_salary_data_no_traces(self):
        fig = charts.create_salary_distribution({})
        assert fig.data == []
        assert fig.layout["barmode"] == "stack"

    def test_full_salary_data_builds_stack(self):
        fig = charts.create_salary_distribution(
            {"min_salary": 50, "max_salary": 200, "avg_min": 60, "avg_max": 120},
        )
        assert len(fig.data) == 3
        assert fig.layout["barmode"] == "stack"


class TestSkillDemandChart:
    def test_empty_data_returns_empty_figure(self):
        fig = charts.create_skill_demand_chart([])
        assert fig.data == []

    def test_top_10_skills(self):
        data = [{"skill": f"skill_{i}", "demand": i} for i in range(15)]
        fig = charts.create_skill_demand_chart(data)
        trace = fig.data[0]
        assert len(trace.x) == 10
        assert "skill_14" not in trace.x
