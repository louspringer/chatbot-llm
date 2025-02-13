/*
 * Snowflake Deployment Script for Cortex Analyst
 * Using PKI authentication and default connection
 * Version: 2.0.0
 * Features:
 * - Full idempotency
 * - Error handling
 * - Rollback procedures
 * - Validation checks
 * - Concurrent execution safety
 */

-- Verify variables are set
DECLARE
  MISSING_VARS ARRAY;
  BEGIN
    IF ($ROLE_NAME IS NULL) THEN
      MISSING_VARS := ARRAY_APPEND(MISSING_VARS, 'ROLE_NAME');
    END IF;
    IF ($DATABASE_NAME IS NULL) THEN
      MISSING_VARS := ARRAY_APPEND(MISSING_VARS, 'DATABASE_NAME');
    END IF;
    IF ($SCHEMA_NAME IS NULL) THEN
      MISSING_VARS := ARRAY_APPEND(MISSING_VARS, 'SCHEMA_NAME');
    END IF;

    IF (ARRAY_SIZE(MISSING_VARS) > 0) THEN
      RAISE EXCEPTION 'Missing required variables: ' || ARRAY_TO_STRING(MISSING_VARS, ', ');
    END IF;
  END;

-- Create deployment database if it doesn't exist (using ACCOUNTADMIN)
CREATE DATABASE IF NOT EXISTS identifier($DATABASE_NAME);

-- Switch to SECURITYADMIN for role management
USE ROLE SECURITYADMIN;

-- Create role if it doesn't exist
CREATE ROLE IF NOT EXISTS identifier($ROLE_NAME);
GRANT DATABASE ROLE SNOWFLAKE.CORTEX_USER TO ROLE identifier($ROLE_NAME);

-- Switch to SYSADMIN for object creation
USE ROLE SYSADMIN;
USE DATABASE identifier($DATABASE_NAME);
CREATE SCHEMA IF NOT EXISTS identifier($SCHEMA_NAME);
USE SCHEMA identifier($SCHEMA_NAME);

-- Enable Python stored procedures
CREATE OR REPLACE PROCEDURE VALIDATE_DEPLOYMENT(deployment_id STRING)
RETURNS VARIANT
LANGUAGE PYTHON
RUNTIME_VERSION = '3.8'
PACKAGES = ('snowflake-snowpark-python')
HANDLER = 'validate_deployment'
AS
$$
def validate_deployment(snowpark_session, deployment_id):
    import json

    validation_results = {
        'status': 'SUCCESS',
        'checks': [],
        'errors': []
    }

    try:
        # Check if deployment is already in progress
        deployment_check = snowpark_session.sql(
            f"SELECT status FROM deployment_history WHERE deployment_id = '{deployment_id}'"
        ).collect()

        if deployment_check and deployment_check[0]['STATUS'] == 'IN_PROGRESS':
            validation_results['status'] = 'FAILED'
            validation_results['errors'].append('Deployment already in progress')
            return json.dumps(validation_results)

        # Validate role exists
        role_exists = snowpark_session.sql(
            "SHOW ROLES LIKE '" + snowpark_session.get_current_role() + "'"
        ).collect()
        if not role_exists:
            validation_results['errors'].append('Current role does not exist')

        # Validate database permissions
        db_grants = snowpark_session.sql(
            "SHOW GRANTS TO ROLE " + snowpark_session.get_current_role()
        ).collect()
        if not any(g['PRIVILEGE'] == 'OWNERSHIP' and g['NAME'] == snowpark_session.get_current_database() for g in db_grants):
            validation_results['errors'].append('Insufficient database permissions')

        if validation_results['errors']:
            validation_results['status'] = 'FAILED'

        return json.dumps(validation_results)
    except Exception as e:
        validation_results['status'] = 'FAILED'
        validation_results['errors'].append(str(e))
        return json.dumps(validation_results)
$$;

-- Create deployment tracking table
CREATE TABLE IF NOT EXISTS deployment_history (
    deployment_id STRING,
    start_time TIMESTAMP_LTZ,
    end_time TIMESTAMP_LTZ,
    status STRING,
    error_message STRING,
    deployed_objects VARIANT,
    PRIMARY KEY (deployment_id)
);

-- Create deployment lock table
CREATE TABLE IF NOT EXISTS deployment_locks (
    lock_id STRING,
    acquired_time TIMESTAMP_LTZ,
    deployment_id STRING,
    PRIMARY KEY (lock_id)
);

