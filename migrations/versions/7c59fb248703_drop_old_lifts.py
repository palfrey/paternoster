"""drop old lifts

Revision ID: 7c59fb248703
Revises: 63b6fa54d77c
Create Date: 2021-09-29 21:14:19.622080

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "7c59fb248703"
down_revision = "63b6fa54d77c"
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_constraint(None, "lift", type_="foreignkey")
    op.create_foreign_key(None, "lift", "station", ["station_id"], ["id"], ondelete="CASCADE")
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_constraint(None, "lift", type_="foreignkey")
    op.create_foreign_key(None, "lift", "station", ["station_id"], ["id"])
    # ### end Alembic commands ###
