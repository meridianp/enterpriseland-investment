"""
Meeting scheduler models for the EnterpriseLand platform.

Provides meeting scheduling, calendar integration, and availability management
for deal-related meetings and investor relations.
"""

import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.core.exceptions import ValidationError
from django.utils import timezone
from django_fsm import FSMField, transition

from assessments.base_models import GroupFilteredModel, TimestampedModel, UUIDModel
from accounts.models import User


class MeetingType(models.TextChoices):
    """Types of meetings that can be scheduled."""
    INITIAL_MEETING = 'initial_meeting', 'Initial Meeting'
    DUE_DILIGENCE = 'due_diligence', 'Due Diligence Session'
    INVESTMENT_COMMITTEE = 'investment_committee', 'Investment Committee'
    BOARD_MEETING = 'board_meeting', 'Board Meeting'
    INVESTOR_UPDATE = 'investor_update', 'Investor Update'
    QUARTERLY_REVIEW = 'quarterly_review', 'Quarterly Review'
    PARTNERSHIP_MEETING = 'partnership_meeting', 'Partnership Meeting'
    FOLLOW_UP = 'follow_up', 'Follow-up Meeting'
    CLOSING_MEETING = 'closing_meeting', 'Closing Meeting'
    OTHER = 'other', 'Other'


class MeetingStatus(models.TextChoices):
    """Status options for meeting lifecycle."""
    DRAFT = 'draft', 'Draft'
    SCHEDULED = 'scheduled', 'Scheduled'
    CONFIRMED = 'confirmed', 'Confirmed'
    IN_PROGRESS = 'in_progress', 'In Progress'
    COMPLETED = 'completed', 'Completed'
    CANCELLED = 'cancelled', 'Cancelled'
    RESCHEDULED = 'rescheduled', 'Rescheduled'
    NO_SHOW = 'no_show', 'No Show'


class RecurrenceType(models.TextChoices):
    """Meeting recurrence patterns."""
    NONE = 'none', 'None'
    DAILY = 'daily', 'Daily'
    WEEKLY = 'weekly', 'Weekly'
    BIWEEKLY = 'biweekly', 'Bi-weekly'
    MONTHLY = 'monthly', 'Monthly'
    QUARTERLY = 'quarterly', 'Quarterly'
    YEARLY = 'yearly', 'Yearly'


class CalendarProvider(models.TextChoices):
    """Supported calendar providers."""
    GOOGLE = 'google', 'Google Calendar'
    OUTLOOK = 'outlook', 'Microsoft Outlook'
    APPLE = 'apple', 'Apple Calendar'
    CALENDLY = 'calendly', 'Calendly'
    ZOOM = 'zoom', 'Zoom'
    TEAMS = 'teams', 'Microsoft Teams'
    INTERNAL = 'internal', 'Internal Calendar'