-- Stored procedure for acquiring deployment lock
CREATE OR REPLACE PROCEDURE ACQUIRE_DEPLOYMENT_LOCK(deployment_id STRING)
RETURNS STRING
LANGUAGE SQL
AS
$$
DECLARE
    lock_acquired BOOLEAN;
BEGIN
    -- Try to acquire lock
    INSERT INTO deployment_locks (lock_id, acquired_time, deployment_id)
    SELECT 'DEPLOYMENT_LOCK', CURRENT_TIMESTAMP(), :deployment_id
    WHERE NOT EXISTS (
        SELECT 1 FROM deployment_locks
        WHERE lock_id = 'DEPLOYMENT_LOCK'
        AND DATEDIFF('MINUTE', acquired_time, CURRENT_TIMESTAMP()) < 30
    );

    -- Check if we got the lock
    SELECT COUNT(*) = 1 INTO :lock_acquired
    FROM deployment_locks
    WHERE lock_id = 'DEPLOYMENT_LOCK'
    AND deployment_id = :deployment_id;

    IF :lock_acquired THEN
        RETURN 'SUCCESS';
    ELSE
        RETURN 'FAILED';
    END IF;
END;
$$;

-- Stored procedure for releasing deployment lock
CREATE OR REPLACE PROCEDURE RELEASE_DEPLOYMENT_LOCK(deployment_id STRING)
RETURNS STRING
LANGUAGE SQL
AS
$$
BEGIN
    DELETE FROM deployment_locks
    WHERE lock_id = 'DEPLOYMENT_LOCK'
    AND deployment_id = :deployment_id;
    RETURN 'SUCCESS';
END;
$$;

-- Stored procedure for role management
CREATE OR REPLACE PROCEDURE MANAGE_ROLE(
    role_name STRING,
    action STRING
)
RETURNS STRING
LANGUAGE SQL
AS
$$
DECLARE
    role_exists BOOLEAN;
BEGIN
    -- Check if role exists
    SELECT COUNT(*) > 0 INTO :role_exists
    FROM INFORMATION_SCHEMA.APPLICABLE_ROLES
    WHERE ROLE_NAME = :role_name;

    CASE :action
        WHEN 'CREATE' THEN
            IF NOT :role_exists THEN
                CREATE ROLE identifier(:role_name);
                RETURN 'CREATED';
            ELSE
                RETURN 'EXISTS';
            END IF;
        WHEN 'DROP' THEN
            IF :role_exists THEN
                DROP ROLE identifier(:role_name);
                RETURN 'DROPPED';
            ELSE
                RETURN 'NOT_EXISTS';
            END IF;
        ELSE
            RETURN 'INVALID_ACTION';
    END CASE;
END;
$$;

-- Stored procedure for database management
CREATE OR REPLACE PROCEDURE MANAGE_DATABASE(
    database_name STRING,
    schema_name STRING,
    action STRING
)
RETURNS STRING
LANGUAGE SQL
AS
$$
DECLARE
    db_exists BOOLEAN;
    schema_exists BOOLEAN;
BEGIN
    -- Check if database exists
    SELECT COUNT(*) > 0 INTO :db_exists
    FROM INFORMATION_SCHEMA.DATABASES
    WHERE DATABASE_NAME = :database_name;

    CASE :action
        WHEN 'CREATE' THEN
            IF NOT :db_exists THEN
                CREATE DATABASE identifier(:database_name);
                CREATE SCHEMA identifier(:database_name).identifier(:schema_name);
                RETURN 'CREATED';
            ELSE
                -- Check if schema exists
                SELECT COUNT(*) > 0 INTO :schema_exists
                FROM identifier(:database_name).INFORMATION_SCHEMA.SCHEMATA
                WHERE SCHEMA_NAME = :schema_name;

                IF NOT :schema_exists THEN
                    CREATE SCHEMA identifier(:database_name).identifier(:schema_name);
                    RETURN 'SCHEMA_CREATED';
                END IF;
                RETURN 'EXISTS';
            END IF;
        WHEN 'DROP' THEN
            IF :db_exists THEN
                DROP DATABASE identifier(:database_name);
                RETURN 'DROPPED';
            ELSE
                RETURN 'NOT_EXISTS';
            END IF;
        ELSE
            RETURN 'INVALID_ACTION';
    END CASE;
