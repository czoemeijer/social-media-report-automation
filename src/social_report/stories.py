"""Story-series calculations with temporal comparability safeguards."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Mapping, Optional, Tuple, Union, cast

from .validation import merge_review_status

Number = Union[int, float]


def format_czech_float(value: float, decimals: int = 1) -> str:
    return f"{value:.{decimals}f}".replace(".", ",")


def _number(value: Any) -> Optional[Number]:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return cast(Number, value)


def _story_reach(story: Mapping[str, Any]) -> Optional[Number]:
    reach = _number(story.get("reach"))
    return reach if reach is not None else _number(story.get("viewers"))


def _parse_iso(timestamp: Any) -> Optional[datetime]:
    if not isinstance(timestamp, str) or not timestamp.strip():
        return None
    try:
        return datetime.fromisoformat(timestamp.strip())
    except (ValueError, TypeError):
        return None


def _diff_hours(captured_dt: datetime, published_dt: datetime) -> Optional[float]:
    captured_aware = (
        captured_dt.tzinfo is not None
        and captured_dt.tzinfo.utcoffset(captured_dt) is not None
    )
    published_aware = (
        published_dt.tzinfo is not None
        and published_dt.tzinfo.utcoffset(published_dt) is not None
    )
    if captured_aware != published_aware:
        return None
    try:
        return (captured_dt - published_dt).total_seconds() / 3600.0
    except (TypeError, ValueError):
        return None


def _age_hours(story: Mapping[str, Any]) -> Optional[Number]:
    explicit = _number(story.get("age_hours"))
    if explicit is not None:
        return explicit
    published_str = story.get("publication_time")
    captured_str = story.get("capture_time")
    if not isinstance(published_str, str) or not isinstance(captured_str, str):
        return None
    pub_dt = _parse_iso(published_str)
    cap_dt = _parse_iso(captured_str)
    if pub_dt is None or cap_dt is None:
        return None
    return _diff_hours(cap_dt, pub_dt)


def _temporally_comparable(stories: List[Mapping[str, Any]]) -> Tuple[bool, Optional[str]]:
    stages = [story.get("snapshot_stage") for story in stories]
    known_stages = [stage for stage in stages if stage is not None]
    if known_stages and (len(known_stages) != len(stages) or len(set(known_stages)) != 1):
        return False, "Story snapshots have incompatible or incomplete snapshot_stage values."

    collected_dts: List[datetime] = []
    for story in stories:
        pub_str = story.get("publication_time")
        cap_str = story.get("capture_time")
        if isinstance(pub_str, str) and pub_str.strip():
            dt = _parse_iso(pub_str)
            if dt is None:
                return False, "Story publication timestamp is invalid."
            collected_dts.append(dt)
        if isinstance(cap_str, str) and cap_str.strip():
            dt = _parse_iso(cap_str)
            if dt is None:
                return False, "Story capture timestamp is invalid."
            collected_dts.append(dt)
        if isinstance(pub_str, str) and isinstance(cap_str, str):
            p_dt = _parse_iso(pub_str)
            c_dt = _parse_iso(cap_str)
            if p_dt and c_dt and _diff_hours(c_dt, p_dt) is None:
                return (
                    False,
                    "Story capture and publication timestamps have mixed timezone awareness.",
                )

    if collected_dts:
        aware_flags = [
            dt.tzinfo is not None and dt.tzinfo.utcoffset(dt) is not None
            for dt in collected_dts
        ]
        if any(aware_flags) and not all(aware_flags):
            return (
                False,
                "Story snapshots contain mixed offset-aware and naive timestamps; "
                "temporal comparability cannot be established.",
            )

    ages = [_age_hours(story) for story in stories]
    known_ages = [age for age in ages if age is not None]
    if known_ages and (len(known_ages) != len(ages) or max(known_ages) - min(known_ages) > 1):
        return False, "Story snapshots were captured at materially different ages."
    return True, None


def _sum_metric(stories: List[Mapping[str, Any]], field: str) -> Tuple[Optional[Number], bool]:
    values = [_number(story.get(field)) for story in stories]
    present = [value for value in values if value is not None]
    return (sum(present) if present else None, len(present) == len(values))


def summarize_story_series(data: Mapping[str, Any]) -> Dict[str, Any]:
    stories_raw = data.get("stories", [])
    if not isinstance(stories_raw, list) or not stories_raw:
        raise ValueError("input must contain at least one Story in 'stories'")
    if not all(isinstance(story, Mapping) for story in stories_raw):
        raise ValueError("every Story must be an object")
    stories: List[Mapping[str, Any]] = stories_raw
    warnings: List[str] = []

    total_views, views_complete = _sum_metric(stories, "views")
    profile_visits, profile_complete = _sum_metric(stories, "profile_visits")
    total_interactions, interactions_complete = _sum_metric(stories, "interactions")
    if not views_complete:
        warnings.append("Some Story views are missing; total_views is a known-values lower bound.")
    if not profile_complete:
        warnings.append("Some profile visits are missing; absence was not converted to zero.")
    if not interactions_complete:
        warnings.append("Some interactions are missing; absence was not converted to zero.")

    first_reach = _story_reach(stories[0])
    last_reach = _story_reach(stories[-1])
    comparable, temporal_warning = _temporally_comparable(stories)
    if temporal_warning:
        warnings.append(temporal_warning)
    drop_off: Optional[float] = None
    if (
        len(stories) > 1
        and comparable
        and first_reach is not None
        and first_reach > 0
        and last_reach is not None
    ):
        candidate = ((first_reach - last_reach) / first_reach) * 100.0
        if candidate < 0:
            warnings.append(
                "Last Story reach exceeds first Story reach; drop-off is invalid and "
                "requires temporal review."
            )
        else:
            drop_off = round(candidate, 4)

    views_values = [_number(story.get("views")) for story in stories]
    interactions_values = [_number(story.get("interactions")) for story in stories]
    views_parts = ["?" if value is None else f"{value:g}" for value in views_values]
    interaction_parts = ["?" if value is None else f"{value:g}" for value in interactions_values]
    views_str = (
        "není k dispozici"
        if total_views is None
        else f"{total_views:g} ({' + '.join(views_parts)})"
        if len(stories) > 1
        else f"{total_views:g}"
    )
    interactions_str = (
        "není k dispozici"
        if total_interactions is None
        else f"{total_interactions:g} ({' + '.join(interaction_parts)})"
        if len(stories) > 1
        else f"{total_interactions:g}"
    )
    reach_str = (
        "není k dispozici"
        if first_reach is None
        else f"{first_reach:g} - maximální dosah na začátku série"
    )
    drop_off_str = (
        "nelze spolehlivě vypočítat" if drop_off is None else f"{format_czech_float(drop_off)} %"
    )
    poll_result = next(
        (
            story.get("poll_result") or story.get("quiz_result")
            for story in stories
            if story.get("poll_result") or story.get("quiz_result")
        ),
        data.get("poll_result")
        or data.get("quiz_result")
        or "Nerelevantní (série neobsahuje anketu ani kvíz)",
    )
    profile_visits_str = "není k dispozici" if profile_visits is None else f"{profile_visits:g}"
    markdown = "\n".join(
        [
            "Souhrnný výkon série",
            f"Zobrazení: {views_str}",
            f"Reach: {reach_str}",
            f"Návštěvy profilu: {profile_visits_str}",
            f"Interakce: {interactions_str}",
            f"Míra opuštění: {drop_off_str}",
            f"Výsledek ankety/kvízu: {poll_result}",
        ]
    )
    first_reach_approx = bool(
        stories[0].get("reach_is_approximate", False)
        or stories[0].get("viewers_is_approximate", False)
    )
    last_reach_approx = bool(
        stories[-1].get("reach_is_approximate", False)
        or stories[-1].get("viewers_is_approximate", False)
    )
    views_approx = any(
        bool(story.get("views_is_approximate", False))
        for story in stories
        if story.get("views") is not None
    )
    interactions_approx = any(
        bool(story.get("interactions_is_approximate", False))
        for story in stories
        if story.get("interactions") is not None
    )
    profile_visits_approx = any(
        bool(story.get("profile_visits_is_approximate", False))
        for story in stories
        if story.get("profile_visits") is not None
    )
    drop_off_approx = bool(
        (first_reach_approx or last_reach_approx) if drop_off is not None else False
    )

    initial_status = data.get("review_status", "verified")
    if warnings:
        result_status = merge_review_status(initial_status, "verified_with_warning")
    else:
        result_status = initial_status

    return {
        "story_count": len(stories),
        "total_views": total_views,
        "total_views_is_approximate": views_approx,
        "views_breakdown": views_str,
        "initial_reach": first_reach,
        "initial_reach_is_approximate": first_reach_approx,
        "reach_str": reach_str,
        "profile_visits": profile_visits,
        "profile_visits_is_approximate": profile_visits_approx,
        "total_interactions": total_interactions,
        "total_interactions_is_approximate": interactions_approx,
        "interactions_breakdown": interactions_str,
        "drop_off_rate_pct": drop_off,
        "drop_off_rate_is_approximate": drop_off_approx,
        "drop_off_rate_str": drop_off_str,
        "temporally_comparable": comparable,
        "poll_result": poll_result,
        "review_status": result_status,
        "warnings": warnings,
        "markdown": markdown,
    }
