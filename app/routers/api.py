from fastapi import APIRouter

router = APIRouter()


@router.get("/")
async def api_root():
    """API root endpoint."""
    return {"message": "API v1"}


# Add your routes here
# @router.get("/items")
# async def get_items():
#     return {"items": []}