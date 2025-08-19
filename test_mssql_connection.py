
import django
from django.conf import settings
from django.db import connections
from django.db.utils import OperationalError

def test_mssql_connection():
    # Check the mssql database connection
    db_connection = connections['mssql']  # Use the 'mssql' connection name
    try:
        db_connection.ensure_connection()
        print("Connection to 'mssql' successful!")
    except OperationalError as e:
        print("Connection to 'mssql' failed!")
        print(f"Error: {e}")

if __name__ == "__main__":
    # Configure settings if not running within Django context
    if not settings.configured:
        import os
        os.environ.setdefault("DJANGO_SETTINGS_MODULE", "runsheet.settings")
        django.setup()
    
    test_mssql_connection()












# import pyodbc

# # Connection parameters
# server = 'EF01DBS3B'  # Replace with your SQL Server hostname or IP
# database = 'DTDev'  # Replace with your database name
# username = 'ARCHBNE\\welshs'  # Replace with your domain and username
# password = 'Yah00$h1nyNewT0y'  # Replace with your password
# driver = 'ODBC Driver 17 for SQL Server'  # Replace with the correct ODBC driver version

# try:
#     # Establish connection
#     connection = pyodbc.connect(
#         f"DRIVER={{{driver}}};"
#         f"SERVER={server};"
#         f"DATABASE={database};"
#         f"UID={username};"
#         f"PWD={password};"
#     )
#     print("Connection successful!")

#     # Create a cursor to run SQL queries
#     cursor = connection.cursor()

#     # Example query
#     cursor.execute("SELECT @@VERSION;")
#     row = cursor.fetchone()

#     # Print SQL Server version
#     print(f"SQL Server Version: {row[0]}")

#     # Close the connection
#     cursor.close()
#     connection.close()
#     print("Connection closed.")

# except pyodbc.Error as e:
#     print("Error while connecting to SQL Server:", e)
