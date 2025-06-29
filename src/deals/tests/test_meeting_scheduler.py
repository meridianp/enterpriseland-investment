"""
Tests for meeting scheduler models and API endpoints.

Comprehensive tests covering Meeting, MeetingAttendee, MeetingResource,
MeetingResourceBooking, and AvailabilitySlot models with FSM transitions,
validation, constraints, and business logic.
"""

from django.test import TestCase
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.utils import timezone
from django.urls import reverse
from rest_framework.test import APITestCase
from rest_framework import status
from datetime import datetime, timedelta
from unittest.mock import patch

from accounts.models import Group
from deals.models import Deal, DealType, DealSource
from deals.models.meeting_scheduler import (
    Meeting, MeetingAttendee, MeetingResource, MeetingResourceBooking,
    AvailabilitySlot, MeetingStatus, MeetingType, RecurrenceType
)

User = get_user_model()


class MeetingModelTests(TestCase):
    """Test Meeting model functionality."""
    
    def setUp(self):
        self.group = Group.objects.create(name="Test Group")
        self.organizer = User.objects.create_user(
            username="organizer",
            email="organizer@example.com",
            password="testpass123"
        )
        self.organizer.groups.add(self.group)
        
        self.deal_type = DealType.objects.create(
            name="Standard Deal",
            code="STANDARD",
            group=self.group
        )
        self.deal_source = DealSource.objects.create(
            name="Direct",
            code="DIRECT",
            group=self.group
        )
        
        # Create a partner for the deal
        from assessments.models import DevelopmentPartner
        self.partner = DevelopmentPartner.objects.create(
            name="Test Partner",
            group=self.group
        )
        
        self.deal = Deal.objects.create(
            name="Test Deal",
            deal_type=self.deal_type,
            partner=self.partner,
            source=self.deal_source,
            organizer=self.organizer,
            group=self.group
        )
    
    def test_create_meeting(self):
        """Test creating a basic meeting."""
        start_time = timezone.now() + timedelta(hours=1)
        end_time = start_time + timedelta(hours=1)
        
        meeting = Meeting.objects.create(
            title="Test Meeting",
            description="A test meeting",
            meeting_type=MeetingType.INITIAL_MEETING,
            deal=self.deal,
            start_time=start_time,
            end_time=end_time,
            organizer=self.organizer,
            group=self.group
        )
        
        self.assertEqual(meeting.title, "Test Meeting")
        self.assertEqual(meeting.status, MeetingStatus.DRAFT)
        self.assertEqual(meeting.organizer, self.organizer)
        self.assertEqual(meeting.duration_minutes, 60)
        self.assertFalse(meeting.is_virtual)
        self.assertFalse(meeting.is_recurring)
        self.assertFalse(meeting.is_past)
    
    def test_meeting_validation(self):
        """Test meeting validation rules."""
        start_time = timezone.now() + timedelta(hours=1)
        
        # Test end time before start time
        with self.assertRaises(ValidationError):
            meeting = Meeting(
                title="Invalid Meeting",
                start_time=start_time,
                end_time=start_time - timedelta(minutes=30),
                organizer=self.organizer,
                group=self.group
            )
            meeting.full_clean()
        
        # Test excessive duration (over 8 hours)
        with self.assertRaises(ValidationError):
            meeting = Meeting(
                title="Long Meeting",
                start_time=start_time,
                end_time=start_time + timedelta(hours=10),
                organizer=self.organizer,
                group=self.group
            )
            meeting.full_clean()
    
    def test_meeting_properties(self):
        """Test meeting computed properties."""
        start_time = timezone.now() + timedelta(hours=1)
        end_time = start_time + timedelta(minutes=90)
        
        meeting = Meeting.objects.create(
            title="Test Meeting",
            start_time=start_time,
            end_time=end_time,
            virtual_meeting_url="https://zoom.us/j/123456789",
            recurrence_type=RecurrenceType.WEEKLY,
            organizer=self.organizer,
            group=self.group
        )
        
        self.assertEqual(meeting.duration_minutes, 90)
        self.assertTrue(meeting.is_virtual)
        self.assertTrue(meeting.is_recurring)
        self.assertFalse(meeting.is_past)
        self.assertFalse(meeting.is_today)
    
    def test_meeting_fsm_transitions(self):
        """Test meeting state machine transitions."""
        start_time = timezone.now() + timedelta(hours=1)
        end_time = start_time + timedelta(hours=1)
        
        meeting = Meeting.objects.create(
            title="FSM Test Meeting",
            start_time=start_time,
            end_time=end_time,
            organizer=self.organizer,
            group=self.group
        )
        
        # Test scheduling
        self.assertEqual(meeting.status, MeetingStatus.DRAFT)
        meeting.schedule()
        self.assertEqual(meeting.status, MeetingStatus.SCHEDULED)
        
        # Test confirming
        meeting.confirm()
        self.assertEqual(meeting.status, MeetingStatus.CONFIRMED)
        
        # Test starting
        meeting.start_meeting()
        self.assertEqual(meeting.status, MeetingStatus.IN_PROGRESS)
        self.assertIsNotNone(meeting.actual_start_time)
        
        # Test completing
        meeting.complete_meeting()
        self.assertEqual(meeting.status, MeetingStatus.COMPLETED)
        self.assertIsNotNone(meeting.actual_end_time)
    
    def test_meeting_cancellation(self):
        """Test meeting cancellation."""
        start_time = timezone.now() + timedelta(hours=1)
        end_time = start_time + timedelta(hours=1)
        
        meeting = Meeting.objects.create(
            title="Cancel Test Meeting",
            start_time=start_time,
            end_time=end_time,
            organizer=self.organizer,
            group=self.group
        )
        
        meeting.schedule()
        meeting.cancel()
        self.assertEqual(meeting.status, MeetingStatus.CANCELLED)
    
    def test_recurring_meeting_validation(self):
        """Test recurring meeting validation."""
        start_time = timezone.now() + timedelta(hours=1)
        end_time = start_time + timedelta(hours=1)
        
        # Test valid recurrence
        meeting = Meeting(
            title="Recurring Meeting",
            start_time=start_time,
            end_time=end_time,
            recurrence_type=RecurrenceType.WEEKLY,
            recurrence_end_date=start_time + timedelta(weeks=4),
            organizer=self.organizer,
            group=self.group
        )
        meeting.full_clean()  # Should not raise
        
        # Test invalid recurrence end date
        with self.assertRaises(ValidationError):
            meeting = Meeting(
                title="Invalid Recurring Meeting",
                start_time=start_time,
                end_time=end_time,
                recurrence_type=RecurrenceType.WEEKLY,
                recurrence_end_date=start_time - timedelta(days=1),
                organizer=self.organizer,
                group=self.group
            )
            meeting.full_clean()


