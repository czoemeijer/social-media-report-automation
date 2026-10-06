"""Story-series calculations with temporal comparability safeguards."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Mapping, Optional, Tuple, Union, cast

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


def _age_hours(story: Mapping[str, Any]) -> Optional[Number]:
    explicit = _number(story.get("age_hours"))
    if explicit is not None:
        return explicit
    published = story.get("publication_time")
    captured = story.get("capture_time")
    if not isinstance(published, str) or not isinstance(captured, str):
        return None
    try:
        return (
            datetime.fromisoformat(captured) - datetime.fromisoformat(published)
        ).total_seconds() / 3600
    except ValueError:
        return None


def _temporally_comparable(stories: List[Mapping[str, Any]]) -> Tuple[bool, Optional[str]]:
    stages = [story.get("snapshot_stage") for story in stories]
    known_stages = [stage for stage in stages if stage is not None]
    if known_stages and (len(known_stages) != len(stages) or len(set(known_stages)) != 1):
        return False, "Story snapshots have incompatible or incomplete snapshot_stage values."
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
    return {
        "story_count": len(stories),
        "total_views": total_views,
        "views_breakdown": views_str,
        "initial_reach": first_reach,
        "reach_str": reach_str,
        "profile_visits": profile_visits,
        "total_interactions": total_interactions,
        "interactions_breakdown": interactions_str,
        "drop_off_rate_pct": drop_off,
        "drop_off_rate_str": drop_off_str,
        "temporally_comparable": comparable,
        "poll_result": poll_result,
        "review_status": "verified_with_warning" if warnings else "verified",
        "warnings": warnings,
        "markdown": markdown,
    }
