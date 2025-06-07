import math

class PagePartition:
    def __init__(self, results_per_page=10):
        self.RESULTS_PER_PAGE = results_per_page
       
    def process_results(self, results, page=1):
        """处理搜索结果并应用分页"""
        total_results = len(results)
        total_pages = math.ceil(total_results / self.RESULTS_PER_PAGE)

        # 计算分页
        start_page = max(1, page - 5)
        end_page = min(total_pages, start_page + 9)
        if end_page - start_page < 9:
            start_page = max(1, end_page - 9)

        # 获取当前页的结果
        start_idx = (page - 1) * self.RESULTS_PER_PAGE
        end_idx = start_idx + self.RESULTS_PER_PAGE
        page_results = results[start_idx:end_idx]

        # 处理结果
        processed_results = [self._process_single_result(hit) for hit in page_results]

        return {
            'results': processed_results,
            'total': total_results,
            'total_pages': total_pages,
            'page_range': range(start_page, end_page + 1)
        }

    def _process_single_result(self, hit):
        """处理单个搜索结果，兼容ES高亮"""
        # 文档类型处理
        if hit.get('filetype'):
            return {
                'title': hit.get('title_highlight') or hit.get('title', '无标题'),
                'filename': hit.get('filename', '未知文件名'),
                'filetype': hit.get('filetype', '未知类型'),
                'upload_date': hit.get('upload_date', None),
                'url': hit.get('url', '#'),
                'snippet': None,
                'source': '',
                'date': '',
                'sort_date': '',
                'snapshot_hash': None,
                'snapshot_date': None
            }

        # 普通新闻/网页类型
        title = hit.get('title_highlight') or hit.get('title', '无标题')
        content = hit.get('content_highlight') or hit.get('content', '')
        snippet = content[:200] if content else hit.get('content', '')[:200]

        # 来源、日期等
        source = hit.get('source', '')
        date_str = hit.get('date', '') or hit.get('publish_date', '')
        sort_date = self._process_date(date_str)

        # 快照信息
        snapshot_hash = hit.get('snapshot_hash')
        captured_at = hit.get('captured_at')
        snapshot_date = None
        if captured_at:
            try:
                # 支持字符串和datetime
                if hasattr(captured_at, 'strftime'):
                    snapshot_date = captured_at.strftime('%Y/%m/%d')
                else:
                    snapshot_date = str(captured_at)[:10].replace('-', '/')
            except:
                snapshot_date = None

        return {
            'title': title,
            'url': hit.get('url', '#'),
            'snippet': snippet,
            'source': source,
            'date': date_str,
            'sort_date': sort_date,
            'filetype': hit.get('filetype', None),
            'filename': hit.get('filename', None),
            'snapshot_hash': snapshot_hash,
            'snapshot_date': snapshot_date
        }

    def _process_date(self, date_str):
        """处理日期格式"""
        if not date_str:
            return ''
        try:
            parts = date_str.split('-')
            return f"{parts[0]}-{parts[1].zfill(2)}-{parts[2].zfill(2)}"
        except:
            return ''