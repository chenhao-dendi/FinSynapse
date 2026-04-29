from __future__ import annotations

import json
import shutil
from pathlib import Path
from types import SimpleNamespace

import markdown as _md
import pandas as pd
from jinja2 import Environment, FileSystemLoader, select_autoescape
from markupsafe import Markup
from plotly.utils import PlotlyJSONEncoder

from finsynapse.dashboard import charts
from finsynapse.dashboard.data import MARKETS, DashboardData, load
from finsynapse.dashboard.i18n import DEFAULT_LANG, SUPPORTED, TRANSLATIONS, t, translate_div
from finsynapse.report.brief import BriefMeta, list_briefs, load_latest_narrative


def _fig_to_json(fig) -> str:
    return json.dumps(fig.to_dict(), cls=PlotlyJSONEncoder)


def _i18n_namespace(lang: str) -> SimpleNamespace:
    """Pre-resolve every translation key for the template (`tx.foo` access)."""
    return SimpleNamespace(**{k: t(k, lang) for k in TRANSLATIONS})


def _render_one(env: Environment, data: DashboardData, lang: str, alt_href: str, archive_href: str) -> str:
    latest = data.latest_per_market()
    history_market = next(iter(latest), MARKETS[0])

    gauges, radars, attribs, data_quality = {}, {}, {}, {}
    for market, row in latest.items():
        gauges[market] = _fig_to_json(charts.gauge(market, row["overall"], row.get("overall_change_1w"), lang))
        radars[market] = _fig_to_json(
            charts.radar(
                market,
                {
                    "valuation": row.get("valuation"),
                    "sentiment": row.get("sentiment"),
                    "liquidity": row.get("liquidity"),
                },
                lang,
            )
        )
        attribs[market] = _fig_to_json(charts.attribution_bars(row, lang))
        data_quality[market] = row.get("data_quality", "ok")

    time_series_json = _fig_to_json(charts.time_series(data.temperature, history_market, lang))
    divergence_json = _fig_to_json(charts.divergence_recent(data.divergence, lang=lang))

    cross_market_input = {
        market: {
            "valuation": row.get("valuation"),
            "sentiment": row.get("sentiment"),
            "liquidity": row.get("liquidity"),
        }
        for market, row in latest.items()
    }
    cross_market_json = _fig_to_json(charts.cross_market_radar(cross_market_input, lang))

    # Latest LLM-narrated brief, if any. Same brief.md is used for both lang
    # variants — the LLM-written paragraph is bilingual-friendly Chinese; we
    # don't auto-translate to keep the source of truth single (matches
    # README / config policy of avoiding translation drift).
    narrative_md, narrative_asof = load_latest_narrative()
    narrative_html = Markup(_md.markdown(narrative_md, extensions=["extra"])) if narrative_md else ""

    div_table = []
    if not data.divergence.empty:
        df = data.divergence[data.divergence["is_divergent"]].copy()
        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values("date", ascending=False).head(10)
        df["description"] = df["description"].map(lambda d: translate_div(d, lang))
        div_table = df.to_dict(orient="records")

    health_summary, health_table = None, []
    if not data.health.empty:
        h = data.health.copy()
        health_summary = {
            "total": len(h),
            "fail": int((h["severity"] == "fail").sum()),
            "warn": int((h["severity"] == "warn").sum()),
        }
        health_table = h.sort_values("date", ascending=False).head(50).to_dict(orient="records")

    template = env.get_template("static.html.j2")
    return template.render(
        lang=lang,
        tx=_i18n_namespace(lang),
        alt_lang_href=alt_href,
        archive_href=archive_href,
        asof=data.asof().date().isoformat(),
        markets=MARKETS,
        gauges=gauges,
        radars=radars,
        attribs=attribs,
        data_quality=data_quality,
        history_market=history_market,
        time_series_json=time_series_json,
        cross_market_json=cross_market_json,
        divergence_json=divergence_json,
        narrative_html=narrative_html,
        narrative_asof=narrative_asof,
        divergence_table=div_table,
        health_summary=health_summary,
        health_table=health_table,
    )


