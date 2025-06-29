"""
Tests for deal collaboration features (comments, discussions, notifications).
"""

from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APITestCase
from rest_framework import status
from unittest.mock import patch

from accounts.models import Group
from assessments.models import DevelopmentPartner
from deals.models import (
    Deal, DealType, DealSource, DealComment, DealDiscussion, 
    DealNotification, DealTeamMember, DealRole
)

User = get_user_model()


class DealCommentModelTests(TestCase):
    """Test DealComment model functionality."""
    
    def setUp(self):
        self.group = Group.objects.create(name="Test Group")
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
            first_name="Test",
            last_name="User"
        )
        self.user.groups.add(self.group)
        
        self.partner = DevelopmentPartner.objects.create(
            company_name="Test Partner Company",
            group=self.group
        )
        
        self.deal_type = DealType.objects.create(
            name="Test Deal Type",
            code="TEST",
            group=self.group
        )
        
        self.deal_source = DealSource.objects.create(
            name="Test Source",
            code="TEST_SRC",
            group=self.group
        )
        
        self.deal = Deal.objects.create(
            name="Test Deal",
            code="TEST-001",
            deal_type=self.deal_type,
            deal_source=self.deal_source,
            investment_amount=1000000,
            group=self.group
        )
    
    def test_create_comment(self):
        """Test creating a deal comment."""
        comment = DealComment.objects.create(
            deal=self.deal,
            author=self.user,
            content="This is a test comment",
            comment_type=DealComment.CommentType.GENERAL,
            group=self.group
        )
        
        self.assertEqual(comment.deal, self.deal)
        self.assertEqual(comment.author, self.user)
        self.assertEqual(comment.content, "This is a test comment")
        self.assertFalse(comment.is_private)
        self.assertFalse(comment.is_resolved)
    
    def test_comment_threading(self):
        """Test comment threading functionality."""
        parent_comment = DealComment.objects.create(
            deal=self.deal,
            author=self.user,
            content="Parent comment",
            comment_type=DealComment.CommentType.QUESTION,
            group=self.group
        )
        
        reply = DealComment.objects.create(
            deal=self.deal,
            author=self.user,
            content="Reply to parent",
            parent=parent_comment,
            group=self.group
        )
        
        self.assertEqual(reply.parent, parent_comment)
        self.assertEqual(parent_comment.replies.count(), 1)
        self.assertEqual(parent_comment.reply_count, 1)
    
    def test_comment_resolution(self):
        """Test comment resolution functionality."""
        comment = DealComment.objects.create(
            deal=self.deal,
            author=self.user,
            content="This needs to be resolved",
            comment_type=DealComment.CommentType.CONCERN,
            group=self.group
        )
        
        # Resolve the comment
        comment.resolve(self.user)
        
        self.assertTrue(comment.is_resolved)
        self.assertEqual(comment.resolved_by, self.user)
        self.assertIsNotNone(comment.resolved_at)
    
    def test_comment_mentions(self):
        """Test @mention functionality."""
        mentioned_user = User.objects.create_user(
            username="mentioned",
            email="mentioned@example.com",
            password="testpass123"
        )
        mentioned_user.groups.add(self.group)
        
        comment = DealComment.objects.create(
            deal=self.deal,
            author=self.user,
            content="@mentioned@example.com please review this",
            group=self.group
        )
        
        comment.mentioned_users.add(mentioned_user)
        
        self.assertEqual(comment.mentioned_users.count(), 1)
        self.assertIn(mentioned_user, comment.mentioned_users.all())