class Meeting(GroupFilteredModel, TimestampedModel, UUIDModel):
    """
    Core meeting model for scheduling and managing deal-related meetings.
    
    Supports calendar integration, attendee management, and workflow tracking.
    """
    
    # Core meeting information
    title = models.CharField(
        max_length=255,
        help_text="Meeting title"
    )
    description = models.TextField(
        blank=True,
        help_text="Meeting description and agenda"
    )
    meeting_type = models.CharField(
        max_length=30,
        choices=MeetingType.choices,
        default=MeetingType.OTHER,
        help_text="Type of meeting"
    )
    
    # Deal relationship
    deal = models.ForeignKey(
        'deals.Deal',
        on_delete=models.CASCADE,
        related_name='meetings',
        null=True,
        blank=True,
        help_text="Associated deal (optional)"
    )
    
    # Scheduling details
    start_time = models.DateTimeField(
        help_text="Meeting start time"
    )
    end_time = models.DateTimeField(
        help_text="Meeting end time"
    )
    timezone_name = models.CharField(
        max_length=50,
        default='UTC',
        help_text="Timezone for the meeting (e.g., 'America/New_York')"
    )
    
    # Location and format
    location = models.CharField(
        max_length=500,
        blank=True,
        help_text="Physical meeting location"
    )
    virtual_meeting_url = models.URLField(
        blank=True,
        help_text="Virtual meeting URL (Zoom, Teams, etc.)"
    )
    meeting_room = models.CharField(
        max_length=100,
        blank=True,
        help_text="Conference room or meeting room"
    )
    
    # Status tracking
    status = FSMField(
        default=MeetingStatus.DRAFT,
        choices=MeetingStatus.choices,
        help_text="Current meeting status"
    )
    
    # Organizer and attendees
    organizer = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='organized_meetings',
        help_text="Meeting organizer"
    )
    
    # Recurrence
    recurrence_type = models.CharField(
        max_length=20,
        choices=RecurrenceType.choices,
        default=RecurrenceType.NONE,
        help_text="Meeting recurrence pattern"
    )
    recurrence_interval = models.PositiveIntegerField(
        default=1,
        validators=[MinValueValidator(1), MaxValueValidator(12)],
        help_text="Recurrence interval (e.g., every 2 weeks)"
    )
    recurrence_end_date = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When recurrence ends"
    )
    parent_meeting = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='recurring_instances',
        help_text="Parent meeting for recurring instances"
    )
    
    # Calendar integration
    calendar_provider = models.CharField(
        max_length=20,
        choices=CalendarProvider.choices,
        default=CalendarProvider.INTERNAL,
        help_text="Calendar provider for integration"
    )
    external_calendar_id = models.CharField(
        max_length=255,
        blank=True,
        help_text="External calendar event ID"
    )
    calendar_sync_enabled = models.BooleanField(
        default=True,
        help_text="Whether to sync with external calendar"
    )
    
    # Meeting management
    requires_confirmation = models.BooleanField(
        default=True,
        help_text="Whether attendees need to confirm attendance"
    )
    allow_guests = models.BooleanField(
        default=False,
        help_text="Whether attendees can invite guests"
    )
    send_reminders = models.BooleanField(
        default=True,
        help_text="Whether to send meeting reminders"
    )
    
    # Preparation and materials
    agenda = models.JSONField(
        default=list,
        blank=True,
        help_text="""
        Meeting agenda items:
        [
            {
                "item": "Review Q3 results",
                "duration_minutes": 15,
                "presenter": "John Doe"
            }
        ]
        """
    )
    preparation_notes = models.TextField(
        blank=True,
        help_text="Notes for meeting preparation"
    )
    
    # Post-meeting
    meeting_notes = models.TextField(
        blank=True,
        help_text="Meeting notes and minutes"
    )
    action_items = models.JSONField(
        default=list,
        blank=True,
        help_text="""
        Action items from the meeting:
        [
            {
                "action": "Follow up on due diligence",
                "assigned_to": "user_id",
                "due_date": "2024-01-15"
            }
        ]
        """
    )
    next_steps = models.TextField(
        blank=True,
        help_text="Next steps identified in the meeting"
    )
    
    # Analytics
    actual_start_time = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the meeting actually started"
    )
    actual_end_time = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the meeting actually ended"
    )
    attendee_count = models.PositiveIntegerField(
        default=0,
        help_text="Number of attendees who joined"
    )
    
    class Meta:
        db_table = 'meetings'
        verbose_name = 'Meeting'
        verbose_name_plural = 'Meetings'
        ordering = ['start_time']
        indexes = [
            models.Index(fields=['group', 'start_time']),
            models.Index(fields=['group', 'deal']),
            models.Index(fields=['group', 'organizer']),
            models.Index(fields=['group', 'status']),
            models.Index(fields=['group', 'meeting_type']),
            models.Index(fields=['external_calendar_id']),
        ]
    
    def __str__(self):
        return f"{self.title} - {self.start_time.strftime('%Y-%m-%d %H:%M')}"
    
    def clean(self):
        """Validate meeting data."""
        if self.end_time <= self.start_time:
            raise ValidationError("End time must be after start time")
        
        # Check for reasonable meeting duration (max 8 hours)
        duration = self.end_time - self.start_time
        if duration > timedelta(hours=8):
            raise ValidationError("Meeting duration cannot exceed 8 hours")
        
        # Validate recurrence end date
        if self.recurrence_type != RecurrenceType.NONE and self.recurrence_end_date:
            if self.recurrence_end_date <= self.start_time:
                raise ValidationError("Recurrence end date must be after meeting start time")
    
    @property
    def duration_minutes(self) -> int:
        """Calculate meeting duration in minutes."""
        return int((self.end_time - self.start_time).total_seconds() / 60)
    
    @property
    def is_virtual(self) -> bool:
        """Check if meeting has virtual component."""
        return bool(self.virtual_meeting_url)
    
    @property
    def is_recurring(self) -> bool:
        """Check if meeting is recurring."""
        return self.recurrence_type != RecurrenceType.NONE
    
    @property
    def is_past(self) -> bool:
        """Check if meeting is in the past."""
        return self.end_time < timezone.now()
    
    @property
    def is_today(self) -> bool:
        """Check if meeting is today."""
        today = timezone.now().date()
        return self.start_time.date() == today
    
    # FSM transitions
    @transition(field=status, source=MeetingStatus.DRAFT, target=MeetingStatus.SCHEDULED)
    def schedule(self):
        """Schedule the meeting."""
        pass
    
    @transition(field=status, source=MeetingStatus.SCHEDULED, target=MeetingStatus.CONFIRMED)
    def confirm(self):
        """Confirm the meeting."""
        pass
    
    @transition(field=status, source=[MeetingStatus.SCHEDULED, MeetingStatus.CONFIRMED], target=MeetingStatus.IN_PROGRESS)
    def start_meeting(self):
        """Start the meeting."""
        self.actual_start_time = timezone.now()
    
    @transition(field=status, source=MeetingStatus.IN_PROGRESS, target=MeetingStatus.COMPLETED)
    def complete_meeting(self):
        """Complete the meeting."""
        self.actual_end_time = timezone.now()
    
    @transition(field=status, source=[MeetingStatus.SCHEDULED, MeetingStatus.CONFIRMED], target=MeetingStatus.CANCELLED)
    def cancel(self):
        """Cancel the meeting."""
        pass
    
    @transition(field=status, source=[MeetingStatus.SCHEDULED, MeetingStatus.CONFIRMED], target=MeetingStatus.RESCHEDULED)
    def reschedule(self):
        """Reschedule the meeting."""
        pass
    
    @transition(field=status, source=[MeetingStatus.SCHEDULED, MeetingStatus.CONFIRMED], target=MeetingStatus.NO_SHOW)
    def mark_no_show(self):
        """Mark as no show."""
        pass


