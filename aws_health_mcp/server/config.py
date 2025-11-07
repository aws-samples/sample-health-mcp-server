"""Configuration management for AWS Health MCP Server."""

import os
from pathlib import Path
from typing import Optional


class Config:
    """Configuration settings for the MCP server."""
    
    # AWS Configuration
    AWS_REGION: str = os.getenv("AWS_REGION", "us-east-1")
    AWS_PROFILE: Optional[str] = os.getenv("AWS_PROFILE")
    
    # Logging Configuration
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_FORMAT: str = os.getenv(
        "LOG_FORMAT", 
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    # Health API Configuration
    HEALTH_API_TIMEOUT: int = int(os.getenv("HEALTH_API_TIMEOUT", "30"))
    MAX_EVENTS_PER_REQUEST: int = int(os.getenv("MAX_EVENTS_PER_REQUEST", "100"))
    
    # Cache Configuration
    CACHE_TTL: int = int(os.getenv("CACHE_TTL", "300"))  # 5 minutes
    ENABLE_CACHE: bool = os.getenv("ENABLE_CACHE", "true").lower() == "true"
    
    # Server Configuration
    SERVER_NAME: str = os.getenv("SERVER_NAME", "aws-health")
    SERVER_VERSION: str = "1.0.0"
    
    @classmethod
    def get_config_dir(cls) -> Path:
        """Get configuration directory."""
        config_dir = Path.home() / ".aws-health-mcp"
        config_dir.mkdir(exist_ok=True)
        return config_dir
    
    @classmethod
    def validate(cls) -> bool:
        """Validate configuration."""
        try:
            # Validate timeout values
            if cls.HEALTH_API_TIMEOUT <= 0:
                raise ValueError("HEALTH_API_TIMEOUT must be positive")
            
            if cls.MAX_EVENTS_PER_REQUEST <= 0:
                raise ValueError("MAX_EVENTS_PER_REQUEST must be positive")
                
            if cls.CACHE_TTL < 0:
                raise ValueError("CACHE_TTL must be non-negative")
                
            return True
        except ValueError as e:
            import logging
            logging.getLogger(__name__).error(f"Configuration validation failed: {e}")
            return False
