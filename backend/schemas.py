from pydantic import BaseModel, Field


class Source(BaseModel):
    id: str
    name: str


class Coverage(BaseModel):
    title: str
    url: str
    source_id: str
    source: str
    published_at: str | None


class Article(BaseModel):
    id: str
    title: str
    url: str
    source_id: str
    source: str
    published_at: str | None
    description: str
    publisher_count: int = 1
    coverage: list[Coverage] = Field(default_factory=list)


class Warning(BaseModel):
    source_id: str
    message: str


class NewsResponse(BaseModel):
    articles: list[Article]
    sources: list[Source]
    collected_at: str
    warnings: list[Warning]
