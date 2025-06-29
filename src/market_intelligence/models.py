"""
Market Intelligence models for news scraping, target identification, and lead scoring.

Follows Django modular architecture best practices with service layer integration.
"""

import uuid
import hashlib
from decimal import Decimal
from datetime import datetime
from typing import Dict, Any, Optional

from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from django.contrib.postgres.fields import ArrayField

from platform_core.accounts.models import User, Group
from assessments.base_models import UUIDModel, TimestampedModel, PlatformModel


class QueryTemplate(UUIDModel, TimestampedModel, PlatformModel):
    """
    Search query templates for automated news scraping.
    
    Defines search patterns, keywords, and regions for systematic
    market intelligence gathering.
    """
    
    class TemplateType(models.TextChoices):
        COMPANY_DISCOVERY = 'company_discovery', 'Company Discovery'
        FUNDING_ANNOUNCEMENT = 'funding_announcement', 'Funding Announcement'
        DEVELOPMENT_NEWS = 'development_news', 'Development News'
        PARTNERSHIP_NEWS = 'partnership_news', 'Partnership News'
        ACQUISITION_NEWS = 'acquisition_news', 'Acquisition News'
    
    name = models.CharField(
        max_length=200,
        help_text="Human-readable name for the query template"
    )
    description = models.TextField(
        blank=True,
        help_text="Description of what this template searches for"
    )
    template_type = models.CharField(
        max_length=30,
        choices=TemplateType.choices,
        default=TemplateType.COMPANY_DISCOVERY
    )
    query_pattern = models.TextField(
        help_text="Search query pattern with placeholders"
    )
    keywords = models.JSONField(
        default=list,
        help_text="List of keywords to include in searches"
    )
    excluded_keywords = models.JSONField(
        default=list,
        help_text="List of keywords to exclude from searches"
    )
    regions = models.JSONField(
        default=list,
        help_text="Geographic regions to focus search on"
    )
    languages = ArrayField(
        models.CharField(max_length=10),
        default=list,
        blank=True,
        help_text="Language codes for search (e.g., ['en', 'es'])"
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Whether this template is actively used"
    )
    schedule_frequency = models.CharField(
        max_length=20,
        choices=[
            ('daily', 'Daily'),
            ('weekly', 'Weekly'),
            ('monthly', 'Monthly'),
        ],
        default='daily'
    )
    last_executed = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When this template was last executed"
    )
    
    class Meta:
        db_table = 'market_intelligence_query_templates'
        unique_together = ['group', 'name']
        indexes = [
            models.Index(fields=['template_type', 'is_active']),
            models.Index(fields=['schedule_frequency', 'last_executed']),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.template_type})"
    
    def generate_search_query(self, **kwargs) -> str:
        """Generate actual search query from template and parameters."""
        query = self.query_pattern
        
        # Replace placeholders with actual values
        for key, value in kwargs.items():
            query = query.replace(f"{{{key}}}", str(value))
        
        # Add keywords
        if self.keywords:
            keywords_str = " OR ".join(f'"{kw}"' for kw in self.keywords)
            query += f" AND ({keywords_str})"
        
        # Add exclusions
        if self.excluded_keywords:
            exclusions = " AND ".join(f'-"{kw}"' for kw in self.excluded_keywords)
            query += f" AND {exclusions}"
        
        return query


