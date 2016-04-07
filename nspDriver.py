from newsSiteParser import ArticleCollector, NewsSiteParser, ArticleScraper
import pprint


# ac = ArticleCollector()
# article_list = ac.get_articles()

nsp = NewsSiteParser(start_index=7000)

nsp.run(start_year=2005, end_year=2005)

