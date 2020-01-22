"""empty message

Revision ID: d87b192daa53
Revises: 237bf78fe76d
Create Date: 2020-01-22 19:04:22.448658

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd87b192daa53'
down_revision = '237bf78fe76d'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_foreign_key(None, 'items', 'users', ['author_id'], ['id'])
    op.add_column('journeys', sa.Column('name', sa.String(length=64), nullable=True))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('journeys', 'name')
    op.drop_constraint(None, 'items', type_='foreignkey')
    # ### end Alembic commands ###
