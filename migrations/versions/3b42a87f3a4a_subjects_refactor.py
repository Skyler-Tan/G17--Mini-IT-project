"""
Refactor classes -> subjects and related FKs

Handles both cases:
- Existing DB previously using 'classes' (rename to 'subjects', and rename FKs)
- Fresh DB with no tables yet (create required tables with current schema)
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '3b42a87f3a4a'
down_revision = None
branch_labels = None
depends_on = None


def _table_exists(bind, name: str) -> bool:
    try:
        return bind.execute(sa.text("SELECT name FROM sqlite_master WHERE type='table' AND name=:n"), {"n": name}).scalar() is not None
    except Exception:
        inspector = sa.inspect(bind)
        return name in inspector.get_table_names()


def _column_exists(bind, table: str, column: str) -> bool:
    try:
        rows = bind.execute(sa.text(f"PRAGMA table_info({table})")).fetchall()
        # PRAGMA table_info columns: (cid, name, type, notnull, dflt_value, pk)
        return any(r[1] == column for r in rows)
    except Exception:
        inspector = sa.inspect(bind)
        cols = [c['name'] for c in inspector.get_columns(table)]
        return column in cols


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    # 1) Ensure 'subjects' table exists (rename from 'classes' if needed)
    subjects_exists = _table_exists(bind, 'subjects')
    classes_exists = _table_exists(bind, 'classes')

    if not subjects_exists:
        if classes_exists:
            # Rename classes -> subjects
            if dialect == 'sqlite':
                op.execute(sa.text("ALTER TABLE classes RENAME TO subjects"))
            else:
                op.rename_table('classes', 'subjects')
        else:
            # Fresh DB: create 'subjects'
            op.create_table(
                'subjects',
                sa.Column('id', sa.Integer(), primary_key=True),
                sa.Column('name', sa.String(length=120), nullable=False, unique=True),
            )

    # 2) Ensure 'groups' has subject_id (rename column or create table)
    if _table_exists(bind, 'groups'):
        if _column_exists(bind, 'groups', 'class_id') and not _column_exists(bind, 'groups', 'subject_id'):
            if dialect == 'sqlite':
                op.execute(sa.text("ALTER TABLE groups RENAME COLUMN class_id TO subject_id"))
            else:
                with op.batch_alter_table('groups') as batch_op:
                    batch_op.alter_column('class_id', new_column_name='subject_id', existing_type=sa.Integer())
        elif not _column_exists(bind, 'groups', 'subject_id') and not _column_exists(bind, 'groups', 'class_id'):
            # Legacy table had no association; add nullable subject_id so app can run
            try:
                op.add_column('groups', sa.Column('subject_id', sa.Integer(), nullable=True))
            except Exception:
                pass
        # Unique constraint name update cannot be altered easily on SQLite; skip if exists
        try:
            op.create_unique_constraint('uq_group_name_per_subject', 'groups', ['name', 'subject_id'])
        except Exception:
            pass
    else:
        # Fresh DB: create 'groups'
        op.create_table(
            'groups',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('name', sa.String(length=120), nullable=False),
            sa.Column('subject_id', sa.Integer(), sa.ForeignKey('subjects.id', ondelete='CASCADE'), nullable=False),
            sa.UniqueConstraint('name', 'subject_id', name='uq_group_name_per_subject'),
        )

    # 3) Ensure 'students' has subject_id (rename column or create table)
    if _table_exists(bind, 'students'):
        if _column_exists(bind, 'students', 'class_id') and not _column_exists(bind, 'students', 'subject_id'):
            if dialect == 'sqlite':
                op.execute(sa.text("ALTER TABLE students RENAME COLUMN class_id TO subject_id"))
            else:
                with op.batch_alter_table('students') as batch_op:
                    batch_op.alter_column('class_id', new_column_name='subject_id', existing_type=sa.Integer())
        elif not _column_exists(bind, 'students', 'subject_id') and not _column_exists(bind, 'students', 'class_id'):
            # Legacy table had no association; add nullable subject_id so app can run
            try:
                op.add_column('students', sa.Column('subject_id', sa.Integer(), nullable=True))
            except Exception:
                pass
        # Create helpful indexes/constraints if missing
        try:
            op.create_unique_constraint('uq_student_id_per_subject', 'students', ['student_id', 'subject_id'])
        except Exception:
            pass
        for ix_name, cols in [
            ('ix_students_email', ['email']),
            ('ix_students_student_id', ['student_id']),
        ]:
            try:
                op.create_index(ix_name, 'students', cols, unique=False)
            except Exception:
                pass
    else:
        # Fresh DB: create 'students'
        op.create_table(
            'students',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('student_id', sa.String(length=64), nullable=True),
            sa.Column('name', sa.String(length=120), nullable=False),
            sa.Column('email', sa.String(length=255), nullable=False),
            sa.Column('subject_id', sa.Integer(), sa.ForeignKey('subjects.id', ondelete='SET NULL'), nullable=True),
            sa.Column('group_id', sa.Integer(), sa.ForeignKey('groups.id', ondelete='SET NULL'), nullable=True),
            sa.UniqueConstraint('student_id', 'subject_id', name='uq_student_id_per_subject'),
        )
        # Indexes
        op.create_index('ix_students_email', 'students', ['email'], unique=False)
        op.create_index('ix_students_student_id', 'students', ['student_id'], unique=False)

    # 4) Reviews table
    if not _table_exists(bind, 'reviews'):
        op.create_table(
            'reviews',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('reviewer_id', sa.Integer(), sa.ForeignKey('students.id', ondelete='CASCADE'), nullable=False),
            sa.Column('reviewee_id', sa.Integer(), sa.ForeignKey('students.id', ondelete='CASCADE'), nullable=False),
            sa.Column('score', sa.Integer(), nullable=False),
            sa.Column('comment', sa.Text(), nullable=True),
            sa.Column('timestamp', sa.DateTime(), nullable=True),
            sa.CheckConstraint('reviewer_id <> reviewee_id', name='ck_review_not_self'),
            sa.CheckConstraint('score >= 0', name='ck_review_score_non_negative'),
        )
        try:
            op.create_index('ix_reviews_reviewer_id', 'reviews', ['reviewer_id'], unique=False)
        except Exception:
            pass
        try:
            op.create_index('ix_reviews_reviewee_id', 'reviews', ['reviewee_id'], unique=False)
        except Exception:
            pass

    # 5) Settings table
    if not _table_exists(bind, 'settings'):
        op.create_table(
            'settings',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('criteria', sa.String(length=255), nullable=True),
            sa.Column('max_score', sa.Integer(), nullable=True),
            sa.Column('deadline', sa.DateTime(), nullable=True),
        )


def downgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    # Best-effort partial downgrade
    if _table_exists(bind, 'students') and _column_exists(bind, 'students', 'subject_id') and not _column_exists(bind, 'students', 'class_id'):
        if dialect == 'sqlite':
            op.execute(sa.text("ALTER TABLE students RENAME COLUMN subject_id TO class_id"))
        else:
            with op.batch_alter_table('students') as batch_op:
                batch_op.alter_column('subject_id', new_column_name='class_id', existing_type=sa.Integer())

    if _table_exists(bind, 'groups') and _column_exists(bind, 'groups', 'subject_id') and not _column_exists(bind, 'groups', 'class_id'):
        if dialect == 'sqlite':
            op.execute(sa.text("ALTER TABLE groups RENAME COLUMN subject_id TO class_id"))
        else:
            with op.batch_alter_table('groups') as batch_op:
                batch_op.alter_column('subject_id', new_column_name='class_id', existing_type=sa.Integer())

    if _table_exists(bind, 'subjects') and not _table_exists(bind, 'classes'):
        if dialect == 'sqlite':
            op.execute(sa.text("ALTER TABLE subjects RENAME TO classes"))
        else:
            op.rename_table('subjects', 'classes')