# Filename convention:
#   zh dashboard  -> index.html (default landing), archive -> briefs.html
#   en dashboard  -> en.html,                       archive -> briefs.en.html
LANG_FILENAME = {"zh": "index.html", "en": "en.html"}
ARCHIVE_FILENAME = {"zh": "briefs.html", "en": "briefs.en.html"}


def _render_brief_pages(env: Environment, out_dir: Path, briefs: list[BriefMeta]) -> list[Path]:
    """For each brief on disk:
      1. copy raw .md to dist/brief/<date>.md (direct download / share URL)
      2. render dist/brief/<date>.html using the same site chrome

    Single-language only — brief content is Chinese, so chrome stays Chinese.
    English-speaking visitors arriving here from the EN archive still see
    the same content; the back-link is to the (zh) archive page.
    """
    if not briefs:
        return []
    brief_out = out_dir / "brief"
    brief_out.mkdir(parents=True, exist_ok=True)

    template = env.get_template("brief_single.html.j2")
    tx = _i18n_namespace(DEFAULT_LANG)
    written: list[Path] = []

    for b in briefs:
        # 1. raw md copy
        md_dest = brief_out / f"{b.asof}.md"
        shutil.copyfile(b.path, md_dest)
        written.append(md_dest)

        # 2. rendered html
        body_md = b.path.read_text(encoding="utf-8")
        body_html = Markup(_md.markdown(body_md, extensions=["extra"]))
        html = template.render(tx=tx, asof=b.asof, body_html=body_html)
        html_dest = brief_out / f"{b.asof}.html"
        html_dest.write_text(html, encoding="utf-8")
        written.append(html_dest)

    return written


def _render_archive_index(env: Environment, out_dir: Path, briefs: list[BriefMeta]) -> list[Path]:
    """Render the bilingual /briefs.html (and /briefs.en.html) index page
    listing every brief on disk, newest first."""
    template = env.get_template("brief_archive.html.j2")
    written: list[Path] = []

    for lang in SUPPORTED:
        alt_lang = next(other for other in SUPPORTED if other != lang)
        alt_href = ARCHIVE_FILENAME[alt_lang]
        # Back-to-dashboard target depends on which lang we're rendering.
        dashboard_href = LANG_FILENAME[lang]

        html = template.render(
            lang=lang,
            tx=_i18n_namespace(lang),
            briefs=briefs,
            alt_lang_href=alt_href,
            dashboard_href=dashboard_href,
        )
        target = out_dir / ARCHIVE_FILENAME[lang]
        target.write_text(html, encoding="utf-8")
        written.append(target)

    return written


def render(out_dir: Path | str = "dist", data: DashboardData | None = None) -> list[Path]:
    """Render every page that lands on GitHub Pages:
      - dashboard (zh + en)
      - per-brief HTML pages + raw .md copies
      - bilingual brief archive index

    Returns the full list of written paths."""
    data = data or load()
    if data.temperature.empty:
        raise RuntimeError("No silver data. Run `finsynapse transform run --layer all` first.")

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    env = Environment(
        loader=FileSystemLoader(Path(__file__).parent / "templates"),
        autoescape=select_autoescape(["html"]),
    )

    briefs = list_briefs()

    written: list[Path] = []
    for lang in SUPPORTED:
        # Other lang's file is the alternate href for the toggle in this lang's page.
        alt_lang = next(other for other in SUPPORTED if other != lang)
        alt_href = LANG_FILENAME[alt_lang]
        # Default lang lives at index.html; non-default at <lang>.html.
        if lang == DEFAULT_LANG:
            target = out_dir / "index.html"
            # Toggle link from default page must point to the alt-lang file
            alt_href = LANG_FILENAME[alt_lang]
        else:
            target = out_dir / LANG_FILENAME[lang]
            # Toggle link back to default goes to index.html (root), not zh.html
            alt_href = "index.html" if alt_lang == DEFAULT_LANG else LANG_FILENAME[alt_lang]

        archive_href = ARCHIVE_FILENAME[lang]
        html = _render_one(env, data, lang, alt_href, archive_href)
        target.write_text(html, encoding="utf-8")
        written.append(target)

    written.extend(_render_brief_pages(env, out_dir, briefs))
    written.extend(_render_archive_index(env, out_dir, briefs))
    return written
