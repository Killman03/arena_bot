"""Add todo reminders and timezone support

Revision ID: 004
Revises: 
Create Date: 2025-01-27 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '004'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Добавляем поля для напоминаний в таблицу todos
    op.add_column('todos', sa.Column('reminder_time', sa.String(5), nullable=True))
    op.add_column('todos', sa.Column('is_reminder_active', sa.Boolean(), nullable=False, server_default='false'))
    
    # Добавляем индекс для timezone в таблице users (если поле уже существует)
    try:
        op.create_index('ix_user_timezone', 'users', ['timezone'])
    except Exception:
        # Индекс уже существует или поле не существует
        pass


def downgrade() -> None:
    # Удаляем поля для напоминаний
    try:
        op.drop_column('todos', 'is_reminder_active')
        op.drop_column('todos', 'reminder_time')
    except Exception:
        pass
    
    # Удаляем индекс timezone
    try:
        op.drop_index('ix_user_timezone', table_name='users')
    except Exception:
        pass