class DealDiscussionModelTests(TestCase):
    """Test DealDiscussion model functionality."""
    
    def setUp(self):
        self.group = Group.objects.create(name="Test Group")
        self.user = User.objects.create_user(
            username="testuser2",
            email="test@example.com",
            password="testpass123"
        )
        self.user.groups.add(self.group)
        
        self.partner = DevelopmentPartner.objects.create(
            company_name="Test Partner Company",
            group=self.group
        )
        
        self.deal_type = DealType.objects.create(
            name="Test Deal Type",
            code="TEST",
            group=self.group
        )
        
        self.deal_source = DealSource.objects.create(
            name="Test Source",
            code="TEST_SRC",
            group=self.group
        )
        
        self.deal = Deal.objects.create(
            name="Test Deal",
            code="TEST-001",
            deal_type=self.deal_type,
            deal_source=self.deal_source,
            investment_amount=1000000,
            group=self.group
        )
    
    def test_create_discussion(self):
        """Test creating a deal discussion."""
        discussion = DealDiscussion.objects.create(
            deal=self.deal,
            title="Test Discussion",
            description="Discussion about the deal",
            discussion_type=DealDiscussion.DiscussionType.GENERAL,
            created_by=self.user,
            group=self.group
        )
        
        self.assertEqual(discussion.deal, self.deal)
        self.assertEqual(discussion.title, "Test Discussion")
        self.assertEqual(discussion.created_by, self.user)
        self.assertEqual(discussion.status, DealDiscussion.DiscussionStatus.ACTIVE)
    
    def test_discussion_participants(self):
        """Test adding participants to discussion."""
        discussion = DealDiscussion.objects.create(
            deal=self.deal,
            title="Test Discussion",
            created_by=self.user,
            group=self.group
        )
        
        participant = User.objects.create_user(
            username="participant",
            email="participant@example.com",
            password="testpass123"
        )
        participant.groups.add(self.group)
        
        discussion.add_participant(participant)
        
        self.assertIn(participant, discussion.participants.all())
    
    def test_discussion_resolution(self):
        """Test resolving a discussion."""
        discussion = DealDiscussion.objects.create(
            deal=self.deal,
            title="Test Discussion",
            created_by=self.user,
            group=self.group
        )
        
        resolution_summary = "Discussion resolved successfully"
        discussion.resolve(self.user, resolution_summary)
        
        self.assertEqual(discussion.status, DealDiscussion.DiscussionStatus.RESOLVED)
        self.assertEqual(discussion.resolved_by, self.user)
        self.assertEqual(discussion.resolution_summary, resolution_summary)
        self.assertIsNotNone(discussion.resolved_at)


class DealNotificationModelTests(TestCase):
    """Test DealNotification model functionality."""
    
    def setUp(self):
        self.group = Group.objects.create(name="Test Group")
        self.sender = User.objects.create_user(
            username="sender",
            email="sender@example.com",
            password="testpass123"
        )
        self.recipient = User.objects.create_user(
            username="recipient",
            email="recipient@example.com",
            password="testpass123"
        )
        self.sender.groups.add(self.group)
        self.recipient.groups.add(self.group)
        
        self.partner = DevelopmentPartner.objects.create(
            company_name="Test Partner Company",
            group=self.group
        )
        
        self.deal_type = DealType.objects.create(
            name="Test Deal Type",
            code="TEST",
            group=self.group
        )
        
        self.deal_source = DealSource.objects.create(
            name="Test Source",
            code="TEST_SRC",
            group=self.group
        )
        
        self.deal = Deal.objects.create(
            name="Test Deal",
            code="TEST-001",
            deal_type=self.deal_type,
            deal_source=self.deal_source,
            investment_amount=1000000,
            group=self.group
        )
    
    def test_create_notification(self):
        """Test creating a deal notification."""
        notification = DealNotification.objects.create(
            deal=self.deal,
            recipient=self.recipient,
            sender=self.sender,
            notification_type=DealNotification.NotificationType.COMMENT_MENTION,
            title="New Comment Added",
            message="A new comment was added to the deal",
            group=self.group
        )
        
        self.assertEqual(notification.deal, self.deal)
        self.assertEqual(notification.recipient, self.recipient)
        self.assertEqual(notification.sender, self.sender)
        self.assertFalse(notification.is_read)
        self.assertFalse(notification.is_dismissed)
    
    def test_mark_notification_read(self):
        """Test marking notification as read."""
        notification = DealNotification.objects.create(
            deal=self.deal,
            recipient=self.recipient,
            sender=self.sender,
            notification_type=DealNotification.NotificationType.COMMENT_MENTION,
            title="New Comment Added",
            message="A new comment was added to the deal",
            group=self.group
        )
        
        notification.mark_as_read()
        
        self.assertTrue(notification.is_read)
        self.assertIsNotNone(notification.read_at)
    
    def test_dismiss_notification(self):
        """Test dismissing notification."""
        notification = DealNotification.objects.create(
            deal=self.deal,
            recipient=self.recipient,
            sender=self.sender,
            notification_type=DealNotification.NotificationType.COMMENT_MENTION,
            title="New Comment Added",
            message="A new comment was added to the deal",
            group=self.group
        )
        
        notification.dismiss()
        
        self.assertTrue(notification.is_dismissed)
        self.assertIsNotNone(notification.dismissed_at)


