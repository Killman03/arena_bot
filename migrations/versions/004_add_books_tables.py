"""Add books tables

Revision ID: 004
Revises: 003
Create Date: 2024-01-01 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '004'
down_revision = '003'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create book_status enum
    book_status = postgresql.ENUM('want_to_read', 'reading', 'completed', 'abandoned', name='bookstatus')
    book_status.create(op.get_bind())
    
    # Create book table
    op.create_table('book',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(length=256), nullable=False),
        sa.Column('author', sa.String(length=256), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('status', sa.Enum('want_to_read', 'reading', 'completed', 'abandoned', name='bookstatus'), nullable=False),
        sa.Column('start_date', sa.Date(), nullable=True),
        sa.Column('finish_date', sa.Date(), nullable=True),
        sa.Column('current_page', sa.Integer(), nullable=True),
        sa.Column('total_pages', sa.Integer(), nullable=True),
        sa.Column('genre', sa.String(length=100), nullable=True),
        sa.Column('rating', sa.Integer(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['user.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_book_status'), 'book', ['status'], unique=False)
    op.create_index(op.f('ix_book_user_id'), 'book', ['user_id'], unique=False)
    
    # Create book_quote table
    op.create_table('book_quote',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('book_id', sa.Integer(), nullable=False),
        sa.Column('quote_text', sa.Text(), nullable=False),
        sa.Column('page_number', sa.Integer(), nullable=True),
        sa.Column('context', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['book_id'], ['book.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_book_quote_book_id'), 'book_quote', ['book_id'], unique=False)
    
    # Create book_thought table
    op.create_table('book_thought',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('book_id', sa.Integer(), nullable=False),
        sa.Column('thought_text', sa.Text(), nullable=False),
        sa.Column('thought_type', sa.String(length=50), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['book_id'], ['book.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_book_thought_book_id'), 'book_thought', ['book_id'], unique=False)


def downgrade() -> None:
    # Drop tables
    op.drop_index(op.f('ix_book_thought_book_id'), table_name='book_thought')
    op.drop_table('book_thought')
    
    op.drop_index(op.f('ix_book_quote_book_id'), table_name='book_quote')
    op.drop_table('book_quote')
    
    op.drop_index(op.f('ix_book_user_id'), table_name='book')
    op.drop_index(op.f('ix_book_status'), table_name='book')
    op.drop_table('book')
    
    # Drop enum
    book_status = postgresql.ENUM('want_to_read', 'reading', 'completed', 'abandoned', name='bookstatus')
    book_status.drop(op.get_bind())
