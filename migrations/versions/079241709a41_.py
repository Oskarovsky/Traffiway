"""empty message

Revision ID: 079241709a41
Revises: 99b200dd6db9
Create Date: 2020-01-02 19:10:18.378089

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '079241709a41'
down_revision = '99b200dd6db9'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('journeys',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('start_localization', sa.String(), nullable=True),
    sa.Column('start_time', sa.DateTime(), nullable=True),
    sa.Column('destination', sa.String(), nullable=True),
    sa.Column('author_id', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['author_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_journeys_start_time'), 'journeys', ['start_time'], unique=False)
    op.create_table('posts',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('body', sa.Text(), nullable=True),
    sa.Column('timestamp', sa.DateTime(), nullable=True),
    sa.Column('author_id', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['author_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_posts_timestamp'), 'posts', ['timestamp'], unique=False)
    op.create_table('items',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(), nullable=True),
    sa.Column('journey_id', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['journey_id'], ['journeys.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.drop_column('users', 'avatar_link')
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('users', sa.Column('avatar_link', sa.VARCHAR(length=64), nullable=True))
    op.drop_table('items')
    op.drop_index(op.f('ix_posts_timestamp'), table_name='posts')
    op.drop_table('posts')
    op.drop_index(op.f('ix_journeys_start_time'), table_name='journeys')
    op.drop_table('journeys')
    # ### end Alembic commands ###
