import os
import mysql.connector
from mysql.connector import Error

def get_connection():
    try:
        connection = mysql.connector.connect(
            host='localhost',
            user='root',
            password=os.getenv('MYSQL_PASSWORD'),
            database='inventory_db'
        )
        if connection.is_connected():
            return connection
        
    except Error as error:
        print('Database connection error:', error)

    return None