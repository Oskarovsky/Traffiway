"""empty message

Revision ID: c060a4bbaba0
Revises: 54b3f88f24dc
Create Date: 2020-01-08 21:47:03.759746

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c060a4bbaba0'
down_revision = '54b3f88f24dc'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('dangers',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('place', sa.String(length=64), nullable=True),
    sa.Column('position', sa.String(length=64), nullable=True),
    sa.Column('timestamp', sa.DateTime(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_dangers_timestamp'), 'dangers', ['timestamp'], unique=False)
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index(op.f('ix_dangers_timestamp'), table_name='dangers')
    op.drop_table('dangers')
    # ### end Alembic commands ###
