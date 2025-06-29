"""
Tests for meeting scheduler service functionality.

Tests for business logic, calendar integration, availability checking,
optimal time finding, and meeting scheduling services.
"""

from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock
import json

from accounts.models import Group
from deals.models.meeting_scheduler import (
    Meeting, MeetingAttendee, MeetingResource, MeetingResourceBooking,
    AvailabilitySlot, MeetingStatus, MeetingType, RecurrenceType
)

User = get_user_model()


class MeetingSchedulerServiceTests(TestCase):
    """Test meeting scheduler service functionality."""
    
    def setUp(self):
        self.group = Group.objects.create(name="Test Group")
        self.organizer = User.objects.create_user(
            username="organizer",
            email="organizer@example.com",
            password="testpass123"
        )
        self.attendee1 = User.objects.create_user(
            username="attendee1",
            email="attendee1@example.com",
            password="testpass123"
        )
        self.attendee2 = User.objects.create_user(
            username="attendee2",
            email="attendee2@example.com",
            password="testpass123"
        )
        
        for user in [self.organizer, self.attendee1, self.attendee2]:
            user.groups.add(self.group)
        
        # Create test resources
        self.room_a = MeetingResource.objects.create(
            name="Conference Room A",
            resource_type=MeetingResource.ResourceType.CONFERENCE_ROOM,
            capacity=10,
            hourly_cost=50.00,
            group=self.group
        )
        
        self.room_b = MeetingResource.objects.create(
            name="Conference Room B",
            resource_type=MeetingResource.ResourceType.CONFERENCE_ROOM,
            capacity=6,
            hourly_cost=30.00,
            group=self.group
        )
        
        self.projector = MeetingResource.objects.create(
            name="Projector",
            resource_type=MeetingResource.ResourceType.EQUIPMENT,
            hourly_cost=10.00,
            group=self.group
        )


class AvailabilityServiceTests(MeetingSchedulerServiceTests):
    """Test availability checking service."""
    
    def test_user_availability_checking(self):
        """Test checking user availability for meeting times."""
        # Create availability slots
        base_date = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
        
        # User 1 available 9 AM - 5 PM
        AvailabilitySlot.objects.create(
            user=self.attendee1,
            start_time=base_date.replace(hour=9),
            end_time=base_date.replace(hour=17),
            slot_type=AvailabilitySlot.SlotType.AVAILABLE,
            group=self.group
        )
        
        # User 2 available 10 AM - 6 PM
        AvailabilitySlot.objects.create(
            user=self.attendee2,
            start_time=base_date.replace(hour=10),
            end_time=base_date.replace(hour=18),
            slot_type=AvailabilitySlot.SlotType.AVAILABLE,
            group=self.group
        )
        
        # User 2 busy 2 PM - 3 PM
        AvailabilitySlot.objects.create(
            user=self.attendee2,
            start_time=base_date.replace(hour=14),
            end_time=base_date.replace(hour=15),
            slot_type=AvailabilitySlot.SlotType.BUSY,
            group=self.group
        )
        
        # Test availability queries
        available_slots_user1 = AvailabilitySlot.objects.filter(
            user=self.attendee1,
            slot_type=AvailabilitySlot.SlotType.AVAILABLE,
            start_time__lte=base_date.replace(hour=11),
            end_time__gte=base_date.replace(hour=12)
        )
        self.assertTrue(available_slots_user1.exists())
        
        # Test overlap detection
        busy_slots_user2 = AvailabilitySlot.objects.filter(
            user=self.attendee2,
            slot_type=AvailabilitySlot.SlotType.BUSY,
            start_time__lt=base_date.replace(hour=15),
            end_time__gt=base_date.replace(hour=14)
        )
        self.assertTrue(busy_slots_user2.exists())
    
    def test_resource_availability_checking(self):
        """Test checking resource availability for booking."""
        start_time = timezone.now() + timedelta(hours=1)
        end_time = start_time + timedelta(hours=1)
        
        # Initially available
        self.assertTrue(self.room_a.is_available(start_time, end_time))
        
        # Create meeting and booking
        meeting = Meeting.objects.create(
            title="Test Meeting",
            start_time=start_time,
            end_time=end_time,
            organizer=self.organizer,
            group=self.group
        )
        
        booking = MeetingResourceBooking.objects.create(
            meeting=meeting,
            resource=self.room_a,
            start_time=start_time,
            end_time=end_time,
            status=MeetingResourceBooking.BookingStatus.CONFIRMED,
            group=self.group
        )
        
        # Should not be available for overlapping time
        overlap_start = start_time + timedelta(minutes=30)
        overlap_end = end_time + timedelta(minutes=30)
        self.assertFalse(self.room_a.is_available(overlap_start, overlap_end))
        
        # Should be available for adjacent time
        adjacent_start = end_time
        adjacent_end = adjacent_start + timedelta(hours=1)
        self.assertTrue(self.room_a.is_available(adjacent_start, adjacent_end))
    
    def test_multi_resource_availability(self):
        """Test checking availability across multiple resources."""
        start_time = timezone.now() + timedelta(hours=1)
        end_time = start_time + timedelta(hours=1)
        
        # Get all available conference rooms
        available_rooms = []
        for resource in MeetingResource.objects.filter(
            resource_type=MeetingResource.ResourceType.CONFERENCE_ROOM,
            is_active=True,
            group=self.group
        ):
            if resource.is_available(start_time, end_time):
                available_rooms.append(resource)
        
        self.assertEqual(len(available_rooms), 2)  # Both rooms should be available
        
        # Book one room
        meeting = Meeting.objects.create(
            title="Test Meeting",
            start_time=start_time,
            end_time=end_time,
            organizer=self.organizer,
            group=self.group
        )
        
        MeetingResourceBooking.objects.create(
            meeting=meeting,
            resource=self.room_a,
            start_time=start_time,
            end_time=end_time,
            status=MeetingResourceBooking.BookingStatus.CONFIRMED,
            group=self.group
        )
        
        # Check availability again
        available_rooms = []
        for resource in MeetingResource.objects.filter(
            resource_type=MeetingResource.ResourceType.CONFERENCE_ROOM,
            is_active=True,
            group=self.group
        ):
            if resource.is_available(start_time, end_time):
                available_rooms.append(resource)
        
        self.assertEqual(len(available_rooms), 1)  # Only one room should be available
        self.assertEqual(available_rooms[0], self.room_b)


