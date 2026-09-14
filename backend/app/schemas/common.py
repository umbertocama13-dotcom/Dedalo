from pydantic import BaseModel


class MessageResponse(BaseModel):
    """Plain confirmation message, used by endpoints with nothing else to return (e.g. deletes)."""

    message: str
