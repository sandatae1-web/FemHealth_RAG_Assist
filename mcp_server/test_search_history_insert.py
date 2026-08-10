#!/usr/bin/env python3
"""
Test script to verify search history table INSERT works correctly.
Run this to diagnose why search history isn't being logged.
"""

import sys
import os
import uuid
from datetime import datetime, timezone

# Add parent directory to path to import lakebase
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import lakebase

def test_search_history_insert():
    """Test inserting a record into health_search_history."""
    
    print("\n" + "="*60)
    print("Testing health_search_history table INSERT")
    print("="*60 + "\n")
    
    # Test parameters
    test_search_id = str(uuid.uuid4())
    test_user_id = "test@femlens.health"
    test_query = "Test search query for menopause"
    test_search_type = "semantic_vector"
    test_result_count = 5
    test_timestamp = datetime.now(timezone.utc)
    
    print(f"Test data:")
    print(f"  search_id: {test_search_id}")
    print(f"  user_id: {test_user_id}")
    print(f"  search_query: {test_query}")
    print(f"  search_type: {test_search_type}")
    print(f"  result_count: {test_result_count}")
    print(f"  created_at: {test_timestamp}")
    print()
    
    # Step 1: Check if table exists
    print("Step 1: Checking if table exists...")
    try:
        check_table_sql = """
        SELECT EXISTS (
            SELECT FROM information_schema.tables 
            WHERE table_name = 'health_search_history'
        )
        """
        result = lakebase.run_query(check_table_sql)
        table_exists = result[0]['exists'] if result else False
        
        if table_exists:
            print("  ✅ Table 'health_search_history' exists")
        else:
            print("  ❌ Table 'health_search_history' does NOT exist")
            print("  Please run sql/01_setup_health_search_history _table.sql first")
            return
    except Exception as e:
        print(f"  ❌ Error checking table: {e}")
        return
    
    # Step 2: Check table schema
    print("\nStep 2: Checking table schema...")
    try:
        schema_sql = """
        SELECT column_name, data_type, is_nullable
        FROM information_schema.columns
        WHERE table_name = 'health_search_history'
        ORDER BY ordinal_position
        """
        columns = lakebase.run_query(schema_sql)
        print("  Current schema:")
        for col in columns:
            print(f"    - {col['column_name']}: {col['data_type']} (nullable: {col['is_nullable']})")
    except Exception as e:
        print(f"  ⚠️  Could not fetch schema: {e}")
    
    # Step 3: Attempt INSERT
    print("\nStep 3: Attempting INSERT...")
    try:
        insert_sql = """
        INSERT INTO health_search_history 
            (search_id, user_id, search_query, search_type, result_count, created_at)
        VALUES (%s, %s, %s, %s, %s, %s)
        """
        
        rows_affected = lakebase.run_write(insert_sql, (
            test_search_id,
            test_user_id,
            test_query,
            test_search_type,
            test_result_count,
            test_timestamp
        ))
        
        print(f"  ✅ INSERT successful! Rows affected: {rows_affected}")
    except Exception as e:
        print(f"  ❌ INSERT failed: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # Step 4: Verify the INSERT
    print("\nStep 4: Verifying the inserted record...")
    try:
        verify_sql = """
        SELECT search_id, user_id, search_query, search_type, result_count, created_at
        FROM health_search_history
        WHERE search_id = %s
        """
        
        rows = lakebase.run_query(verify_sql, (test_search_id,))
        
        if rows:
            print("  ✅ Record found in database:")
            for key, value in rows[0].items():
                print(f"    - {key}: {value}")
        else:
            print("  ❌ Record NOT found in database (but INSERT reported success)")
    except Exception as e:
        print(f"  ❌ Verification query failed: {e}")
    
    # Step 5: Count total records
    print("\nStep 5: Checking total records in table...")
    try:
        count_sql = "SELECT COUNT(*) as total FROM health_search_history"
        result = lakebase.run_query(count_sql)
        total = result[0]['total'] if result else 0
        print(f"  Total records in health_search_history: {total}")
    except Exception as e:
        print(f"  ⚠️  Could not count records: {e}")
    
    print("\n" + "="*60)
    print("Test complete!")
    print("="*60 + "\n")

if __name__ == "__main__":
    test_search_history_insert()