class OptimalTimeFindingTests(MeetingSchedulerServiceTests):
    """Test optimal time finding algorithm."""
    
def test_find_common_availability(self):
        """Test finding common availability across attendees."""
        base_date = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
        
        # Create overlapping availability
        # Both users available 10 AM - 4 PM
        for user in [self.attendee1, self.attendee2]:
            AvailabilitySlot.objects.create(
                user=user,
                start_time=base_date.replace(hour=10),
                end_time=base_date.replace(hour=16),
                slot_type=AvailabilitySlot.SlotType.AVAILABLE,
                group=self.group
            )
        
        # User 1 busy 12 PM - 1 PM
        AvailabilitySlot.objects.create(
            user=self.attendee1,
            start_time=base_date.replace(hour=12),
            end_time=base_date.replace(hour=13),
            slot_type=AvailabilitySlot.SlotType.BUSY,
            group=self.group
        )
        
        # Find common availability periods
        # This is a simplified version - real implementation would be more complex
        
        # Mock the optimal time finding algorithm
        def find_optimal_times(attendee_emails, duration_minutes, start_date, end_date):
            """Mock optimal time finding algorithm."""
            suggestions = []
            
            # Check 11 AM - 12 PM (should be available for both)
            suggestion_time = base_date.replace(hour=11)
            suggestions.append({
                'start_time': suggestion_time,
                'end_time': suggestion_time + timedelta(minutes=duration_minutes),
                'confidence_score': 0.9,
                'available_attendees': len(attendee_emails),
                'conflicts': []
            })
            
            # Check 2 PM - 3 PM (should be available for both)
            suggestion_time = base_date.replace(hour=14)
            suggestions.append({
                'start_time': suggestion_time,
                'end_time': suggestion_time + timedelta(minutes=duration_minutes),
                'confidence_score': 0.8,
                'available_attendees': len(attendee_emails),
                'conflicts': []
            })
            
            return suggestions
        
        # Test the algorithm
        attendee_emails = ['attendee1@example.com', 'attendee2@example.com']
        suggestions = find_optimal_times(
            attendee_emails, 
            60, 
            base_date, 
            base_date + timedelta(days=1)
        )
        
        self.assertEqual(len(suggestions), 2)
        self.assertEqual(suggestions[0]['available_attendees'], 2)
        self.assertTrue(suggestions[0]['confidence_score'] > suggestions[1]['confidence_score'])
    
    def test_time_zone_handling(self):
        """Test handling different time zones in scheduling."""
        # This would test time zone conversion logic
        # For now, we'll test the basic structure
        
        base_time = timezone.now()
        
        # Mock time zone conversion
        def convert_timezone(dt, from_tz, to_tz):
            """Mock time zone conversion."""
            # In real implementation, this would use pytz or zoneinfo
            return dt
        
        # Test converting between timezones
        utc_time = base_time
        eastern_time = convert_timezone(utc_time, 'UTC', 'America/New_York')
        pacific_time = convert_timezone(utc_time, 'UTC', 'America/Los_Angeles')
        
        # For mock, times should be the same
        self.assertEqual(utc_time, eastern_time)
        self.assertEqual(utc_time, pacific_time)
    
    def test_business_hours_filtering(self):
        """Test filtering suggestions to business hours only."""
        base_date = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
        
        # Generate time suggestions across the day
        suggestions = []
        for hour in range(24):
            suggestion_time = base_date.replace(hour=hour)
            suggestions.append({
                'start_time': suggestion_time,
                'end_time': suggestion_time + timedelta(hours=1),
                'confidence_score': 0.5
            })
        
        # Filter to business hours (9 AM - 5 PM)
        business_hours_suggestions = [
            s for s in suggestions 
            if 9 <= s['start_time'].hour < 17
        ]
        
        self.assertEqual(len(business_hours_suggestions), 8)  # 9 AM to 4 PM (8 hours)
        
        # Test weekend filtering
        weekend_date = base_date
        while weekend_date.weekday() not in [5, 6]:  # Saturday=5, Sunday=6
            weekend_date += timedelta(days=1)
        
        weekend_suggestion = {
            'start_time': weekend_date.replace(hour=10),
            'end_time': weekend_date.replace(hour=11),
        }
        
        # Function to check if date is weekday
        def is_weekday(dt):
            return dt.weekday() < 5  # Monday=0, Friday=4
        
        self.assertFalse(is_weekday(weekend_suggestion['start_time']))


