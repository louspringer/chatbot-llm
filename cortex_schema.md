# Deploy Cortex Analyst Test Schema

## Overview
Deploy the revenue timeseries demo schema from [Snowflake's Cortex Analyst Quickstart](https://quickstarts.snowflake.com/guide/getting_started_with_cortex_analyst/index.html?index=..%2F..index#0). This provides a sample financial dataset for development and testing.

## Dependencies
- 🔄 Access Control (Issue #11) - for schema permissions
- 🔄 Key Vault Integration (Issue #11) - for secure credential management

## Required Implementation

### 1. Development Environment Setup
- [ ] Configure Snowflake development database
  - Create CORTEX_ANALYST_DEMO database
  - Create REVENUE_TIMESERIES schema
  - Set up CORTEX_USER_ROLE
  - Configure CORTEX_ANALYST_WH warehouse
- [ ] Set up test data loading
  - Create RAW_DATA stage
  - Import sample CSVs:
    - daily_revenue.csv
    - region.csv
    - product.csv
  - Import semantic model:
    - revenue_timeseries.yaml

### 2. Schema Deployment
- [ ] Deploy quickstart schema
  - Create fact table: DAILY_REVENUE
  - Create dimension tables:
    - PRODUCT_DIM
    - REGION_DIM
  - Load sample data
  - Verify data loaded correctly
- [ ] Configure Cortex Search
  - Set up search service
  - Enable literal string searches
  - Verify search functionality

### 3. Integration Testing
- [ ] Basic validation
  - Test sample queries from quickstart
  - Verify data relationships
  - Check search integration
- [ ] Set up test queries
  - Document test cases
  - Create test scripts
  - Verify expected results

## Documentation
- Schema layout (fact/dimension tables)
- Sample queries from quickstart
- Setup instructions
- Data refresh process

## Success Criteria
- Demo schema deployed
- Sample data loaded
- Basic queries working
- Search service configured
- Access controls verified

## References
- [Snowflake Quickstart: Getting Started with Cortex Framework - Analyst](https://quickstarts.snowflake.com/guide/getting_started_with_cortex_analyst/index.html?index=..%2F..index#0)
- [Source Code on GitHub](https://github.com/Snowflake-Labs/cortex-framework-getting-started)

## Labels
- cortex
- schema
- snowflake
- high-priority
