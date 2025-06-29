"""
Tests for outreach sequence functionality.
"""

import json
from datetime import timedelta
from django.test import TestCase
from django.utils import timezone
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status

from accounts.models import Group
from .models import Contact, EmailTemplate
from .models_outreach import (
    OutreachSequence,
    SequenceStep,
    SequenceEnrollment,
    SequenceStepExecution,
    SequenceTemplate
)
from .tasks_outreach import (
    execute_sequence_step,
    start_sequence_enrollment,
    calculate_next_execution_time
)

User = get_user_model()


class OutreachSequenceModelTests(TestCase):
    """Test outreach sequence models."""
    
    def setUp(self):
        """Set up test data."""
        self.group = Group.objects.create(name='test_group')
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass'
        )
        self.user.group = self.group
        self.user.save()
        
        self.sequence = OutreachSequence.objects.create(
            name='Test Sequence',
            description='Test sequence description',
            group=self.group,
            created_by=self.user
        )
        
        self.email_template = EmailTemplate.objects.create(
            name='Test Template',
            slug='test-template',
            subject='Test Subject',
            text_content='Test body',
            html_content='<p>Test body</p>',
            group=self.group
        )
    
    def test_sequence_creation(self):
        """Test sequence creation with defaults."""
        self.assertEqual(self.sequence.status, OutreachSequence.Status.DRAFT)
        self.assertEqual(self.sequence.trigger_type, OutreachSequence.TriggerType.MANUAL)
        self.assertTrue(self.sequence.skip_weekends)
        self.assertTrue(self.sequence.exit_on_reply)
        self.assertFalse(self.sequence.exit_on_click)
    
    def test_sequence_state_transitions(self):
        """Test sequence state transitions."""
        # Create a step
        SequenceStep.objects.create(
            sequence=self.sequence,
            group=self.group,
            step_type=SequenceStep.StepType.EMAIL,
            order=0,
            name='First Email',
            email_template=self.email_template
        )
        
        # Activate sequence
        self.sequence.activate()
        self.sequence.save()
        self.assertEqual(self.sequence.status, OutreachSequence.Status.ACTIVE)
        
        # Pause sequence
        self.sequence.pause()
        self.sequence.save()
        self.assertEqual(self.sequence.status, OutreachSequence.Status.PAUSED)
        
        # Resume sequence
        self.sequence.resume()
        self.sequence.save()
        self.assertEqual(self.sequence.status, OutreachSequence.Status.ACTIVE)
        
        # Complete sequence
        self.sequence.complete()
        self.sequence.save()
        self.assertEqual(self.sequence.status, OutreachSequence.Status.COMPLETED)
    
    def test_sequence_step_creation(self):
        """Test creating sequence steps."""
        # Email step
        email_step = SequenceStep.objects.create(
            sequence=self.sequence,
            group=self.group,
            step_type=SequenceStep.StepType.EMAIL,
            order=0,
            name='Welcome Email',
            delay_days=0,
            email_template=self.email_template,
            email_subject='Welcome {{first_name}}!'
        )
        self.assertEqual(email_step.get_total_delay_hours(), 0)
        
        # Wait step
        wait_step = SequenceStep.objects.create(
            sequence=self.sequence,
            group=self.group,
            step_type=SequenceStep.StepType.WAIT,
            order=1,
            name='Wait 3 business days',
            delay_days=3,
            day_type=SequenceStep.DayType.BUSINESS
        )
        # Business days calculation (3 * 7/5 * 24)
        self.assertEqual(wait_step.get_total_delay_hours(), 3 * 7/5 * 24)
        
        # Condition step
        condition_step = SequenceStep.objects.create(
            sequence=self.sequence,
            group=self.group,
            step_type=SequenceStep.StepType.CONDITION,
            order=2,
            name='Check if opened',
            condition_type='has_opened',
            condition_config={'check_all': True}
        )
        self.assertEqual(condition_step.condition_type, 'has_opened')
    
    def test_enrollment_creation(self):
        """Test enrollment creation and state management."""
        contact = Contact.objects.create(
            first_name='John',
            last_name='Doe',
            email='john@example.com',
            group=self.group
        )
        
        enrollment = SequenceEnrollment.objects.create(
            sequence=self.sequence,
            contact=contact,
            group=self.group,
            custom_variables={'company': 'Acme Corp'}
        )
        
        self.assertEqual(enrollment.status, SequenceEnrollment.Status.ACTIVE)
        self.assertEqual(enrollment.current_step_index, 0)
        self.assertIsNone(enrollment.current_step)
        
        # Test state transitions
        enrollment.pause()
        enrollment.save()
        self.assertEqual(enrollment.status, SequenceEnrollment.Status.PAUSED)
        
        enrollment.resume()
        enrollment.save()
        self.assertEqual(enrollment.status, SequenceEnrollment.Status.ACTIVE)
        
        enrollment.exit(
            reason=SequenceEnrollment.ExitReason.REPLIED,
            details='Contact replied to email'
        )
        enrollment.save()
        self.assertEqual(enrollment.status, SequenceEnrollment.Status.EXITED)
        self.assertEqual(enrollment.exit_reason, SequenceEnrollment.ExitReason.REPLIED)
        self.assertIsNotNone(enrollment.exited_at)


