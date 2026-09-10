"""Database configuration helper."""
import os
def database_url():
    url=os.getenv('DATABASE_URL')
    if not url: raise RuntimeError('DATABASE_URL is not configured')
    return url
