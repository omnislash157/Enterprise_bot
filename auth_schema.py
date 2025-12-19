"""
Auth Schema Extension - Users and Department Access Control

Extends the enterprise schema with:
- enterprise.users - User records with role assignments
- enterprise.user_department_access - Department access grants
- enterprise.auth_sessions - Optional session tracking

SOX Compliance:
- Purchasing and Executive are "gated" departments
- Users must be explicitly granted access (no auto-assign)
- Audit trail for access changes

Usage:
    python auth_schema.py --init          # Create tables
    python auth_schema.py --seed          # Seed Driscoll users
    python auth_schema.py --list          # Show current users
"""

import os
import sys
from datetime import datetime
from contextlib import contextmanager
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()

# =============================================================================
# DATABASE CONFIG (same as tenant_service.py)
# =============================================================================

DB_CONFIG = {
    "user": os.getenv("AZURE_PG_USER", "mhartigan"),
    "password": os.getenv("AZURE_PG_PASSWORD", "Lalamoney3!"),
    "host": os.getenv("AZURE_PG_HOST", "cogtwin.postgres.database.azure.com"),
    "port": int(os.getenv("AZURE_PG_PORT", "5432")),
    "database": os.getenv("AZURE_PG_DATABASE", "postgres"),
    "sslmode": "require"
}

SCHEMA = "enterprise"

# =============================================================================
# GATED DEPARTMENTS (require explicit access grant)
# =============================================================================

# These departments are SOX-sensitive or restricted
# Users cannot auto-join based on email domain
GATED_DEPARTMENTS = {"purchasing", "executive", "hr"}

# Open departments - anyone with valid tenant email can access
OPEN_DEPARTMENTS = {"warehouse", "sales", "credit", "transportation"}

# =============================================================================
# DATABASE HELPERS
# =============================================================================

@contextmanager
def get_connection():
    conn = psycopg2.connect(**DB_CONFIG)
    try:
        yield conn
    finally:
        conn.close()


@contextmanager
def get_cursor(conn=None, dict_cursor=True):
    if conn is None:
        with get_connection() as conn:
            cursor_factory = RealDictCursor if dict_cursor else None
            cur = conn.cursor(cursor_factory=cursor_factory)
            try:
                yield cur
                conn.commit()
            finally:
                cur.close()
    else:
        cursor_factory = RealDictCursor if dict_cursor else None
        cur = conn.cursor(cursor_factory=cursor_factory)
        try:
            yield cur
        finally:
            cur.close()


# =============================================================================
# SCHEMA CREATION
# =============================================================================

