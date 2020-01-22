"""empty message

Revision ID: ae0b78e84baa
Revises: 2e77b0cc47b0
Create Date: 2020-01-22 19:16:30.523848

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'ae0b78e84baa'
down_revision = '2e77b0cc47b0'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_foreign_key(None, 'items', 'users', ['author_id'], ['id'])
    op.add_column('journeys', sa.Column('title', sa.String(length=64), nullable=True))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('journeys', 'title')
    op.drop_constraint(None, 'items', type_='foreignkey')
    # ### end Alembic commands ###