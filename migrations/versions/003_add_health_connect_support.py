"""Add Health Connect support

Revision ID: 003
Revises: 002
Create Date: 2024-01-01 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '003'
down_revision = '002'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add Health Connect support to existing tables."""
    
    # Добавляем поддержку health_connect в существующую таблицу google_fit_token
    # Это делается через изменение существующих записей, так как таблица уже существует
    
    # Обновляем существующие записи google_fit, чтобы они могли работать с Health Connect
    # Health Connect использует те же OAuth токены, что и Google Fit
    
    # Добавляем комментарий к таблице для документации
    op.execute("""
        COMMENT ON TABLE google_fit_token IS 
        'Google OAuth tokens for users (Google Fit, Google Drive, or Health Connect)'
    """)
    
    # Добавляем комментарий к колонке integration_type
    op.execute("""
        COMMENT ON COLUMN google_fit_token.integration_type IS 
        'Type of integration: google_fit, google_drive, or health_connect'
    """)


def downgrade() -> None:
    """Remove Health Connect support."""
    
    # Удаляем комментарии
    op.execute("COMMENT ON TABLE google_fit_token IS NULL")
    op.execute("COMMENT ON COLUMN google_fit_token.integration_type IS NULL")
    
    # Примечание: мы не удаляем данные, так как Health Connect использует
    # те же OAuth токены, что и Google Fit, и может быть полезен для
    # пользователей с Android 14+