def init_auth_tables():
    """
    Create auth tables in the enterprise schema.
    Safe to run multiple times (uses IF NOT EXISTS).
    """
    with get_connection() as conn:
        cur = conn.cursor()
        
        # Ensure schema exists
        cur.execute(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA};")
        
        # ---------------------------------------------------------------------
        # enterprise.users - User accounts
        # ---------------------------------------------------------------------
        cur.execute(f"""
            CREATE TABLE IF NOT EXISTS {SCHEMA}.users (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                
                -- Identity
                email VARCHAR(255) UNIQUE NOT NULL,
                display_name VARCHAR(100),
                employee_id VARCHAR(20),          -- e.g., 'JA' for sales rep filtering
                
                -- Tenant membership (for multi-tenant future)
                tenant_id UUID REFERENCES {SCHEMA}.tenants(id),
                
                -- Global role (highest permission level)
                role VARCHAR(20) DEFAULT 'user',  -- 'user', 'dept_head', 'super_user'
                
                -- Primary department (their "home" department)
                primary_department_id UUID REFERENCES {SCHEMA}.departments(id),
                
                -- Status
                active BOOLEAN DEFAULT TRUE,
                email_verified BOOLEAN DEFAULT FALSE,
                
                -- SSO integration
                sso_provider VARCHAR(50),         -- 'azure_ad', 'google', null
                sso_subject_id VARCHAR(255),      -- External ID from SSO provider
                
                -- Timestamps
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                last_login_at TIMESTAMP WITH TIME ZONE
            );
        """)
        
        # Index for email lookups (most common query)
        cur.execute(f"""
            CREATE INDEX IF NOT EXISTS idx_users_email 
            ON {SCHEMA}.users(email);
        """)
        
        # Index for tenant filtering
        cur.execute(f"""
            CREATE INDEX IF NOT EXISTS idx_users_tenant 
            ON {SCHEMA}.users(tenant_id) WHERE active = TRUE;
        """)
        
        # ---------------------------------------------------------------------
        # enterprise.user_department_access - Department access grants
        # ---------------------------------------------------------------------
        cur.execute(f"""
            CREATE TABLE IF NOT EXISTS {SCHEMA}.user_department_access (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                
                -- Who has access
                user_id UUID NOT NULL REFERENCES {SCHEMA}.users(id) ON DELETE CASCADE,
                
                -- To which department
                department_id UUID NOT NULL REFERENCES {SCHEMA}.departments(id),
                
                -- Access level within this department
                access_level VARCHAR(20) DEFAULT 'read',  -- 'read', 'write', 'admin'
                
                -- Is this user a dept head for this department?
                is_dept_head BOOLEAN DEFAULT FALSE,
                
                -- Who granted this access (audit trail)
                granted_by UUID REFERENCES {SCHEMA}.users(id),
                granted_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                
                -- Expiration (optional, for temp access)
                expires_at TIMESTAMP WITH TIME ZONE,
                
                -- Prevent duplicate grants
                UNIQUE(user_id, department_id)
            );
        """)
        
        # Index for user's department lookups
        cur.execute(f"""
            CREATE INDEX IF NOT EXISTS idx_user_dept_access_user 
            ON {SCHEMA}.user_department_access(user_id);
        """)
        
        # Index for department's user lookups (admin view)
        cur.execute(f"""
            CREATE INDEX IF NOT EXISTS idx_user_dept_access_dept 
            ON {SCHEMA}.user_department_access(department_id);
        """)
        
        # ---------------------------------------------------------------------
        # enterprise.access_audit_log - Track access changes (SOX compliance)
        # ---------------------------------------------------------------------
        cur.execute(f"""
            CREATE TABLE IF NOT EXISTS {SCHEMA}.access_audit_log (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                
                -- What happened
                action VARCHAR(50) NOT NULL,      -- 'grant', 'revoke', 'role_change', 'login'
                
                -- Who did it
                actor_id UUID REFERENCES {SCHEMA}.users(id),
                actor_email VARCHAR(255),         -- Denormalized for audit permanence
                
                -- Target user (if applicable)
                target_user_id UUID REFERENCES {SCHEMA}.users(id),
                target_email VARCHAR(255),
                
                -- Target department (if applicable)
                department_id UUID REFERENCES {SCHEMA}.departments(id),
                department_slug VARCHAR(50),
                
                -- Details
                old_value TEXT,                   -- Previous state
                new_value TEXT,                   -- New state
                reason TEXT,                      -- Why the change was made
                
                -- Timestamp
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                
                -- IP/context (optional)
                ip_address INET,
                user_agent TEXT
            );
        """)
        
        # Index for audit queries by target
        cur.execute(f"""
            CREATE INDEX IF NOT EXISTS idx_audit_target_user 
            ON {SCHEMA}.access_audit_log(target_user_id);
        """)
        
        # Index for audit queries by time
        cur.execute(f"""
            CREATE INDEX IF NOT EXISTS idx_audit_created 
            ON {SCHEMA}.access_audit_log(created_at DESC);
        """)
        
        conn.commit()
        cur.close()
        
        print("[OK] Auth tables created successfully")
        print(f"     Schema: {SCHEMA}")
        print(f"     Tables: users, user_department_access, access_audit_log")
        print(f"     Gated departments: {', '.join(GATED_DEPARTMENTS)}")