class MeetingAttendee(GroupFilteredModel, TimestampedModel, UUIDModel):
    """
    Meeting attendee with response tracking and permissions.
    
    Handles both internal users and external participants.
    """
    
    class AttendeeType(models.TextChoices):
        REQUIRED = 'required', 'Required'
        OPTIONAL = 'optional', 'Optional'
        ORGANIZER = 'organizer', 'Organizer'
        PRESENTER = 'presenter', 'Presenter'
        OBSERVER = 'observer', 'Observer'
    
    class ResponseStatus(models.TextChoices):
        PENDING = 'pending', 'Pending'
        ACCEPTED = 'accepted', 'Accepted'
        DECLINED = 'declined', 'Declined'
        TENTATIVE = 'tentative', 'Tentative'
        NO_RESPONSE = 'no_response', 'No Response'
    
    meeting = models.ForeignKey(
        Meeting,
        on_delete=models.CASCADE,
        related_name='attendees'
    )
    
    # Attendee information
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='meeting_attendances',
        help_text="Internal user (if applicable)"
    )
    email = models.EmailField(
        help_text="Attendee email address"
    )
    name = models.CharField(
        max_length=255,
        help_text="Attendee full name"
    )
    organization = models.CharField(
        max_length=255,
        blank=True,
        help_text="Attendee organization"
    )
    
    # Attendee role and permissions
    attendee_type = models.CharField(
        max_length=20,
        choices=AttendeeType.choices,
        default=AttendeeType.REQUIRED
    )
    can_edit_agenda = models.BooleanField(
        default=False,
        help_text="Whether attendee can edit meeting agenda"
    )
    can_invite_guests = models.BooleanField(
        default=False,
        help_text="Whether attendee can invite additional guests"
    )
    
    # Response tracking
    response_status = models.CharField(
        max_length=20,
        choices=ResponseStatus.choices,
        default=ResponseStatus.PENDING
    )
    response_notes = models.TextField(
        blank=True,
        help_text="Notes provided with response"
    )
    responded_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When attendee responded"
    )
    
    # Attendance tracking
    joined_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When attendee joined the meeting"
    )
    left_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When attendee left the meeting"
    )
    attended = models.BooleanField(
        default=False,
        help_text="Whether attendee actually attended"
    )
    
    # Notifications
    send_invitations = models.BooleanField(
        default=True,
        help_text="Whether to send meeting invitations"
    )
    send_reminders = models.BooleanField(
        default=True,
        help_text="Whether to send meeting reminders"
    )
    
    class Meta:
        db_table = 'meeting_attendees'
        verbose_name = 'Meeting Attendee'
        verbose_name_plural = 'Meeting Attendees'
        ordering = ['attendee_type', 'name']
        indexes = [
            models.Index(fields=['group', 'meeting']),
            models.Index(fields=['group', 'user']),
            models.Index(fields=['group', 'response_status']),
            models.Index(fields=['email']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['meeting', 'email'],
                name='unique_attendee_per_meeting'
            )
        ]
    
    def __str__(self):
        return f"{self.name} ({self.get_attendee_type_display()}) - {self.meeting.title}"
    
    def respond(self, status: str, notes: str = ''):
        """Record attendee response to meeting invitation."""
        self.response_status = status
        self.response_notes = notes
        self.responded_at = timezone.now()
        self.save()
    
    @property
    def attendance_duration_minutes(self) -> Optional[int]:
        """Calculate how long attendee was in the meeting."""
        if self.joined_at and self.left_at:
            return int((self.left_at - self.joined_at).total_seconds() / 60)
        return None


