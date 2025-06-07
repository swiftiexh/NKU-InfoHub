# 爬取网页和文档信息，保存网页快照

import os #用于处理文件和路径。
import requests #用于发送 HTTP 请求，获取网页内容。
from bs4 import BeautifulSoup #用于解析 HTML 文档，提取所需信息。
from concurrent.futures import ThreadPoolExecutor #用于多线程处理，提高爬取效率。

from pymongo import MongoClient #用于连接和操作 MongoDB 数据库。
from pymongo.errors import DuplicateKeyError #用于处理 MongoDB 中的重复键错误。
import logging #用于记录日志，方便调试和错误追踪。
import gridfs #用于在 MongoDB 中存储大文件（如附件）。

from datetime import datetime #用于处理日期和时间。
import re #用于正则表达式操作。
import time #用于时间相关的操作，如延时。
import random #用于生成随机数，增加请求的随机性以防止被网站封禁。
import hashlib #用于生成内容的哈希值，以便快速比较和去重。

from urllib.parse import urljoin
#-----------------------------------------------------------------------------------------------------------------------
class spider:
    def __init__(self):
        # 基础配置
        self.base_url =  "http://math.nankai.edu.cn"
        self.first_page = "http://math.nankai.edu.cn/yjspy/list.htm"
        self.page_template = "https://math.nankai.edu.cn/yjspy/list{}.htm"
        self.max_pages = 4

        # MongoDB连接设置
        self.mongo_client = MongoClient('mongodb://localhost:27017/')
        self.db = self.mongo_client['nku_news'] # 数据库名称
        self.news_collection = self.db['NEWS'] # 新闻数据集合
        self.snapshot_collection = self.db['WEB_snapshot']  # 网页快照集合
        self.fs = gridfs.GridFS(self.db)  # 用于存储附件

        # 创建索引，保证数据的唯一性和查询效率
        self.news_collection.create_index([('url', 1)], unique=True)
        self.snapshot_collection.create_index([('url', 1), ('captured_at', -1)])

        # 支持的附件类型
        self.supported_attachments = [
            ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",  # 常见文档格式
            ".mp3", ".mp4", ".avi", ".mkv", ".mov", ".wmv", ".flv",  # 音频和视频格式
            ".zip", ".rar", ".tar", ".gz", ".bz2", ".7z",  # 压缩文件格式
            ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff",  # 图片格式
            ".exe", ".apk", ".dmg",  # 可执行文件和应用程序
            ".csv", ".txt", ".rtf",  # 文本文件
            ".xls", ".xlsx",  # 表格文件
        ]

        # 日志配置
        logging.basicConfig(
            level=logging.INFO, 
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('spider.log', encoding='utf-8'),
                logging.StreamHandler()
            ]
        )

        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Connection': 'keep-alive'
        }
#-----------------------------------------------------------------------------------------------------------------------
    def get_page_urls(self):
        """生成所有页面的URL"""
        urls = [self.first_page]  # 第一页
        # 添加后续页面
        urls.extend(self.page_template.format(i) for i in range(1, self.max_pages+1))
        return urls
    
    def get_soup(self, url, retries=3):
        """获取页面的BeautifulSoup对象和原始HTML内容"""
        for i in range(retries):
            try:
                time.sleep(random.uniform(2, 5))
                response = requests.get(url, headers=self.headers, timeout=10)
                response.encoding = 'utf-8'

                if response.status_code == 200:
                    html_content = response.text
                    return BeautifulSoup(html_content, 'html.parser'), html_content
                else:
                    logging.warning(f"Failed to fetch {url}, status code: {response.status_code}")

            except Exception as e:
                logging.error(f"Attempt {i + 1} failed for {url}: {str(e)}")
                if i == retries - 1:
                    logging.error(f"All attempts failed for {url}")
                    return None, None
                time.sleep(random.uniform(2, 5))
        return None, None

    def save_snapshot(self, url, html_content):
        """保存网页快照"""
        try:
            snapshot_data = {
                'url': url,
                'html_content': html_content,
                'captured_at': datetime.now(),
                'content_hash': hashlib.md5(html_content.encode('utf-8')).hexdigest()
            }
            self.snapshot_collection.insert_one(snapshot_data)
            return snapshot_data['content_hash']
        except Exception as e:
            logging.error(f"Error saving snapshot for {url}: {str(e)}")
            return None

    def find_attachments(self, soup, url):
        attachments = []
        for link in soup.find_all('a', href=True):
            href = link['href'].lower()
            if any(ext in href for ext in self.supported_attachments):
                full_url = self.base_url + href if href.startswith('/') else href
                attachments.append({
                'url': full_url,
                'filename': os.path.basename(href),
                'title': link.text.strip()
                })
        return attachments

    def save_attachment(self, attachment_info):
        """保存附件到GridFS"""
        try:
            response = requests.get(attachment_info['url'], headers=self.headers, timeout=30)
            if response.status_code == 200:
                file_id = self.fs.put(
                    response.content,
                    filename=attachment_info['filename'],
                    url=attachment_info['url'],
                    title=attachment_info['title'],
                    upload_date=datetime.now()
                )
                return file_id
        except Exception as e:
            logging.error(f"Error saving attachment {attachment_info['url']}: {str(e)}")
        return None
