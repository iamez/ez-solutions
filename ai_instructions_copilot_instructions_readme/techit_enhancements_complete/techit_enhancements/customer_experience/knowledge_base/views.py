# customer_experience/knowledge_base/views.py
"""
Knowledge Base Views
"""

from django.shortcuts import render, get_object_or_404, redirect
from django.views.generic import ListView, DetailView
from django.db.models import Q, Count
from django.http import JsonResponse
from django.contrib import messages
from .models import Category, Article, FAQ, ArticleFeedback, SearchQuery
from django.contrib.postgres.search import SearchVector, SearchQuery as PgSearchQuery, SearchRank
import markdown


class KnowledgeBaseHomeView(ListView):
    """Knowledge base homepage with categories"""

    model = Category
    template_name = "kb/home.html"
    context_object_name = "categories"

    def get_queryset(self):
        return Category.objects.filter(is_active=True, parent=None).prefetch_related("articles")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["popular_articles"] = Article.objects.filter(status="published").order_by(
            "-view_count"
        )[:5]
        context["recent_articles"] = Article.objects.filter(status="published").order_by(
            "-published_at"
        )[:5]
        return context


class CategoryDetailView(DetailView):
    """Category detail with articles"""

    model = Category
    template_name = "kb/category.html"
    context_object_name = "category"
    slug_field = "slug"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["articles"] = self.object.articles.filter(status="published").order_by(
            "-published_at"
        )
        context["subcategories"] = self.object.subcategories.filter(is_active=True)
        return context


class ArticleDetailView(DetailView):
    """Article detail view"""

    model = Article
    template_name = "kb/article.html"
    context_object_name = "article"
    slug_field = "slug"

    def get_queryset(self):
        return Article.objects.filter(status="published")

    def get_object(self, queryset=None):
        obj = super().get_object(queryset)
        # Increment view count
        obj.increment_views()
        return obj

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Convert markdown to HTML
        context["content_html"] = markdown.markdown(
            self.object.content, extensions=["extra", "codehilite", "toc"]
        )

        # Get related articles
        context["related_articles"] = self.object.get_related_articles()

        # Check if user has already provided feedback
        if self.request.user.is_authenticated:
            context["user_feedback"] = ArticleFeedback.objects.filter(
                article=self.object, user=self.request.user
            ).first()

        return context


def search_knowledge_base(request):
    """Search articles"""
    query = request.GET.get("q", "")
    results = []

    if query:
        # Track search query
        SearchQuery.objects.create(
            query=query,
            user=request.user if request.user.is_authenticated else None,
            ip_address=get_client_ip(request),
            results_count=0,
        )

        # Search using PostgreSQL full-text search
        search_query = PgSearchQuery(query)
        results = (
            Article.objects.filter(status="published")
            .annotate(
                search=SearchVector("title", "summary", "content"),
                rank=SearchRank(
                    SearchVector("title", weight="A")
                    + SearchVector("summary", weight="B")
                    + SearchVector("content", weight="C"),
                    search_query,
                ),
            )
            .filter(
                Q(search=search_query) | Q(title__icontains=query) | Q(summary__icontains=query)
            )
            .order_by("-rank", "-view_count")[:20]
        )

        # Update results count
        SearchQuery.objects.filter(query=query).update(results_count=results.count())

    context = {"query": query, "results": results, "results_count": len(results)}

    return render(request, "kb/search.html", context)


def article_feedback(request, slug):
    """Handle article feedback"""
    if request.method == "POST" and request.user.is_authenticated:
        article = get_object_or_404(Article, slug=slug, status="published")
        is_helpful = request.POST.get("helpful") == "yes"
        comment = request.POST.get("comment", "")

        # Create or update feedback
        feedback, created = ArticleFeedback.objects.update_or_create(
            article=article,
            user=request.user,
            defaults={
                "is_helpful": is_helpful,
                "comment": comment,
                "ip_address": get_client_ip(request),
            },
        )

        # Update article counts
        if created:
            if is_helpful:
                article.helpful_count += 1
            else:
                article.not_helpful_count += 1
            article.save()

        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JsonResponse({"success": True, "message": "Thank you for your feedback!"})

        messages.success(request, "Thank you for your feedback!")
        return redirect("kb:article", slug=slug)

    return JsonResponse({"error": "Invalid request"}, status=400)


class FAQListView(ListView):
    """FAQ listing"""

    model = FAQ
    template_name = "kb/faq.html"
    context_object_name = "faqs"

    def get_queryset(self):
        return FAQ.objects.filter(is_active=True).select_related("category")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Group FAQs by category
        context["faq_by_category"] = {}
        for faq in context["faqs"]:
            if faq.category not in context["faq_by_category"]:
                context["faq_by_category"][faq.category] = []
            context["faq_by_category"][faq.category].append(faq)
        return context


def get_client_ip(request):
    """Get client IP address"""
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        return x_forwarded_for.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


# API endpoints for AJAX requests
def get_popular_searches(request):
    """Get popular search queries"""
    popular = (
        SearchQuery.objects.values("query")
        .annotate(count=Count("id"))
        .filter(results_count__gt=0)
        .order_by("-count")[:10]
    )

    return JsonResponse({"popular_searches": list(popular)})


def autocomplete_search(request):
    """Autocomplete search suggestions"""
    query = request.GET.get("q", "")

    if len(query) < 2:
        return JsonResponse({"suggestions": []})

    # Search article titles
    suggestions = Article.objects.filter(status="published", title__icontains=query).values_list(
        "title", flat=True
    )[:10]

    return JsonResponse({"suggestions": list(suggestions)})
