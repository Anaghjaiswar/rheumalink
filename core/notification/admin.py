from django.contrib import admin
from .models import Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'title',
        'target_role',
        'recipient',
        'notification_type',
        'priority',
        'is_read',
        'is_soft_deleted',
        'created_at',
    )
    list_filter = (
        'target_role',
        'notification_type',
        'priority',
        'is_read',
        'is_soft_deleted',
        'created_at',
    )
    search_fields = ('title', 'message', 'recipient__email')
    ordering = ('-created_at',)

    actions = ['soft_delete_selected', 'restore_selected']

    def get_queryset(self, request):
        # Allow admin to see all items including soft-deleted ones
        return Notification.all_objects.all()

    @admin.action(description="Soft delete selected notifications")
    def soft_delete_selected(self, request, queryset):
        count = queryset.update(is_soft_deleted=True)
        self.message_user(request, f"{count} notifications soft-deleted successfully.")

    @admin.action(description="Restore selected soft-deleted notifications")
    def restore_selected(self, request, queryset):
        count = queryset.update(is_soft_deleted=False, deleted_at=None)
        self.message_user(request, f"{count} notifications restored successfully.")
