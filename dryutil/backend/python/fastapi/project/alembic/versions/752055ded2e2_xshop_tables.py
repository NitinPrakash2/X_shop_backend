"""xshop_tables

Revision ID: 752055ded2e2
Revises: 
Create Date: 2026-06-19 11:20:48.513004

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '752055ded2e2'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE INDEX IF NOT EXISTS ix_xshop_analytics_event_seller_id ON xshop_analytics_event (seller_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_xshop_order_seller_id ON xshop_order (seller_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_xshop_product_external_product_id ON xshop_product (external_product_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_xshop_product_seller_id ON xshop_product (seller_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_xshop_product_sync_log_seller_id ON xshop_product_sync_log (seller_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_xshop_publish_job_product_id ON xshop_publish_job (product_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_xshop_publish_job_seller_id ON xshop_publish_job (seller_id)")
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS ix_xshop_seller_email ON xshop_seller (email)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_xshop_x_account_x_user_id ON xshop_x_account (x_user_id)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_xshop_analytics_event_seller_id")
    op.execute("DROP INDEX IF EXISTS ix_xshop_order_seller_id")
    op.execute("DROP INDEX IF EXISTS ix_xshop_product_external_product_id")
    op.execute("DROP INDEX IF EXISTS ix_xshop_product_seller_id")
    op.execute("DROP INDEX IF EXISTS ix_xshop_product_sync_log_seller_id")
    op.execute("DROP INDEX IF EXISTS ix_xshop_publish_job_product_id")
    op.execute("DROP INDEX IF EXISTS ix_xshop_publish_job_seller_id")
    op.execute("DROP INDEX IF EXISTS ix_xshop_seller_email")
    op.execute("DROP INDEX IF EXISTS ix_xshop_x_account_x_user_id")
