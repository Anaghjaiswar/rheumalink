from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_POST
from .models import Notification


@require_GET
def list_notifications_api(request):
    """Returns unread count and active notifications list formatted as JSON."""
    role = request.GET.get('role', 'ALL').upper()
    queryset = Notification.objects.filter(is_soft_deleted=False)
    
    if role in ['DOCTOR', 'COMPOUNDER', 'PATIENT']:
        queryset = queryset.filter(target_role__in=[role, 'ALL'])

    unread_count = queryset.filter(is_read=False).count()
    notifications_qs = queryset.order_by('-created_at')[:20]

    notifications = []
    for n in notifications_qs:
        notifications.append({
            'id': n.id,
            'title': n.title,
            'message_json': n.message_json,
            'notification_type': n.get_notification_type_display(),
            'priority': n.get_priority_display(),
            'is_read': n.is_read,
            'action_url': n.action_url,
            'created_at': n.created_at.strftime('%Y-%m-%d %H:%M') if n.created_at else ''
        })

    return JsonResponse({
        'status': 'success',
        'unread_count': unread_count,
        'notifications': notifications
    })


@require_POST
def mark_notification_read_api(request, pk):
    """Marks a specific notification as read."""
    try:
        notification = Notification.objects.get(pk=pk)
        notification.mark_as_read()
        return JsonResponse({'status': 'success', 'id': pk})
    except Notification.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Notification not found'}, status=404)
