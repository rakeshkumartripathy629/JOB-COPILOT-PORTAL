from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.analytics_agent import analytics_agent
from app.db.session import get_db
from app.dependencies import get_current_user

router = APIRouter()


@router.get("/me")
async def get_analytics(
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await analytics_agent.ainvoke(
        {
            "db": db,
            "user_id": current_user.id,
            "metrics": {},
            "insights": [],
        }
    )
    return {"metrics": result.get("metrics", {}), "insights": result.get("insights", [])}