class MeetingAttendeeModelTests(TestCase):
    """Test MeetingAttendee model functionality."""
    
    def setUp(self):
        self.group = Group.objects.create(name="Test Group")
        self.organizer = User.objects.create_user(
            username="organizer",
            email="organizer@example.com",
            password="testpass123"
        )
        self.attendee_user = User.objects.create_user(
            username="attendee",
            email="attendee@example.com",
            password="testpass123"
        )
        self.organizer.groups.add(self.group)
        self.attendee_user.groups.add(self.group)
        
        start_time = timezone.now() + timedelta(hours=1)
        end_time = start_time + timedelta(hours=1)
        
        self.meeting = Meeting.objects.create(
            title="Test Meeting",
            start_time=start_time,
            end_time=end_time,
            organizer=self.organizer,
            group=self.group
        )
    
    def test_create_internal_attendee(self):
        """Test creating an attendee with internal user."""
        attendee = MeetingAttendee.objects.create(
            meeting=self.meeting,
            user=self.attendee_user,
            email=self.attendee_user.email,
            name=self.attendee_user.get_full_name(),
            attendee_type=MeetingAttendee.AttendeeType.REQUIRED,
            group=self.group
        )
        
        self.assertEqual(attendee.meeting, self.meeting)
        self.assertEqual(attendee.user, self.attendee_user)
        self.assertEqual(attendee.response_status, MeetingAttendee.ResponseStatus.PENDING)
        self.assertFalse(attendee.attended)
    
    def test_create_external_attendee(self):
        """Test creating an external attendee."""
        attendee = MeetingAttendee.objects.create(
            meeting=self.meeting,
            email="external@example.com",
            name="External User",
            organization="External Corp",
            attendee_type=MeetingAttendee.AttendeeType.OPTIONAL,
            group=self.group
        )
        
        self.assertEqual(attendee.meeting, self.meeting)
        self.assertIsNone(attendee.user)
        self.assertEqual(attendee.email, "external@example.com")
        self.assertEqual(attendee.organization, "External Corp")
    
    def test_unique_attendee_constraint(self):
        """Test unique attendee per meeting constraint."""
        MeetingAttendee.objects.create(
            meeting=self.meeting,
            email="test@example.com",
            name="Test User",
            group=self.group
        )
        
        # Try to create another attendee with same email
        with self.assertRaises(IntegrityError):
            MeetingAttendee.objects.create(
                meeting=self.meeting,
                email="test@example.com",
                name="Test User 2",
                group=self.group
            )
    
    def test_attendee_response(self):
        """Test attendee response functionality."""
        attendee = MeetingAttendee.objects.create(
            meeting=self.meeting,
            user=self.attendee_user,
            email=self.attendee_user.email,
            name=self.attendee_user.get_full_name(),
            group=self.group
        )
        
        # Test response
        attendee.respond(MeetingAttendee.ResponseStatus.ACCEPTED, "Looking forward to it!")
        
        self.assertEqual(attendee.response_status, MeetingAttendee.ResponseStatus.ACCEPTED)
        self.assertEqual(attendee.response_notes, "Looking forward to it!")
        self.assertIsNotNone(attendee.responded_at)
    
    def test_attendance_tracking(self):
        """Test attendance duration calculation."""
        attendee = MeetingAttendee.objects.create(
            meeting=self.meeting,
            user=self.attendee_user,
            email=self.attendee_user.email,
            name=self.attendee_user.get_full_name(),
            group=self.group
        )
        
        # Simulate joining and leaving
        join_time = timezone.now()
        leave_time = join_time + timedelta(minutes=45)
        
        attendee.joined_at = join_time
        attendee.left_at = leave_time
        attendee.attended = True
        attendee.save()
        
        self.assertEqual(attendee.attendance_duration_minutes, 45)


