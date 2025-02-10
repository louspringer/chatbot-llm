#!/usr/bin/env python3
"""Simple Snowpark connection test"""

from snowflake.snowpark import Session


def main():
    print("Testing Snowpark connection...")
    try:
        # Create session with minimal config
        session = Session.builder.configs({}).create()
        print("✓ Session created successfully")

        # Run test query
        result = session.sql(
            "SELECT CURRENT_WAREHOUSE() as warehouse"
        ).collect()
        print(f"✓ Connected to warehouse: {result[0]['WAREHOUSE']}")

        session.close()
        print("✓ Test completed successfully")

    except Exception as e:
        print(f"❌ Error: {str(e)}")
        raise


if __name__ == "__main__":
    main()