class NewsArticle(UUIDModel, TimestampedModel, PlatformModel):
    """
    Scraped news articles with relevance scoring and entity extraction.
    
    Stores article content, metadata, and AI-generated insights for
    investment opportunity identification.
    """
    
    class ArticleStatus(models.TextChoices):
        PENDING = 'pending', 'Pending Analysis'
        ANALYZED = 'analyzed', 'Analyzed'
        RELEVANT = 'relevant', 'Relevant'
        IRRELEVANT = 'irrelevant', 'Irrelevant'
        ARCHIVED = 'archived', 'Archived'
    
    title = models.CharField(
        max_length=500,
        help_text="Article headline"
    )
    content = models.TextField(
        help_text="Full article content"
    )
    summary = models.TextField(
        blank=True,
        help_text="AI-generated summary of article"
    )
    url = models.URLField(
        unique=True,
        help_text="Source URL of the article"
    )
    published_date = models.DateTimeField(
        help_text="When the article was originally published"
    )
    scraped_date = models.DateTimeField(
        auto_now_add=True,
        help_text="When the article was scraped"
    )
    source = models.CharField(
        max_length=200,
        help_text="Publication source (e.g., 'TechCrunch', 'Reuters')"
    )
    author = models.CharField(
        max_length=200,
        blank=True,
        help_text="Article author if available"
    )
    language = models.CharField(
        max_length=10,
        default='en',
        help_text="Article language code"
    )
    content_hash = models.CharField(
        max_length=64,
        unique=True,
        help_text="SHA-256 hash for deduplication"
    )
    
    # Analysis fields
    status = models.CharField(
        max_length=20,
        choices=ArticleStatus.choices,
        default=ArticleStatus.PENDING
    )
    relevance_score = models.FloatField(
        default=0.0,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        help_text="AI-calculated relevance score (0-1)"
    )
    sentiment_score = models.FloatField(
        null=True,
        blank=True,
        validators=[MinValueValidator(-1.0), MaxValueValidator(1.0)],
        help_text="Sentiment analysis score (-1 to 1)"
    )
    entities_extracted = models.JSONField(
        default=dict,
        help_text="Extracted entities (companies, people, locations, etc.)"
    )
    topics = models.JSONField(
        default=list,
        help_text="Identified topics/themes in the article"
    )
    
    # Source tracking
    query_template = models.ForeignKey(
        QueryTemplate,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="Template used to find this article"
    )
    search_keywords = models.JSONField(
        default=list,
        help_text="Keywords that matched this article"
    )
    
    class Meta:
        db_table = 'market_intelligence_news_articles'
        indexes = [
            models.Index(fields=['status', 'relevance_score']),
            models.Index(fields=['published_date', 'source']),
            models.Index(fields=['language', 'status']),
            models.Index(fields=['query_template', 'scraped_date']),
        ]
        ordering = ['-published_date']
    
    def __str__(self):
        return f"{self.title[:100]}... ({self.source})"
    
    def save(self, *args, **kwargs):
        """Auto-generate content hash for deduplication."""
        if not self.content_hash and self.content:
            self.content_hash = hashlib.sha256(
                self.content.encode('utf-8')
            ).hexdigest()
        super().save(*args, **kwargs)
    
    @property
    def is_relevant(self) -> bool:
        """Check if article meets relevance threshold."""
        return self.relevance_score >= 0.7
    
    @property
    def word_count(self) -> int:
        """Calculate approximate word count."""
        return len(self.content.split()) if self.content else 0