class OutreachSequenceAPITests(TestCase):
    """Test outreach sequence API endpoints."""
    
    def setUp(self):
        """Set up test data."""
        self.client = APIClient()
        self.group = Group.objects.create(name='test_group')
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass',
            role='MANAGER'
        )
        self.user.group = self.group
        self.user.save()
        self.client.force_authenticate(user=self.user)
        
        self.email_template = EmailTemplate.objects.create(
            name='Test Template',
            slug='test-template',
            subject='Test Subject',
            text_content='Test body',
            group=self.group
        )
    
    def test_create_sequence(self):
        """Test creating a sequence via API."""
        data = {
            'name': 'API Test Sequence',
            'description': 'Created via API',
            'trigger_type': 'manual',
            'skip_weekends': True,
            'exit_on_reply': True
        }
        
        response = self.client.post('/api/contacts/outreach-sequences/', data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['name'], 'API Test Sequence')
        self.assertEqual(response.data['status'], 'draft')
    
    def test_create_sequence_with_steps(self):
        """Test creating a sequence with steps."""
        # First create the sequence
        sequence_data = {
            'name': 'Sequence with Steps',
            'description': 'Has multiple steps'
        }
        response = self.client.post('/api/contacts/outreach-sequences/', sequence_data)
        sequence_id = response.data['id']
        
        # Add steps
        steps_data = [
            {
                'sequence': sequence_id,
                'step_type': 'email',
                'order': 0,
                'name': 'Welcome Email',
                'delay_days': 0,
                'email_template': str(self.email_template.id)
            },
            {
                'sequence': sequence_id,
                'step_type': 'wait',
                'order': 1,
                'name': 'Wait 3 days',
                'delay_days': 3,
                'day_type': 'business'
            },
            {
                'sequence': sequence_id,
                'step_type': 'email',
                'order': 2,
                'name': 'Follow-up Email',
                'delay_days': 0,
                'email_template': str(self.email_template.id)
            }
        ]
        
        for step_data in steps_data:
            response = self.client.post('/api/contacts/sequence-steps/', step_data)
            self.assertEqual(response.status_code, status.HTTP_201_CREATED)
    
    def test_activate_sequence(self):
        """Test activating a sequence."""
        # Create sequence with step
        sequence = OutreachSequence.objects.create(
            name='Test Activation',
            group=self.group,
            created_by=self.user
        )
        
        SequenceStep.objects.create(
            sequence=sequence,
            group=self.group,
            step_type=SequenceStep.StepType.EMAIL,
            order=0,
            name='First Email',
            email_template=self.email_template
        )
        
        # Activate via API
        response = self.client.post(f'/api/contacts/outreach-sequences/{sequence.id}/activate/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'active')
        
        # Try to activate sequence without steps
        empty_sequence = OutreachSequence.objects.create(
            name='Empty Sequence',
            group=self.group,
            created_by=self.user
        )
        
        response = self.client.post(f'/api/contacts/outreach-sequences/{empty_sequence.id}/activate/')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_enroll_contacts(self):
        """Test enrolling contacts in a sequence."""
        # Create active sequence
        sequence = OutreachSequence.objects.create(
            name='Test Enrollment',
            group=self.group,
            created_by=self.user,
            status=OutreachSequence.Status.ACTIVE
        )
        
        # Create contacts
        contacts = []
        for i in range(3):
            contact = Contact.objects.create(
                first_name=f'Contact{i}',
                last_name='Test',
                email=f'contact{i}@example.com',
                group=self.group
            )
            contacts.append(contact)
        
        # Enroll contacts
        data = {
            'contact_ids': [str(c.id) for c in contacts],
            'custom_variables': {'source': 'API Test'}
        }
        
        response = self.client.post(
            f'/api/contacts/outreach-sequences/{sequence.id}/enroll_contacts/',
            data,
            format='json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['enrolled_count'], 3)
        self.assertEqual(response.data['skipped_count'], 0)
        
        # Try to enroll same contacts again
        response = self.client.post(
            f'/api/contacts/outreach-sequences/{sequence.id}/enroll_contacts/',
            data,
            format='json'
        )
        
        self.assertEqual(response.data['enrolled_count'], 0)
        self.assertEqual(response.data['skipped_count'], 3)
    
    def test_sequence_analytics(self):
        """Test sequence analytics endpoint."""
        # Create sequence with data
        sequence = OutreachSequence.objects.create(
            name='Analytics Test',
            group=self.group,
            created_by=self.user,
            total_enrolled=10,
            total_completed=5,
            total_converted=3
        )
        
        # Create steps with metrics
        step1 = SequenceStep.objects.create(
            sequence=sequence,
            group=self.group,
            step_type=SequenceStep.StepType.EMAIL,
            order=0,
            name='Email 1',
            email_template=self.email_template,
            total_sent=10,
            total_opened=8,
            total_clicked=4
        )
        
        step2 = SequenceStep.objects.create(
            sequence=sequence,
            group=self.group,
            step_type=SequenceStep.StepType.EMAIL,
            order=1,
            name='Email 2',
            email_template=self.email_template,
            total_sent=8,
            total_opened=6,
            total_clicked=2
        )
        
        response = self.client.get(f'/api/contacts/outreach-sequences/{sequence.id}/analytics/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        data = response.data
        self.assertEqual(data['total_enrolled'], 10)
        self.assertEqual(data['total_converted'], 3)
        self.assertEqual(data['conversion_rate'], 30.0)
        self.assertEqual(len(data['step_performance']), 2)
        self.assertEqual(data['step_performance'][0]['open_rate'], 80.0)
        self.assertEqual(data['step_performance'][0]['click_rate'], 40.0)


class OutreachSequenceTaskTests(TestCase):
    """Test outreach sequence background tasks."""
    
    def setUp(self):
        """Set up test data."""
        self.group = Group.objects.create(name='test_group')
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass'
        )
        self.user.group = self.group
        self.user.save()
        
        self.contact = Contact.objects.create(
            first_name='John',
            last_name='Doe',
            email='john@example.com',
            group=self.group
        )
        
        self.email_template = EmailTemplate.objects.create(
            name='Test Template',
            slug='test-template',
            subject='Hello {{first_name}}',
            text_content='Test body for {{first_name}}',
            group=self.group
        )
        
        self.sequence = OutreachSequence.objects.create(
            name='Test Sequence',
            group=self.group,
            created_by=self.user,
            status=OutreachSequence.Status.ACTIVE
        )
        
        self.step = SequenceStep.objects.create(
            sequence=self.sequence,
            group=self.group,
            step_type=SequenceStep.StepType.EMAIL,
            order=0,
            name='First Email',
            delay_days=0,
            email_template=self.email_template
        )
    
    def test_calculate_next_execution_time(self):
        """Test execution time calculation."""
        enrollment = SequenceEnrollment.objects.create(
            sequence=self.sequence,
            contact=self.contact,
            group=self.group
        )
        
        # Test immediate execution
        step = SequenceStep.objects.create(
            sequence=self.sequence,
            group=self.group,
            step_type=SequenceStep.StepType.EMAIL,
            order=1,
            name='Immediate',
            delay_days=0,
            delay_hours=0
        )
        
        now = timezone.now()
        next_time = calculate_next_execution_time(enrollment, step)
        
        # For timezone-optimized sequences, should be set to optimal hour
        self.assertEqual(next_time.hour, self.sequence.optimal_send_hour)
        
        # Test business days calculation
        business_step = SequenceStep.objects.create(
            sequence=self.sequence,
            group=self.group,
            step_type=SequenceStep.StepType.EMAIL,
            order=2,
            name='Business Days',
            delay_days=3,
            day_type=SequenceStep.DayType.BUSINESS
        )
        
        # Create sequence that doesn't skip weekends
        no_skip_sequence = OutreachSequence.objects.create(
            name='No Skip Weekends',
            group=self.group,
            created_by=self.user,
            skip_weekends=False,
            timezone_optimized=False
        )
        
        no_skip_enrollment = SequenceEnrollment.objects.create(
            sequence=no_skip_sequence,
            contact=self.contact,
            group=self.group
        )
        
        next_time = calculate_next_execution_time(no_skip_enrollment, business_step)
        expected = now + timedelta(days=3)
        
        # Should be roughly 3 days later (allowing for small differences)
        diff = abs((next_time - expected).total_seconds())
        self.assertLess(diff, 86400)  # Less than 1 day difference


class SequenceTemplateTests(TestCase):
    """Test sequence template functionality."""
    
    def setUp(self):
        """Set up test data."""
        self.client = APIClient()
        self.group = Group.objects.create(name='test_group')
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass',
            role='MANAGER'
        )
        self.user.group = self.group
        self.user.save()
        self.client.force_authenticate(user=self.user)
    
    def test_create_template(self):
        """Test creating a sequence template."""
        data = {
            'name': 'Test Template',
            'description': 'A test template',
            'category': 'cold_outreach',
            'configuration': {
                'name': 'Cold Outreach',
                'description': 'Template for cold outreach',
                'trigger_type': 'manual',
                'steps': [
                    {
                        'step_type': 'email',
                        'order': 0,
                        'name': 'Initial Contact',
                        'delay_days': 0
                    },
                    {
                        'step_type': 'wait',
                        'order': 1,
                        'name': 'Wait Period',
                        'delay_days': 3
                    }
                ]
            }
        }
        
        response = self.client.post('/api/contacts/sequence-templates/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['name'], 'Test Template')
        
        # Test invalid configuration
        invalid_data = {
            'name': 'Invalid Template',
            'description': 'Missing required fields',
            'category': 'cold_outreach',
            'configuration': {
                'name': 'Missing Steps'
                # Missing 'description' and 'steps'
            }
        }
        
        response = self.client.post('/api/contacts/sequence-templates/', invalid_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_create_sequence_from_template(self):
        """Test creating a sequence from a template."""
        # Create template
        template = SequenceTemplate.objects.create(
            name='Template',
            description='Test template',
            category=SequenceTemplate.Category.COLD_OUTREACH,
            group=self.group,
            created_by=self.user,
            configuration={
                'name': 'Cold Outreach',
                'description': 'Cold outreach sequence',
                'trigger_type': 'manual',
                'skip_weekends': True,
                'steps': [
                    {
                        'step_type': 'email',
                        'order': 0,
                        'name': 'First Email',
                        'delay_days': 0
                    }
                ]
            }
        )
        
        # Create sequence from template
        response = self.client.post(
            f'/api/contacts/sequence-templates/{template.id}/create_sequence/',
            {'name': 'My New Sequence'}
        )
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['name'], 'My New Sequence')
        self.assertTrue(response.data['skip_weekends'])
        self.assertEqual(response.data['step_count'], 1)
        
        # Check template usage was incremented
        template.refresh_from_db()
        self.assertEqual(template.times_used, 1)