# SINGLE DATABASE CONFIGURATION GUIDE

## ✅ Perfect! Your system is now FULLY MODULAR

You now have **ONE SINGLE PLACE** to configure your database that updates **EVERYWHERE** automatically!

## 🎯 How to Switch to Your New Database

### Method 1: Edit the Central Config File (Recommended)

**File to edit**: `shared_config.py`

Just update these values in the `GlobalDatabaseConfig` class (around line 30):

```python
# Your new PostgreSQL database settings
db_type: str = os.getenv("DB_TYPE", "postgresql")
db_host: str = os.getenv("DB_HOST", "localhost")  # ✅ Already correct
db_port: int = int(os.getenv("DB_PORT", "5432"))  # ✅ Already correct  
db_name: str = os.getenv("DB_NAME", "mywebshop")  # ✅ Already correct
db_schema: str = os.getenv("DB_SCHEMA", "webshop")  # ✅ Already correct
db_user: str = os.getenv("DB_USER", "postgres")  # Change to "juli" if needed
db_password: str = os.getenv("DB_PASSWORD", "")  # Add your password here
```

### Method 2: Use Environment Variables (Even Better!)

Create or update the `.env` file in the root directory:

```bash
# PostgreSQL Database Configuration - SINGLE SOURCE OF TRUTH
DB_TYPE=postgresql
DB_HOST=localhost
DB_PORT=5432
DB_NAME=mywebshop
DB_SCHEMA=webshop
DB_USER=postgres
# Or use: DB_USER=juli
DB_PASSWORD=your_actual_password_here
```

## 🚀 What Happens Automatically

Once you update either the config file or .env file, **ALL** of these will automatically use your new database:

✅ **Synthetic Data Service** - Generates data in your new database  
✅ **MCP Server** - Connects agents to your new database  
✅ **Agent System** - All agents query your new database  
✅ **All Database Connections** - Every part of the system  

## 🔧 Test Your Configuration

Run this command to verify your settings:

```bash
python shared_config.py
```

Or:

```bash
python update_database_config.py --show
```

## 🎯 Your Database Details

```
Host: localhost (or 127.0.0.1)
Port: 5432 (default PostgreSQL port)
Database: mywebshop
Schema: webshop
Users: postgres or juli (both have superuser privileges)

Connection String: postgresql://postgres:password@localhost:5432/mywebshop
JDBC URL: jdbc:postgresql://localhost:5432/mywebshop
```

## ⚡ That's It!

You literally just need to:
1. **Edit ONE file**: `shared_config.py` (or the `.env` file)
2. **Change the password**: Add your actual password
3. **Restart your services**: Everything will connect to your new database

The modular design is working perfectly! 🎉

## 🔍 Verification

After making changes, you can verify everything is working by:

1. Check configuration: `python shared_config.py`
2. Test database connection: `python synthetic_data_service/quick_setup.py --dry-run`
3. Run the agent system and see it connects to your new database

## 📁 Files That Were Modified

- ✅ `shared_config.py` - **The SINGLE source of truth**
- ✅ `synthetic_data_service/config.py` - Now uses shared config
- ✅ `mcp_server/config.py` - Now uses shared config
- ✅ All other components automatically inherit from shared config

**Result**: Change 1 file → Everything updates! 🚀