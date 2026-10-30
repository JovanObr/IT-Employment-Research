import pandas as pd
import plotly.graph_objects as go

from analysis import viz_theme as vt


def test_topic_colors_are_ten_distinct_values():
    assert len(vt.TOPIC_COLORS) == 10 and len(set(vt.TOPIC_COLORS)) == 10


def test_base_layout_sets_title_decimal_comma_and_no_fixed_width():
    fig = go.Figure().update_layout(**vt.base_layout("Naslov"))
    assert fig.layout.title.text == "Naslov" and fig.layout.separators == ",." and fig.layout.width is None
    assert go.Figure().update_layout(**vt.base_layout()).layout.title.text is None


def test_base_layout_extra_arguments_override_defaults():
    assert vt.base_layout(height=300, template="simple_white")["template"] == "simple_white"
    assert vt.base_layout(height=300)["height"] == 300


def test_event_lines_work_on_a_date_axis_and_select_by_key():
    fig = go.Figure(go.Scatter(x=pd.date_range("2021-01-01", periods=30, freq="MS"), y=list(range(30))))
    vt.add_event_lines(fig)                                        # default: fed + chatgpt
    assert len(fig.layout.shapes) == 2 and len(fig.layout.annotations) == 2
    assert {s.x0 for s in fig.layout.shapes} == {"2022-03-16", "2022-11-30"}
    vt.add_event_lines(fig, keys=("covid",))
    assert len(fig.layout.shapes) == 3 and fig.layout.annotations[-1].text == "začetek pandemije"


def test_event_lines_can_target_a_subplot_axis():
    fig = go.Figure()
    vt.add_event_lines(fig, keys=("fed",), xref="x2")
    assert fig.layout.shapes[0].xref == "x2" and fig.layout.annotations[0].xref == "x2"


def test_save_html_writes_a_standalone_file(tmp_path):
    fig = go.Figure(go.Scatter(x=[1, 2], y=[3, 4])).update_layout(**vt.base_layout("Preizkus"))
    p = vt.save_html(fig, "preizkus", outdir=tmp_path / "nova_mapa")
    assert p.exists() and p.suffix == ".html" and "Preizkus" in p.read_text(encoding="utf-8")


def test_slovenian_number_formatting():
    assert vt.sl_num(15.43) == "15,4" and vt.sl_num(12345.6) == "12.345,6" and vt.sl_num(3, 0) == "3"
    assert vt.sl_pct(0.154) == "15 %" and vt.sl_pct(0.0541, 1) == "5,4 %"
