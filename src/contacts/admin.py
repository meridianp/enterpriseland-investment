"""
Admin configuration for the contacts app.
"""

from django.contrib import admin
from django.utils.html import format_html

from .models import Contact, ContactActivity, ContactList, ContactPartner


@admin.register(Contact)
class ContactAdmin(admin.ModelAdmin):
    """Admin interface for Contact model."""
    
    list_display = [
        'email', 'full_name', 'company_name', 'contact_type', 
        'status', 'current_score', 'assigned_to', 'last_activity_at'
    ]
    list_filter = [
        'status', 'contact_type', 'email_opt_in', 'country',
        'created_at', 'last_activity_at'
    ]
    search_fields = [
        'email', 'first_name', 'last_name', 'company_name',
        'notes', 'city'
    ]
    readonly_fields = [
        'id', 'current_score', 'last_activity_at', 
        'last_email_sent_at', 'last_email_opened_at',
        'created_at', 'updated_at'
    ]
    fieldsets = (
        ('Basic Information', {
            'fields': (
                'id', 'group', 'email', 'first_name', 'last_name',
                'company_name', 'contact_type', 'status'
            )
        }),
        ('Contact Details', {
            'fields': (
                'phone_primary', 'phone_secondary', 'website',
                'city', 'country', 'job_title', 'department'
            )
        }),
        ('Marketing', {
            'fields': (
                'current_score', 'source', 'tags', 
                'email_opt_in', 'sms_opt_in', 'assigned_to'
            )
        }),
        ('Activity Tracking', {
            'fields': (
                'last_activity_at', 'last_email_sent_at', 
                'last_email_opened_at'
            )
        }),
        ('Additional Information', {
            'fields': ('notes', 'custom_fields')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        })
    )
    
    def full_name(self, obj):
        """Display full name for individual contacts."""
        return obj.full_name
    full_name.short_description = 'Full Name'


@admin.register(ContactActivity)
class ContactActivityAdmin(admin.ModelAdmin):
    """Admin interface for ContactActivity model."""
    
    list_display = [
        'contact', 'activity_type', 'subject', 'actor',
        'follow_up_required', 'created_at'
    ]
    list_filter = [
        'activity_type', 'follow_up_required', 'created_at'
    ]
    search_fields = [
        'subject', 'description', 'outcome',
        'contact__email', 'contact__first_name', 'contact__last_name'
    ]
    readonly_fields = ['id', 'created_at', 'updated_at']
    raw_id_fields = ['contact', 'actor']
    
    fieldsets = (
        ('Activity Information', {
            'fields': (
                'id', 'group', 'contact', 'activity_type',
                'subject', 'description', 'actor'
            )
        }),
        ('Related Object', {
            'fields': (
                'content_type', 'object_id'
            )
        }),
        ('Outcome & Follow-up', {
            'fields': (
                'outcome', 'follow_up_required', 'follow_up_date'
            )
        }),
        ('Metadata', {
            'fields': ('metadata',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        })
    )


@admin.register(ContactList)
class ContactListAdmin(admin.ModelAdmin):
    """Admin interface for ContactList model."""
    
    list_display = [
        'name', 'is_dynamic', 'is_public', 'created_by',
        'contact_count', 'created_at'
    ]
    list_filter = [
        'is_dynamic', 'is_public', 'created_at'
    ]
    search_fields = ['name', 'description']
    readonly_fields = ['id', 'created_at', 'updated_at']
    filter_horizontal = ['contacts']
    
    fieldsets = (
        ('Basic Information', {
            'fields': (
                'id', 'group', 'name', 'description',
                'is_dynamic', 'is_public', 'created_by'
            )
        }),
        ('Dynamic List Settings', {
            'fields': ('filter_criteria',),
            'description': 'Only applicable for dynamic lists'
        }),
        ('Static List Members', {
            'fields': ('contacts',),
            'description': 'Only applicable for static lists'
        }),
        ('Metadata', {
            'fields': ('tags',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        })
    )
    
    def contact_count(self, obj):
        """Display number of contacts in the list."""
        return obj.get_contact_count()
    contact_count.short_description = 'Contacts'


@admin.register(ContactPartner)
class ContactPartnerAdmin(admin.ModelAdmin):
    """Admin interface for ContactPartner relationships."""
    
    list_display = [
        'contact', 'partner', 'relationship_type', 
        'is_primary', 'start_date', 'end_date'
    ]
    list_filter = [
        'relationship_type', 'is_primary', 'start_date'
    ]
    search_fields = [
        'contact__email', 'contact__first_name', 'contact__last_name',
        'partner__company_name', 'notes'
    ]
    readonly_fields = ['id', 'created_at', 'updated_at']
    raw_id_fields = ['contact', 'partner']
    
    fieldsets = (
        ('Relationship', {
            'fields': (
                'id', 'group', 'contact', 'partner',
                'relationship_type', 'is_primary'
            )
        }),
        ('Timeline', {
            'fields': ('start_date', 'end_date')
        }),
        ('Additional Information', {
            'fields': ('notes',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        })
    )
