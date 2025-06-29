"""
Meeting scheduler service for the EnterpriseLand platform.

Handles meeting scheduling, calendar integration, availability checking,
resource booking, and automated notifications.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from django.db import transaction
from django.db.models import Q, Count
from django.utils import timezone
from django.core.exceptions import ValidationError

from accounts.models import User
from notifications.models import Notification
from integrations.services.calendar_service import CalendarService
from ..models import (
    Meeting, MeetingAttendee, MeetingResource, MeetingResourceBooking,
    AvailabilitySlot, Deal, MeetingType, MeetingStatus, RecurrenceType
)

logger = logging.getLogger(__name__)


class MeetingSchedulingError(Exception):
    """Exception raised during meeting scheduling operations."""
    pass


class MeetingSchedulerService:
    """
    Service for managing meeting scheduling, availability, and calendar integration.
    
    Provides comprehensive meeting lifecycle management with smart scheduling,
    resource booking, and multi-provider calendar integration.
    """
    
    def __init__(self):
        self.calendar_service = CalendarService()
    
    @transaction.atomic
    def create_meeting(self, organizer: User, title: str, start_time: datetime,
                      end_time: datetime, attendee_emails: List[str] = None,
                      deal: Deal = None, meeting_type: str = MeetingType.OTHER,
                      location: str = '', virtual_meeting_url: str = '',
                      agenda: List[Dict] = None, **kwargs) -> Meeting:
        """
        Create a new meeting with attendees and optional resource booking.
        
        Args:
            organizer: User organizing the meeting
            title: Meeting title
            start_time: Meeting start time
            end_time: Meeting end time
            attendee_emails: List of attendee email addresses
            deal: Associated deal (optional)
            meeting_type: Type of meeting
            location: Physical location
            virtual_meeting_url: Virtual meeting URL
            agenda: Meeting agenda items
            **kwargs: Additional meeting parameters
            
        Returns:
            Created Meeting instance
        """
        # Validate meeting times
        self._validate_meeting_times(start_time, end_time)
        
        # Check organizer availability
        if not self._is_user_available(organizer, start_time, end_time):
            raise MeetingSchedulingError(
                f"Organizer {organizer.get_full_name()} is not available at the requested time"
            )
        
        # Create meeting
        meeting = Meeting.objects.create(
            group=organizer.groups.first(),
            title=title,
            start_time=start_time,
            end_time=end_time,
            organizer=organizer,
            deal=deal,
            meeting_type=meeting_type,
            location=location,
            virtual_meeting_url=virtual_meeting_url,
            agenda=agenda or [],
            **kwargs
        )
        
        # Add organizer as attendee
        self._add_attendee(
            meeting=meeting,
            email=organizer.email,
            name=organizer.get_full_name(),
            user=organizer,
            attendee_type=MeetingAttendee.AttendeeType.ORGANIZER
        )
        
        # Add other attendees
        if attendee_emails:
            for email in attendee_emails:
                user = User.objects.filter(email=email).first()
                name = user.get_full_name() if user else email
                
                self._add_attendee(
                    meeting=meeting,
                    email=email,
                    name=name,
                    user=user,
                    attendee_type=MeetingAttendee.AttendeeType.REQUIRED
                )
        
        # Schedule the meeting
        meeting.schedule()
        meeting.save()
        
        # Create calendar events
        self._create_calendar_events(meeting)
        
        # Send invitations
        self._send_meeting_invitations(meeting)
        
        logger.info(f"Created meeting '{title}' for {start_time}")
        return meeting
    
    def _validate_meeting_times(self, start_time: datetime, end_time: datetime):
        """Validate meeting start and end times."""
        if end_time <= start_time:
            raise ValidationError("End time must be after start time")
        
        # Check for reasonable meeting duration (max 8 hours)
        duration = end_time - start_time
        if duration > timedelta(hours=8):
            raise ValidationError("Meeting duration cannot exceed 8 hours")
        
        # Check if meeting is in the past
        if start_time < timezone.now():
            raise ValidationError("Cannot schedule meetings in the past")
    
    def _add_attendee(self, meeting: Meeting, email: str, name: str,
                     user: User = None, attendee_type: str = MeetingAttendee.AttendeeType.REQUIRED,
                     **kwargs) -> MeetingAttendee:
        """Add an attendee to the meeting."""
        return MeetingAttendee.objects.create(
            group=meeting.group,
            meeting=meeting,
            email=email,
            name=name,
            user=user,
            attendee_type=attendee_type,
            **kwargs
        )
    
    def find_optimal_meeting_time(self, organizer: User, attendee_emails: List[str],
                                 duration_minutes: int, preferred_start_date: datetime = None,
                                 preferred_end_date: datetime = None,
                                 meeting_type: str = MeetingType.OTHER,
                                 business_hours_only: bool = True) -> List[Dict[str, datetime]]:
        """
        Find optimal meeting times based on attendee availability.
        
        Args:
            organizer: Meeting organizer
            attendee_emails: List of attendee email addresses
            duration_minutes: Required meeting duration in minutes
            preferred_start_date: Earliest preferred date
            preferred_end_date: Latest preferred date
            meeting_type: Type of meeting for preferences
            business_hours_only: Whether to only consider business hours
            
        Returns:
            List of suggested time slots with start and end times
        """
        if not preferred_start_date:
            preferred_start_date = timezone.now()
        
        if not preferred_end_date:
            preferred_end_date = preferred_start_date + timedelta(days=14)
        
        # Get all users involved
        users = [organizer]
        for email in attendee_emails:
            user = User.objects.filter(email=email).first()
            if user:
                users.append(user)
        
        # Find common availability
        suggested_slots = []
        current_time = preferred_start_date.replace(minute=0, second=0, microsecond=0)
        
        while current_time < preferred_end_date and len(suggested_slots) < 10:
            # Check business hours constraint
            if business_hours_only and not self._is_business_hours(current_time):
                current_time += timedelta(hours=1)
                continue
            
            meeting_end_time = current_time + timedelta(minutes=duration_minutes)
            
            # Check if all users are available
            if self._are_users_available(users, current_time, meeting_end_time):
                suggested_slots.append({
                    'start_time': current_time,
                    'end_time': meeting_end_time,
                    'score': self._calculate_time_slot_score(
                        users, current_time, meeting_end_time, meeting_type
                    )
                })
            
            current_time += timedelta(minutes=30)  # Check every 30 minutes
        
        # Sort by score (higher is better)
        suggested_slots.sort(key=lambda x: x['score'], reverse=True)
        
        return suggested_slots[:5]  # Return top 5 suggestions
    
    def _is_business_hours(self, dt: datetime) -> bool:
        """Check if datetime falls within business hours."""
        # Monday = 0, Sunday = 6
        if dt.weekday() >= 5:  # Weekend
            return False
        
        hour = dt.hour
        return 9 <= hour <= 17  # 9 AM to 5 PM
    
    def _are_users_available(self, users: List[User], start_time: datetime,
                           end_time: datetime) -> bool:
        """Check if all users are available for the given time slot."""
        for user in users:
            if not self._is_user_available(user, start_time, end_time):
                return False
        return True
    
    def _is_user_available(self, user: User, start_time: datetime,
                          end_time: datetime) -> bool:
        """Check if a user is available for the given time slot."""
        # Check for conflicting meetings
        conflicting_meetings = Meeting.objects.filter(
            attendees__user=user,
            start_time__lt=end_time,
            end_time__gt=start_time,
            status__in=[MeetingStatus.SCHEDULED, MeetingStatus.CONFIRMED, MeetingStatus.IN_PROGRESS]
        )
        
        if conflicting_meetings.exists():
            return False
        
        # Check availability slots
        availability_slots = AvailabilitySlot.objects.filter(
            user=user,
            start_time__lte=start_time,
            end_time__gte=end_time,
            slot_type=AvailabilitySlot.SlotType.AVAILABLE
        )
        
        # If user has explicit availability slots, they must be available
        if AvailabilitySlot.objects.filter(user=user).exists():
            return availability_slots.exists()
        
        # If no explicit availability, assume available during business hours
        return self._is_business_hours(start_time)
    
    def _calculate_time_slot_score(self, users: List[User], start_time: datetime,
                                  end_time: datetime, meeting_type: str) -> float:
        """Calculate a score for a time slot based on various factors."""
        score = 100.0  # Base score
        
        # Prefer business hours
        if self._is_business_hours(start_time):
            score += 20
        
        # Prefer times that match user preferences
        for user in users:
            user_preference_score = self._get_user_time_preference_score(
                user, start_time, meeting_type
            )
            score += user_preference_score
        
        # Prefer earlier in the day
        hour_penalty = (start_time.hour - 9) * 2  # Penalty increases after 9 AM
        score -= max(0, hour_penalty)
        
        # Prefer earlier in the week
        weekday_bonus = (7 - start_time.weekday()) * 3
        score += weekday_bonus
        
        return score
    
    def _get_user_time_preference_score(self, user: User, start_time: datetime,
                                       meeting_type: str) -> float:
        """Get user's preference score for a specific time."""
        # Check if user has preferred times for this meeting type
        availability_slots = AvailabilitySlot.objects.filter(
            user=user,
            start_time__time__lte=start_time.time(),
            end_time__time__gte=start_time.time(),
            preferred_meeting_types__contains=[meeting_type]
        )
        
        if availability_slots.exists():
            return 15.0
        
        return 0.0
    
    @transaction.atomic
    def book_resources(self, meeting: Meeting, resource_ids: List[str],
                      setup_minutes: int = 0, breakdown_minutes: int = 0) -> List[MeetingResourceBooking]:
        """
        Book resources for a meeting.
        
        Args:
            meeting: The meeting to book resources for
            resource_ids: List of resource UUIDs to book
            setup_minutes: Setup time before meeting
            breakdown_minutes: Breakdown time after meeting
            
        Returns:
            List of created resource bookings
        """
        bookings = []
        
        # Calculate extended time range including setup/breakdown
        booking_start = meeting.start_time - timedelta(minutes=setup_minutes)
        booking_end = meeting.end_time + timedelta(minutes=breakdown_minutes)
        
        for resource_id in resource_ids:
            try:
                resource = MeetingResource.objects.get(
                    id=resource_id,
                    group=meeting.group,
                    is_active=True
                )
                
                # Check availability
                if not resource.is_available(booking_start, booking_end):
                    raise MeetingSchedulingError(
                        f"Resource '{resource.name}' is not available for the requested time"
                    )
                
                # Create booking
                booking = MeetingResourceBooking.objects.create(
                    group=meeting.group,
                    meeting=meeting,
                    resource=resource,
                    start_time=booking_start,
                    end_time=booking_end,
                    setup_minutes=setup_minutes,
                    breakdown_minutes=breakdown_minutes,
                    status=MeetingResourceBooking.BookingStatus.CONFIRMED
                )
                
                # Calculate estimated cost
                booking.estimated_cost = booking.calculate_cost()
                booking.save()
                
                bookings.append(booking)
                
                logger.info(f"Booked resource '{resource.name}' for meeting '{meeting.title}'")
                
            except MeetingResource.DoesNotExist:
                logger.warning(f"Resource with ID {resource_id} not found")
                continue
        
        return bookings
    
    def _create_calendar_events(self, meeting: Meeting):
        """Create calendar events for meeting attendees."""
        if not meeting.calendar_sync_enabled:
            return
        
        try:
            # Create calendar event for organizer
            if meeting.organizer.email:
                event_id = self.calendar_service.create_event(
                    title=meeting.title,
                    start_time=meeting.start_time,
                    end_time=meeting.end_time,
                    description=meeting.description,
                    location=meeting.location or meeting.virtual_meeting_url,
                    attendees=[attendee.email for attendee in meeting.attendees.all()],
                    user_email=meeting.organizer.email
                )
                
                if event_id:
                    meeting.external_calendar_id = event_id
                    meeting.save()
        
        except Exception as e:
            logger.error(f"Failed to create calendar event: {str(e)}")
    
    def _send_meeting_invitations(self, meeting: Meeting):
        """Send meeting invitations to attendees."""
        for attendee in meeting.attendees.all():
            if not attendee.send_invitations:
                continue
            
            # Create notification
            Notification.objects.create(
                user=attendee.user,
                title=f"Meeting Invitation: {meeting.title}",
                message=f"You have been invited to '{meeting.title}' on {meeting.start_time.strftime('%B %d, %Y at %I:%M %p')}",
                notification_type='MEETING_INVITATION',
                related_object_id=str(meeting.id),
                action_url=f"/meetings/{meeting.id}/"
            )
    
    @transaction.atomic
    def reschedule_meeting(self, meeting: Meeting, new_start_time: datetime,
                          new_end_time: datetime, user: User,
                          reason: str = '') -> Meeting:
        """
        Reschedule an existing meeting.
        
        Args:
            meeting: Meeting to reschedule
            new_start_time: New start time
            new_end_time: New end time
            user: User requesting the reschedule
            reason: Reason for rescheduling
            
        Returns:
            Updated meeting instance
        """
        # Validate new times
        self._validate_meeting_times(new_start_time, new_end_time)
        
        # Check organizer availability for new time
        if not self._is_user_available(meeting.organizer, new_start_time, new_end_time):
            raise MeetingSchedulingError(
                f"Organizer is not available at the new requested time"
            )
        
        # Update meeting
        old_start_time = meeting.start_time
        meeting.start_time = new_start_time
        meeting.end_time = new_end_time
        meeting.reschedule()
        meeting.save()
        
        # Update resource bookings
        for booking in meeting.resource_bookings.all():
            duration = booking.end_time - booking.start_time
            booking.start_time = new_start_time - timedelta(minutes=booking.setup_minutes)
            booking.end_time = new_end_time + timedelta(minutes=booking.breakdown_minutes)
            booking.save()
        
        # Update calendar events
        self._update_calendar_event(meeting)
        
        # Notify attendees
        self._send_reschedule_notifications(meeting, old_start_time, reason)
        
        logger.info(f"Rescheduled meeting '{meeting.title}' from {old_start_time} to {new_start_time}")
        return meeting
    
    def _update_calendar_event(self, meeting: Meeting):
        """Update calendar event for rescheduled meeting."""
        if not meeting.calendar_sync_enabled or not meeting.external_calendar_id:
            return
        
        try:
            self.calendar_service.update_event(
                event_id=meeting.external_calendar_id,
                title=meeting.title,
                start_time=meeting.start_time,
                end_time=meeting.end_time,
                description=meeting.description,
                location=meeting.location or meeting.virtual_meeting_url,
                user_email=meeting.organizer.email
            )
        except Exception as e:
            logger.error(f"Failed to update calendar event: {str(e)}")
    
    def _send_reschedule_notifications(self, meeting: Meeting, old_start_time: datetime,
                                     reason: str):
        """Send reschedule notifications to attendees."""
        for attendee in meeting.attendees.all():
            if not attendee.user:
                continue
            
            message = (
                f"Meeting '{meeting.title}' has been rescheduled from "
                f"{old_start_time.strftime('%B %d, %Y at %I:%M %p')} to "
                f"{meeting.start_time.strftime('%B %d, %Y at %I:%M %p')}"
            )
            
            if reason:
                message += f"\n\nReason: {reason}"
            
            Notification.objects.create(
                user=attendee.user,
                title=f"Meeting Rescheduled: {meeting.title}",
                message=message,
                notification_type='MEETING_RESCHEDULED',
                related_object_id=str(meeting.id),
                action_url=f"/meetings/{meeting.id}/"
            )
    
    @transaction.atomic
    def cancel_meeting(self, meeting: Meeting, user: User, reason: str = ''):
        """
        Cancel a meeting and notify attendees.
        
        Args:
            meeting: Meeting to cancel
            user: User cancelling the meeting
            reason: Reason for cancellation
        """
        meeting.cancel()
        meeting.save()
        
        # Cancel resource bookings
        meeting.resource_bookings.update(
            status=MeetingResourceBooking.BookingStatus.CANCELLED
        )
        
        # Cancel calendar event
        self._cancel_calendar_event(meeting)
        
        # Notify attendees
        self._send_cancellation_notifications(meeting, reason)
        
        logger.info(f"Cancelled meeting '{meeting.title}' by {user.get_full_name()}")
    
    def _cancel_calendar_event(self, meeting: Meeting):
        """Cancel calendar event for cancelled meeting."""
        if not meeting.calendar_sync_enabled or not meeting.external_calendar_id:
            return
        
        try:
            self.calendar_service.delete_event(
                event_id=meeting.external_calendar_id,
                user_email=meeting.organizer.email
            )
        except Exception as e:
            logger.error(f"Failed to cancel calendar event: {str(e)}")
    
    def _send_cancellation_notifications(self, meeting: Meeting, reason: str):
        """Send cancellation notifications to attendees."""
        for attendee in meeting.attendees.all():
            if not attendee.user:
                continue
            
            message = f"Meeting '{meeting.title}' scheduled for {meeting.start_time.strftime('%B %d, %Y at %I:%M %p')} has been cancelled"
            
            if reason:
                message += f"\n\nReason: {reason}"
            
            Notification.objects.create(
                user=attendee.user,
                title=f"Meeting Cancelled: {meeting.title}",
                message=message,
                notification_type='MEETING_CANCELLED',
                related_object_id=str(meeting.id),
                action_url=f"/meetings/{meeting.id}/"
            )
    
    def get_user_availability(self, user: User, start_date: datetime,
                            end_date: datetime) -> List[Dict[str, Any]]:
        """
        Get user availability for a date range.
        
        Args:
            user: User to check availability for
            start_date: Start of date range
            end_date: End of date range
            
        Returns:
            List of availability periods with details
        """
        availability = []
        
        # Get explicit availability slots
        availability_slots = AvailabilitySlot.objects.filter(
            user=user,
            start_time__gte=start_date,
            end_time__lte=end_date
        ).order_by('start_time')
        
        # Get meetings in the date range
        meetings = Meeting.objects.filter(
            attendees__user=user,
            start_time__gte=start_date,
            end_time__lte=end_date,
            status__in=[MeetingStatus.SCHEDULED, MeetingStatus.CONFIRMED]
        ).order_by('start_time')
        
        # Combine availability and busy periods
        current_time = start_date
        
        for slot in availability_slots:
            if slot.start_time > current_time:
                # Gap before this slot
                availability.append({
                    'start_time': current_time,
                    'end_time': slot.start_time,
                    'type': 'unknown',
                    'title': 'No explicit availability'
                })
            
            availability.append({
                'start_time': slot.start_time,
                'end_time': slot.end_time,
                'type': slot.slot_type,
                'title': slot.title or f"{slot.get_slot_type_display()}"
            })
            
            current_time = slot.end_time
        
        # Add meetings as busy periods
        for meeting in meetings:
            availability.append({
                'start_time': meeting.start_time,
                'end_time': meeting.end_time,
                'type': 'busy',
                'title': f"Meeting: {meeting.title}",
                'meeting_id': str(meeting.id)
            })
        
        # Sort by start time
        availability.sort(key=lambda x: x['start_time'])
        
        return availability
    
    def get_meeting_analytics(self, group_id: str = None, 
                             start_date: datetime = None,
                             end_date: datetime = None) -> Dict[str, Any]:
        """
        Get meeting analytics for a group and date range.
        
        Args:
            group_id: Group to analyze (optional)
            start_date: Start of analysis period
            end_date: End of analysis period
            
        Returns:
            Dictionary with analytics data
        """
        if not start_date:
            start_date = timezone.now() - timedelta(days=30)
        
        if not end_date:
            end_date = timezone.now()
        
        # Base queryset
        meetings = Meeting.objects.filter(
            start_time__gte=start_date,
            start_time__lte=end_date
        )
        
        if group_id:
            meetings = meetings.filter(group_id=group_id)
        
        # Basic metrics
        total_meetings = meetings.count()
        completed_meetings = meetings.filter(status=MeetingStatus.COMPLETED).count()
        cancelled_meetings = meetings.filter(status=MeetingStatus.CANCELLED).count()
        
        # Meeting types distribution
        meeting_types = meetings.values('meeting_type').annotate(count=Count('id'))
        
        # Average duration
        completed = meetings.filter(
            status=MeetingStatus.COMPLETED,
            actual_start_time__isnull=False,
            actual_end_time__isnull=False
        )
        
        total_duration_minutes = 0
        for meeting in completed:
            duration = (meeting.actual_end_time - meeting.actual_start_time).total_seconds() / 60
            total_duration_minutes += duration
        
        avg_duration_minutes = total_duration_minutes / completed.count() if completed.count() > 0 else 0
        
        # Resource utilization
        resource_bookings = MeetingResourceBooking.objects.filter(
            meeting__in=meetings
        ).values('resource__name').annotate(count=Count('id'))
        
        return {
            'period': {
                'start_date': start_date,
                'end_date': end_date
            },
            'summary': {
                'total_meetings': total_meetings,
                'completed_meetings': completed_meetings,
                'cancelled_meetings': cancelled_meetings,
                'completion_rate': (completed_meetings / total_meetings * 100) if total_meetings > 0 else 0,
                'cancellation_rate': (cancelled_meetings / total_meetings * 100) if total_meetings > 0 else 0
            },
            'meeting_types': list(meeting_types),
            'average_duration_minutes': round(avg_duration_minutes, 1),
            'resource_utilization': list(resource_bookings)
        }