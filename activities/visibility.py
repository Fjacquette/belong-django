"""The Pilot audience rule shared by discovery, detail, and participation actions."""

from django.db.models import Q

from social.models import Friendship

from .models import Activity, ActivityVisibility


def visible_activities(user):
    if not user.is_authenticated:
        return Activity.objects.none()

    pairs = Friendship.objects.filter(Q(user_a=user) | Q(user_b=user)).values_list("user_a_id", "user_b_id")
    direct = {user_id for pair in pairs for user_id in pair} - {user.pk}
    extended_pairs = Friendship.objects.filter(
        Q(user_a_id__in=direct) | Q(user_b_id__in=direct)
    ).values_list("user_a_id", "user_b_id")
    extended = direct | {user_id for pair in extended_pairs for user_id in pair}

    # Unsupported legacy audiences (including GROUP/CUSTOM) remain host-only.
    return Activity.objects.filter(
        Q(host=user)
        | Q(audience=ActivityVisibility.EVERYONE)
        | Q(audience=ActivityVisibility.FRIENDS, host_id__in=direct)
        | Q(audience=ActivityVisibility.EXTENDED_FRIENDS, host_id__in=extended)
    )
