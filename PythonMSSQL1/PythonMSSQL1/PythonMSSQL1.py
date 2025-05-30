
import pandas as pd
import pyodbc

# Connection details
server = 'DESKTOP-1GV96N5\MSSQLSERVER01'
database = 'master'
username = 'sa'
password = 'abc123'

connection_string = f"DRIVER={{ODBC Driver 17 for SQL Server}};SERVER={server};DATABASE={database};UID={username};PWD={password};Trusted_Connection=yes"

try:
    # Establish the connection
    connection = pyodbc.connect(connection_string)
    print("Connection successful!")

    # Create a cursor
    cursor = connection.cursor()

    # Insert data
    #query = "select * FROM [master].[dbo].[Employees]" # (column1, column2) VALUES (?, ?)"  # Replace with your table name and columns
    #data = ("value1", "value2")  # Replace with your values
    #cursor.execute(query, data)
    query = "SELECT * FROM Employees"
    value = "search_value"
    cursor.execute(query)
    records = cursor.fetchall()
    for r in records:
        print(f"{r}")
    # Commit the transaction
    #connection.commit()
    #print("Data inserted successfully!")

    # Close the connection
    cursor.close()
    connection.close()
    print("Connection closed.")
except Exception as e:
    print(f"Error: {e}")