class MeetingResourceModelTests(TestCase):
    """Test MeetingResource model functionality."""
    
    def setUp(self):
        self.group = Group.objects.create(name="Test Group")
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123"
        )
        self.user.groups.add(self.group)
    
    def test_create_resource(self):
        """Test creating a meeting resource."""
        resource = MeetingResource.objects.create(
            name="Conference Room A",
            resource_type=MeetingResource.ResourceType.CONFERENCE_ROOM,
            description="Large conference room with projector",
            capacity=12,
            location="2nd Floor",
            hourly_cost=50.00,
            group=self.group
        )
        
        self.assertEqual(resource.name, "Conference Room A")
        self.assertEqual(resource.capacity, 12)
        self.assertTrue(resource.is_active)
        self.assertFalse(resource.requires_approval)
    
    def test_unique_resource_name_constraint(self):
        """Test unique resource name per group constraint."""
        MeetingResource.objects.create(
            name="Room A",
            resource_type=MeetingResource.ResourceType.CONFERENCE_ROOM,
            group=self.group
        )
        
        # Try to create another resource with same name in same group
        with self.assertRaises(IntegrityError):
            MeetingResource.objects.create(
                name="Room A",
                resource_type=MeetingResource.ResourceType.EQUIPMENT,
                group=self.group
            )
        
        # Should be able to create same name in different group
        group2 = Group.objects.create(name="Group 2")
        resource2 = MeetingResource.objects.create(
            name="Room A",
            resource_type=MeetingResource.ResourceType.CONFERENCE_ROOM,
            group=group2
        )
        self.assertEqual(resource2.name, "Room A")
    
    def test_resource_availability(self):
        """Test resource availability checking."""
        resource = MeetingResource.objects.create(
            name="Test Room",
            resource_type=MeetingResource.ResourceType.CONFERENCE_ROOM,
            group=self.group
        )
        
        start_time = timezone.now() + timedelta(hours=1)
        end_time = start_time + timedelta(hours=1)
        
        # Resource should be available initially
        self.assertTrue(resource.is_available(start_time, end_time))
        
        # Create a meeting and booking
        organizer = User.objects.create_user(
            username="organizer",
            email="organizer@example.com",
            password="testpass123"
        )
        organizer.groups.add(self.group)
        
        meeting = Meeting.objects.create(
            title="Test Meeting",
            start_time=start_time,
            end_time=end_time,
            organizer=organizer,
            group=self.group
        )
        
        booking = MeetingResourceBooking.objects.create(
            meeting=meeting,
            resource=resource,
            start_time=start_time,
            end_time=end_time,
            status=MeetingResourceBooking.BookingStatus.CONFIRMED,
            group=self.group
        )
        
        # Resource should not be available for overlapping time
        overlap_start = start_time + timedelta(minutes=30)
        overlap_end = end_time + timedelta(minutes=30)
        self.assertFalse(resource.is_available(overlap_start, overlap_end))
        
        # Resource should be available for non-overlapping time
        later_start = end_time + timedelta(hours=1)
        later_end = later_start + timedelta(hours=1)
        self.assertTrue(resource.is_available(later_start, later_end))