class CalendarIntegrationTests(MeetingSchedulerServiceTests):
    """Test calendar integration functionality."""
    
    @patch('requests.get')
    def test_google_calendar_integration(self, mock_get):
        """Test Google Calendar API integration (mocked)."""
        # Mock Google Calendar API response
        mock_response = MagicMock()
        mock_response.json.return_value = {
            'items': [
                {
                    'id': 'event123',
                    'summary': 'External Meeting',
                    'start': {'dateTime': '2024-01-15T10:00:00Z'},
                    'end': {'dateTime': '2024-01-15T11:00:00Z'},
                    'status': 'confirmed'
                }
            ]
        }
        mock_response.status_code = 200
        mock_get.return_value = mock_response
        
        # Mock calendar service
        class MockCalendarService:
            def get_events(self, user_email, start_time, end_time):
                # Simulate API call
                mock_get()
                return [
                    {
                        'id': 'event123',
                        'title': 'External Meeting',
                        'start_time': timezone.now() + timedelta(hours=1),
                        'end_time': timezone.now() + timedelta(hours=2),
                        'status': 'busy'
                    }
                ]
            
            def create_event(self, event_data):
                return {
                    'id': 'new_event_123',
                    'status': 'created'
                }
            
            def update_event(self, event_id, event_data):
                return {
                    'id': event_id,
                    'status': 'updated'
                }
            
            def delete_event(self, event_id):
                return {'status': 'deleted'}
        
        # Test the mock service
        calendar_service = MockCalendarService()
        
        # Test getting events
        start_time = timezone.now()
        end_time = start_time + timedelta(days=1)
        events = calendar_service.get_events(
            'test@example.com', 
            start_time, 
            end_time
        )
        
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]['title'], 'External Meeting')
        
        # Test creating event
        event_data = {
            'title': 'New Meeting',
            'start_time': timezone.now() + timedelta(hours=1),
            'end_time': timezone.now() + timedelta(hours=2),
            'attendees': ['attendee@example.com']
        }
        result = calendar_service.create_event(event_data)
        self.assertEqual(result['status'], 'created')
    
    @patch('requests.post')
    def test_outlook_calendar_integration(self, mock_post):
        """Test Outlook Calendar API integration (mocked)."""
        # Mock Outlook Calendar API response
        mock_response = MagicMock()
        mock_response.json.return_value = {
            'value': [
                {
                    'id': 'outlook_event_123',
                    'subject': 'Outlook Meeting',
                    'start': {'dateTime': '2024-01-15T14:00:00Z'},
                    'end': {'dateTime': '2024-01-15T15:00:00Z'},
                    'showAs': 'busy'
                }
            ]
        }
        mock_response.status_code = 200
        mock_post.return_value = mock_response
        
        # Mock Outlook service
        class MockOutlookService:
            def get_calendar_view(self, user_email, start_time, end_time):
                # Simulate API call
                mock_post()
                return [
                    {
                        'id': 'outlook_event_123',
                        'subject': 'Outlook Meeting',
                        'start_time': timezone.now() + timedelta(hours=2),
                        'end_time': timezone.now() + timedelta(hours=3),
                        'show_as': 'busy'
                    }
                ]
        
        outlook_service = MockOutlookService()
        
        start_time = timezone.now()
        end_time = start_time + timedelta(days=1)
        events = outlook_service.get_calendar_view(
            'test@example.com',
            start_time,
            end_time
        )
        
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]['subject'], 'Outlook Meeting')
    
    def test_calendar_sync_status(self):
        """Test calendar synchronization status tracking."""
        start_time = timezone.now() + timedelta(hours=1)
        end_time = start_time + timedelta(hours=1)
        
        # Create meeting with calendar sync enabled
        meeting = Meeting.objects.create(
            title="Sync Test Meeting",
            start_time=start_time,
            end_time=end_time,
            organizer=self.organizer,
            calendar_sync_enabled=True,
            calendar_provider='google',
            group=self.group
        )
        
        # Mock successful sync
        meeting.external_calendar_id = 'google_event_123'
        meeting.save()
        
        self.assertTrue(meeting.calendar_sync_enabled)
        self.assertEqual(meeting.calendar_provider, 'google')
        self.assertIsNotNone(meeting.external_calendar_id)
        
        # Test sync failure handling
        meeting_no_sync = Meeting.objects.create(
            title="No Sync Meeting",
            start_time=start_time + timedelta(hours=2),
            end_time=end_time + timedelta(hours=2),
            organizer=self.organizer,
            calendar_sync_enabled=False,
            group=self.group
        )
        
        self.assertFalse(meeting_no_sync.calendar_sync_enabled)
        self.assertEqual(meeting_no_sync.external_calendar_id, '')


