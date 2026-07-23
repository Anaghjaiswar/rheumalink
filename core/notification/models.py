from django.db import models
from django.utils import timezone
from user.models import User


class SoftDeleteNotificationQuerySet(models.QuerySet):
    def active(self):
        return self.filter(is_soft_deleted=False)

    def deleted(self):
        return self.filter(is_soft_deleted=True)

    def soft_delete(self):
        return self.update(is_soft_deleted=True, deleted_at=timezone.now())

    def restore(self):
        return self.update(is_soft_deleted=False, deleted_at=None)


class NotificationManager(models.Manager):
    def get_queryset(self):
        return SoftDeleteNotificationQuerySet(self.model, using=self._db).filter(is_soft_deleted=False)

    def all_with_deleted(self):
        return SoftDeleteNotificationQuerySet(self.model, using=self._db)

    def deleted_only(self):
        return SoftDeleteNotificationQuerySet(self.model, using=self._db).filter(is_soft_deleted=True)


class Notification(models.Model):
    """
    Model representing system & role-specific notifications with soft deletion capabilities.
    """
    class TargetRole(models.TextChoices):
        DOCTOR = 'DOCTOR', 'Doctor'
        COMPOUNDER = 'COMPOUNDER', 'Compounder'
        PATIENT = 'PATIENT', 'Patient'
        ALL = 'ALL', 'All Staff / General'

    class NotificationType(models.TextChoices):
        APPOINTMENT = 'APPOINTMENT', 'Appointment'
        LAB_REPORT = 'LAB_REPORT', 'Lab Report'
        PRESCRIPTION = 'PRESCRIPTION', 'Prescription'
        SYSTEM = 'SYSTEM', 'System Alert'
        GENERAL = 'GENERAL', 'General Info'
        URGENT = 'URGENT', 'Urgent Attention'

    class Priority(models.TextChoices):
        LOW = 'LOW', 'Low'
        NORMAL = 'NORMAL', 'Normal'
        HIGH = 'HIGH', 'High'
        URGENT = 'URGENT', 'Urgent'

    # Target audience / Role labeling
    target_role = models.CharField(
        max_length=20,
        choices=TargetRole.choices,
        default=TargetRole.ALL,
        help_text="Role for whom this notification is intended (e.g. Doctor, Compounder)",
        db_index=True
    )
    recipient = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='notifications',
        null=True,
        blank=True,
        help_text="Optional specific user recipient. If null, target_role receives it."
    )

    # Core Notification Details
    title = models.CharField(max_length=255)
    message_json = models.JSONField(default=dict, blank=True)
    notification_type = models.CharField(
        max_length=20,
        choices=NotificationType.choices,
        default=NotificationType.GENERAL,
        db_index=True
    )
    priority = models.CharField(
        max_length=10,
        choices=Priority.choices,
        default=Priority.NORMAL
    )

    # Status tracking
    is_read = models.BooleanField(default=False, db_index=True)
    read_at = models.DateTimeField(null=True, blank=True)
    action_url = models.CharField(
        max_length=500,
        null=True,
        blank=True,
        help_text="Optional link to navigate when notification is clicked"
    )

    # Soft Delete Flags
    is_soft_deleted = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Soft delete flag — set true to archive without permanent DB deletion"
    )
    deleted_at = models.DateTimeField(null=True, blank=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Model Managers
    objects = NotificationManager()
    all_objects = models.Manager()  # Includes soft-deleted items

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Notification'
        verbose_name_plural = 'Notifications'

    def __str__(self):
        target = self.recipient.email if self.recipient else self.get_target_role_display()
        return f"[{self.get_priority_display()}] {self.title} -> {target}"

    def mark_as_read(self):
        """Mark notification as read with current timestamp."""
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            self.save(update_fields=['is_read', 'read_at', 'updated_at'])

    def soft_delete(self):
        """Soft delete the notification."""
        self.is_soft_deleted = True
        self.deleted_at = timezone.now()
        self.save(update_fields=['is_soft_deleted', 'deleted_at', 'updated_at'])

    def restore(self):
        """Restore a soft-deleted notification."""
        self.is_soft_deleted = False
        self.deleted_at = None
        self.save(update_fields=['is_soft_deleted', 'deleted_at', 'updated_at'])