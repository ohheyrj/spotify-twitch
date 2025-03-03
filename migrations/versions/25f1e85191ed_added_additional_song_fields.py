"""Added additional song fields

Revision ID: 25f1e85191ed
Revises: 
Create Date: 2025-03-02 12:01:55.766279

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '25f1e85191ed'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('user_tokens', schema=None) as batch_op:
        batch_op.add_column(sa.Column('current_playing_song_title', sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column('current_playing_song_artist', sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column('current_playing_song_uri', sa.String(length=255), nullable=True))

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('user_tokens', schema=None) as batch_op:
        batch_op.drop_column('current_playing_song_uri')
        batch_op.drop_column('current_playing_song_artist')
        batch_op.drop_column('current_playing_song_title')

    # ### end Alembic commands ###