class MeetingResource(GroupFilteredModel, TimestampedModel, UUIDModel):
    """
    Resources required for meetings (rooms, equipment, catering).
    
    Handles resource booking and availability checking.
    """
    
    class ResourceType(models.TextChoices):
        CONFERENCE_ROOM = 'conference_room', 'Conference Room'
        EQUIPMENT = 'equipment', 'Equipment'
        CATERING = 'catering', 'Catering'
        TRANSPORTATION = 'transportation', 'Transportation'
        ACCOMMODATION = 'accommodation', 'Accommodation'
        OTHER = 'other', 'Other'
    
    class BookingStatus(models.TextChoices):
        AVAILABLE = 'available', 'Available'
        RESERVED = 'reserved', 'Reserved'
        CONFIRMED = 'confirmed', 'Confirmed'
        IN_USE = 'in_use', 'In Use'
        UNAVAILABLE = 'unavailable', 'Unavailable'
    
    # Resource information
    name = models.CharField(
        max_length=255,
        help_text="Resource name"
    )
    resource_type = models.CharField(
        max_length=20,
        choices=ResourceType.choices,
        default=ResourceType.OTHER
    )
    description = models.TextField(
        blank=True,
        help_text="Resource description and capabilities"
    )
    
    # Capacity and specifications
    capacity = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Maximum capacity (for rooms)"
    )
    location = models.CharField(
        max_length=255,
        blank=True,
        help_text="Resource location"
    )
    specifications = models.JSONField(
        default=dict,
        blank=True,
        help_text="Resource specifications and features"
    )
    
    # Availability
    is_active = models.BooleanField(
        default=True,
        help_text="Whether resource is available for booking"
    )
    requires_approval = models.BooleanField(
        default=False,
        help_text="Whether booking requires approval"
    )
    
    # Cost
    hourly_cost = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Cost per hour (if applicable)"
    )
    setup_cost = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="One-time setup cost"
    )
    
    class Meta:
        db_table = 'meeting_resources'
        verbose_name = 'Meeting Resource'
        verbose_name_plural = 'Meeting Resources'
        ordering = ['resource_type', 'name']
        indexes = [
            models.Index(fields=['group', 'resource_type']),
            models.Index(fields=['group', 'is_active']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['group', 'name'],
                name='unique_resource_name_per_group'
            )
        ]
    
    def __str__(self):
        return f"{self.name} ({self.get_resource_type_display()})"
    
    def is_available(self, start_time: datetime, end_time: datetime) -> bool:
        """Check if resource is available for the given time period."""
        if not self.is_active:
            return False
        
        # Check for overlapping bookings
        overlapping_bookings = self.bookings.filter(
            models.Q(start_time__lt=end_time) & models.Q(end_time__gt=start_time),
            status__in=[
                MeetingResourceBooking.BookingStatus.CONFIRMED,
                MeetingResourceBooking.BookingStatus.IN_USE
            ]
        )
        
        return not overlapping_bookings.exists()


