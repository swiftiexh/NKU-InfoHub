from pymongo import MongoClient, ASCENDING

def init_user_database():
    """初始化用户相关的所有数据库集合"""
    try:
        # 连接数据库
        client = MongoClient('localhost', 27017)
        db = client['nku_news'] 

        # 1. 用户集合 (users)
        if 'users' not in db.list_collection_names():
            users = db.create_collection('users')
            users.create_index([('username', ASCENDING)], unique=True)
            print("用户集合创建成功")

        # 2. 搜索历史集合 (search_history)
        if 'search_history' not in db.list_collection_names():
            search_history = db.create_collection('search_history')
            search_history.create_index([('username', ASCENDING)])
            search_history.create_index([('timestamp', ASCENDING)])
            print("搜索历史集合创建成功")

        # 3.用户身份信息集合 (user_profiles)
        if 'user_profiles' not in db.list_collection_names():
            user_profiles = db.create_collection('user_profiles')
            # 创建user_id索引确保一个用户只有一个profile
            user_profiles.create_index([('username', ASCENDING)], unique=True)
            # 为了支持按身份类型和学院查询，创建这些字段的索引
            user_profiles.create_index([('role', ASCENDING)])
            user_profiles.create_index([('college', ASCENDING)])
            print("用户身份信息集合创建成功")

        print("\n数据库初始化完成！创建了以下集合：")
        print("- users: 用户基本信息")
        print("- search_history: 搜索历史记录")
        print("- user_profiles: 用户身份信息")

        # 展示所有集合的结构
        print("\n各集合的数据结构：")
        print("\nusers 集合结构：")
        print({
            "username": "用户名 * ",
            "email": "邮箱 ",
            "password": "密码哈希",
            "created_at": "创建时间"
        })

        print("\nsearch_history 集合结构：")
        print({
            "username": "用户名 * ",
            "query": "搜索关键词",
            "search_in": "搜索范围",
            "sort_by": "结果排序",
            "timestamp": "查询时间 * "
        })

        print("\nuser_profiles 集合结构：")
        print({
            "username": "用户ID * ",
            "age": "年龄 ",
            "role": "身份 * ",
            "college": "学院 * ",
            "major": "专业",
            "grade": "年级",
        })

    except Exception as e:
        print(f"初始化数据库时出错: {str(e)}")
        raise e


if __name__ == "__main__":
    init_user_database()