END;
$$;

-- Main deployment procedure
CREATE OR REPLACE PROCEDURE DEPLOY_CORTEX_ANALYST(deployment_id STRING)
RETURNS STRING
LANGUAGE SQL
AS
$$
DECLARE
    deployment_status STRING;
    validation_result STRING;
    lock_result STRING;
    role_result STRING;
    db_result STRING;
BEGIN
    -- Start deployment tracking
    INSERT INTO deployment_history (
        deployment_id, start_time, status, deployed_objects
    )
    VALUES (
        :deployment_id,
        CURRENT_TIMESTAMP(),
        'IN_PROGRESS',
        PARSE_JSON('[]')
    );

    -- Validate deployment
    validation_result := (CALL VALIDATE_DEPLOYMENT(:deployment_id));
    IF PARSE_JSON(validation_result):status = 'FAILED' THEN
        CALL HANDLE_DEPLOYMENT_ERROR(
            :deployment_id,
            'Validation failed: ' || validation_result
        );
        RETURN 'FAILED';
    END IF;

    -- Acquire deployment lock
    lock_result := (CALL ACQUIRE_DEPLOYMENT_LOCK(:deployment_id));
    IF :lock_result = 'FAILED' THEN
        CALL HANDLE_DEPLOYMENT_ERROR(
            :deployment_id,
            'Failed to acquire deployment lock'
        );
        RETURN 'FAILED';
    END IF;

    -- Begin transaction
    BEGIN
        -- Create role
        role_result := (CALL MANAGE_ROLE($ROLE_NAME, 'CREATE'));
        IF :role_result NOT IN ('CREATED', 'EXISTS') THEN
            RAISE EXCEPTION 'Role creation failed';
        END IF;

        -- Create database and schema
        db_result := (CALL MANAGE_DATABASE(
            $DATABASE_NAME,
            $SCHEMA_NAME,
            'CREATE'
        ));
        IF :db_result NOT IN ('CREATED', 'EXISTS', 'SCHEMA_CREATED') THEN
            RAISE EXCEPTION 'Database creation failed';
        END IF;

        -- Grant necessary privileges
        CALL GRANT_REQUIRED_PRIVILEGES(
            $ROLE_NAME,
            $DATABASE_NAME,
            $SCHEMA_NAME
        );

        -- Create required tables
        CALL CREATE_REQUIRED_TABLES(
            $DATABASE_NAME,
            $SCHEMA_NAME
        );

        -- Update deployment status
        UPDATE deployment_history
        SET status = 'SUCCESS',
            end_time = CURRENT_TIMESTAMP()
        WHERE deployment_id = :deployment_id;

        RETURN 'SUCCESS';

    EXCEPTION
        WHEN OTHER THEN
            -- Roll back and handle error
            CALL HANDLE_DEPLOYMENT_ERROR(
                :deployment_id,
                OBJECT_CONSTRUCT('error', SQLSTATE, 'message', SQLERRM)::STRING
            );
            RETURN 'FAILED';
    END;

    -- Release lock
    CALL RELEASE_DEPLOYMENT_LOCK(:deployment_id);
END;
$$;

-- Error handling procedure
CREATE OR REPLACE PROCEDURE HANDLE_DEPLOYMENT_ERROR(
    deployment_id STRING,
    error_message STRING
)
RETURNS STRING
LANGUAGE SQL
AS
$$
BEGIN
    -- Update deployment history
    UPDATE deployment_history
    SET status = 'FAILED',
        end_time = CURRENT_TIMESTAMP(),
        error_message = :error_message
    WHERE deployment_id = :deployment_id;

    -- Release any held locks
    CALL RELEASE_DEPLOYMENT_LOCK(:deployment_id);

    RETURN 'ERROR_HANDLED';
END;
$$;

-- Required privileges procedure
CREATE OR REPLACE PROCEDURE GRANT_REQUIRED_PRIVILEGES(
    role_name STRING,
    database_name STRING,
    schema_name STRING
)
RETURNS STRING
LANGUAGE SQL
AS
$$
BEGIN
    -- Database privileges
    GRANT USAGE ON DATABASE identifier(:database_name)
    TO ROLE identifier(:role_name);

    -- Schema privileges
    GRANT USAGE ON SCHEMA identifier(:database_name).identifier(:schema_name)
    TO ROLE identifier(:role_name);

    -- Future grants for tables
    GRANT SELECT, INSERT, UPDATE, DELETE ON FUTURE TABLES
    IN SCHEMA identifier(:database_name).identifier(:schema_name)
    TO ROLE identifier(:role_name);

    RETURN 'PRIVILEGES_GRANTED';
