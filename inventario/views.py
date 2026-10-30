from django.http import JsonResponse


def health(request):
    """Endpoint ligero para monitores y chequeos de disponibilidad."""
    return JsonResponse({"status": "ok"})