class DealCollaborationAPITests(APITestCase):
    """Test collaboration API endpoints."""
    
    def setUp(self):
        self.group = Group.objects.create(name="Test Group")
        self.user = User.objects.create_user(
            username="testapi",
            email="test@example.com",
            password="testpass123",
            role=User.Role.PORTFOLIO_MANAGER
        )
        self.user.groups.add(self.group)
        
        self.partner = DevelopmentPartner.objects.create(
            company_name="Test Partner Company",
            group=self.group
        )
        
        self.deal_type = DealType.objects.create(
            name="Test Deal Type",
            code="TEST",
            group=self.group
        )
        
        self.deal_source = DealSource.objects.create(
            name="Test Source",
            code="TEST_SRC",
            group=self.group
        )
        
        self.deal = Deal.objects.create(
            name="Test Deal",
            code="TEST-001",
            deal_type=self.deal_type,
            deal_source=self.deal_source,
            investment_amount=1000000,
            group=self.group
        )
        
        # Add user to deal team
        self.deal_role = DealRole.objects.create(
            name="Deal Lead",
            code="deal_lead",
            group=self.group
        )
        
        DealTeamMember.objects.create(
            deal=self.deal,
            user=self.user,
            role=self.deal_role,
            group=self.group
        )
        
        self.client.force_authenticate(user=self.user)
    
    def test_create_comment_api(self):
        """Test creating comment via API."""
        url = '/api/deals/comments/'
        data = {
            'deal': str(self.deal.id),
            'content': 'Test comment via API',
            'comment_type': 'general'
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(DealComment.objects.count(), 1)
        
        comment = DealComment.objects.first()
        self.assertEqual(comment.content, 'Test comment via API')
        self.assertEqual(comment.author, self.user)
    
    def test_resolve_comment_api(self):
        """Test resolving comment via API."""
        comment = DealComment.objects.create(
            deal=self.deal,
            author=self.user,
            content="Question that needs resolution",
            comment_type=DealComment.CommentType.QUESTION,
            group=self.group
        )
        
        url = f'/api/deals/comments/{comment.id}/resolve/'
        response = self.client.post(url, {}, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        comment.refresh_from_db()
        self.assertTrue(comment.is_resolved)
        self.assertEqual(comment.resolved_by, self.user)
    
    def test_create_discussion_api(self):
        """Test creating discussion via API."""
        url = '/api/deals/discussions/'
        data = {
            'deal': str(self.deal.id),
            'title': 'API Discussion',
            'description': 'Discussion created via API',
            'discussion_type': 'general'
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(DealDiscussion.objects.count(), 1)
        
        discussion = DealDiscussion.objects.first()
        self.assertEqual(discussion.title, 'API Discussion')
        self.assertEqual(discussion.created_by, self.user)
    
    def test_join_discussion_api(self):
        """Test joining discussion via API."""
        discussion = DealDiscussion.objects.create(
            deal=self.deal,
            title="Test Discussion",
            created_by=self.user,
            group=self.group
        )
        
        participant = User.objects.create_user(
            username="participant",
            email="participant@example.com",
            password="testpass123"
        )
        participant.groups.add(self.group)
        
        self.client.force_authenticate(user=participant)
        
        url = f'/api/deals/discussions/{discussion.id}/join/'
        response = self.client.post(url, {}, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn(participant, discussion.participants.all())
    
    def test_get_notifications_api(self):
        """Test getting notifications via API."""
        notification = DealNotification.objects.create(
            deal=self.deal,
            recipient=self.user,
            sender=self.user,
            notification_type=DealNotification.NotificationType.COMMENT_MENTION,
            title="Test Notification",
            message="Test notification message",
            group=self.group
        )
        
        url = '/api/deals/notifications/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['title'], 'Test Notification')
    
    def test_mark_notification_read_api(self):
        """Test marking notification as read via API."""
        notification = DealNotification.objects.create(
            deal=self.deal,
            recipient=self.user,
            sender=self.user,
            notification_type=DealNotification.NotificationType.COMMENT_MENTION,
            title="Test Notification",
            message="Test notification message",
            group=self.group
        )
        
        url = f'/api/deals/notifications/{notification.id}/mark_read/'
        response = self.client.post(url, {}, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        notification.refresh_from_db()
        self.assertTrue(notification.is_read)
    
    def test_comment_thread_api(self):
        """Test getting comment thread via API."""
        parent_comment = DealComment.objects.create(
            deal=self.deal,
            author=self.user,
            content="Parent comment",
            group=self.group
        )
        
        reply = DealComment.objects.create(
            deal=self.deal,
            author=self.user,
            content="Reply comment",
            parent=parent_comment,
            group=self.group
        )
        
        url = f'/api/deals/comments/{parent_comment.id}/thread/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)  # Parent + reply
    
    def test_comment_permissions(self):
        """Test comment creation permissions."""
        # Test with user not on deal team
        non_team_user = User.objects.create_user(
            username="nonteam",
            email="nonteam@example.com",
            password="testpass123"
        )
        non_team_user.groups.add(self.group)
        
        self.client.force_authenticate(user=non_team_user)
        
        url = '/api/deals/comments/'
        data = {
            'deal': str(self.deal.id),
            'content': 'Unauthorized comment',
            'comment_type': 'general'
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(DealComment.objects.count(), 0)