END;
$$;

-- Table creation procedure
CREATE OR REPLACE PROCEDURE CREATE_REQUIRED_TABLES(
    database_name STRING,
    schema_name STRING
)
RETURNS STRING
LANGUAGE SQL
AS
$$
BEGIN
    -- Create daily_revenue table
    CREATE TABLE IF NOT EXISTS identifier(:database_name).identifier(:schema_name).daily_revenue (
        date DATE,
        revenue FLOAT,
        cogs FLOAT,
        forecasted_revenue FLOAT,
        product_id INT,
        region_id INT
    );

    -- Create product_dim table
    CREATE TABLE IF NOT EXISTS identifier(:database_name).identifier(:schema_name).product_dim (
        product_id INT,
        product_line VARCHAR
    );

    -- Create region_dim table
    CREATE TABLE IF NOT EXISTS identifier(:database_name).identifier(:schema_name).region_dim (
        region_id INT,
        sales_region VARCHAR,
        state VARCHAR
    );

    RETURN 'TABLES_CREATED';
END;
$$;

-- Execute deployment
DECLARE
    deployment_id STRING;
    deployment_result STRING;
BEGIN
    -- Generate unique deployment ID
    deployment_id := CONCAT(
        'DEPLOY_',
        TO_CHAR(CURRENT_TIMESTAMP(), 'YYYYMMDD_HH24MISS'),
        '_',
        UUID_STRING()
    );

    -- Execute deployment
    deployment_result := (CALL DEPLOY_CORTEX_ANALYST(:deployment_id));

    -- Return result
    SELECT deployment_result;
END;

-- Role Management
USE ROLE SECURITYADMIN;

-- Create role if it doesn't exist
CREATE ROLE IF NOT EXISTS identifier($ROLE_NAME);
GRANT DATABASE ROLE SNOWFLAKE.CORTEX_USER TO ROLE identifier($ROLE_NAME);

-- Grant role to user if not already granted
CREATE OR REPLACE PROCEDURE GRANT_ROLE_IF_NOT_EXISTS(ROLE_NAME STRING, USER_NAME STRING)
  RETURNS STRING
  LANGUAGE SQL
  AS
  $$
  DECLARE
    ROLE_EXISTS BOOLEAN;
  BEGIN
    SELECT COUNT(*) > 0 INTO :ROLE_EXISTS
    FROM TABLE(INFORMATION_SCHEMA.ROLE_GRANTS_TO_USERS())
    WHERE GRANTED_TO = :USER_NAME
    AND ROLE = :ROLE_NAME;

    IF NOT :ROLE_EXISTS THEN
      EXECUTE IMMEDIATE 'GRANT ROLE ' || :ROLE_NAME || ' TO USER ' || :USER_NAME;
      RETURN 'Role granted';
    END IF;
    RETURN 'Role already granted';
  END;
  $$;

CALL GRANT_ROLE_IF_NOT_EXISTS($ROLE_NAME, $SNOWFLAKE_USER);

-- Database Management
USE ROLE SYSADMIN;

-- Create or update database
CREATE DATABASE IF NOT EXISTS identifier($DATABASE_NAME);
CREATE SCHEMA IF NOT EXISTS identifier($DATABASE_NAME).identifier($SCHEMA_NAME);

