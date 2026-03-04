# Create a test file
import certifi
from pymongo import MongoClient
import ssl
import sys

# 👇 PASTE YOUR CONNECTION STRING HERE
uri = "mongodb+srv://grocery_data:wAidYBoDaEDuXJoa@cluster0.ldxmerg.mongodb.net/groceryfood?retryWrites=true&w=majority&appName=Cluster0"

print("Testing MongoDB Atlas connection...")
print(f"Using certifi from: {certifi.where()}")

try:
    # Try connection with certifi
    client = MongoClient(uri, tlsCAFile=certifi.where())
    client.admin.command('ping')
    print("✅ SUCCESS! Connected to MongoDB Atlas")
    
    # List databases
    dbs = client.list_database_names()
    print(f"Available databases: {dbs}")
    
except Exception as e:
    print(f"❌ FAILED: {e}")
    
    # Try alternative method for debugging
    print("\nTrying alternative connection method...")
    try:
        client = MongoClient(uri, tlsAllowInvalidCertificates=True)
        client.admin.command('ping')
        print("✅ SUCCESS with tlsAllowInvalidCertificates=True (development only)")
    except Exception as e2:
        print(f"❌ Also failed: {e2}")

# Run the test
