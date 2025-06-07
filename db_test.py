# MongoDB数据库连接测试
from pymongo import MongoClient

def test_mongodb_connection():
    try:
        client = MongoClient('mongodb://localhost:27017/', serverSelectionTimeoutMS=3000)
        # 尝试获取服务器信息
        info = client.server_info()
        print("MongoDB 连接成功！")
        print("服务器信息：", info)
    except Exception as e:
        print("MongoDB 连接失败：", e)

if __name__ == "__main__":
    test_mongodb_connection()