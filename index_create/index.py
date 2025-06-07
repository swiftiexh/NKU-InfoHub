import pymongo
from elasticsearch import Elasticsearch
from elasticsearch.helpers import bulk
from datetime import datetime


class NewsIndexer:
    def __init__(self,
                 mongo_host='localhost',
                 mongo_port=27017,
                 mongo_db='nku_news',
                 es_host='localhost',
                 es_port=9200,
                 index_name='nankai_news_index'):
        # MongoDB连接
        self.mongo_client = pymongo.MongoClient(mongo_host, mongo_port)
        self.mongo_db = self.mongo_client[mongo_db]
        self.news_collection = self.mongo_db['NEWS']
        self.documents_collection = self.mongo_db['fs.files']
        self.snapshot_collection = self.mongo_db['WEB_snapshot']

        # 构建快照字典
        self.snapshot_dict = {doc['content_hash']: doc for doc in self.snapshot_collection.find()}

        # Elasticsearch连接
        self.es = Elasticsearch(
            [f'http://{es_host}:{es_port}'],
            basic_auth=('elastic', 'ZCjtuz7ZKNWy7u5DaOId'),
            request_timeout=300,
            max_retries=3,
            retry_on_timeout=True
        )
        self.index_name = index_name

    def create_index(self):
        """创建Elasticsearch索引"""
        settings = {
            "index": {
                "number_of_replicas": 2,
                "number_of_shards": 1
            },
            "analysis": {
                "analyzer": {
                    "ik_smart_pinyin": {
                        "type": "custom",
                        "tokenizer": "ik_smart",
                        "filter": ["lowercase", "pinyin_filter"]
                    }
                },
                "filter": {
                    "pinyin_filter": {
                        "type": "pinyin",
                        "keep_full_pinyin": False,
                        "keep_joined_full_pinyin": False,
                        "keep_original": True,
                        "limit_first_letter_length": 16,
                        "remove_duplicated_term": True,
                        "none_chinese_pinyin_tokenize": False
                    }
                }
            }
        }

        mappings = {
            "properties": {
                "title": {
                    "type": "text",
                    "analyzer": "ik_max_word",
                    "fields": {
                        "pinyin": {
                            "type": "text",
                            "analyzer": "ik_smart_pinyin"
                        }
                    }
                },
                "url": {"type": "keyword"},
                "content": {
                    "type": "text",
                    "analyzer": "ik_max_word",
                    "search_analyzer": "ik_smart"
                },
                "source": {"type": "keyword"},
                "date": {"type": "date", "format": "yyyy-MM-dd"},
                "snapshot_hash": {"type": "keyword"},
                "captured_at": {"type": "date", "format": "yyyy-MM-dd HH:mm:ss||yyyy-MM-dd'T'HH:mm:ss.SSS'Z'"},
                "filetype": {"type": "keyword"},
                "filename": {"type": "keyword"},
                "upload_date": {"type": "date", "format": "yyyy-MM-dd HH:mm:ss||yyyy-MM-dd'T'HH:mm:ss.SSS'Z'"},
                "suggest": {
                    "type": "completion",
                    "analyzer": "ik_max_word",
                    "search_analyzer": "ik_smart"
                }
            }
        }

        if self.es.indices.exists(index=self.index_name):
            self.es.indices.delete(index=self.index_name)

        self.es.indices.create(
            index=self.index_name,
            body={
                "settings": settings,
                "mappings": mappings
            }
        )

    def prepare_documents(self):
        """准备所有类型的索引文档"""
        documents = []

        # 1. 处理文档集合
        for doc in self.documents_collection.find():
            upload_date = doc.get('upload_date', '')
            # 格式化 upload_date
            if isinstance(upload_date, datetime):
                upload_date = upload_date.strftime("%Y-%m-%d %H:%M:%S")
            elif isinstance(upload_date, str):
                # 可选：尝试截断微秒部分
                if 'T' in upload_date and '.' in upload_date:
                    upload_date = upload_date.split('.')[0].replace('T', ' ')
            documents.append({
                "_id": str(doc['_id']),
                "title": doc.get('title', ''),
                "url": doc.get('url', ''),
                "filetype": doc.get('filetype', ''),
                "filename": doc.get('filename', ''),
                "upload_date":upload_date,
                "suggest": {"input": [doc.get('title', '')], "weight": 10}
            })

        # 2. 处理NEWS集合
        for doc in self.news_collection.find():
            # 检查date字段格式
            date_str = doc.get('date', '')
            if isinstance(date_str, datetime):
                date_str = date_str.strftime("%Y-%m-%d")
            elif isinstance(date_str, str):
                import re
                if not re.match(r"^\d{4}-\d{2}-\d{2}$", date_str):
                    date_str = ""
            else:
                date_str = ""

            d = {
                "_id": str(doc['_id']),
                "title": doc.get('title', ''),
                "url": doc.get('url', ''),
                "content": doc.get('content', ''),
                "source": doc.get('source', ''),
                "snapshot_hash": doc.get('snapshot_hash', ''),
                "suggest": {"input": [doc.get('title', '')], "weight": 10}
            }
            if date_str:  # 只在有合法日期时添加
                d["date"] = date_str
            # 关联快照捕获时间
            snapshot_hash = doc.get('snapshot_hash')
            if snapshot_hash and snapshot_hash in self.snapshot_dict:
                snap = self.snapshot_dict[snapshot_hash]
                captured_at = snap.get("captured_at")
                # 尝试转为标准格式
                if isinstance(captured_at, datetime):
                    d["captured_at"] = captured_at.strftime("%Y-%m-%d %H:%M:%S")
                elif isinstance(captured_at, str):
                    d["captured_at"] = captured_at
            documents.append(d)

        return documents

    def close(self):
        """关闭数据库连接"""
        self.mongo_client.close()


def main():
    indexer = NewsIndexer(
        mongo_host='localhost',
        mongo_port=27017,
        mongo_db='nku_news',
        es_host='localhost',
        es_port=9200,
        index_name='nankai_news_index'
    )
    try:
        print("开始创建索引...")
        indexer.create_index()
        print("索引结构创建完成")

        print("开始准备文档...")
        documents = indexer.prepare_documents()
        print(f"文档准备完成，共 {len(documents)} 条记录")

        print("开始批量索引文档...")
        try:
            from elasticsearch.helpers import BulkIndexError
            success, failed = bulk(
                indexer.es,
                [
                    {
                        '_index': indexer.index_name,
                        '_id': doc['_id'],
                        **doc
                    }
                    for doc in documents
                ],
                chunk_size=500,
                request_timeout=300,
                refresh=True
            )
            print(f"文档索引完成，成功：{success} 条，失败：{failed} 条")
        except BulkIndexError as e:
            print(f"批量索引过程中发生错误0: {str(e)}")
            for error in e.errors:
                print(error)
        except Exception as e:
            print(f"批量索引过程中发生错误: {str(e)}")
            import traceback
            print(traceback.format_exc())
    finally:
        indexer.close()


if __name__ == "__main__":
    main()