class MeetingResourceBookingModelTests(TestCase):
    """Test MeetingResourceBooking model functionality."""
    
    def setUp(self):
        self.group = Group.objects.create(name="Test Group")
        self.organizer = User.objects.create_user(
            username="organizer",
            email="organizer@example.com",
            password="testpass123"
        )
        self.organizer.groups.add(self.group)
        
        self.resource = MeetingResource.objects.create(
            name="Test Room",
            resource_type=MeetingResource.ResourceType.CONFERENCE_ROOM,
            hourly_cost=50.00,
            setup_cost=25.00,
            group=self.group
        )
        
        start_time = timezone.now() + timedelta(hours=1)
        end_time = start_time + timedelta(hours=1)
        
        self.meeting = Meeting.objects.create(
            title="Test Meeting",
            start_time=start_time,
            end_time=end_time,
            organizer=self.organizer,
            group=self.group
        )
    
    def test_create_booking(self):
        """Test creating a resource booking."""
        start_time = self.meeting.start_time
        end_time = self.meeting.end_time
        
        booking = MeetingResourceBooking.objects.create(
            meeting=self.meeting,
            resource=self.resource,
            start_time=start_time,
            end_time=end_time,
            setup_minutes=15,
            breakdown_minutes=10,
            group=self.group
        )
        
        self.assertEqual(booking.meeting, self.meeting)
        self.assertEqual(booking.resource, self.resource)
        self.assertEqual(booking.status, MeetingResourceBooking.BookingStatus.PENDING)
        self.assertEqual(booking.total_duration_minutes, 85)  # 60 + 15 + 10
    
    def test_cost_calculation(self):
        """Test booking cost calculation."""
        start_time = self.meeting.start_time
        end_time = self.meeting.end_time
        
        booking = MeetingResourceBooking.objects.create(
            meeting=self.meeting,
            resource=self.resource,
            start_time=start_time,
            end_time=end_time,
            setup_minutes=30,
            breakdown_minutes=30,
            group=self.group
        )
        
        # Total duration: 60 + 30 + 30 = 120 minutes = 2 hours
        # Cost: (2 hours * $50) + $25 setup = $125
        expected_cost = 125.0
        self.assertEqual(booking.calculate_cost(), expected_cost)
    
    def test_booking_validation(self):
        """Test booking validation."""
        start_time = self.meeting.start_time
        
        # Test end time before start time
        with self.assertRaises(ValidationError):
            booking = MeetingResourceBooking(
                meeting=self.meeting,
                resource=self.resource,
                start_time=start_time,
                end_time=start_time - timedelta(minutes=30),
                group=self.group
            )
            booking.full_clean()


