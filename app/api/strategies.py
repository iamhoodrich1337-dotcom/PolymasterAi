from fastapi import APIRouter

router = APIRouter(prefix="/strategies", tags=["strategies"])

@router.get("")
async def list_strategies() -> list[dict]:
    return [{"name": "weather", "display_name": "Weather Trading", "enabled": True}, {"name": "sports", "display_name": "Sports Trading", "enabled": True}, {"name": "arbitrage", "display_name": "Arbitrage Research", "enabled": True}, {"name": "wallet_intelligence", "display_name": "Wallet Intelligence", "enabled": True}, {"name": "market_making", "display_name": "Market Making Research", "enabled": True}, {"name": "latency_monitor", "display_name": "Latency Monitor", "enabled": True}]
