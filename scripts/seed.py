import asyncio
from app.database.init_db import init_db
from app.database.session import AsyncSessionLocal
from app.models.strategy import Strategy

async def main() -> None:
    await init_db()
    async with AsyncSessionLocal() as db:
        for name, display in [("weather", "Weather Trading"), ("sports", "Sports Trading"), ("arbitrage", "Arbitrage Research"), ("wallet_intelligence", "Wallet Intelligence"), ("market_making", "Market Making Research"), ("latency_monitor", "Latency & Price Monitor")]:
            db.add(Strategy(name=name, display_name=display))
        await db.commit()

if __name__ == "__main__":
    asyncio.run(main())
