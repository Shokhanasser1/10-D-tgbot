from collections import defaultdict
from collections.abc import Iterable, Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.translation import Translation


async def translations_for(
    db: AsyncSession,
    entity_type: str,
    entity_ids: Sequence[int],
    fields: Iterable[str],
    locale: str,
    fallback_locale: str,
) -> dict[tuple[int, str], str]:
    """Batch-resolve translated field values for a set of entities of one type.

    Returns {(entity_id, field): value}, preferring `locale` and falling back
    to `fallback_locale` when a translation is missing for the requested locale.
    Avoids N+1 queries when resolving translations for a list of entities.
    """
    if not entity_ids:
        return {}

    locales = {locale, fallback_locale}
    stmt = select(Translation).where(
        Translation.entity_type == entity_type,
        Translation.entity_id.in_(entity_ids),
        Translation.field.in_(list(fields)),
        Translation.locale.in_(locales),
    )
    rows = (await db.execute(stmt)).scalars().all()

    by_entity_field: dict[tuple[int, str], dict[str, str]] = defaultdict(dict)
    for row in rows:
        by_entity_field[(row.entity_id, row.field)][row.locale] = row.value

    resolved: dict[tuple[int, str], str] = {}
    for key, locale_map in by_entity_field.items():
        value = locale_map.get(locale) or locale_map.get(fallback_locale)
        if value is not None:
            resolved[key] = value
    return resolved
