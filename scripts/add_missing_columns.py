#!/usr/bin/env python
"""
Script untuk menambahkan kolom current_price dan pnl ke tabel trades di PostgreSQL
"""

import os
import sys
import logging
from dotenv import load_dotenv
import psycopg2

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Add parent directory to path to import from src
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load environment variables
load_dotenv()

def add_missing_columns():
    """Add missing columns to trades table in PostgreSQL"""
    try:
        # Get PostgreSQL connection details from environment variables
        pg_host = os.getenv("POSTGRES_HOST", "localhost")
        pg_port = os.getenv("POSTGRES_PORT", "5432")
        pg_db = os.getenv("POSTGRES_DB", "trading")
        pg_user = os.getenv("POSTGRES_USER", "postgres")
        pg_password = os.getenv("POSTGRES_PASSWORD", "postgres")
        
        # Connect to PostgreSQL
        conn = psycopg2.connect(
            host=pg_host,
            port=pg_port,
            dbname=pg_db,
            user=pg_user,
            password=pg_password
        )
        
        # Create a cursor
        cursor = conn.cursor()
        
        # Check if columns exist
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'trades' 
            AND (column_name = 'current_price' OR column_name = 'pnl')
        """)
        
        existing_columns = [row[0] for row in cursor.fetchall()]
        
        # Add current_price column if it doesn't exist
        if 'current_price' not in existing_columns:
            logger.info("Adding current_price column to trades table")
            cursor.execute("""
                ALTER TABLE trades 
                ADD COLUMN current_price NUMERIC
            """)
            logger.info("Added current_price column successfully")
        else:
            logger.info("current_price column already exists")
        
        # Add pnl column if it doesn't exist
        if 'pnl' not in existing_columns:
            logger.info("Adding pnl column to trades table")
            cursor.execute("""
                ALTER TABLE trades 
                ADD COLUMN pnl NUMERIC
            """)
            logger.info("Added pnl column successfully")
        else:
            logger.info("pnl column already exists")
        
        # Commit the changes
        conn.commit()
        
        # Close the cursor and connection
        cursor.close()
        conn.close()
        
        logger.info("Database update completed successfully")
        return True
    
    except Exception as e:
        logger.error(f"Error updating database: {e}")
        return False

if __name__ == "__main__":
    logger.info("Starting database update script")
    success = add_missing_columns()
    if success:
        logger.info("Database update completed successfully")
    else:
        logger.error("Database update failed")
