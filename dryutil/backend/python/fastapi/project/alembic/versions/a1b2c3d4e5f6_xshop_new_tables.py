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
    op.create_table(
        'xshop_seller_refresh_token',
        sa.Column('id',         UUID(as_uuid=True), primary_key=True),
        sa.Column('seller_id',  UUID(as_uuid=True), sa.ForeignKey('xshop_seller.id', ondelete='CASCADE'), nullable=False, unique=True),
        sa.Column('token_hash', sa.String(),         nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('is_revoked', sa.Boolean(),        nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_xshop_seller_refresh_token_seller_id', 'xshop_seller_refresh_token', ['seller_id'])

    op.create_table(
        'xshop_published_post',
        sa.Column('id',             UUID(as_uuid=True), primary_key=True),
        sa.Column('seller_id',      UUID(as_uuid=True), sa.ForeignKey('xshop_seller.id',      ondelete='CASCADE'),  nullable=False),
        sa.Column('product_id',     UUID(as_uuid=True), sa.ForeignKey('xshop_product.id',     ondelete='CASCADE'),  nullable=False),
        sa.Column('publish_job_id', UUID(as_uuid=True), sa.ForeignKey('xshop_publish_job.id', ondelete='SET NULL'), nullable=True),
        sa.Column('x_post_id',      sa.String(),         nullable=False),
        sa.Column('tweet_text',     sa.Text(),           nullable=True),
        sa.Column('published_at',   sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at',     sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_xshop_published_post_seller_id',  'xshop_published_post', ['seller_id'])
    op.create_index('ix_xshop_published_post_product_id', 'xshop_published_post', ['product_id'])
    op.create_index('ix_xshop_published_post_x_post_id',  'xshop_published_post', ['x_post_id'])

    op.create_table(
        'xshop_scheduler_job',
        sa.Column('id',          UUID(as_uuid=True), primary_key=True),
        sa.Column('job_name',    sa.String(),         nullable=False),
        sa.Column('status',      sa.String(),         nullable=False, server_default='running'),
        sa.Column('started_at',  sa.DateTime(timezone=True), nullable=False),
        sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('error_msg',   sa.Text(),           nullable=True),
        sa.Column('meta',        sa.JSON(),           nullable=True),
        sa.Column('created_at',  sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_xshop_scheduler_job_job_name', 'xshop_scheduler_job', ['job_name'])


def downgrade() -> None:
    op.drop_table('xshop_scheduler_job')
    op.drop_table('xshop_published_post')
    op.drop_table('xshop_seller_refresh_token')