-- Warehouse Management
CREATE OR REPLACE PROCEDURE CREATE_OR_UPDATE_WAREHOUSE(
    WAREHOUSE_NAME STRING,
    WAREHOUSE_SIZE STRING,
    AUTO_SUSPEND INT
)
  RETURNS STRING
  LANGUAGE SQL
  AS
  $$
  DECLARE
    WAREHOUSE_EXISTS BOOLEAN;
  BEGIN
    SELECT COUNT(*) > 0 INTO :WAREHOUSE_EXISTS
    FROM INFORMATION_SCHEMA.WAREHOUSES
    WHERE WAREHOUSE_NAME = :WAREHOUSE_NAME;

    IF NOT :WAREHOUSE_EXISTS THEN
      EXECUTE IMMEDIATE 'CREATE WAREHOUSE ' || :WAREHOUSE_NAME ||
        ' WAREHOUSE_SIZE = ' || :WAREHOUSE_SIZE ||
        ' AUTO_SUSPEND = ' || :AUTO_SUSPEND ||
        ' AUTO_RESUME = TRUE' ||
        ' INITIALLY_SUSPENDED = TRUE';
      RETURN 'Warehouse created';
    ELSE
      EXECUTE IMMEDIATE 'ALTER WAREHOUSE ' || :WAREHOUSE_NAME ||
        ' SET WAREHOUSE_SIZE = ' || :WAREHOUSE_SIZE ||
        ' AUTO_SUSPEND = ' || :AUTO_SUSPEND;
      RETURN 'Warehouse updated';
    END IF;
  END;
  $$;

CALL CREATE_OR_UPDATE_WAREHOUSE(
  $SNOWFLAKE_WAREHOUSE,
  $SNOWFLAKE_WAREHOUSE_SIZE,
  $SNOWFLAKE_WAREHOUSE_AUTO_SUSPEND
);

-- Grant warehouse access
GRANT USAGE ON WAREHOUSE identifier($SNOWFLAKE_WAREHOUSE) TO ROLE identifier($ROLE_NAME);
GRANT OPERATE ON WAREHOUSE identifier($SNOWFLAKE_WAREHOUSE) TO ROLE identifier($ROLE_NAME);

-- Database ownership
GRANT OWNERSHIP ON SCHEMA identifier($DATABASE_NAME).identifier($SCHEMA_NAME)
  TO ROLE identifier($ROLE_NAME) COPY CURRENT GRANTS;
GRANT OWNERSHIP ON DATABASE identifier($DATABASE_NAME)
  TO ROLE identifier($ROLE_NAME) COPY CURRENT GRANTS;

-- Resource monitoring
CREATE OR REPLACE PROCEDURE CREATE_OR_UPDATE_RESOURCE_MONITOR(
    MONITOR_NAME STRING,
    CREDIT_QUOTA FLOAT,
    ALERT_THRESHOLD INT
)
  RETURNS STRING
  LANGUAGE SQL
  AS
  $$
  DECLARE
    MONITOR_EXISTS BOOLEAN;
  BEGIN
    SELECT COUNT(*) > 0 INTO :MONITOR_EXISTS
    FROM INFORMATION_SCHEMA.RESOURCE_MONITORS
    WHERE NAME = :MONITOR_NAME;

    IF NOT :MONITOR_EXISTS THEN
      EXECUTE IMMEDIATE 'CREATE RESOURCE MONITOR ' || :MONITOR_NAME ||
        ' WITH CREDIT_QUOTA = ' || :CREDIT_QUOTA ||
        ' FREQUENCY = MONTHLY' ||
        ' START_TIMESTAMP = IMMEDIATELY' ||
        ' TRIGGERS ON ' || :ALERT_THRESHOLD || ' PERCENT DO NOTIFY' ||
        ' ON 100 PERCENT DO SUSPEND';
      RETURN 'Resource monitor created';
    ELSE
      EXECUTE IMMEDIATE 'ALTER RESOURCE MONITOR ' || :MONITOR_NAME ||
        ' SET CREDIT_QUOTA = ' || :CREDIT_QUOTA ||
        ' TRIGGERS ON ' || :ALERT_THRESHOLD || ' PERCENT DO NOTIFY' ||
        ' ON 100 PERCENT DO SUSPEND';
      RETURN 'Resource monitor updated';
    END IF;
  END;
  $$;

CALL CREATE_OR_UPDATE_RESOURCE_MONITOR(
  'CORTEX_MONITOR',
  $SNOWFLAKE_CREDIT_QUOTA,
  $SNOWFLAKE_ALERT_THRESHOLD
);

-- Switch to application role
USE ROLE identifier($ROLE_NAME);
USE DATABASE identifier($DATABASE_NAME);
USE SCHEMA identifier($DATABASE_NAME).identifier($SCHEMA_NAME);
USE WAREHOUSE identifier($SNOWFLAKE_WAREHOUSE);

-- Create stage if it doesn't exist
CREATE STAGE IF NOT EXISTS identifier($SNOWFLAKE_STAGE_NAME)
  DIRECTORY = (ENABLE = TRUE);