# -----------------------------------------------------------------------------------------------------------------------
    def parse_news_list_page(self, url):
        """解析新闻列表页面"""
        soup, html_content = self.get_soup(url)
        if not soup:
            return []

        # 保存列表页快照
        snapshot_hash = self.save_snapshot(url, html_content)

        news_items = []

        # 找到所有新闻块
        news_blocks = soup.find_all('li', class_='news')
        for block in news_blocks:
            try:
                # 提取标题和链接
                title_span = block.find('span', class_='news_title')
                a_tag = title_span.find('a', href=True) if title_span else None
                if not a_tag:
                    continue
                title = a_tag.get_text(strip=True)
                href = a_tag['href']
                news_url = urljoin(url, href)

                # 提取日期
                date_span = block.find('span', class_='news_meta')
                date = date_span.get_text(strip=True) if date_span else ''

                logging.info(f"Processing: {title}")

                # 获取新闻详细内容和快照
                article_content, article_snapshot_hash, article_attachments = self.parse_news_detail(news_url)

                news_item = {
                    'title': title,
                    'url': news_url,
                    'date': date,
                    'source': article_content.get('source', ''),
                    'content': article_content.get('content', ''),
                    'snapshot_hash': article_snapshot_hash,
                    'attachments': article_attachments
                }

                news_items.append(news_item)

            except Exception as e:
                logging.error(f"Error parsing news item: {str(e)}")
                continue

        return news_items

    def parse_news_detail(self, url):
        """解析新闻详细页面，包括快照和附件"""
        soup, html_content = self.get_soup(url)
        if not soup:
            return {'source': '', 'content': ''}, None, []

        try:
            # 保存快照
            snapshot_hash = self.save_snapshot(url, html_content)

            # 查找附件
            attachments = self.find_attachments(soup, url)
            saved_attachments = []

            # 保存附件
            for attachment in attachments:
                file_id = self.save_attachment(attachment)
                if file_id:
                    saved_attachments.append({
                        'file_id': file_id,
                        'url': attachment['url'],
                        'filename': attachment['filename'],
                        'title': attachment['title']
                    })

            # 解析内容
            source_span = soup.find('span', string=re.compile('来源：'))
            source = source_span.text.strip() if source_span else ''

            # 扩大正文搜索范围
            content_div = (
                soup.find('td', id='txt') or
                soup.find('div', class_='wp_articlecontent') or
                soup.find('div', id='content') or
                soup.find('div', class_='article-content') or
                soup.find('div', class_='content') or
                soup.find('div', id='vsb_content') or
                soup.find('div', id='vsb_content_2') or
                soup.find('article', class_='blog') or
                soup.find('article') or
                soup.find('section', id='main-content')
            )
            if content_div:
                paragraphs = content_div.find_all('p')
                if paragraphs:
                    content = '\n'.join([p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True)])
                else:
                    content = content_div.get_text(separator='\n', strip=True)
            else:
                content = ''

            return {
                'source': source,
                'content': content
            }, snapshot_hash, saved_attachments

        except Exception as e:
            logging.error(f"Error parsing detail page {url}: {str(e)}")
            return {'source': '', 'content': ''}, None, []
# -----------------------------------------------------------------------------------------------------------------------
    def save_to_mongodb(self, news_items, batch_number=None):
        """保存数据到MongoDB"""
        if not news_items:
            logging.warning("No data to save to MongoDB")
            return 0, 0

        inserted_count = 0
        updated_count = 0

        for item in news_items:
            try:
                # 添加时间戳和批次信息
                item['created_at'] = datetime.now()
                item['batch_number'] = batch_number

                # 使用update_one with upsert=True来避免重复插入
                result = self.news_collection.update_one(
                    {'url': item['url']},  # 查询条件
                    {'$set': item},  # 更新的数据
                    upsert=True  # 如果不存在则插入
                )

                if result.upserted_id:
                    inserted_count += 1
                elif result.modified_count:
                    updated_count += 1

            except Exception as e:
                logging.error(f"Error saving to MongoDB: {str(e)}")
                continue

        logging.info(
            f"Batch {batch_number}: Inserted {inserted_count} new documents, Updated {updated_count} documents")
        return inserted_count, updated_count

    def scrape_batch(self, urls, batch_size=10):
        """批量抓取新闻并保存到MongoDB"""
        for i in range(0, len(urls), batch_size):
            batch_urls = urls[i:i + batch_size]
            batch_number = i // batch_size + 1

            logging.info(f"Processing batch {batch_number}, pages {i + 1} to {min(i + batch_size, len(urls))}")

            # 使用线程池并行处理每批URL
            with ThreadPoolExecutor(max_workers=5) as executor:
                batch_results = list(executor.map(self.parse_news_list_page, batch_urls))

            # 合并结果
            batch_news = [item for sublist in batch_results if sublist for item in sublist]

            # 保存这一批次的数据到MongoDB
            inserted, updated = self.save_to_mongodb(batch_news, batch_number)
            logging.info(f"Batch {batch_number} completed: {inserted} new items, {updated} updates")

            # 批次间休息
            time.sleep(random.uniform(3, 5))

    def get_news_count(self):
        """获取数据库中的新闻总数"""
        return self.news_collection.count_documents({})
    
    def scrape(self):
        """主抓取函数"""
        logging.info("Starting to scrape news...")
        urls = self.get_page_urls()
        self.scrape_batch(urls)

        # 打印最终统计信息
        total_news = self.get_news_count()
        logging.info(f"Scraping completed. Total news in database: {total_news}")

    def cleanup(self):
        """清理资源"""
        self.mongo_client.close()


def main():
    scraper = None
    try:
        scraper = spider()
        scraper.scrape()
    except Exception as e:
        logging.error(f"An error occurred during scraping: {str(e)}")
    finally:
        if scraper:
            scraper.cleanup()


if __name__ == "__main__":
    main()