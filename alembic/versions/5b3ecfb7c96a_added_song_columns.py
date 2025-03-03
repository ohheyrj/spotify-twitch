"""Added song columns

Revision ID: 5b3ecfb7c96a
Revises: f281fd479e3b
Create Date: 2025-03-01 21:07:31.190586

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision: str = '5b3ecfb7c96a'
down_revision: Union[str, None] = 'f281fd479e3b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index('twitch_user_id', table_name='user_tokens')
    op.drop_index('user_id', table_name='user_tokens')
    op.drop_index('user_uri', table_name='user_tokens')
    op.drop_table('user_tokens')
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('user_tokens',
    sa.Column('id', mysql.INTEGER(), autoincrement=True, nullable=False),
    sa.Column('user_id', mysql.VARCHAR(length=255), nullable=True),
    sa.Column('user_uri', mysql.VARCHAR(length=255), nullable=True),
    sa.Column('twitch_user_id', mysql.VARCHAR(length=255), nullable=True),
    sa.Column('spotify_access_token', sa.BLOB(), nullable=True),
    sa.Column('spotify_refresh_token', sa.BLOB(), nullable=True),
    sa.Column('spotify_token_expiration', mysql.DATETIME(), nullable=True),
    sa.Column('twitch_access_token', sa.BLOB(), nullable=True),
    sa.Column('twitch_refresh_token', sa.BLOB(), nullable=True),
    sa.Column('twitch_token_expiration', mysql.DATETIME(), nullable=True),
    sa.PrimaryKeyConstraint('id'),
    mysql_collate='utf8mb4_0900_ai_ci',
    mysql_default_charset='utf8mb4',
    mysql_engine='InnoDB'
    )
    op.create_index('user_uri', 'user_tokens', ['user_uri'], unique=True)
    op.create_index('user_id', 'user_tokens', ['user_id'], unique=True)
    op.create_index('twitch_user_id', 'user_tokens', ['twitch_user_id'], unique=True)
    # ### end Alembic commands ###