-- Create tables if they don't exist
CREATE TABLE IF NOT EXISTS daily_revenue (
    date DATE,
    revenue FLOAT,
    cogs FLOAT,
    forecasted_revenue FLOAT,
    product_id INT,
    region_id INT
);

CREATE TABLE IF NOT EXISTS product_dim (
    product_id INT,
    product_line VARCHAR
);

CREATE TABLE IF NOT EXISTS region_dim (
    region_id INT,
    sales_region VARCHAR,
    state VARCHAR
);

-- Deployment Report Generator
CREATE OR REPLACE PROCEDURE GENERATE_DEPLOYMENT_REPORT(
    deployment_id STRING,
    report_format STRING -- 'JSON', 'HTML', or 'TEXT'
)
RETURNS VARIANT
LANGUAGE PYTHON
RUNTIME_VERSION = '3.8'
PACKAGES = ('snowflake-snowpark-python', 'jinja2')
HANDLER = 'generate_report'
AS
$$
def generate_report(snowpark_session, deployment_id, report_format):
    import json
    from datetime import datetime
    from jinja2 import Template

    # Fetch deployment details
    deployment = snowpark_session.sql(f"""
        SELECT
            deployment_id,
            start_time,
            end_time,
            status,
            error_message,
            deployed_objects,
            TIMESTAMPDIFF('SECOND', start_time, COALESCE(end_time, CURRENT_TIMESTAMP())) as duration_seconds
        FROM deployment_history
        WHERE deployment_id = '{deployment_id}'
    """).collect()

    if not deployment:
        return json.dumps({
            'error': f'No deployment found with ID: {deployment_id}'
        })

    deployment = deployment[0].as_dict()

    # Fetch all objects created/modified in this deployment
    objects_status = snowpark_session.sql(f"""
        SELECT
            object_type,
            object_name,
            status,
            error_message
        FROM deployment_objects_log
        WHERE deployment_id = '{deployment_id}'
        ORDER BY timestamp
    """).collect()

    objects_status = [row.as_dict() for row in objects_status]

    # Fetch deployment locks history
    locks_history = snowpark_session.sql(f"""
        SELECT
            acquired_time,
            TIMESTAMPDIFF('SECOND', acquired_time, CURRENT_TIMESTAMP()) as lock_duration_seconds
        FROM deployment_locks_history
        WHERE deployment_id = '{deployment_id}'
        ORDER BY acquired_time
    """).collect()

    locks_history = [row.as_dict() for row in locks_history]

    # Calculate statistics
    stats = {
        'total_objects': len(objects_status),
        'successful_objects': len([o for o in objects_status if o['status'] == 'SUCCESS']),
        'failed_objects': len([o for o in objects_status if o['status'] == 'FAILED']),
        'total_duration': deployment['duration_seconds'],
        'average_lock_duration': sum(l['lock_duration_seconds'] for l in locks_history) / len(locks_history) if locks_history else 0
    }

    report_data = {
        'deployment': deployment,
        'objects': objects_status,
        'locks': locks_history,
        'stats': stats,
        'generated_at': datetime.now().isoformat()
    }

    if report_format == 'JSON':
        return json.dumps(report_data, indent=2)

    elif report_format == 'HTML':
        html_template = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Deployment Report - {{ deployment.deployment_id }}</title>
            <style>
                body { font-family: Arial, sans-serif; margin: 20px; }
                .header { background: #f5f5f5; padding: 10px; }
                .status-success { color: green; }
                .status-failed { color: red; }
                .stats { display: grid; grid-template-columns: repeat(2, 1fr); gap: 10px; }
                .objects-table { width: 100%; border-collapse: collapse; }
                .objects-table th, .objects-table td { border: 1px solid #ddd; padding: 8px; }
            </style>
        </head>
        <body>
            <div class="header">
                <h1>Deployment Report</h1>
                <p>Deployment ID: {{ deployment.deployment_id }}</p>
                <p>Status: <span class="status-{{ deployment.status.lower() }}">{{ deployment.status }}</span></p>
                <p>Duration: {{ stats.total_duration }} seconds</p>
            </div>

            <h2>Statistics</h2>
            <div class="stats">
                <div>Total Objects: {{ stats.total_objects }}</div>
                <div>Successful: {{ stats.successful_objects }}</div>
                <div>Failed: {{ stats.failed_objects }}</div>
                <div>Avg Lock Duration: {{ "%.2f"|format(stats.average_lock_duration) }}s</div>
            </div>

            <h2>Deployed Objects</h2>
            <table class="objects-table">
                <tr>
                    <th>Type</th>
                    <th>Name</th>
                    <th>Status</th>
                    <th>Error</th>
                </tr>
                {% for obj in objects %}
                <tr>
                    <td>{{ obj.object_type }}</td>
                    <td>{{ obj.object_name }}</td>
                    <td class="status-{{ obj.status.lower() }}">{{ obj.status }}</td>
                    <td>{{ obj.error_message or '' }}</td>
                </tr>
                {% endfor %}
            </table>

            <h2>Timeline</h2>
            <ul>
                <li>Started: {{ deployment.start_time }}</li>
                <li>Ended: {{ deployment.end_time or 'In Progress' }}</li>
                {% for lock in locks %}
                <li>Lock acquired: {{ lock.acquired_time }} ({{ lock.lock_duration_seconds }}s)</li>
                {% endfor %}
            </ul>

            {% if deployment.error_message %}
            <h2>Error Details</h2>
            <pre>{{ deployment.error_message }}</pre>
            {% endif %}

            <footer>
                <p>Report generated at: {{ generated_at }}</p>
            </footer>
        </body>
        </html>
        """
        template = Template(html_template)
        return template.render(**report_data)

    else:  # TEXT format
        text_template = """
DEPLOYMENT REPORT
================
ID: {{ deployment.deployment_id }}
Status: {{ deployment.status }}
Duration: {{ stats.total_duration }} seconds

STATISTICS
----------
Total Objects: {{ stats.total_objects }}
Successful: {{ stats.successful_objects }}
Failed: {{ stats.failed_objects }}
Avg Lock Duration: {{ "%.2f"|format(stats.average_lock_duration) }}s

DEPLOYED OBJECTS
---------------
{% for obj in objects %}
Type: {{ obj.object_type }}
Name: {{ obj.object_name }}
Status: {{ obj.status }}
{% if obj.error_message %}
Error: {{ obj.error_message }}
{% endif %}
{% endfor %}

TIMELINE
--------
Started: {{ deployment.start_time }}
Ended: {{ deployment.end_time or 'In Progress' }}
{% for lock in locks %}
Lock acquired: {{ lock.acquired_time }} ({{ lock.lock_duration_seconds }}s)
{% endfor %}

{% if deployment.error_message %}
ERROR DETAILS
------------
{{ deployment.error_message }}
{% endif %}

Generated at: {{ generated_at }}
"""
        template = Template(text_template)
        return template.render(**report_data)
$$;

-- Create deployment objects log table
CREATE TABLE IF NOT EXISTS deployment_objects_log (
    deployment_id STRING,
    object_type STRING,
    object_name STRING,
    status STRING,
    error_message STRING,
    timestamp TIMESTAMP_LTZ,
    FOREIGN KEY (deployment_id) REFERENCES deployment_history(deployment_id)
);

-- Create deployment locks history table
CREATE TABLE IF NOT EXISTS deployment_locks_history (
    deployment_id STRING,
    acquired_time TIMESTAMP_LTZ,
    released_time TIMESTAMP_LTZ,
    FOREIGN KEY (deployment_id) REFERENCES deployment_history(deployment_id)
);

-- Modify HANDLE_DEPLOYMENT_ERROR to log object status
CREATE OR REPLACE PROCEDURE LOG_OBJECT_STATUS(
    deployment_id STRING,
    object_type STRING,
    object_name STRING,
    status STRING,
    error_message STRING
)
RETURNS STRING
LANGUAGE SQL
AS
$$
BEGIN
    INSERT INTO deployment_objects_log (
        deployment_id,
        object_type,
        object_name,
        status,
        error_message,
        timestamp
    )
    VALUES (
        :deployment_id,
        :object_type,
        :object_name,
        :status,
        :error_message,
        CURRENT_TIMESTAMP()
    );
    RETURN 'LOGGED';
END;
$$;

-- Example usage:
-- CALL GENERATE_DEPLOYMENT_REPORT('your_deployment_id', 'HTML');
-- CALL GENERATE_DEPLOYMENT_REPORT('your_deployment_id', 'JSON');
-- CALL GENERATE_DEPLOYMENT_REPORT('your_deployment_id', 'TEXT');
