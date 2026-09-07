"""enable row level security on candidates

Revision ID: 3810da34240d
Revises: ed8229af8a7f
Create Date: 2026-09-07 19:40:12.403274

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3810da34240d'
down_revision: Union[str, Sequence[str], None] = 'ed8229af8a7f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("ALTER TABLE candidates ENABLE ROW LEVEL SECURITY")
    # The table owner bypasses RLS by default, FORCE closes that hole even
    # though the application connects as the non-superuser app role, not
    # the owner.
    op.execute("ALTER TABLE candidates FORCE ROW LEVEL SECURITY")

    op.execute(
        """
        CREATE POLICY candidates_region_scope ON candidates
        FOR SELECT
        USING (
            -- Used only by writes such as the bulk upsert, which is
            -- intentionally scope-free: it does not set app.recruiter_id
            -- at all, so it sets this instead of impersonating a recruiter.
            -- RETURNING is checked against this same SELECT policy, so
            -- without it a successful insert would read back as invisible.
            current_setting('app.bypass_rls', true) = 'true'
            OR EXISTS (
                SELECT 1 FROM recruiters r
                WHERE r.id = current_setting('app.recruiter_id', true)
                  AND r.is_admin
            )
            OR region_code IN (
                SELECT rr.region_code FROM recruiter_regions rr
                WHERE rr.recruiter_id = current_setting('app.recruiter_id', true)
            )
        )
        """
    )

    # Only SELECT is scoped by recruiter, writes are already gated by the
    # repository/service layer and by the plain table GRANTs. Without these,
    # row security's default deny would block every insert and the ON
    # CONFLICT update the bulk upsert relies on.
    op.execute("CREATE POLICY candidates_write_insert ON candidates FOR INSERT WITH CHECK (true)")
    op.execute("CREATE POLICY candidates_write_update ON candidates FOR UPDATE USING (true) WITH CHECK (true)")


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("DROP POLICY IF EXISTS candidates_write_update ON candidates")
    op.execute("DROP POLICY IF EXISTS candidates_write_insert ON candidates")
    op.execute("DROP POLICY IF EXISTS candidates_region_scope ON candidates")
    op.execute("ALTER TABLE candidates NO FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE candidates DISABLE ROW LEVEL SECURITY")
