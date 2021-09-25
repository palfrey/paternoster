"""stations

Revision ID: 41fb2961c584
Revises: 
Create Date: 2021-09-25 22:19:43.797809

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '41fb2961c584'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('station',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=128), nullable=True),
    sa.Column('source', sa.String(length=128), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('station')
    # ### end Alembic commands ###