class AvailabilitySlotModelTests(TestCase):
    """Test AvailabilitySlot model functionality."""
    
    def setUp(self):
        self.group = Group.objects.create(name="Test Group")
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123"
        )
        self.user.groups.add(self.group)
    
    def test_create_availability_slot(self):
        """Test creating an availability slot."""
        start_time = timezone.now().replace(hour=9, minute=0, second=0, microsecond=0)
        end_time = start_time.replace(hour=17)  # 9 AM to 5 PM
        
        slot = AvailabilitySlot.objects.create(
            user=self.user,
            start_time=start_time,
            end_time=end_time,
            slot_type=AvailabilitySlot.SlotType.AVAILABLE,
            title="Working Hours",
            max_meetings_per_slot=3,
            group=self.group
        )
        
        self.assertEqual(slot.user, self.user)
        self.assertEqual(slot.duration_minutes, 480)  # 8 hours
        self.assertEqual(slot.title, "Working Hours")
        self.assertFalse(slot.is_recurring)
    
    def test_availability_validation(self):
        """Test availability slot validation."""
        start_time = timezone.now() + timedelta(hours=1)
        
        # Test end time before start time
        with self.assertRaises(ValidationError):
            slot = AvailabilitySlot(
                user=self.user,
                start_time=start_time,
                end_time=start_time - timedelta(minutes=30),
                group=self.group
            )
            slot.full_clean()
    
    def test_availability_for_meeting(self):
        """Test checking availability for meeting scheduling."""
        start_time = timezone.now().replace(hour=9, minute=0, second=0, microsecond=0)
        end_time = start_time.replace(hour=17)
        
        slot = AvailabilitySlot.objects.create(
            user=self.user,
            start_time=start_time,
            end_time=end_time,
            slot_type=AvailabilitySlot.SlotType.AVAILABLE,
            max_meetings_per_slot=2,
            group=self.group
        )
        
        # Should be available for 60-minute meeting
        self.assertTrue(slot.is_available_for_meeting(60))
        
        # Should not be available for 9-hour meeting (exceeds slot duration)
        self.assertFalse(slot.is_available_for_meeting(540))
        
        # Test with busy slot
        busy_slot = AvailabilitySlot.objects.create(
            user=self.user,
            start_time=start_time + timedelta(hours=1),
            end_time=end_time - timedelta(hours=1),
            slot_type=AvailabilitySlot.SlotType.BUSY,
            group=self.group
        )
        
        self.assertFalse(busy_slot.is_available_for_meeting(60))


