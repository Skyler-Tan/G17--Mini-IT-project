"""
add table for subject (robust, SQLite-friendly)

Revision ID: af9e1805aac5
Revises: 3b42a87f3a4a
Create Date: 2025-09-18 14:06:25.933192

This migration safely transitions from 'classes' to 'subjects' and updates
related foreign keys and constraints for 'groups' and 'students'.
It is written to be resilient on SQLite and to avoid breaking when
previous migrations were partially applied.
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'af9e1805aac5'
down_revision = '3b42a87f3a4a'
branch_labels = None
depends_on = None


def _bind():
    return op.get_bind()


def _inspector():
    return sa.inspect(_bind())


def _table_exists(name: str) -> bool:
    insp = _inspector()
    try:
        return name in insp.get_table_names()
    except Exception:
        return False


def _column_exists(table: str, column: str) -> bool:
    insp = _inspector()
    try:
        cols = [c['name'] for c in insp.get_columns(table)]
        return column in cols
    except Exception:
        return False


def _index_exists(table: str, name: str) -> bool:
    insp = _inspector()
    try:
        return any(ix['name'] == name for ix in insp.get_indexes(table))
    except Exception:
        return False


def _drop_fk_if_refers(table: str, refers_to_table: str):
    insp = _inspector()
    try:
        fks = insp.get_foreign_keys(table)
    except Exception:
        fks = []
    for fk in fks:
        if fk.get('referred_table') == refers_to_table and fk.get('name'):
            with op.batch_alter_table(table) as batch_op:
                try:
                    batch_op.drop_constraint(fk['name'], type_='foreignkey')
                except Exception:
                    pass


def upgrade():
    bind = _bind()
    dialect = bind.dialect.name

    # 1) Ensure 'subjects' exists: rename 'classes' -> 'subjects' or create fresh
    has_subjects = _table_exists('subjects')
    has_classes = _table_exists('classes')

    if not has_subjects:
        if has_classes:
            if dialect == 'sqlite':
                op.execute(sa.text("ALTER TABLE classes RENAME TO subjects"))
            else:
                op.rename_table('classes', 'subjects')
        else:
            op.create_table(
                'subjects',
                sa.Column('id', sa.Integer(), primary_key=True),
                sa.Column('name', sa.String(length=120), nullable=False, unique=True),
            )

    # 2) Groups: ensure subject_id column, constraints and FK
    if _table_exists('groups'):
        # Column rename class_id -> subject_id if needed
        if _column_exists('groups', 'class_id') and not _column_exists('groups', 'subject_id'):
            with op.batch_alter_table('groups') as batch_op:
                batch_op.alter_column('class_id', new_column_name='subject_id', existing_type=sa.Integer())
        # Unique constraint: switch to per-subject
        # Try drop old per-class unique constraint if it exists
        try:
            with op.batch_alter_table('groups') as batch_op:
                batch_op.drop_constraint('uq_group_name_per_class', type_='unique')
        except Exception:
            pass
        # Create per-subject unique constraint if missing
        try:
            with op.batch_alter_table('groups') as batch_op:
                batch_op.create_unique_constraint('uq_group_name_per_subject', ['name', 'subject_id'])
        except Exception:
            pass
        # Drop any FK that points to classes.id, then create FK to subjects.id
        _drop_fk_if_refers('groups', 'classes')
        try:
            with op.batch_alter_table('groups') as batch_op:
                batch_op.create_foreign_key('fk_groups_subject_id_subjects', 'subjects', ['subject_id'], ['id'], ondelete='CASCADE')
        except Exception:
            pass
    else:
        # Create groups if it doesn't exist
        op.create_table(
            'groups',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('name', sa.String(length=120), nullable=False),
            sa.Column('subject_id', sa.Integer(), sa.ForeignKey('subjects.id', ondelete='CASCADE'), nullable=False),
            sa.UniqueConstraint('name', 'subject_id', name='uq_group_name_per_subject'),
        )

    # 3) Students: ensure subject_id column, constraints and FKs
    if _table_exists('students'):
        if _column_exists('students', 'class_id') and not _column_exists('students', 'subject_id'):
            with op.batch_alter_table('students') as batch_op:
                batch_op.alter_column('class_id', new_column_name='subject_id', existing_type=sa.Integer())
        # Unique per subject
        try:
            with op.batch_alter_table('students') as batch_op:
                batch_op.create_unique_constraint('uq_student_id_per_subject', ['student_id', 'subject_id'])
        except Exception:
            pass
        # Drop FKs pointing to classes and recreate to subjects/groups
        _drop_fk_if_refers('students', 'classes')
        try:
            with op.batch_alter_table('students') as batch_op:
                batch_op.create_foreign_key('fk_students_subject_id_subjects', 'subjects', ['subject_id'], ['id'], ondelete='SET NULL')
        except Exception:
            pass
        try:
            with op.batch_alter_table('students') as batch_op:
                batch_op.create_foreign_key('fk_students_group_id_groups', 'groups', ['group_id'], ['id'], ondelete='SET NULL')
        except Exception:
            pass
        # Indexes
        if not _index_exists('students', 'ix_students_email'):
            op.create_index('ix_students_email', 'students', ['email'], unique=False)
        if not _index_exists('students', 'ix_students_student_id'):
            op.create_index('ix_students_student_id', 'students', ['student_id'], unique=False)
    else:
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
        if not _index_exists('students', 'ix_students_email'):
            op.create_index('ix_students_email', 'students', ['email'], unique=False)
        if not _index_exists('students', 'ix_students_student_id'):
            op.create_index('ix_students_student_id', 'students', ['student_id'], unique=False)

    # 4) Reviews indexes
    if _table_exists('reviews'):
        if not _index_exists('reviews', 'ix_reviews_reviewer_id'):
            op.create_index('ix_reviews_reviewer_id', 'reviews', ['reviewer_id'], unique=False)
        if not _index_exists('reviews', 'ix_reviews_reviewee_id'):
            op.create_index('ix_reviews_reviewee_id', 'reviews', ['reviewee_id'], unique=False)
    else:
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
        if not _index_exists('reviews', 'ix_reviews_reviewer_id'):
            op.create_index('ix_reviews_reviewer_id', 'reviews', ['reviewer_id'], unique=False)
        if not _index_exists('reviews', 'ix_reviews_reviewee_id'):
            op.create_index('ix_reviews_reviewee_id', 'reviews', ['reviewee_id'], unique=False)

    # 5) Settings table ensure exists
    if not _table_exists('settings'):
        op.create_table(
            'settings',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('criteria', sa.String(length=255), nullable=True),
            sa.Column('max_score', sa.Integer(), nullable=True),
            sa.Column('deadline', sa.DateTime(), nullable=True),
        )



def downgrade():
    bind = _bind()
    dialect = bind.dialect.name

    # Revert students: subject_id -> class_id
    if _table_exists('students') and _column_exists('students', 'subject_id') and not _column_exists('students', 'class_id'):
        with op.batch_alter_table('students') as batch_op:
            batch_op.alter_column('subject_id', new_column_name='class_id', existing_type=sa.Integer())
        try:
            with op.batch_alter_table('students') as batch_op:
                batch_op.drop_constraint('uq_student_id_per_subject', type_='unique')
        except Exception:
            pass

    # Revert groups: subject_id -> class_id
    if _table_exists('groups') and _column_exists('groups', 'subject_id') and not _column_exists('groups', 'class_id'):
        with op.batch_alter_table('groups') as batch_op:
            batch_op.alter_column('subject_id', new_column_name='class_id', existing_type=sa.Integer())
        try:
            with op.batch_alter_table('groups') as batch_op:
                batch_op.drop_constraint('uq_group_name_per_subject', type_='unique')
        except Exception:
            pass

    # Rename subjects -> classes
    if _table_exists('subjects') and not _table_exists('classes'):
        if dialect == 'sqlite':
            op.execute(sa.text("ALTER TABLE subjects RENAME TO classes"))
        else:
            op.rename_table('subjects', 'classes')
