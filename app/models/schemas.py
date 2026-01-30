from pydantic import BaseModel


class HealthResponse(BaseModel):
    """Health check response."""
    status: str


class MessageResponse(BaseModel):
    """Generic message response."""
    message: str


# Add your models here
# class Item(BaseModel):
#     id: int
#     name: str
#     description: str | None = None