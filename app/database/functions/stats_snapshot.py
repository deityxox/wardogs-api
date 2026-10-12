from sqlalchemy import insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.wardogs_models import PlayerStats, RoleStats
from app.database.dto import StatsSnapshot, WardogAccount, DiscordUser
from app.database.functions import unlocks


async def get(
    session: AsyncSession,
    account_id: int | None,
    steam_id: int | None,
    discord_id: int | None,
    limit: int = 100,
) -> list[PlayerStats]:
    stmt = select(StatsSnapshot)
    if account_id is not None:
        stmt = stmt.filter(StatsSnapshot.account_id == account_id)
    elif steam_id is not None:
        stmt = stmt.filter(
            StatsSnapshot.account.has(WardogAccount.steam_id == str(steam_id))
        )
    elif discord_id is not None:
        stmt = stmt.filter(
            StatsSnapshot.account.has(
                WardogAccount.discord_users.any(DiscordUser.discord_id == discord_id)
            )
        )
    stmt = stmt.order_by(StatsSnapshot.id.desc()).limit(limit)
    res = (await session.execute(stmt)).scalars().all()

    return [
        PlayerStats(
            player_data_version=item.player_data_version,
            infantry=RoleStats(item.infantry_level, item.infantry_xp),
            medic=RoleStats(item.medic_level, item.medic_xp),
            recon=RoleStats(item.recon_level, item.recon_xp),
            support=RoleStats(item.support_level, item.support_xp),
            driver=RoleStats(item.driver_level, item.driver_xp),
            pilot=RoleStats(item.pilot_level, item.pilot_xp),
            cash=item.cash,
            gold=item.gold,
            created_at=item.created_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
        )
        for item in res
    ]


async def get_latest(
    session: AsyncSession,
    account_id: int | None,
    steam_id: int | None,
    discord_id: int | None,
) -> PlayerStats | None:
    stmt = select(StatsSnapshot)
    if account_id is not None:
        stmt = stmt.filter(StatsSnapshot.account_id == account_id)
    elif steam_id is not None:
        stmt = stmt.filter(
            StatsSnapshot.account.has(WardogAccount.steam_id == str(steam_id))
        )
    elif discord_id is not None:
        stmt = stmt.filter(
            StatsSnapshot.account.has(
                WardogAccount.discord_users.any(DiscordUser.discord_id == discord_id)
            )
        )
    stmt = stmt.order_by(StatsSnapshot.id.desc()).limit(1)
    result = await session.execute(stmt)
    res = result.scalar_one_or_none()
    if res is None:
        return None

    cur_unlocks = await unlocks.get(session, res.account_id)

    return PlayerStats(
        player_data_version=res.player_data_version,
        infantry=RoleStats(res.infantry_level, res.infantry_xp),
        medic=RoleStats(res.medic_level, res.medic_xp),
        recon=RoleStats(res.recon_level, res.recon_xp),
        support=RoleStats(res.support_level, res.support_xp),
        driver=RoleStats(res.driver_level, res.driver_xp),
        pilot=RoleStats(res.pilot_level, res.pilot_xp),
        cash=res.cash,
        gold=res.gold,
        unlocks=cur_unlocks,
        created_at=res.created_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
    )


async def create(
    session: AsyncSession,
    account_id: int,
    stats: PlayerStats,
):
    channel = {
        "account_id": account_id,
        "player_data_version": stats.player_data_version,
        "wardog_level": stats.wardog_level,
        "infantry_level": stats.infantry.level,
        "infantry_xp": stats.infantry.xp,
        "medic_level": stats.medic.level,
        "medic_xp": stats.medic.xp,
        "recon_level": stats.recon.level,
        "recon_xp": stats.recon.xp,
        "support_level": stats.support.level,
        "support_xp": stats.support.xp,
        "driver_level": stats.driver.level,
        "driver_xp": stats.driver.xp,
        "pilot_level": stats.pilot.level,
        "pilot_xp": stats.pilot.xp,
        "cash": stats.cash,
        "gold": stats.gold,
    }
    stmt = insert(StatsSnapshot).values(channel).returning(StatsSnapshot)
    result = await session.execute(stmt)
    await session.commit()

    for unlock in stats.unlocks:
        await unlocks.upsert(session, account_id, unlock)

    return result.scalar_one()
