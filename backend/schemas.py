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
    content: str = ""
    content_word_count: int = 0
    content_is_excerpt: bool = False
    content_note: str = ""
    ai_relevance: int = 0
    ai_importance: int = 0
    ai_reason: str = ""
    publisher_count: int = 1
    coverage: list[Coverage] = Field(default_factory=list)


class Warning(BaseModel):
    source_id: str
    message: str


class NewsResponse(BaseModel):
    candidates_found: int = 0
    stories_checked: int = 0
    ai_reviewed: int = 0
    ai_selected: int = 0
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
    body: str
    source_url: str
    model: str


class ArticleCandidate(BaseModel):
    url: str = Field(min_length=1, max_length=8192)
    source: str = Field(default="", max_length=256)


class ArticleRequest(BaseModel):
    url: str = Field(min_length=1, max_length=8192)
    expected_title: str = Field(default="", max_length=1000)
    source: str = Field(default="", max_length=256)
    alternatives: list[ArticleCandidate] = Field(default_factory=list, max_length=9)


class ExtractedArticle(BaseModel):
    access_note: str = ""
    source: str = ""
    url: str
    text: str
    word_count: int
    truncated: bool


class EvidenceSource(BaseModel):
    title: str
    url: str
    publisher: str
    relationship: str
    passage: str
    explanation: str


class EvidenceResponse(BaseModel):
    claim: str
    status: str
    checked_at: str
    sources: list[EvidenceSource] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
