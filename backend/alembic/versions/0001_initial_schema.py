"""initial_schema_with_grants_consent_and_audit

Revision ID: 0001_initial
Revises: 
Create Date: 2026-10-28 06:38:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0001_initial'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. users
    op.create_table(
        'users',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('email', sa.String(), nullable=True),
        sa.Column('hashed_password', sa.String(), nullable=True),
        sa.Column('role', sa.String(), server_default='patient', nullable=False),
        sa.Column('invite_code', sa.String(length=32), nullable=True),
        sa.Column('is_active', sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column('name', sa.String(), server_default='User', nullable=True),
        sa.Column('age', sa.Integer(), server_default='45', nullable=True),
        sa.Column('sex', sa.String(), server_default='Male', nullable=True),
        sa.Column('is_smoker', sa.Boolean(), server_default=sa.false(), nullable=True),
        sa.Column('is_diabetic', sa.Boolean(), server_default=sa.false(), nullable=True),
        sa.Column('has_family_history', sa.Boolean(), server_default=sa.false(), nullable=True),
        sa.Column('height_cm', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
    )
    op.create_index('ix_users_email', 'users', ['email'], unique=True)
    op.create_index('ix_users_invite_code', 'users', ['invite_code'], unique=True)

    # 2. vitals_logs
    op.create_table(
        'vitals_logs',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('bp_sys', sa.Integer(), nullable=False),
        sa.Column('bp_dia', sa.Integer(), nullable=False),
        sa.Column('hr', sa.Integer(), nullable=False),
        sa.Column('weight', sa.Float(), nullable=False),
        sa.Column('spo2', sa.Float(), nullable=False),
        sa.Column('glucose', sa.Float(), nullable=True),
        sa.Column('cholesterol', sa.Float(), nullable=True),
        sa.Column('risk_score', sa.Float(), nullable=False),
        sa.Column('risk_tier', sa.String(), nullable=False),
        sa.Column('lgbm_probability', sa.Float(), nullable=True),
        sa.Column('framingham_risk', sa.Float(), nullable=True),
        sa.Column('shap_json', sa.Text(), nullable=True),
        sa.Column('ecg_prompt', sa.Boolean(), server_default=sa.false(), nullable=True),
        sa.Column('timestamp', sa.DateTime(), nullable=True),
    )
    op.create_index('ix_vitals_logs_user_id', 'vitals_logs', ['user_id'])
    op.create_index('ix_vitals_logs_timestamp', 'vitals_logs', ['timestamp'])

    # 3. ecg_analyses (with file_data for persistent cloud database storage!)
    op.create_table(
        'ecg_analyses',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('file_path', sa.String(), nullable=True),
        sa.Column('file_name', sa.String(), nullable=True),
        sa.Column('file_data', sa.LargeBinary(), nullable=True),
        sa.Column('urgency', sa.String(), server_default='see_doctor_today', nullable=True),
        sa.Column('heart_rate_bpm', sa.Integer(), nullable=True),
        sa.Column('rhythm', sa.String(), nullable=True),
        sa.Column('qtc_ms', sa.Integer(), nullable=True),
        sa.Column('image_quality', sa.String(), nullable=True),
        sa.Column('top_condition', sa.String(), nullable=True),
        sa.Column('top_condition_prob', sa.Float(), nullable=True),
        sa.Column('analysis_json', sa.Text(), nullable=True),
        sa.Column('timestamp', sa.DateTime(), nullable=True),
    )
    op.create_index('ix_ecg_analyses_user_id', 'ecg_analyses', ['user_id'])
    op.create_index('ix_ecg_analyses_timestamp', 'ecg_analyses', ['timestamp'])

    # 4. triage_events
    op.create_table(
        'triage_events',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('symptoms_json', sa.Text(), nullable=True),
        sa.Column('severity', sa.String(), nullable=False),
        sa.Column('confidence', sa.Float(), nullable=True),
        sa.Column('risk_score', sa.Float(), nullable=True),
        sa.Column('lat', sa.Float(), nullable=True),
        sa.Column('lon', sa.Float(), nullable=True),
        sa.Column('timestamp', sa.DateTime(), nullable=True),
    )
    op.create_index('ix_triage_events_user_id', 'triage_events', ['user_id'])
    op.create_index('ix_triage_events_timestamp', 'triage_events', ['timestamp'])

    # 5. patient_clinician_grants
    op.create_table(
        'patient_clinician_grants',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('patient_id', sa.String(), nullable=False),
        sa.Column('clinician_id', sa.String(), nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
    )
    op.create_index('ix_patient_clinician_grants_patient_id', 'patient_clinician_grants', ['patient_id'])
    op.create_index('ix_patient_clinician_grants_clinician_id', 'patient_clinician_grants', ['clinician_id'])

    # 6. rate_limit_events
    op.create_table(
        'rate_limit_events',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('key', sa.String(length=128), nullable=False),
        sa.Column('scope', sa.String(length=32), nullable=False),
        sa.Column('timestamp', sa.Float(), nullable=False),
    )
    op.create_index('ix_rate_limit_events_key', 'rate_limit_events', ['key'])
    op.create_index('ix_rate_limit_events_scope', 'rate_limit_events', ['scope'])
    op.create_index('ix_rate_limit_events_timestamp', 'rate_limit_events', ['timestamp'])

    # 7. login_lockouts
    op.create_table(
        'login_lockouts',
        sa.Column('key', sa.String(length=128), primary_key=True),
        sa.Column('locked_until', sa.Float(), nullable=False),
        sa.Column('failure_count', sa.Integer(), server_default='0', nullable=False),
        sa.Column('last_failure_at', sa.Float(), nullable=False),
    )

    # 8. user_consents
    op.create_table(
        'user_consents',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('consent_type', sa.String(length=64), nullable=False),
        sa.Column('granted', sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column('policy_version', sa.String(length=32), server_default='v1.0', nullable=False),
        sa.Column('ip_address', sa.String(length=64), nullable=True),
        sa.Column('timestamp', sa.DateTime(), nullable=True),
    )
    op.create_index('ix_user_consents_user_id', 'user_consents', ['user_id'])
    op.create_index('ix_user_consents_consent_type', 'user_consents', ['consent_type'])
    op.create_index('ix_user_consents_timestamp', 'user_consents', ['timestamp'])

    # 9. access_audit_logs
    op.create_table(
        'access_audit_logs',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('accessor_user_id', sa.String(length=64), nullable=False),
        sa.Column('accessor_email', sa.String(length=128), nullable=True),
        sa.Column('patient_user_id', sa.String(length=64), nullable=False),
        sa.Column('endpoint', sa.String(length=128), nullable=False),
        sa.Column('ip_address', sa.String(length=64), nullable=False),
        sa.Column('timestamp', sa.DateTime(), nullable=False),
    )
    op.create_index('ix_access_audit_logs_accessor_user_id', 'access_audit_logs', ['accessor_user_id'])
    op.create_index('ix_access_audit_logs_patient_user_id', 'access_audit_logs', ['patient_user_id'])
    op.create_index('ix_access_audit_logs_timestamp', 'access_audit_logs', ['timestamp'])


def downgrade() -> None:
    op.drop_table('access_audit_logs')
    op.drop_table('user_consents')
    op.drop_table('login_lockouts')
    op.drop_table('rate_limit_events')
    op.drop_table('patient_clinician_grants')
    op.drop_table('triage_events')
    op.drop_table('ecg_analyses')
    op.drop_table('vitals_logs')
    op.drop_table('users')
