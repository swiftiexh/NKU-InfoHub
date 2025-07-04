# 南开大学信息检索系统原理课程设计 -- NKU InfoHub
本项目旨在实现一个名为NKU InfoHub信息检索系统。该系统通过爬虫整合了南开大学新闻网等11个网站的数10w条网页、文档等信息，供用户查询和获取有关南开大学的新闻、课程、课外活动等信息，提高信息获取的效率。
## 主要技术选型
- **爬虫**：使用 Python 编写爬虫程序，利用 **requests** 和 **BeautifulSoup** 库抓取目标网站的网页内容。
- **前端技术栈**：原生 **HTML、CSS、JavaScript** 构建用户界面，基于模板引擎 **Jinja2** 进行页面渲染，利用 **AJAX** 技术与后端进行异步数据交互。
- **后端技术栈**：采用 **Python Flask** 框架作为 Web 服务器，**MongoDB** 作为主数据库，存储用户信息、搜索历史等，利用 **ElasticSearch** 创建索引和查询文档。
## 核心功能
- **数据获取与预处理**：使用 Python 编写爬虫程序抓取目标网站内容，存储至 MongoDB，并通过脚本进行数据清洗与预处理。
- **用户认证**：支持用户注册、登录、登出，用户可查看和修改个人信息。
- **搜索模块**：基于 ElasticSearch 实现全文搜索，支持站内查询、短语查询、文档查询、通配符查询及个性化查询等多种搜索方式。  

**具体项目介绍参见`NKU_InfoHub项目说明.pdf`**
