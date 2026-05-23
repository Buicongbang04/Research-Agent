"""switch memory embedding index from ivfflat to hnsw

Revision ID: 11e6692420e0
Revises: e499796aabe5
Create Date: 2026-05-24 01:10:14.331109

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '11e6692420e0'
down_revision: Union[str, Sequence[str], None] = 'e499796aabe5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Switch from IVFFlat to HNSW for memories.embedding.

    HNSW tunes itself and works well for small / incrementally-growing datasets,
    whereas IVFFlat with a high `lists` value misses neighbours when row count is low.
    """
    op.execute("DROP INDEX IF EXISTS ix_memories_embedding_cosine")
    op.execute(
        "CREATE INDEX ix_memories_embedding_cosine ON memories "
        "USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_memories_embedding_cosine")
    op.execute(
        "CREATE INDEX ix_memories_embedding_cosine ON memories "
        "USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)"
    )
