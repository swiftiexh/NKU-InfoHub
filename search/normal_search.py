from elasticsearch import Elasticsearch

class NormalSearch:
    def __init__(self, es_host='localhost', es_port=9200, index_name='nankai_news_index'):
        self.es = Elasticsearch([f'http://{es_host}:{es_port}'], basic_auth=('elastic', 'ZCjtuz7ZKNWy7u5DaOId'))
        self.index_name = index_name
        self.SUPPORTED_FILETYPES = ['pdf', 'doc', 'docx', 'xls', 'xlsx']

    def execute_search(self, search_type, query_text, search_in='all', sort_by='relevance', filetypes=None, size=2000):
        field_config = self._get_field_config(search_in)
        if search_type == 'document':
            body = self._build_document_query(query_text, field_config, filetypes)
        elif search_type == 'phrase':
            body = self._build_phrase_query(query_text, field_config)
        elif search_type == 'wildcard':
            body = self._build_wildcard_query(query_text, field_config)
        else:  # basic
            body = self._build_basic_query(query_text, field_config)

        # 添加高亮配置
        body['highlight'] = {
            "pre_tags": ["<mark>"],
            "post_tags": ["</mark>"],
            "fields": {field: {} for field in field_config["fields"]}
        }

        if sort_by == 'date':
            body['sort'] = [{"date": {"order": "desc"}}]

        # 关键：设置返回结果数量
        body['size'] = size

        res = self.es.search(index=self.index_name, body=body)
        results = []
        for hit in res['hits']['hits']:
            source = hit['_source']
            highlight = hit.get('highlight', {})
            for field in field_config["fields"]:
                if field in highlight:
                    source[field + '_highlight'] = highlight[field][0]
                else:
                    source[field + '_highlight'] = source.get(field, '')
            results.append(source)
        return results

    def _get_field_config(self, search_in='all'):
        if search_in == 'title':
            return {"fields": ["title"], "weights": {"title": 2.0}}
        elif search_in == 'content':
            return {"fields": ["content"], "weights": {"content": 1.0}}
        else:
            return {"fields": ["title", "content"], "weights": {"title": 2.0, "content": 1.0}}

    def _build_basic_query(self, query_text, field_config):
        return {
            "query": {
                "multi_match": {
                    "query": query_text,
                    "fields": [f"{f}^{w}" for f, w in field_config["weights"].items()]
                }
            }
        }

    def _build_document_query(self, query_text, field_config, filetypes):
        if not filetypes:
            filetypes = self.SUPPORTED_FILETYPES
        return {
            "query": {
                "bool": {
                    "must": [
                        {
                            "multi_match": {
                                "query": query_text,
                                "fields": [f"{f}^{w}" for f, w in field_config["weights"].items()] + ["filename^1.5", "filetype^1.0"]
                            }
                        }
                    ],
                    "filter": [
                        {"terms": {"filetype": [ft.lower() for ft in filetypes]}}
                    ]
                }
            }
        }

    def _build_phrase_query(self, query_text, field_config):
        # 精确短语匹配
        return {
            "query": {
                "bool": {
                    "should": [
                        {"match_phrase": {field: query_text}} for field in field_config["fields"]
                    ]
                }
            }
        }

    def _build_wildcard_query(self, query_text, field_config):
        # 通配符查询
        query_text = query_text.replace('？', '?').replace('＊', '*')
        if not any(c in query_text for c in ['*', '?']):
            query_text += '*'
        return {
            "query": {
                "bool": {
                    "should": [
                        {"wildcard": {field: {"value": query_text}}} for field in field_config["fields"]
                    ]
                }
            }
        }
