"""xshop_new_tables

Revision ID: a1b2c3d4e5f6
Revises: 752055ded2e2
Create Date: 2026-06-20 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '752055ded2e2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # All tables are created via SQLAlchemy models
    # This migration creates only the indexes for tables created in previous migrations
    op.create_index('ix_xshop_seller_refresh_token_seller_id', 'xshop_seller_refresh_token', ['seller_id'], if_not_exists=True)
    op.create_index('ix_xshop_published_post_seller_id',  'xshop_published_post', ['seller_id'], if_not_exists=True)
    op.create_index('ix_xshop_published_post_product_id', 'xshop_published_post', ['product_id'], if_not_exists=True)
    op.create_index('ix_xshop_published_post_x_post_id',  'xshop_published_post', ['x_post_id'], if_not_exists=True)
    op.create_index('ix_xshop_scheduler_job_job_name', 'xshop_scheduler_job', ['job_name'], if_not_exists=True)


def downgrade() -> None:
    op.drop_index('ix_xshop_scheduler_job_job_name', if_exists=True)
    op.drop_index('ix_xshop_published_post_x_post_id', if_exists=True)
    op.drop_index('ix_xshop_published_post_product_id', if_exists=True)
    op.drop_index('ix_xshop_published_post_seller_id', if_exists=True)
    op.drop_index('ix_xshop_seller_refresh_token_seller_id', if_exists=True)
