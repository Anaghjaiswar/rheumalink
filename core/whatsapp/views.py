import json
from logging import getLogger
from django.http import JsonResponse
from .handler import dispatch_whatsapp_message
from django.views.decorators.csrf import csrf_exempt
from .utils import extract_phone_from_jid

all_logs = getLogger('all_logs.log')

# Create your views here.
@csrf_exempt
def whatsapp_action_webhook(request):
    if request.method != 'POST':
       return JsonResponse({'status': 'error', 'message': 'Method not allowed'}, status=405)
    
    try:
        data = json.loads(request.body)
        incoming_jid = data.get('sendernumber')
        msg_content = str(data.get('messageContent', '')).strip()

        if not incoming_jid:
            return JsonResponse({'status': 'ignored', 'reason': 'no_jid'})
        
        # we need to identify user by his phone
        clean_phone = extract_phone_from_jid(incoming_jid)

        if not clean_phone:
            return JsonResponse({'status': 'ignored', 'reason': 'no_phone'})
        
        # delegation layer (fire and forget)
        dispatch_whatsapp_message(clean_phone, msg_content)

        return JsonResponse({'status': 'ok'})
    
    except Exception as e:
        all_logs.error(f"whatsapp webhook error: {e}")
        return JsonResponse({'status': 'error'}, status=200)

        