class MeetingAPITests(APITestCase):
    """Test Meeting API endpoints."""
    
    def setUp(self):
        self.group = Group.objects.create(name="Test Group")
        self.organizer = User.objects.create_user(
            username="organizer",
            email="organizer@example.com",
            password="testpass123"
        )
        self.attendee = User.objects.create_user(
            username="attendee",
            email="attendee@example.com",
            password="testpass123"
        )
        self.organizer.groups.add(self.group)
        self.attendee.groups.add(self.group)
        
        self.client.force_authenticate(user=self.organizer)
    
    def test_create_meeting(self):
        """Test creating a meeting via API."""
        url = reverse('deals:meeting-list')
        data = {
            'title': 'API Test Meeting',
            'description': 'A meeting created via API',
            'meeting_type': MeetingType.INITIAL_MEETING,
            'start_time': (timezone.now() + timedelta(hours=1)).isoformat(),
            'end_time': (timezone.now() + timedelta(hours=2)).isoformat(),
            'location': 'Conference Room A',
            'attendees_data': [
                {
                    'user': self.attendee.id,
                    'attendee_type': MeetingAttendee.AttendeeType.REQUIRED
                },
                {
                    'email': 'external@example.com',
                    'name': 'External User',
                    'attendee_type': MeetingAttendee.AttendeeType.OPTIONAL
                }
            ]
        }
        
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Check meeting was created
        meeting = Meeting.objects.get(id=response.data['id'])
        self.assertEqual(meeting.title, 'API Test Meeting')
        self.assertEqual(meeting.organizer, self.organizer)
        self.assertEqual(meeting.attendees.count(), 2)
    
    def test_list_meetings(self):
        """Test listing meetings."""
        # Create test meetings
        start_time = timezone.now() + timedelta(hours=1)
        end_time = start_time + timedelta(hours=1)
        
        meeting1 = Meeting.objects.create(
            title="Meeting 1",
            start_time=start_time,
            end_time=end_time,
            organizer=self.organizer,
            group=self.group
        )
        
        meeting2 = Meeting.objects.create(
            title="Meeting 2",
            start_time=start_time + timedelta(hours=2),
            end_time=end_time + timedelta(hours=2),
            organizer=self.organizer,
            group=self.group
        )
        
        url = reverse('deals:meeting-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 2)
    
    def test_start_meeting(self):
        """Test starting a meeting."""
        start_time = timezone.now() + timedelta(hours=1)
        end_time = start_time + timedelta(hours=1)
        
        meeting = Meeting.objects.create(
            title="Test Meeting",
            start_time=start_time,
            end_time=end_time,
            organizer=self.organizer,
            group=self.group
        )
        meeting.schedule()
        meeting.save()
        
        url = reverse('deals:meeting-start-meeting', kwargs={'pk': meeting.id})
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        meeting.refresh_from_db()
        self.assertEqual(meeting.status, MeetingStatus.IN_PROGRESS)
    
    def test_reschedule_meeting(self):
        """Test rescheduling a meeting."""
        start_time = timezone.now() + timedelta(hours=1)
        end_time = start_time + timedelta(hours=1)
        
        meeting = Meeting.objects.create(
            title="Test Meeting",
            start_time=start_time,
            end_time=end_time,
            organizer=self.organizer,
            group=self.group
        )
        meeting.schedule()
        meeting.save()
        
        new_start = start_time + timedelta(days=1)
        new_end = end_time + timedelta(days=1)
        
        url = reverse('deals:meeting-reschedule', kwargs={'pk': meeting.id})
        data = {
            'new_start_time': new_start.isoformat(),
            'new_end_time': new_end.isoformat(),
            'reason': 'Schedule conflict',
            'notify_attendees': True
        }
        
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        meeting.refresh_from_db()
        self.assertEqual(meeting.start_time.replace(microsecond=0), new_start.replace(microsecond=0))
        self.assertEqual(meeting.end_time.replace(microsecond=0), new_end.replace(microsecond=0))
    
    def test_find_optimal_time(self):
        """Test finding optimal meeting times."""
        url = reverse('deals:meeting-find-optimal-time')
        data = {
            'attendee_emails': ['attendee1@example.com', 'attendee2@example.com'],
            'duration_minutes': 60,
            'max_suggestions': 3
        }
        
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        self.assertIn('suggestions', response.data)
        self.assertEqual(len(response.data['suggestions']), 3)
        
        # Check suggestion structure
        suggestion = response.data['suggestions'][0]
        self.assertIn('start_time', suggestion)
        self.assertIn('end_time', suggestion)
        self.assertIn('confidence_score', suggestion)
    
    def test_meeting_analytics(self):
        """Test meeting analytics endpoint."""
        # Create test meetings with different types and statuses
        start_time = timezone.now() + timedelta(hours=1)
        end_time = start_time + timedelta(hours=1)
        
        meeting1 = Meeting.objects.create(
            title="Meeting 1",
            meeting_type=MeetingType.INITIAL_MEETING,
            status=MeetingStatus.COMPLETED,
            start_time=start_time,
            end_time=end_time,
            organizer=self.organizer,
            group=self.group
        )
        
        meeting2 = Meeting.objects.create(
            title="Meeting 2",
            meeting_type=MeetingType.DUE_DILIGENCE,
            status=MeetingStatus.SCHEDULED,
            start_time=start_time + timedelta(hours=2),
            end_time=end_time + timedelta(hours=2),
            organizer=self.organizer,
            group=self.group
        )
        
        url = reverse('deals:meeting-analytics')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Check analytics structure
        self.assertIn('total_meetings', response.data)
        self.assertIn('meetings_by_status', response.data)
        self.assertIn('meetings_by_type', response.data)
        self.assertEqual(response.data['total_meetings'], 2)
    
    def test_upcoming_meetings(self):
        """Test upcoming meetings endpoint."""
        # Create upcoming meeting where user is organizer
        start_time = timezone.now() + timedelta(hours=1)
        end_time = start_time + timedelta(hours=1)
        
        meeting = Meeting.objects.create(
            title="Upcoming Meeting",
            start_time=start_time,
            end_time=end_time,
            status=MeetingStatus.SCHEDULED,
            organizer=self.organizer,
            group=self.group
        )
        
        url = reverse('deals:meeting-upcoming')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['title'], 'Upcoming Meeting')
    
    def test_calendar_view(self):
        """Test calendar view endpoint."""
        # Create meeting in date range
        start_time = timezone.now() + timedelta(hours=1)
        end_time = start_time + timedelta(hours=1)
        
        meeting = Meeting.objects.create(
            title="Calendar Meeting",
            start_time=start_time,
            end_time=end_time,
            organizer=self.organizer,
            group=self.group
        )
        
        url = reverse('deals:meeting-calendar-view')
        params = {
            'start_date': (timezone.now()).isoformat(),
            'end_date': (timezone.now() + timedelta(days=7)).isoformat()
        }
        
        response = self.client.get(url, params)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
    
    def test_permission_checks(self):
        """Test permission checks for meeting operations."""
        # Create meeting by different organizer
        other_organizer = User.objects.create_user(
            username="other",
            email="other@example.com",
            password="testpass123"
        )
        other_organizer.groups.add(self.group)
        
        start_time = timezone.now() + timedelta(hours=1)
        end_time = start_time + timedelta(hours=1)
        
        meeting = Meeting.objects.create(
            title="Other's Meeting",
            start_time=start_time,
            end_time=end_time,
            organizer=other_organizer,
            group=self.group
        )
        
        # Try to start meeting as non-organizer
        url = reverse('deals:meeting-start-meeting', kwargs={'pk': meeting.id})
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class MeetingResourceAPITests(APITestCase):
    """Test Meeting Resource API endpoints."""
    
    def setUp(self):
        self.group = Group.objects.create(name="Test Group")
        self.manager = User.objects.create_user(
            username="manager",
            email="manager@example.com",
            password="testpass123"
        )
        self.user = User.objects.create_user(
            username="user",
            email="user@example.com",
            password="testpass123"
        )
        self.manager.groups.add(self.group)
        self.user.groups.add(self.group)
        
        # Set up manager permissions (mock)
        self.manager.is_staff = True
        self.manager.save()
        
        self.resource = MeetingResource.objects.create(
            name="Test Room",
            resource_type=MeetingResource.ResourceType.CONFERENCE_ROOM,
            capacity=10,
            hourly_cost=50.00,
            group=self.group
        )
    
    def test_list_resources(self):
        """Test listing meeting resources."""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('deals:meetingresource-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
    
    def test_check_resource_availability(self):
        """Test checking resource availability."""
        self.client.force_authenticate(user=self.user)
        
        start_time = timezone.now() + timedelta(hours=1)
        end_time = start_time + timedelta(hours=1)
        
        url = reverse('deals:meetingresource-availability', kwargs={'pk': self.resource.id})
        params = {
            'start_time': start_time.isoformat(),
            'end_time': end_time.isoformat()
        }
        
        response = self.client.get(url, params)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['is_available'])
    
    def test_available_resources(self):
        """Test getting available resources for time period."""
        self.client.force_authenticate(user=self.user)
        
        start_time = timezone.now() + timedelta(hours=1)
        end_time = start_time + timedelta(hours=1)
        
        url = reverse('deals:meetingresource-available-resources')
        params = {
            'start_time': start_time.isoformat(),
            'end_time': end_time.isoformat(),
            'resource_type': MeetingResource.ResourceType.CONFERENCE_ROOM,
            'min_capacity': '5'
        }
        
        response = self.client.get(url, params)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['name'], 'Test Room')