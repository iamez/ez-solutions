# customer_experience/knowledge_base/models.py
"""
Knowledge Base / Documentation System
Provides self-service support documentation for customers
"""

from django.db import models
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils.text import slugify

User = get_user_model()


class Category(models.Model):
    """Knowledge base categories"""

    name = models.CharField(max_length=200)
    slug = models.SlugField(unique=True)
    description = models.TextField(blank=True)
    icon = models.CharField(max_length=50, blank=True, help_text="Font Awesome icon class")
    parent = models.ForeignKey(
        "self", on_delete=models.CASCADE, null=True, blank=True, related_name="subcategories"
    )
    order = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "Categories"
        ordering = ["order", "name"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("kb:category", kwargs={"slug": self.slug})

    def get_article_count(self):
        return self.articles.filter(status="published").count()


class Article(models.Model):
    """Knowledge base articles"""

    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("published", "Published"),
        ("archived", "Archived"),
    ]

    title = models.CharField(max_length=300)
    slug = models.SlugField(unique=True)
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name="articles")
    summary = models.TextField(max_length=500, help_text="Brief summary for search results")
    content = models.TextField(help_text="Full article content (Markdown supported)")
    author = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name="kb_articles"
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft")

    # SEO fields
    meta_description = models.CharField(max_length=160, blank=True)
    meta_keywords = models.CharField(max_length=255, blank=True)

    # Metrics
    view_count = models.IntegerField(default=0)
    helpful_count = models.IntegerField(default=0)
    not_helpful_count = models.IntegerField(default=0)

    # Timestamps
    published_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Search
    search_vector = models.GeneratedField(
        expression=models.Q(), output_field=models.TextField(), db_persist=False
    )

    class Meta:
        ordering = ["-published_at"]
        indexes = [
            models.Index(fields=["status", "-published_at"]),
            models.Index(fields=["category", "status"]),
        ]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        if self.status == "published" and not self.published_at:
            from django.utils import timezone

            self.published_at = timezone.now()
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("kb:article", kwargs={"slug": self.slug})

    def increment_views(self):
        """Increment view count"""
        self.view_count += 1
        self.save(update_fields=["view_count"])

    def get_helpfulness_score(self):
        """Calculate helpfulness percentage"""
        total = self.helpful_count + self.not_helpful_count
        if total == 0:
            return None
        return int((self.helpful_count / total) * 100)

    def get_related_articles(self, limit=5):
        """Get related articles from same category"""
        return Article.objects.filter(category=self.category, status="published").exclude(
            id=self.id
        )[:limit]


class ArticleAttachment(models.Model):
    """File attachments for articles"""

    article = models.ForeignKey(Article, on_delete=models.CASCADE, related_name="attachments")
    file = models.FileField(upload_to="kb/attachments/%Y/%m/")
    filename = models.CharField(max_length=255)
    file_size = models.IntegerField(help_text="Size in bytes")
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.filename


class ArticleRevision(models.Model):
    """Track article revision history"""

    article = models.ForeignKey(Article, on_delete=models.CASCADE, related_name="revisions")
    content = models.TextField()
    editor = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    revision_notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.article.title} - {self.created_at}"


class ArticleFeedback(models.Model):
    """User feedback on articles"""

    article = models.ForeignKey(Article, on_delete=models.CASCADE, related_name="feedback")
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    is_helpful = models.BooleanField()
    comment = models.TextField(blank=True)
    ip_address = models.GenericIPAddressField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ["article", "user"]

    def __str__(self):
        helpful = "Helpful" if self.is_helpful else "Not Helpful"
        return f"{self.article.title} - {helpful}"


class FAQ(models.Model):
    """Frequently Asked Questions"""

    question = models.CharField(max_length=300)
    answer = models.TextField()
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name="faqs")
    order = models.IntegerField(default=0)
    view_count = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["order", "question"]
        verbose_name = "FAQ"
        verbose_name_plural = "FAQs"

    def __str__(self):
        return self.question


class SearchQuery(models.Model):
    """Track search queries for analytics"""

    query = models.CharField(max_length=255)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    results_count = models.IntegerField(default=0)
    ip_address = models.GenericIPAddressField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Search Query"
        verbose_name_plural = "Search Queries"

    def __str__(self):
        return self.query
