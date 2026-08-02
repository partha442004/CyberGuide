"""
Unit tests for the CyberGuide Streamlit dashboard entry point
(``src/cybershield/dashboard/app.py``).

Streamlit and plotly are not required for the backend test suite, so this
module injects lightweight fakes into ``sys.modules`` before importing the
dashboard and exercises ``main()`` page routing plus every ``show_*`` page
renderer.
"""

import sys
import types

# ---------------------------------------------------------------------------
# Fake streamlit / plotly modules (persistent for this module's session)
# ---------------------------------------------------------------------------


class _FakeColumn:
    """Context-manager stand-in for ``st.columns`` / ``st.tabs`` entries."""

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class FakeStreamlit(types.ModuleType):
    """Configurable fake of the streamlit module surface used by the app."""

    def __init__(self):
        super().__init__("streamlit")
        self.calls: list[str] = []
        self.values: dict[str, object] = {}
        self.sidebar = _FakeColumn()

    def _record(self, name, *args, **kwargs):
        self.calls.append(name)

    def set_page_config(self, *args, **kwargs):
        self._record("set_page_config")

    def markdown(self, *args, **kwargs):
        self._record("markdown")

    def header(self, *args, **kwargs):
        self._record("header")

    def subheader(self, *args, **kwargs):
        self._record("subheader")

    def title(self, *args, **kwargs):
        self._record("title")

    def caption(self, *args, **kwargs):
        self._record("caption")

    def divider(self, *args, **kwargs):
        self._record("divider")

    def metric(self, *args, **kwargs):
        self._record("metric")

    def info(self, *args, **kwargs):
        self._record("info")

    def success(self, *args, **kwargs):
        self._record("success")

    def image(self, *args, **kwargs):
        self._record("image")

    def progress(self, *args, **kwargs):
        self._record("progress")

    def plotly_chart(self, *args, **kwargs):
        self._record("plotly_chart")

    def dataframe(self, *args, **kwargs):
        self._record("dataframe")

    def columns(self, spec):
        n = spec if isinstance(spec, int) else len(spec)
        return [_FakeColumn() for _ in range(n)]

    def tabs(self, labels):
        return [_FakeColumn() for _ in labels]

    def container(self, *args, **kwargs):
        return _FakeColumn()

    def expander(self, *args, **kwargs):
        return _FakeColumn()

    def radio(self, label=None, options=None, index=0, key=None, **kwargs):
        self._record("radio")
        key = key or label
        if key in self.values:
            return self.values[key]
        if options is None or index >= len(options):
            return None
        return options[index]

    def text_input(self, label=None, key=None, **kwargs):
        self._record("text_input")
        return self.values.get(key or label, "")

    def button(self, label=None, key=None, **kwargs):
        self._record("button")
        return self.values.get(key or label, False)

    def selectbox(self, label=None, options=None, index=0, key=None, **kwargs):
        self._record("selectbox")
        key = key or label
        if key in self.values:
            return self.values[key]
        if options is None or index >= len(options):
            return None
        return options[index]

    def multiselect(self, label=None, options=None, default=None, key=None, **kwargs):
        self._record("multiselect")
        return self.values.get(key or label, default if default is not None else [])

    def slider(self, label=None, min_value=0, max_value=10, value=None, key=None, **kwargs):
        self._record("slider")
        return self.values.get(key or label, value if value is not None else 0)

    def toggle(self, label=None, value=False, key=None, **kwargs):
        self._record("toggle")
        return self.values.get(key or label, value)

    def file_uploader(self, *args, **kwargs):
        self._record("file_uploader")
        return None

    def text_area(self, label=None, key=None, **kwargs):
        self._record("text_area")
        return self.values.get(key or label, "")


class FakeTrace:
    """Stand-in for plotly traces: stores constructor kwargs."""

    def __init__(self, **kwargs):
        for name, value in kwargs.items():
            setattr(self, name, value)


class FakeFigure:
    """Minimal ``go.Figure`` stand-in recording traces and layout."""

    def __init__(self, data=None):
        # plotly accepts either a single trace or an iterable of traces.
        if data is None:
            self.data: list = []
        elif isinstance(data, (list, tuple)):
            self.data = list(data)
        else:
            self.data = [data]
        self.layout: dict = {}

    def add_trace(self, trace):
        self.data.append(trace)
        return self

    def update_layout(self, **kwargs):
        self.layout.update(kwargs)
        return self


