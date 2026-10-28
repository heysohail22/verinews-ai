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


class PostRequest(BaseModel):
    title: str = Field(min_length=1, max_length=1000)
    description: str = Field(default="", max_length=8000)
    source: str = Field(min_length=1, max_length=256)
    url: str = Field(min_length=1, max_length=8192)


class PostResponse(BaseModel):
    draft: str
    model: str