class MeetingResourceBooking(GroupFilteredModel, TimestampedModel, UUIDModel):
    """
    Resource booking for meetings.
    
    Tracks resource reservations and usage.
    """
    
    class BookingStatus(models.TextChoices):
        PENDING = 'pending', 'Pending'
        CONFIRMED = 'confirmed', 'Confirmed'
        IN_USE = 'in_use', 'In Use'
        COMPLETED = 'completed', 'Completed'
        CANCELLED = 'cancelled', 'Cancelled'
    
    meeting = models.ForeignKey(
        Meeting,
        on_delete=models.CASCADE,
        related_name='resource_bookings'
    )
    resource = models.ForeignKey(
        MeetingResource,
        on_delete=models.CASCADE,
        related_name='bookings'
    )
    
    # Booking details
    start_time = models.DateTimeField(
        help_text="Resource booking start time"
    )
    end_time = models.DateTimeField(
        help_text="Resource booking end time"
    )
    status = models.CharField(
        max_length=20,
        choices=BookingStatus.choices,
        default=BookingStatus.PENDING
    )
    
    # Setup and breakdown time
    setup_minutes = models.PositiveIntegerField(
        default=0,
        help_text="Setup time required before meeting"
    )
    breakdown_minutes = models.PositiveIntegerField(
        default=0,
        help_text="Breakdown time required after meeting"
    )
    
    # Cost tracking
    estimated_cost = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Estimated booking cost"
    )
    actual_cost = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Actual booking cost"
    )
    
    # Notes
    booking_notes = models.TextField(
        blank=True,
        help_text="Special requirements or notes"
    )
    
    class Meta:
        db_table = 'meeting_resource_bookings'
        verbose_name = 'Meeting Resource Booking'
        verbose_name_plural = 'Meeting Resource Bookings'
        ordering = ['start_time']
        indexes = [
            models.Index(fields=['group', 'meeting']),
            models.Index(fields=['group', 'resource']),
            models.Index(fields=['group', 'start_time']),
            models.Index(fields=['group', 'status']),
        ]
    
    def __str__(self):
        return f"{self.resource.name} for {self.meeting.title}"
    
    def clean(self):
        """Validate booking data."""
        if self.end_time <= self.start_time:
            raise ValidationError("End time must be after start time")
        
        # Check resource availability
        if not self.resource.is_available(self.start_time, self.end_time):
            raise ValidationError("Resource is not available for the requested time")
    
    @property
    def total_duration_minutes(self) -> int:
        """Calculate total booking duration including setup/breakdown."""
        base_duration = int((self.end_time - self.start_time).total_seconds() / 60)
        return base_duration + self.setup_minutes + self.breakdown_minutes
    
    def calculate_cost(self) -> Optional[float]:
        """Calculate booking cost based on resource pricing."""
        if not self.resource.hourly_cost:
            return None
        
        duration_hours = self.total_duration_minutes / 60
        cost = float(self.resource.hourly_cost) * duration_hours
        
        if self.resource.setup_cost:
            cost += float(self.resource.setup_cost)
        
        return cost