class TargetCompany(UUIDModel, TimestampedModel, PlatformModel):
    """
    Companies identified as potential investment targets.
    
    Tracks companies discovered through news analysis with lead scoring
    and progression through the investment pipeline.
    """
    
    class TargetStatus(models.TextChoices):
        IDENTIFIED = 'identified', 'Identified'
        RESEARCHING = 'researching', 'Under Research'
        QUALIFIED = 'qualified', 'Qualified Lead'
        CONTACTED = 'contacted', 'Initial Contact Made'
        ENGAGED = 'engaged', 'Actively Engaged'
        CONVERTED = 'converted', 'Converted to Partner'
        REJECTED = 'rejected', 'Rejected'
        ARCHIVED = 'archived', 'Archived'
    
    class CompanySize(models.TextChoices):
        STARTUP = 'startup', 'Startup (<50 employees)'
        SMALL = 'small', 'Small (50-200 employees)'
        MEDIUM = 'medium', 'Medium (200-1000 employees)'
        LARGE = 'large', 'Large (1000+ employees)'
        UNKNOWN = 'unknown', 'Unknown'
    
    # Basic company information
    company_name = models.CharField(
        max_length=255,
        help_text="Official company name"
    )
    trading_name = models.CharField(
        max_length=255,
        blank=True,
        help_text="Trading or brand name if different"
    )
    domain = models.URLField(
        blank=True,
        help_text="Company website domain"
    )
    linkedin_url = models.URLField(
        blank=True,
        help_text="LinkedIn company page URL"
    )
    description = models.TextField(
        blank=True,
        help_text="Company description/business model"
    )
    
    # Location and size
    headquarters_city = models.CharField(
        max_length=100,
        blank=True
    )
    headquarters_country = models.CharField(
        max_length=2,
        blank=True,
        help_text="ISO 3166-1 alpha-2 country code"
    )
    company_size = models.CharField(
        max_length=20,
        choices=CompanySize.choices,
        default=CompanySize.UNKNOWN
    )
    employee_count = models.IntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1)]
    )
    
    # Business details
    business_model = models.CharField(
        max_length=50,
        choices=[
            ('developer', 'Property Developer'),
            ('investor', 'Real Estate Investor'),
            ('operator', 'Property Operator'),
            ('platform', 'PropTech Platform'),
            ('service', 'Real Estate Services'),
            ('other', 'Other'),
        ],
        default='other'
    )
    focus_sectors = models.JSONField(
        default=list,
        help_text="List of real estate sectors (e.g., ['pbsa', 'office', 'retail'])"
    )
    geographic_focus = models.JSONField(
        default=list,
        help_text="Geographic markets of operation"
    )
    
    # Lead tracking
    status = models.CharField(
        max_length=20,
        choices=TargetStatus.choices,
        default=TargetStatus.IDENTIFIED
    )
    lead_score = models.FloatField(
        default=0.0,
        validators=[MinValueValidator(0.0), MaxValueValidator(100.0)],
        help_text="Calculated lead score (0-100)"
    )
    qualification_notes = models.TextField(
        blank=True,
        help_text="Notes on lead qualification and research"
    )
    
    # Source tracking
    source_articles = models.ManyToManyField(
        NewsArticle,
        blank=True,
        help_text="Articles that mentioned this company"
    )
    identified_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="User who identified this target"
    )
    assigned_analyst = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_targets',
        help_text="Analyst assigned to research this target"
    )
    
    # Conversion tracking
    development_partner = models.OneToOneField(
        'assessments.DevelopmentPartner',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="Development partner record if converted"
    )
    converted_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When target was converted to partner"
    )
    
    # Research data (enriched from external APIs)
    enrichment_data = models.JSONField(
        default=dict,
        help_text="Data from LinkedIn, Clearbit, etc."
    )
    last_enriched = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When enrichment data was last updated"
    )
    
    class Meta:
        db_table = 'market_intelligence_target_companies'
        unique_together = ['group', 'company_name']
        indexes = [
            models.Index(fields=['status', 'lead_score']),
            models.Index(fields=['business_model', 'status']),
            models.Index(fields=['assigned_analyst', 'status']),
            models.Index(fields=['headquarters_country', 'status']),
        ]
        ordering = ['-lead_score', '-created_at']
    
    def __str__(self):
        return f"{self.company_name} ({self.status})"
    
    @property
    def is_qualified(self) -> bool:
        """Check if target meets qualification threshold."""
        return self.lead_score >= 70.0
    
    @property
    def days_since_identification(self) -> int:
        """Calculate days since target was identified."""
        return (timezone.now() - self.created_at).days
    
    def calculate_lead_score(self) -> float:
        """
        Calculate lead score based on various factors.
        
        This is a simplified version - the service layer will have
        more sophisticated ML-based scoring.
        """
        score = 0.0
        
        # Base score for having basic information
        if self.domain:
            score += 10
        if self.linkedin_url:
            score += 10
        if self.description:
            score += 10
        
        # Business model alignment
        if self.business_model in ['developer', 'investor']:
            score += 20
        
        # PBSA focus
        if 'pbsa' in self.focus_sectors:
            score += 30
        
        # Recent news mentions
        recent_articles = self.source_articles.filter(
            published_date__gte=timezone.now() - timezone.timedelta(days=90)
        ).count()
        score += min(recent_articles * 5, 20)
        
        return min(score, 100.0)