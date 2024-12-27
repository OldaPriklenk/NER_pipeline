import requests
from newspaper import Article as NewsArticle
import spacy


# Class to fetch data from NewsAPI
class NewsFetcher:
    def __init__(self, query, from_date, api_key):
        self.query = query
        self.from_date = from_date
        self.api_key = api_key
        self.articles_data = []

    def fetch(self):
        url = (f'https://newsapi.org/v2/everything?'
               f'q={self.query}&'
               f'from={self.from_date}&'
               f'sortBy=popularity&'
               f'apiKey={self.api_key}')
        response = requests.get(url)
        response_data = response.json()
        self.articles_data = response_data.get('articles', [])


# Class to handle and parse article data
class Article:
    def __init__(self, article_data):
        self.source = article_data.get("source", {}).get("name", "Unknown")
        self.author = article_data.get("author") or "Unknown author"
        self.title = article_data.get("title") or "No title"
        self.description = article_data.get("description") or "No description"
        self.url = article_data.get("url") or "No URL"
        self.published_at = article_data.get("publishedAt") or "Unknown date"
        self.content = None  # Will be populated later

    def fetch_content(self):
        """Fetch and parse the article content from the URL."""
        try:
            if self.url == "No URL":
                self.content = "Content not available (invalid URL)"
                return
            news_article = NewsArticle(self.url)
            news_article.download()
            news_article.parse()
            self.content = news_article.text
        except Exception as e:
            self.content = f"Error fetching content: {e}"

    def __str__(self):
        """String representation of the article."""
        return (f"Title: {self.title}\n"
                f"Author: {self.author}\n"
                f"Source: {self.source}\n"
                f"Published At: {self.published_at}\n"
                f"Description: {self.description}\n"
                f"URL: {self.url}\n"
                f"Content: {self.content[:500]}...\n")


# Class to extract entities from text
class EntityExtractor:
    def __init__(self):
        self.nlp = spacy.load('en_core_web_trf')
        self.entities = []

    def process_text(self, text):
        """Process text to extract entities."""
        doc = self.nlp(text)
        self.entities = [
            {
                'text': ent.text,
                'start': ent.start_char,
                'end': ent.end_char,
                'label': ent.label_,
                'description': spacy.explain(ent.label_)
            }
            for ent in doc.ents
        ]

    def get_entities(self):
        """Return the extracted entities."""
        return self.entities


# Main pipeline
def main():
    # Step 1: Fetch articles
    fetcher = NewsFetcher(query="Apple", from_date="2024-12-20", api_key="your_api_key")
    fetcher.fetch()

    # Step 2: Process articles
    articles = []
    for article_data in fetcher.articles_data:
        article = Article(article_data)
        article.fetch_content()  # Fetch the article content
        articles.append(article)

    # Step 3: Extract entities from each article
    extractor = EntityExtractor()
    for article in articles:
        print(article)  # Print article details
        print("-" * 50)

        # Process article content
        if article.content:
            extractor.process_text(article.content)
            entities = extractor.get_entities()
            print("Extracted Entities:")
            for entity in entities:
                print(f"{entity['text']} ({entity['label']}): {entity['description']}")
            print("-" * 50)


from neo4j import GraphDatabase
class Neo4jConnector:
    def __init__(self, uri, user, password):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))

    def close(self):
        self.driver.close()

    def create_article_and_entities(self, article_metadata, entities):
        """Create article and related entities in the Neo4j database."""
        with self.driver.session() as session:
            session.write_transaction(self._create_article_and_entities_tx, article_metadata, entities)


    @staticmethod
    def _create_article_and_entities_tx(tx, metadata, entities):
        article_query = """
        MERGE (a:Article {title: $title})
        SET a.author = $author,
            a.source = $source,
            a.published_at = $published_at,
            a.description = $description,
            a.url = $url
        """
        tx.run(article_query, **metadata)

        for entity in entities:
            entity_query = """
            MERGE (e:Entity {text: $text})
            SET e.label = $label,
                e.description = $description
            MERGE (a:Article {title: $article_title})
            MERGE (a)-[:MENTIONS]->(e)
            """
            tx.run(entity_query, text=entity['text'], label=entity['label'],
                   description=entity['description'], article_title=metadata['title'])

# Main pipeline
def main():
    # Step 1: Fetch articles
    fetcher = NewsFetcher(query="Apple", from_date="2024-12-20", api_key="your_api_key")
    fetcher.fetch()

    # Step 2: Process articles
    articles = []
    for article_data in fetcher.articles_data:
        article = Article(article_data)
        article.fetch_content()  # Fetch the article content
        articles.append(article)

    # Step 3: Extract entities and push to Neo4j
    extractor = EntityExtractor()
    neo4j_connector = Neo4jConnector(uri="bolt://localhost:7687", user="neo4j", password="password")

    try:
        for article in articles:
            print(article)  # Print article details
            print("-" * 50)

            # Process article content
            if article.content:
                extractor.process_text(article.content)
                entities = extractor.get_entities()

                metadata = {
                    'title': article.title,
                    'author': article.author,
                    'source': article.source,
                    'published_at': article.published_at,
                    'description': article.description,
                    'url': article.url
                }

                # Push data to Neo4j
                neo4j_connector.create_article_and_entities(metadata, entities)
                print("Entities pushed to Neo4j successfully.")
    finally:
        neo4j_connector.close()

if __name__ == "__main__":
    main()


    