from pymongo import MongoClient
from bson import Binary
import bcrypt
import datetime

# Connect to MongoDB Atlas
client = MongoClient("mongodb+srv://abhishelke2971:Abhi297127@abhi1792.942ohkd.mongodb.net/attendance_db?retryWrites=true&w=majority")
db = client["attendance_db"]

# Function to hash password and return Binary format
def hash_password_bson(plain_password):
    hashed = bcrypt.hashpw(plain_password.encode('utf-8'), bcrypt.gensalt())
    return Binary(hashed)

# Insert admin manually
admin_data = {
    "username": "abhishek",
    "password": hash_password_bson("admin@123"),
    "role": "admin",
    "created_at": datetime.datetime.utcnow()
}
db.admins.insert_one(admin_data)
print(" Admin inserted successfully.")

# Insert employee manually
employee_data = {
    "username": "emp001",
    "password": hash_password_bson("emp@123"),
    "role": "employee",
    "created_at": datetime.datetime.utcnow()
}
db.users.insert_one(employee_data)
print("Employee inserted successfully.")