class AvailabilitySlot(GroupFilteredModel, TimestampedModel, UUIDModel):
    """
    User availability slots for meeting scheduling.
    
    Allows users to define when they are available for meetings.
    """
    
    class SlotType(models.TextChoices):
        AVAILABLE = 'available', 'Available'
        BUSY = 'busy', 'Busy'
        OUT_OF_OFFICE = 'out_of_office', 'Out of Office'
        TENTATIVE = 'tentative', 'Tentative'
    
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='availability_slots'
    )
    
    # Time slot
    start_time = models.DateTimeField(
        help_text="Slot start time"
    )
    end_time = models.DateTimeField(
        help_text="Slot end time"
    )
    slot_type = models.CharField(
        max_length=20,
        choices=SlotType.choices,
        default=SlotType.AVAILABLE
    )
    
    # Recurrence for regular availability
    is_recurring = models.BooleanField(
        default=False,
        help_text="Whether this is a recurring availability pattern"
    )
    recurrence_pattern = models.JSONField(
        default=dict,
        blank=True,
        help_text="Recurrence pattern configuration"
    )
    
    # Context
    title = models.CharField(
        max_length=255,
        blank=True,
        help_text="Slot title or description"
    )
    notes = models.TextField(
        blank=True,
        help_text="Additional notes about availability"
    )
    
    # Preferences
    preferred_meeting_types = models.JSONField(
        default=list,
        blank=True,
        help_text="Preferred meeting types for this slot"
    )
    max_meetings_per_slot = models.PositiveIntegerField(
        default=1,
        help_text="Maximum meetings that can be scheduled in this slot"
    )
    
    class Meta:
        db_table = 'availability_slots'
        verbose_name = 'Availability Slot'
        verbose_name_plural = 'Availability Slots'
        ordering = ['start_time']
        indexes = [
            models.Index(fields=['group', 'user']),
            models.Index(fields=['group', 'start_time']),
            models.Index(fields=['group', 'slot_type']),
        ]
    
    def __str__(self):
        return f"{self.user.get_full_name()} - {self.get_slot_type_display()} ({self.start_time})"
    
    def clean(self):
        """Validate availability slot."""
        if self.end_time <= self.start_time:
            raise ValidationError("End time must be after start time")
    
    @property
    def duration_minutes(self) -> int:
        """Calculate slot duration in minutes."""
        return int((self.end_time - self.start_time).total_seconds() / 60)
    
    def is_available_for_meeting(self, meeting_duration_minutes: int) -> bool:
        """Check if slot is available for a meeting of given duration."""
        if self.slot_type != self.SlotType.AVAILABLE:
            return False
        
        if self.duration_minutes < meeting_duration_minutes:
            return False
        
        # Check if maximum meetings limit is reached
        current_meetings = Meeting.objects.filter(
            attendees__user=self.user,
            start_time__gte=self.start_time,
            end_time__lte=self.end_time,
            status__in=[MeetingStatus.SCHEDULED, MeetingStatus.CONFIRMED]
        ).count()
        
        return current_meetings < self.max_meetings_per_slot