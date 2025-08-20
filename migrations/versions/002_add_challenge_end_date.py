"""Add end_date field to challenge table

Revision ID: 002
Revises: 001
Create Date: 2024-01-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '002'
down_revision = '001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Добавляем поле end_date в таблицу challenge
    op.add_column('challenge', sa.Column('end_date', sa.Date(), nullable=True))


def downgrade() -> None:
    # Удаляем поле end_date из таблицы challenge
    op.drop_column('challenge', 'end_date')