def init_analytics_tables():
    """
    Create analytics tables in the enterprise schema.
    Safe to run multiple times (uses IF NOT EXISTS).
    """
    with get_connection() as conn:
        cur = conn.cursor()

        # ---------------------------------------------------------------------
        # enterprise.query_log - Full query storage with classification
        # ---------------------------------------------------------------------
        cur.execute(f"""
            CREATE TABLE IF NOT EXISTS {SCHEMA}.query_log (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

                -- Who/When/Where
                user_id UUID REFERENCES {SCHEMA}.users(id),
                user_email VARCHAR(255) NOT NULL,
                department VARCHAR(50) NOT NULL,
                session_id VARCHAR(100),

                -- The Query
                query_text TEXT NOT NULL,
                query_length INT,
                query_word_count INT,

                -- Classification (auto-detected)
                query_category VARCHAR(50),
                query_subcategory VARCHAR(50),
                query_keywords TEXT[],

                -- Sentiment
                sentiment_score FLOAT,
                frustration_signals TEXT[],
                is_repeat_question BOOLEAN DEFAULT FALSE,
                repeat_of_query_id UUID,

                -- Response Metrics
                response_time_ms INT,
                response_length INT,
                tokens_input INT,
                tokens_output INT,
                model_used VARCHAR(50),

                -- Session Context
                query_position_in_session INT,
                time_since_last_query_ms INT,

                -- Outcome Signals
                session_ended_quickly BOOLEAN DEFAULT FALSE,

                -- Timestamps
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # Indexes
        cur.execute(f"""
            CREATE INDEX IF NOT EXISTS idx_query_log_time
            ON {SCHEMA}.query_log(created_at DESC);
        """)
        cur.execute(f"""
            CREATE INDEX IF NOT EXISTS idx_query_log_user
            ON {SCHEMA}.query_log(user_id, created_at DESC);
        """)
        cur.execute(f"""
            CREATE INDEX IF NOT EXISTS idx_query_log_dept
            ON {SCHEMA}.query_log(department, created_at DESC);
        """)
        cur.execute(f"""
            CREATE INDEX IF NOT EXISTS idx_query_log_category
            ON {SCHEMA}.query_log(query_category, created_at DESC);
        """)
        cur.execute(f"""
            CREATE INDEX IF NOT EXISTS idx_query_log_session
            ON {SCHEMA}.query_log(session_id, created_at);
        """)

        # ---------------------------------------------------------------------
        # enterprise.analytics_events - Non-query events
        # ---------------------------------------------------------------------
        cur.execute(f"""
            CREATE TABLE IF NOT EXISTS {SCHEMA}.analytics_events (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

                event_type VARCHAR(50) NOT NULL,
                user_id UUID REFERENCES {SCHEMA}.users(id),
                user_email VARCHAR(255),
                department VARCHAR(50),

                -- Event-specific data
                event_data JSONB,

                -- For dept_switch events
                from_department VARCHAR(50),
                to_department VARCHAR(50),

                -- For error events
                error_type VARCHAR(100),
                error_message TEXT,

                -- For session events
                session_id VARCHAR(100),
                session_duration_ms INT,
                queries_in_session INT,

                -- Timestamps
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
        """)

        cur.execute(f"""
            CREATE INDEX IF NOT EXISTS idx_events_type_time
            ON {SCHEMA}.analytics_events(event_type, created_at DESC);
        """)
        cur.execute(f"""
            CREATE INDEX IF NOT EXISTS idx_events_user
            ON {SCHEMA}.analytics_events(user_id, created_at DESC);
        """)
        cur.execute(f"""
            CREATE INDEX IF NOT EXISTS idx_events_session
            ON {SCHEMA}.analytics_events(session_id);
        """)

        # ---------------------------------------------------------------------
        # enterprise.analytics_daily - Pre-computed aggregates
        # ---------------------------------------------------------------------
        cur.execute(f"""
            CREATE TABLE IF NOT EXISTS {SCHEMA}.analytics_daily (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

                date DATE NOT NULL,
                department VARCHAR(50),

                -- Volume
                total_queries INT DEFAULT 0,
                unique_users INT DEFAULT 0,
                total_sessions INT DEFAULT 0,

                -- Query Categories
                queries_procedural INT DEFAULT 0,
                queries_lookup INT DEFAULT 0,
                queries_troubleshooting INT DEFAULT 0,
                queries_policy INT DEFAULT 0,
                queries_contact INT DEFAULT 0,
                queries_returns INT DEFAULT 0,
                queries_inventory INT DEFAULT 0,
                queries_safety INT DEFAULT 0,
                queries_other INT DEFAULT 0,

                -- Performance
                avg_response_time_ms FLOAT,
                p95_response_time_ms INT,

                -- Quality Signals
                repeat_questions INT DEFAULT 0,
                quick_abandons INT DEFAULT 0,

                -- Errors
                error_count INT DEFAULT 0,

                -- Computed at
                computed_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

                UNIQUE(date, department)
            );
        """)

        cur.execute(f"""
            CREATE INDEX IF NOT EXISTS idx_daily_date
            ON {SCHEMA}.analytics_daily(date DESC);
        """)
        cur.execute(f"""
            CREATE INDEX IF NOT EXISTS idx_daily_dept
            ON {SCHEMA}.analytics_daily(department, date DESC);
        """)

        conn.commit()
        cur.close()

        print("[OK] Analytics tables created successfully")
        print(f"     Tables: query_log, analytics_events, analytics_daily")


# =============================================================================
# SEED DATA
# =============================================================================

def seed_driscoll_users():
    """
    Seed initial Driscoll users for testing.
    
    Creates:
    - 1 super_user (Hartigan)
    - 1 dept_head per department
    - A few regular users
    """
    with get_connection() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Get Driscoll tenant ID
        cur.execute(f"""
            SELECT id FROM {SCHEMA}.tenants WHERE slug = 'driscoll'
        """)
        tenant_row = cur.fetchone()
        if not tenant_row:
            print("[ERROR] Driscoll tenant not found. Run tenant_service.py --init first")
            return
        
        tenant_id = tenant_row["id"]
        
        # Get department IDs
        cur.execute(f"""
            SELECT id, slug, name FROM {SCHEMA}.departments WHERE active = TRUE
        """)
        depts = {row["slug"]: row for row in cur.fetchall()}
        
        if not depts:
            print("[ERROR] No departments found. Run upload_manuals.py --init-db first")
            return
        
        print(f"Found {len(depts)} departments: {', '.join(depts.keys())}")
        
        # Define seed users
        seed_users = [
            # Super users
            {
                "email": "mhartigan@driscollfoods.com",
                "display_name": "Matt Hartigan",
                "role": "super_user",
                "primary_dept": None,  # Super users see all
                "access": list(depts.keys()),  # Access to everything
            },
            
            # Department heads
            {
                "email": "warehouse_head@driscollfoods.com",
                "display_name": "Warehouse Manager",
                "role": "dept_head",
                "primary_dept": "warehouse",
                "access": ["warehouse"],
                "is_dept_head": True,
            },
            {
                "email": "sales_head@driscollfoods.com",
                "display_name": "Sales Director",
                "role": "dept_head",
                "primary_dept": "sales",
                "access": ["sales"],
                "is_dept_head": True,
            },
            {
                "email": "credit_head@driscollfoods.com",
                "display_name": "Credit Manager",
                "role": "dept_head",
                "primary_dept": "credit",
                "access": ["credit"],
                "is_dept_head": True,
            },
            {
                "email": "purchasing_head@driscollfoods.com",
                "display_name": "Purchasing Director",
                "role": "dept_head",
                "primary_dept": "purchasing",
                "access": ["purchasing"],  # Gated - explicit only
                "is_dept_head": True,
            },
            
            # Regular users
            {
                "email": "jafflerbach@driscollfoods.com",
                "display_name": "John Afflerbach",
                "employee_id": "JA",
                "role": "user",
                "primary_dept": "sales",
                "access": ["sales"],
            },
            {
                "email": "driver1@driscollfoods.com",
                "display_name": "Test Driver",
                "role": "user",
                "primary_dept": "warehouse",
                "access": ["warehouse", "transportation"],
            },
        ]
        
        for user_data in seed_users:
            # Insert user
            primary_dept_id = depts[user_data["primary_dept"]]["id"] if user_data.get("primary_dept") else None
            
            cur.execute(f"""
                INSERT INTO {SCHEMA}.users 
                    (email, display_name, employee_id, tenant_id, role, primary_department_id, active)
                VALUES (%s, %s, %s, %s, %s, %s, TRUE)
                ON CONFLICT (email) DO UPDATE SET
                    display_name = EXCLUDED.display_name,
                    role = EXCLUDED.role,
                    primary_department_id = EXCLUDED.primary_department_id,
                    updated_at = CURRENT_TIMESTAMP
                RETURNING id
            """, (
                user_data["email"],
                user_data["display_name"],
                user_data.get("employee_id"),
                tenant_id,
                user_data["role"],
                primary_dept_id
            ))
            
            user_id = cur.fetchone()["id"]
            
            # Grant department access
            for dept_slug in user_data.get("access", []):
                if dept_slug not in depts:
                    continue
                    
                dept_id = depts[dept_slug]["id"]
                is_dept_head = user_data.get("is_dept_head", False) and dept_slug == user_data.get("primary_dept")
                
                cur.execute(f"""
                    INSERT INTO {SCHEMA}.user_department_access
                        (user_id, department_id, access_level, is_dept_head)
                    VALUES (%s, %s, 'read', %s)
                    ON CONFLICT (user_id, department_id) DO UPDATE SET
                        is_dept_head = EXCLUDED.is_dept_head
                """, (user_id, dept_id, is_dept_head))
            
            print(f"  [+] {user_data['email']} ({user_data['role']})")
        
        conn.commit()
        cur.close()
        
        print(f"\n[OK] Seeded {len(seed_users)} users")


def list_users():
    """List all users with their department access."""
    with get_cursor() as cur:
        cur.execute(f"""
            SELECT 
                u.email,
                u.display_name,
                u.role,
                u.employee_id,
                d.name as primary_dept,
                u.active,
                u.last_login_at
            FROM {SCHEMA}.users u
            LEFT JOIN {SCHEMA}.departments d ON u.primary_department_id = d.id
            ORDER BY u.role DESC, u.email
        """)
        users = cur.fetchall()
        
        if not users:
            print("[INFO] No users found")
            return
        
        print(f"\n{'Email':<40} {'Name':<25} {'Role':<12} {'Dept':<15} {'Active'}")
        print("=" * 110)
        
        for u in users:
            status = "Yes" if u["active"] else "No"
            dept = u["primary_dept"] or "-"
            name = u["display_name"] or "-"
            print(f"{u['email']:<40} {name:<25} {u['role']:<12} {dept:<15} {status}")
        
        print(f"\nTotal: {len(users)} users")
        
        # Show department access breakdown
        cur.execute(f"""
            SELECT 
                d.name as dept_name,
                COUNT(uda.user_id) as user_count,
                COUNT(CASE WHEN uda.is_dept_head THEN 1 END) as head_count
            FROM {SCHEMA}.departments d
            LEFT JOIN {SCHEMA}.user_department_access uda ON d.id = uda.department_id
            WHERE d.active = TRUE
            GROUP BY d.id, d.name
            ORDER BY d.name
        """)
        dept_stats = cur.fetchall()
        
        print(f"\nDepartment Access:")
        for stat in dept_stats:
            gated = "(GATED)" if stat["dept_name"].lower() in GATED_DEPARTMENTS else ""
            print(f"  {stat['dept_name']:<20} {stat['user_count']} users, {stat['head_count']} heads {gated}")


# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    args = sys.argv[1:]
    
    if "--help" in args or "-h" in args:
        print(__doc__)
        sys.exit(0)
    
    if "--init" in args:
        print("[INIT] Creating auth tables...")
        init_auth_tables()
        
        if "--seed" not in args:
            print("\n[TIP] Run with --seed to create test users")
    
    if "--seed" in args:
        print("\n[SEED] Creating Driscoll test users...")
        seed_driscoll_users()
    
    if "--list" in args:
        list_users()

    if "--init-analytics" in args:
        print("\n[INIT] Creating analytics tables...")
        init_analytics_tables()

    if not args:
        print("Auth Schema Extension")
        print("=" * 60)
        print("\nUsage:")
        print("  python auth_schema.py --init           # Create auth tables")
        print("  python auth_schema.py --seed           # Seed test users")
        print("  python auth_schema.py --list           # Show users")
        print("  python auth_schema.py --init-analytics # Create analytics tables")
        print("\nRun --init first, then --seed to set up Driscoll users.")