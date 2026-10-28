from pydantic import BaseModel


class Source(BaseModel):
    id: str
    name: str


class Article(BaseModel):
    id: str
    title: str
    url: str
    source_id: str
    source: str
    published_at: str | None
    description: str


class Warning(BaseModel):
    source_id: str
    message: str


class NewsResponse(BaseModel):
    articles: list[Article]
    sources: list[Source]
    collected_at: str
    warnings: list[Warning]