_ST = FakeStreamlit()
_GO = types.ModuleType("plotly.graph_objects")
_PX = types.ModuleType("plotly.express")
_PLOTLY = types.ModuleType("plotly")

# Assignments to module attributes are intentionally dynamic (fake modules).
_GO.Figure = FakeFigure  # type: ignore[attr-defined]
_GO.Scatter = FakeTrace  # type: ignore[attr-defined]
_GO.Bar = FakeTrace  # type: ignore[attr-defined]
_PX.pie = lambda *a, **k: FakeFigure()  # type: ignore[attr-defined]
_PLOTLY.graph_objects = _GO  # type: ignore[attr-defined]
_PLOTLY.express = _PX  # type: ignore[attr-defined]

sys.modules["streamlit"] = _ST
sys.modules["plotly"] = _PLOTLY
sys.modules["plotly.graph_objects"] = _GO
sys.modules["plotly.express"] = _PX

import cybershield.dashboard.app as dashboard_app  # noqa: E402, I001


# ---------------------------------------------------------------------------
# Page routing
# ---------------------------------------------------------------------------

PAGES = {
    "📊 Overview": "show_overview",
    "💼 Jobs": "show_jobs",
    "📋 Applications": "show_applications",
    "📈 Analytics": "show_analytics",
    "🎯 Skills": "show_skills",
    "🏆 CTF": "show_ctf",
    "💰 Bug Bounty": "show_bug_bounty",
    "📅 Events": "show_events",
    "📰 Cyber News": "show_cyber_news",
    "🎓 Learning": "show_learning",
    "📄 Resume": "show_resume",
    "🔔 Notifications": "show_notifications",
    "⚙️ Settings": "show_settings",
}


class TestMainRouting:
    def test_routes_each_page_to_its_renderer(self, monkeypatch):
        for page, renderer in PAGES.items():
            # The fake radio looks up by the label main() passes ("Navigate to:").
            _ST.values["Navigate to:"] = page
            spy_calls: list[str] = []

            # Bind loop state via defaults so closures don't capture the
            # changing loop variable (B023).
            def make_spy(name, calls):
                def spy(*args, **kwargs):
                    calls.append(name)

                return spy

            # Silence every renderer, then spy the target one for this page.
            for _other_page, other_renderer in PAGES.items():
                monkeypatch.setattr(
                    dashboard_app,
                    other_renderer,
                    make_spy(other_renderer, spy_calls),
                    raising=False,
                )
            monkeypatch.setattr(dashboard_app, renderer, make_spy(renderer, spy_calls))

            dashboard_app.main()
            assert spy_calls == [renderer], f"page {page} routed to {spy_calls}"

    def test_default_page_is_overview(self, monkeypatch):
        # radio returns first option (index=0) when no value set
        _ST.values.pop("Navigate to:", None)
        spy_calls: list[str] = []
        monkeypatch.setattr(dashboard_app, "show_overview", lambda: spy_calls.append("ov"))
        for renderer in set(PAGES.values()) - {"show_overview"}:
            monkeypatch.setattr(dashboard_app, renderer, lambda: None, raising=False)
        dashboard_app.main()
        assert "ov" in spy_calls


# ---------------------------------------------------------------------------
# Page renderers (smoke: each renders without raising, calls streamlit)
# ---------------------------------------------------------------------------


class TestPageRenderers:
    """Each page renderer runs without raising and calls streamlit."""


# Generate one smoke test per show_* renderer (dynamic parametrization).
for _func in PAGES.values():

    def _make_test(name):
        def test_impl(self):
            renderer = getattr(dashboard_app, name)
            _ST.calls.clear()
            renderer()
            assert len(_ST.calls) > 0, f"{name} should call streamlit"

        return test_impl

    setattr(TestPageRenderers, f"test_{_func}", _make_test(_func))


class TestDashboardModule:
    def test_module_has_all_renderers(self):
        for renderer in set(PAGES.values()):
            assert callable(getattr(dashboard_app, renderer, None))

    def test_main_is_callable(self):
        assert callable(dashboard_app.main)
