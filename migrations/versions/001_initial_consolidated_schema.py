"""initial consolidated schema

Revision ID: 001_initial
Revises: 
Create Date: 2025-07-02 07:45:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '001_initial'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create wallets table
    op.create_table('wallets',
        sa.Column('address', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('address')
    )
    
    # Create transactions table with correct BigInteger types
    op.create_table('transactions',
        sa.Column('hash', sa.String(), nullable=False),
        sa.Column('asset', sa.String(), nullable=False),
        sa.Column('address_from', sa.String(), nullable=False),
        sa.Column('address_to', sa.String(), nullable=False),
        sa.Column('value', sa.BigInteger(), nullable=False),
        sa.Column('is_token', sa.Boolean(), nullable=False),
        sa.Column('type', sa.String(), nullable=False),
        sa.Column('status', sa.String(), nullable=False),
        sa.Column('effective_fee', sa.BigInteger(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.Column('contract_address', sa.String(), nullable=True),
        sa.PrimaryKeyConstraint('hash')
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('transactions')
    op.drop_table('wallets') 