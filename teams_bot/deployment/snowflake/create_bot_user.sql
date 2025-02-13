/*
 * Ontology: bot:BotUser
 * Implements: bot:TeamsBot
 * Requirement: REQ-SEC-001 Secure bot user creation and management
 * Guidance: guidance:SecurityPatterns#ServiceAccountCreation
 * Description: Creates and configures the Teams bot service account with appropriate security settings
 */

-- Create database and schema
USE ROLE ACCOUNTADMIN;
CREATE DATABASE IF NOT EXISTS TEAMS_BOT_DB;
USE DATABASE TEAMS_BOT_DB;
CREATE SCHEMA IF NOT EXISTS PUBLIC;

/*
 * Implements: bot:TeamsBotRole
 * Description: Creates the bot role with required permissions
 */
USE ROLE SECURITYADMIN;
CREATE ROLE IF NOT EXISTS TEAMS_BOT_ROLE;
CREATE USER IF NOT EXISTS TEAMS_BOT_USER
  RSA_PUBLIC_KEY = '{{BOT_PUBLIC_KEY}}'
  DEFAULT_ROLE = TEAMS_BOT_ROLE
  MUST_CHANGE_PASSWORD = FALSE;
GRANT ROLE TEAMS_BOT_ROLE TO USER TEAMS_BOT_USER;

/*
 * Implements: bot:QueryPermission, bot:DataReadPermission
 * Description: Grants necessary permissions to the bot role
 */
USE ROLE ACCOUNTADMIN;
GRANT USAGE ON WAREHOUSE COMPUTE_WH TO ROLE TEAMS_BOT_ROLE;
GRANT USAGE, CREATE SCHEMA ON DATABASE TEAMS_BOT_DB TO ROLE TEAMS_BOT_ROLE;
GRANT ALL ON SCHEMA PUBLIC TO ROLE TEAMS_BOT_ROLE;
GRANT USAGE ON FUTURE SCHEMAS IN DATABASE TEAMS_BOT_DB TO ROLE TEAMS_BOT_ROLE;
GRANT SELECT ON ALL TABLES IN DATABASE TEAMS_BOT_DB TO ROLE TEAMS_BOT_ROLE;
GRANT SELECT ON FUTURE TABLES IN DATABASE TEAMS_BOT_DB TO ROLE TEAMS_BOT_ROLE;

/*
 * Implements: bot:KeyRotationProcedure
 * Description: Creates stored procedure for secure key rotation
 */
USE DATABASE TEAMS_BOT_DB;
USE SCHEMA PUBLIC;

CREATE OR REPLACE PROCEDURE ROTATE_BOT_KEY(PUBLIC_KEY STRING)
  RETURNS STRING
  LANGUAGE SQL
  EXECUTE AS CALLER
AS
$$
BEGIN
  ALTER USER TEAMS_BOT_USER SET RSA_PUBLIC_KEY = :PUBLIC_KEY;
  RETURN 'Successfully rotated public key for TEAMS_BOT_USER';
END;
$$;

-- Grant procedure execution
GRANT USAGE ON PROCEDURE ROTATE_BOT_KEY(STRING) TO ROLE TEAMS_BOT_ROLE;

/*
 * Validation section
 */
-- Validate setup
SHOW DATABASES LIKE 'TEAMS_BOT_DB';
SHOW USERS LIKE 'TEAMS_BOT_USER';
SHOW ROLES LIKE 'TEAMS_BOT_ROLE';
SHOW GRANTS TO USER TEAMS_BOT_USER;

/*
 * Security Audit Log table
 * Implements: bot:SecurityAuditLog
 */
CREATE TABLE IF NOT EXISTS security_audit_log (
    event_id NUMBER AUTOINCREMENT,
    event_type VARCHAR NOT NULL,
    event_timestamp TIMESTAMP_LTZ DEFAULT CURRENT_TIMESTAMP(),
    user_name VARCHAR,
    role_name VARCHAR,
    action_taken VARCHAR,
    status VARCHAR,
    error_message VARCHAR,
    PRIMARY KEY (event_id)
);

-- Grant audit log access
GRANT INSERT ON TABLE security_audit_log TO ROLE TEAMS_BOT_ROLE;

/*
 * Monitoring and Alerting
 * Implements: bot:SecurityMonitoring
 */
CREATE OR REPLACE PROCEDURE LOG_SECURITY_EVENT(
    event_type STRING,
    user_name STRING,
    role_name STRING,
    action_taken STRING,
    status STRING,
    error_message STRING
)
RETURNS STRING
LANGUAGE SQL
AS
$$
BEGIN
    INSERT INTO security_audit_log (
        event_type,
        user_name,
        role_name,
        action_taken,
        status,
        error_message
    )
    VALUES (
        :event_type,
        :user_name,
        :role_name,
        :action_taken,
        :status,
        :error_message
    );
    RETURN 'Event logged successfully';
END;
$$;

-- Grant logging procedure access
GRANT USAGE ON PROCEDURE LOG_SECURITY_EVENT(STRING, STRING, STRING, STRING, STRING, STRING)
TO ROLE TEAMS_BOT_ROLE;
