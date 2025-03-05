"""Changed profile picture url to text

Revision ID: a0720168a314
Revises: 8f465a7fd63f
Create Date: 2025-03-05 00:54:23.814290

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = 'a0720168a314'
down_revision = '8f465a7fd63f'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.alter_column('spotify_display_picture',
               existing_type=mysql.VARCHAR(length=255),
               type_=sa.Text(),
               existing_nullable=True)
        batch_op.alter_column('twitch_display_picture',
               existing_type=mysql.VARCHAR(length=255),
               type_=sa.Text(),
               existing_nullable=True)

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.alter_column('twitch_display_picture',
               existing_type=sa.Text(),
               type_=mysql.VARCHAR(length=255),
               existing_nullable=True)
        batch_op.alter_column('spotify_display_picture',
               existing_type=sa.Text(),
               type_=mysql.VARCHAR(length=255),
               existing_nullable=True)

    # ### end Alembic commands ###