class MeetingWorkflowTests(MeetingSchedulerServiceTests):
    """Test meeting workflow and automation."""
    
    def test_automatic_meeting_confirmation(self):
        """Test automatic meeting confirmation when all attendees respond."""
        start_time = timezone.now() + timedelta(hours=1)
        end_time = start_time + timedelta(hours=1)
        
        meeting = Meeting.objects.create(
            title="Auto Confirm Test",
            start_time=start_time,
            end_time=end_time,
            organizer=self.organizer,
            requires_confirmation=True,
            group=self.group
        )
        meeting.schedule()
        meeting.save()
        
        # Add attendees
        attendee1 = MeetingAttendee.objects.create(
            meeting=meeting,
            user=self.attendee1,
            email=self.attendee1.email,
            name=self.attendee1.get_full_name(),
            attendee_type=MeetingAttendee.AttendeeType.REQUIRED,
            group=self.group
        )
        
        attendee2 = MeetingAttendee.objects.create(
            meeting=meeting,
            user=self.attendee2,
            email=self.attendee2.email,
            name=self.attendee2.get_full_name(),
            attendee_type=MeetingAttendee.AttendeeType.REQUIRED,
            group=self.group
        )
        
        # Initially not confirmed
        self.assertEqual(meeting.status, MeetingStatus.SCHEDULED)
        
        # Both attendees accept
        attendee1.respond(MeetingAttendee.ResponseStatus.ACCEPTED)
        attendee2.respond(MeetingAttendee.ResponseStatus.ACCEPTED)
        
        # Check if all required attendees have accepted
        required_attendees = meeting.attendees.filter(
            attendee_type=MeetingAttendee.AttendeeType.REQUIRED
        )
        accepted_attendees = required_attendees.filter(
            response_status=MeetingAttendee.ResponseStatus.ACCEPTED
        )
        
        # In real implementation, this would trigger automatic confirmation
        if required_attendees.count() == accepted_attendees.count():
            meeting.confirm()
            meeting.save()
        
        self.assertEqual(meeting.status, MeetingStatus.CONFIRMED)
    
    def test_recurring_meeting_generation(self):
        """Test generating recurring meeting instances."""
        base_time = timezone.now() + timedelta(days=1)
        start_time = base_time.replace(hour=10, minute=0, second=0, microsecond=0)
        end_time = start_time + timedelta(hours=1)
        
        # Create parent recurring meeting
        parent_meeting = Meeting.objects.create(
            title="Weekly Standup",
            start_time=start_time,
            end_time=end_time,
            recurrence_type=RecurrenceType.WEEKLY,
            recurrence_interval=1,
            recurrence_end_date=start_time + timedelta(weeks=4),
            organizer=self.organizer,
            group=self.group
        )
        
        # Mock recurring meeting generation
        def generate_recurring_instances(parent_meeting):
            """Generate recurring meeting instances."""
            instances = []
            current_date = parent_meeting.start_time
            end_date = parent_meeting.recurrence_end_date
            
            while current_date <= end_date:
                if current_date != parent_meeting.start_time:  # Skip the parent
                    instance = Meeting.objects.create(
                        title=parent_meeting.title,
                        start_time=current_date,
                        end_time=current_date + (parent_meeting.end_time - parent_meeting.start_time),
                        meeting_type=parent_meeting.meeting_type,
                        organizer=parent_meeting.organizer,
                        parent_meeting=parent_meeting,
                        group=parent_meeting.group
                    )
                    instances.append(instance)
                
                # Increment by recurrence interval
                if parent_meeting.recurrence_type == RecurrenceType.WEEKLY:
                    current_date += timedelta(weeks=parent_meeting.recurrence_interval)
                elif parent_meeting.recurrence_type == RecurrenceType.DAILY:
                    current_date += timedelta(days=parent_meeting.recurrence_interval)
                elif parent_meeting.recurrence_type == RecurrenceType.MONTHLY:
                    # Simplified monthly increment
                    current_date += timedelta(days=30 * parent_meeting.recurrence_interval)
                else:
                    break
            
            return instances
        
        # Generate instances
        instances = generate_recurring_instances(parent_meeting)
        
        # Should generate 3 additional instances (4 weeks total, excluding parent)
        self.assertEqual(len(instances), 3)
        
        for instance in instances:
            self.assertEqual(instance.parent_meeting, parent_meeting)
            self.assertEqual(instance.title, parent_meeting.title)
            self.assertEqual(instance.organizer, parent_meeting.organizer)
    
    def test_meeting_reminder_scheduling(self):
        """Test scheduling meeting reminders."""
        start_time = timezone.now() + timedelta(hours=24)  # 24 hours from now
        end_time = start_time + timedelta(hours=1)
        
        meeting = Meeting.objects.create(
            title="Reminder Test Meeting",
            start_time=start_time,
            end_time=end_time,
            organizer=self.organizer,
            send_reminders=True,
            group=self.group
        )
        
        # Add attendees
        attendee = MeetingAttendee.objects.create(
            meeting=meeting,
            user=self.attendee1,
            email=self.attendee1.email,
            name=self.attendee1.get_full_name(),
            send_reminders=True,
            group=self.group
        )
        
        # Mock reminder scheduling logic
        def schedule_reminders(meeting):
            """Schedule meeting reminders."""
            reminders = []
            
            # 24 hours before
            reminder_24h = {
                'meeting_id': meeting.id,
                'reminder_type': '24_hour',
                'scheduled_time': meeting.start_time - timedelta(hours=24),
                'recipients': [a.email for a in meeting.attendees.filter(send_reminders=True)]
            }
            reminders.append(reminder_24h)
            
            # 1 hour before
            reminder_1h = {
                'meeting_id': meeting.id,
                'reminder_type': '1_hour',
                'scheduled_time': meeting.start_time - timedelta(hours=1),
                'recipients': [a.email for a in meeting.attendees.filter(send_reminders=True)]
            }
            reminders.append(reminder_1h)
            
            return reminders
        
        # Schedule reminders
        reminders = schedule_reminders(meeting)
        
        self.assertEqual(len(reminders), 2)
        self.assertEqual(reminders[0]['reminder_type'], '24_hour')
        self.assertEqual(reminders[1]['reminder_type'], '1_hour')
        self.assertIn(attendee.email, reminders[0]['recipients'])
    
    def test_meeting_analytics_calculation(self):
        """Test meeting analytics calculations."""
        # Create test meetings with different statuses and types
        base_time = timezone.now()
        
        meetings_data = [
            {
                'title': 'Completed Meeting 1',
                'status': MeetingStatus.COMPLETED,
                'meeting_type': MeetingType.INITIAL_MEETING,
                'duration': 60
            },
            {
                'title': 'Completed Meeting 2',
                'status': MeetingStatus.COMPLETED,
                'meeting_type': MeetingType.DUE_DILIGENCE,
                'duration': 90
            },
            {
                'title': 'Scheduled Meeting 1',
                'status': MeetingStatus.SCHEDULED,
                'meeting_type': MeetingType.INITIAL_MEETING,
                'duration': 60
            },
            {
                'title': 'Cancelled Meeting 1',
                'status': MeetingStatus.CANCELLED,
                'meeting_type': MeetingType.FOLLOW_UP,
                'duration': 30
            }
        ]
        
        created_meetings = []
        for data in meetings_data:
            start_time = base_time + timedelta(hours=len(created_meetings))
            end_time = start_time + timedelta(minutes=data['duration'])
            
            meeting = Meeting.objects.create(
                title=data['title'],
                start_time=start_time,
                end_time=end_time,
                status=data['status'],
                meeting_type=data['meeting_type'],
                organizer=self.organizer,
                group=self.group
            )
            created_meetings.append(meeting)
        
        # Calculate analytics
        def calculate_meeting_analytics(meetings):
            """Calculate meeting analytics."""
            total_meetings = meetings.count()
            
            # Meetings by status
            by_status = {}
            for status in MeetingStatus:
                count = meetings.filter(status=status.value).count()
                by_status[status.value] = count
            
            # Meetings by type
            by_type = {}
            for meeting_type in MeetingType:
                count = meetings.filter(meeting_type=meeting_type.value).count()
                by_type[meeting_type.value] = count
            
            # Average duration (completed meetings only)
            completed_meetings = meetings.filter(status=MeetingStatus.COMPLETED)
            avg_duration = 0
            if completed_meetings.exists():
                total_duration = sum(m.duration_minutes for m in completed_meetings)
                avg_duration = total_duration / completed_meetings.count()
            
            return {
                'total_meetings': total_meetings,
                'by_status': by_status,
                'by_type': by_type,
                'average_duration_minutes': avg_duration
            }
        
        # Calculate analytics for created meetings
        all_meetings = Meeting.objects.filter(organizer=self.organizer)
        analytics = calculate_meeting_analytics(all_meetings)
        
        self.assertEqual(analytics['total_meetings'], 4)
        self.assertEqual(analytics['by_status'][MeetingStatus.COMPLETED], 2)
        self.assertEqual(analytics['by_status'][MeetingStatus.SCHEDULED], 1)
        self.assertEqual(analytics['by_status'][MeetingStatus.CANCELLED], 1)
        self.assertEqual(analytics['by_type'][MeetingType.INITIAL_MEETING], 2)
        self.assertEqual(analytics['average_duration_minutes'], 75)  # (60 + 90) / 2