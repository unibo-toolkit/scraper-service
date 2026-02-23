from typing import Dict

from pydantic import BaseModel, Field


class HealthStatus(BaseModel):
    """Health check status"""

    status: str = Field(..., description="Overall status (healthy/unhealthy)")
    version: str = Field(..., description="Service version")
    database: str = Field(..., description="Database connection status")
    redis: str = Field(..., description="Redis connection status")
    details: Dict[str, str] = Field(default_factory=dict, description="Additional details")
